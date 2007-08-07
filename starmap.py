#! /usr/bin/python

import time
import pygame
import math

from tp.netlib import Connection
from tp.netlib import failed, constants, objects
from tp.netlib.client import url2bits
from tp.client.cache import Cache

version = (0, 0, 1)

ship = None
star = None

SPRITESIZE = None
SYSTEM_TYPE = 2 
PLANET_TYPE = 3
FLEET_TYPE  = 4
TYPENAMES   = {SYSTEM_TYPE: 'System', PLANET_TYPE: 'Planet', FLEET_TYPE: 'Fleet'}

WHITE = (255,255,255)
RED   = (100,  0,  0)
GREEN = (  0,100,  0)

BACKGROUND = (100, 100, 100)
PADDING    = 5

def rendertext(text):
	"""
	Render a bunch of text into a box.

	Takes a list of (color, line)
	IE

	[((255, 0, 0), "Red line"), ((255, 255, 255), "White Line")]
	"""
	font = pygame.font.Font(pygame.font.get_default_font(), 12)
	
	lines = []
	for color, line in text:
		lines.append(font.render(line, True, color))

	height = PADDING*2
	width = 0
	for line in lines:
		height += line.get_height()
		width = max(width, line.get_width()+PADDING*2)

	surface = pygame.surface.Surface((width, height))
	surface.fill(BACKGROUND)
	height = PADDING
	for line in lines:
		surface.blit(line, (PADDING, height))
		height += line.get_height()

	return surface

def findposition(pos, surface):
	"""
	Find the position to blit this surface too, will make sure that the surface 
	doesn't go off the screen.
	"""
	screen_width, screen_height = pygame.display.get_surface().get_size()

	newpos = [0, 0]

	# First try placing the list to the right of the position
	if (pos[0]+PADDING+surface.get_width()) < screen_width:
		newpos[0] = pos[0]+PADDING
	
		# Make sure we don't go off the top of the screen
		newpos[1] = max(0, pos[1]-surface.get_height()/2)

		# Make sure we don't go of the bottom of the screen
		newpos[1] = min(screen_height-surface.get_height(), newpos[1])

	# Maybe to the left of the position?
	elif (pos[0]-PADDING-surface.get_width()) > 0:
		newpos[0] = pos[0]-PADDING-surface.get_width()

		# Make sure we don't go off the top of the screen
		newpos[1] = max(0, pos[1] - surface.get_height()/2)

		# Make sure we don't go of the bottom of the screen
		newpos[1] = min(screen_height-surface.get_height(), newpos[1])

	return newpos

def main():
	import pygame
	pygame.init()
	pygame.display.set_mode((800, 600))

	global ship
	global star
	global SPRITESIZE
	star = pygame.image.load('star.png').convert_alpha()
	ship = pygame.image.load('fleet.png').convert_alpha()
	SPRITESIZE = ship.get_width()

	connection, cache = connect()
	while True:
		update(connection, cache)

def connect():
	import sys
	print sys.argv

	if len(sys.argv) > 1:
		uri = sys.argv.pop(1)
	else:
		uri = 'tp://pygame:cannonfodder@localhost/tp'

	host, username, game, password = url2bits(uri)
	if not game is None:
		username = "%s@%s" % (username, game)

	connection = Connection()

	# Download the entire universe
	if connection.setup(host=host, debug=False):
		print "Unable to connect to the host."
		return

	if failed(connection.connect("tpsai-py/%i.%i.%i" % version)):
		print "Unable to connect to the host."
		return

	if failed(connection.login(username, password)):
		# Try creating the user..
		print "User did not exist, trying to create user."
		if failed(connection.account(username, password, "", "tpsai-py bot")):
			print "Username / Password incorrect."
			return

		if failed(connection.login(username, password)):
			print "Created username, but still couldn't login :/"
			return

	cache = Cache(Cache.key(host, username))
	return connection, cache

def system_ownership(cache, obj):
	"""\
	Returns
		% mine
		% enemies
		% not mine
	"""
	pid = cache.players[0].id

	contains = [obj]
	who = [0.0, 0.0, 0.0] # Mine, Enemies, Neutral
	while len(contains) > 0:
		obj = contains.pop(0)
		for id in obj.contains:
			contains.append(cache.objects[id])

		if not hasattr(obj, 'owner'):
			continue

		if obj.owner == pid:
			who[0] += 1
		elif not obj.owner in (0, -1):
			who[1] += 1
		else:
			who[2] += 1

	overall = reduce(float.__add__, who)
	if overall == 0:
		return [0.0, 0.0, 1.0]
	else:
		return [x/overall for x in who]

def update(connection, cache):
	# Update the cache
	def callback(*args, **kw):
		#print args, kw
		pass
	cache.update(connection, callback)
	pid = cache.players[0].id

	# Figure out the extents of the universe
	xmin = ymin = xmax = ymax = 0
	for obj in cache.objects.values():
		if obj.pos[0] < xmin:
			xmin = obj.pos[0]
		if obj.pos[0] > xmax:
			xmax = obj.pos[0]
		if obj.pos[1] < ymin:
			ymin = obj.pos[1]
		if obj.pos[1] > ymax:
			ymax = obj.pos[1]

	ymin *= 1.3
	xmin *= 1.3
	xdiff = (xmax - xmin)*1.3
	ydiff = (ymax - ymin)*1.3

	# Create the backdrop with the things on it...
	backdrop = pygame.display.get_surface().copy()
	backdrop.fill((0, 0, 0))
	deltax, deltay = backdrop.get_size()

	screen = {}
	for obj in cache.objects.values():
		screenpos = (int((-xmin+obj.pos[0])/xdiff*deltax)-SPRITESIZE/2, int((-ymin+obj.pos[1])/ydiff*deltay)-SPRITESIZE/2)

		green, red, white = system_ownership(cache, obj)
		if obj.subtype is SYSTEM_TYPE:
			screen[(screenpos, (SPRITESIZE, SPRITESIZE))] = obj.id

			thisstar = star.copy()
			array = pygame.surfarray.pixels3d(thisstar)
			array[:,:,0] = 126 + 126 * (red+white)
			array[:,:,1] = 126 + 126 * (green+white)
			array[:,:,2] = 126 + 126 * white
			del array

			backdrop.blit(thisstar, screenpos)
 		if obj.subtype is FLEET_TYPE:
			if not cache.objects[obj.parent].subtype in (SYSTEM_TYPE, PLANET_TYPE):
				screen[(screenpos, (SPRITESIZE, SPRITESIZE))] = obj.id

				thisship = ship.copy()
				array = pygame.surfarray.pixels3d(thisship)
				array[:,:,0] = 126 + 126 * (red+white)
				array[:,:,1] = 126 + 126 * (green+white)
				array[:,:,2] = 126 + 126 * white
				del array

				backdrop.blit(thisship, screenpos)

	display = pygame.display.get_surface()
	display.blit(backdrop, (0,0))

	point = pygame.Rect((0,0), (1,1))

	cid   = None
	cmode = None

	while True:
		# Pump Pygame
		pygame.event.get()
		pygame.display.flip()

		# If we get an EOT, we end the current turn
		connection.pump()
		pending = connection.buffered['frames-async']
		if len(pending) > 0:
			frame = pending.pop(0)
			print repr(frame)
			if isinstance(frame, objects.TimeRemaining):
				if frame.time == 0:
					continue
				return
		if pygame.mouse.get_pressed()[0]:
			nmode = "INFO"
		else:
			nmode = None

		point.center = pygame.mouse.get_pos()

		nid = point.collidedict(screen)
		if cid != nid or cmode != nmode:
			cid   = nid
			cmode = nmode

			# Reset the screen back to empty
			display.blit(backdrop, (0,0))
			if cid != None:
				
				obj  = cache.objects[cid[1]]
				# Find the objects screen position
				screenpos = (int((-xmin+obj.pos[0])/xdiff*deltax), int((-ymin+obj.pos[1])/ydiff*deltay))

				objs = [obj]
				s = []
				while len(objs) > 0:
					obj = objs.pop(0)
				
					for id in obj.contains:
						objs.append(cache.objects[id])
					
					color = WHITE
					if hasattr(obj, 'owner'):
						if obj.owner == pid:
							color = GREEN
						elif not obj.owner in (0, -1):
							color = RED
			
					# Only append the type if it is ambigious	
					if not TYPENAMES[obj.subtype] in obj.name:
						s.append((color, "%s (%s)" % (obj.name, TYPENAMES[obj.subtype])))
					else:
						s.append((color, "%s" % (obj.name)))

					if obj.subtype is FLEET_TYPE:
						for shipid, amount in obj.ships:
							s.append((WHITE, "  %s %ss" % (amount, cache.designs[shipid].name)))

						# Draw the destination lines
						if obj.vel != (0, 0, 0):
							screenvel = [int(obj.vel[0]/xdiff*deltax), int(obj.vel[1]/ydiff*deltay)]
	
							i = 1.0
							while True:
								startpos = (screenpos[0]+screenvel[0]*(i-1), screenpos[1]+screenvel[1]*(i-1))
								endpos   = (screenpos[0]+screenvel[0]*i,     screenpos[1]+screenvel[1]*i)
								
								pygame.draw.line(display, (255*(4-i)/4,255*(4-i)/4,255*(4-i)/4), startpos, endpos)

								i += 1
								if i > 3:
									break							

				for color, line in s:
					print line
				print

				if cmode == "INFO":
					t = rendertext(s)
					display.blit(t, findposition(screenpos, t))


		time.sleep(0.1)

# If the mouse is over a system
# For each object in system
#  Display name.
#    Red Text - Enemey
#    White Text - None
#    Green Text - Ours
#  Show the order name
#  Draw a line to the ships destination/trajectory

# If the mouse is over a fleet
#  Show the fleets destination/trajectory
#  Show the fleets makeup

if __name__ == "__main__":
	main()

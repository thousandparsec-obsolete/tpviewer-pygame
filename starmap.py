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
RED   = (200,  0,  0)
GREEN = (  0,200,  0)


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

	cid = None
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

		point.center = pygame.mouse.get_pos()

		nid = point.collidedict(screen)
		if cid != nid:
			cid = nid

			if cid != None:
				objs = [cache.objects[cid[1]]]
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
				
					s.append((color, "%s (%s)" % (obj.name, TYPENAMES[obj.subtype])))
					if obj.subtype is FLEET_TYPE:
						for shipid, amount in obj.ships:
							s.append((WHITE, "  %s %ss" % (amount, cache.designs[shipid].name)))

						# Draw the destination lines
						if obj.vel != (0, 0, 0):
							screenpos = (int((-xmin+obj.pos[0])/xdiff*deltax), int((-ymin+obj.pos[1])/ydiff*deltay))
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
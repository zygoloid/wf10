import curses
import random
import math
import os
import time

numAngles = 8

keys = {}
class Key(object):
  def __init__(self, code):
    keys[code] = self
    self.pressed = False
  def __bool__(self):
    return self.pressed

def wrap(x, y):
  x %= y
  if x < 0: x += y
  return x

erase = False
centre = (0, 0)
def addch(screen, x, y, ch, bold = True, color = 1, wrapped = True):
  attr = (bold and curses.A_BOLD or 0)
  if wrapped:
    y = int(wrap(y - centre[1] - size[0] / 2, size[0]))
    x = int(wrap(x - centre[0] - size[1] / 2, size[1]))
  try:
    screen.addch(y, x, erase and ' ' or ch,
        curses.color_pair(color) + attr)
  except Exception:
    pass

space = False
def setupScreen(screen):
  curses.curs_set(0)
  if space:
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLACK)
  else:
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLUE)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLUE)

  global size
  size = screen.getmaxyx()
  size = (size[0] - 1, size[1])
  for x in range(size[1]):
    for y in range(size[0]):
      addch(screen, x, y, ' ')

class Vector(object):
  def __init__(self, x = 0, y = 0): self.x, self.y = x, y
  @staticmethod
  def dir(d): return Vector(math.sin(d), -math.cos(d))
  @staticmethod
  def random(): return Vector(random.random() * 2 - 1, random.random() * 2 - 1)
  def __getitem__(self, n): return (self.x, self.y)[n]
  def __bool__(self): return bool(self.x or self.y)
  def __neg__(self): return Vector(-self.x, -self.y)
  def __add__(self, o): return Vector(self.x+o[0], self.y+o[1])
  def __sub__(self, o): return self + -o
  def __mul__(self, o): return Vector(self.x*o, self.y*o)
  def __truediv__(self, o): return self * (1/o)
  def norm(self): return (self.x*self.x + self.y*self.y) ** 0.5
  def normal(self):
    if not self: return Vector()
    return self / self.norm()
  def wrap(self): return Vector(wrap(self.x, size[1]), wrap(self.y, size[0]*2))
  def min(self):
    r = self.wrap()
    if r.x > size[1]/2: r.x -= size[1]
    if r.y > size[0]: r.y -= size[0]*2
    return r

def dotProduct(v1, v2):
  return v1[0] * v2[0] + v1[1] * v2[1]
def crossProductZ(v1, v2):
  return v1[0] * v2[1] - v1[1] * v2[0]

class InertialBody(object):
  """An inertial body, characterized by terminal velocity and
  half-life (time to get halfway to terminal velocity).
  The acceleration is the terminal velocity multiplied by the
  drag coefficient. The drag coefficient (multiple of velocity
  used as an opposing acceleration) is ln(2) / halflife.
  """
  def __init__(self, x, v = Vector(), halfLife = 1):
    self.x, self.v = x, v
    self.drag = math.log(2) / halfLife
  def update(self, t, tv):
    d = self.drag
    vDiff = tv - self.v
    e = math.exp(-t*d)
    r = vDiff * (1 - e) / d
    self.x += tv * t - r
    self.x = self.x.wrap()
    self.v = tv - vDiff * e

class NonInertialBody(object):
  def __init__(self, x): self.x, self.v = x, Vector()
  def update(self, t, v):
    self.x += v * t
    self.v = v

class Chaser(object):
  def __init__(self, target):
    self.target = target
    self.body = InertialBody(self.target.x + Vector.dir(random.random() * 2 * math.pi) * 5)
    self.topSpeed = 5 #fixme
  def update(self, t):
    o = (self.target.x - self.body.x).min()
    if o.norm() < 5: o = -o
    self.body.update(t, o.normal() * 50)
  def render(self, screen):
    addch(screen, self.body.x[0], self.body.x[1]/2, 'X')

class Ship(object):
  def __init__(self, config, x, y, symbol = 'o'):
    self.body = InertialBody(Vector(x, y))
    self.angle, self.turnSpeed, self.speed = random.randint(0, numAngles), 0, 0
    for dir in ('up', 'down', 'left', 'right', 'fire'):
      if dir in config:
        self.__dict__[dir] = Key(config[dir])
      else:
        self.__dict__[dir] = False
    self.bulletsLeft = 3
    self.topSpeed = 5
    self.symbol = symbol
    self.flashFor = 0
  def update(self, elapsed):
    self.turnSpeed = 0
    if self.left: self.turnSpeed = (self.turnSpeed != -1 and -1 or 0)
    if self.right: self.turnSpeed = (self.turnSpeed != 1 and 1 or 0)
    if self.up: self.speed += 1
    self.speed = min(self.speed, self.topSpeed)
    if self.speed > 0 and self.down: self.speed -= 1
    self.flashFor = max(self.flashFor - elapsed, 0)
    global objects
    angle = 2*math.pi*self.angle/numAngles
    if self.fire and self.bulletsLeft > 0:
      dir = [(0,-1),(1,-1),(2,0),(1,1),(0,1),(-1,1),(-2,0),(-1,-1)][int(self.angle)]
      d = Vector.dir(angle)
      objects.append(Torpedo(self.body.x.x + dir[0] + 0.5,
                 self.body.x.y + dir[1] * 2 + 0.5,
                             self.body.v.x,
                             self.body.v.y,
                 d.x, d.y, self))
      self.bulletsLeft -= 1
    self.angle += self.turnSpeed
    self.angle = wrap(self.angle, numAngles)
    self.body.update(elapsed, Vector.dir(angle) * 10 * self.speed)
    for object in objects[:]:
      if object != self and isinstance(object, (Ship, Chaser)) and abs(int(object.body.x.x) - int(self.body.x.x)) < 2 and abs(int(object.body.x.y) - int(self.body.x.y)) < 2:
        objects.remove(object)
        if self in objects:
          objects.remove(self)
        self.topSpeed = 0
        object.topSpeed = 0
        asplode(self.body.x, Vector(), 60, speed = 16)
  def render(self, screen):
    addch(screen, int(self.body.x.x), int(self.body.x.y)/2, self.symbol, color = int(self.flashFor * 4) % 2 == 0 and 1 or 3)
    a = int(self.angle)
    sym = r'|/-\|/-\\'[a]
    dir = [(0,-1),(1,-1),(2,0),(1,1),(0,1),(-1,1),(-2,0),(-1,-1)][a]
    addch(screen, int(self.body.x.x)+dir[0], int(self.body.x.y)/2+dir[1], sym)

class ComputerPlayer(object):
  def __init__(self, x, y, target, symbol = 'o'):
    config = {}
    self.ship = Ship(config, x, y, symbol)
    #self.ship.body = NonInertialBody(Vector(x, y))
    self.target = target
    self.timeLeft = 0
    objects.append(self)
    objects.append(self.ship)
    self.keyspeed = 0.1
    self.lastTurn = 0
    self.sinceLastTurn = 0
    self.angle = 9
  def update(self, elapsed):
    self.timeLeft += elapsed
    self.sinceLastTurn += elapsed
    self.ship.up = self.ship.down = self.ship.left = self.ship.right = self.ship.fire = False
    while self.timeLeft > self.keyspeed:
      if self.ship.speed < self.ship.topSpeed:
        self.ship.up = True
      else:
        o = (self.target.x - self.ship.body.x).min().normal()
        shipAngle = 2*math.pi*self.ship.angle/numAngles
        angle = crossProductZ(o, Vector.dir(shipAngle))
        turn = 0
        if angle > 0.01: turn = -1
        if angle < -0.01: turn = 1
        if turn and (turn != -self.lastTurn or self.sinceLastTurn > 0.5):
          if turn == 1:
            self.ship.right = True
          else:
            self.ship.left = True
          self.lastTurn = turn
          self.sinceLastTurn = 0
        else:
          self.ship.fire = True
      self.timeLeft -= self.keyspeed
  def render(self, screen): pass

def asplode(pos, v, size, speed = 8):
  particles = []
  for n in range(size):
    angle = random.random() * 2 * math.pi
    particles.append(Particle(pos,
      v + (Vector.dir(angle) + Vector.random()) * speed,
      color = (1,4,3,5), timeout = (0.25, 0.25, 0.25, 0.25)))
  objects[0:0] = particles

class Torpedo(object):
  def __init__(self, x, y, vx, vy, dx, dy, ship):
    self.body = InertialBody(x = Vector(x, y), v = Vector(vx, vy))
    self.d = Vector(dx, dy) * 300
    self.timeLeft = 1.25
    self.ship = ship
  def update(self, elapsed):
    self.body.update(elapsed, self.d)
    self.timeLeft -= elapsed
    global objects
    for object in objects[:]:
      if isinstance(object, (Ship, Chaser)) and abs(int(object.body.x.x) - int(self.body.x.x)) < 2 and abs(int(object.body.x.y) - int(self.body.x.y)) < 2 and self.timeLeft < 1.1:
        self.timeLeft = -1
        object.topSpeed -= 1
        object.flashFor = 2
        explosionSize = 8
        if object.topSpeed <= 0:
          objects.remove(object)
          explosionSize = 30
        asplode(self.body.x, object.body.x / 5, explosionSize)
    if self.timeLeft < 0:
      objects.remove(self)
      self.ship.bulletsLeft += 1
  def render(self, screen):
    addch(screen, int(self.body.x.x), int(self.body.x.y)/2, '*', color = 3)

class Particle(object):
  def __init__(self, x, v, color, timeout):
    self.body = InertialBody(x = x, v = v)
    self.color = list(reversed(color))
    self.timeLeft = list(reversed(timeout))
  def update(self, elapsed):
    self.body.update(elapsed, Vector())
    self.timeLeft[-1] -= elapsed
    while self.timeLeft[-1] < 0:
      overshoot = self.timeLeft.pop()
      self.color.pop()
      if self.timeLeft:
        self.timeLeft[-1] -= overshoot
      else:
        global objects
        objects.remove(self)
        break
  def render(self, screen):
    addch(screen, int(self.body.x.x), int(self.body.x.y)/2, '.', color = self.color and self.color[-1] or 0)

class Wave(object):
  def __init__(self): self.update(20)
  def update(self, elapsed):
    if 4 * random.random() < elapsed:
      self.x = random.randint(0, size[1])
      self.y = random.randint(0, size[0])
  def render(self, screen):
    addch(screen, self.x, self.y, space and '.' or '~', color = 2, bold = not space)

class StatusBar(object):
  def __init__(self): self.centre = ''
  def update(self, elapsed): pass
  def render(self, screen):
    txts = []
    for ship in (ship1, ship2):
      if ship.topSpeed <= 0:
        txt = '  dedded  '
      else:
        txt = '  ' + '=' * ship.speed + '-' * (ship.topSpeed - ship.speed)
        txt += '  ' + '*' * ship.bulletsLeft
      txts.append(txt)
    txts[1] = ''.join(reversed(txts[1]))
    txts[1:1] = [self.centre]
    free = size[1] - sum(len(t) for t in txts)
    gap = int(free / (len(txts)-1))
    bar = txts[0] + ' ' * gap + txts[1] + ' ' * (free - gap) + txts[2]
    for x, c in enumerate(bar):
      addch(screen, x, size[0], c, color = 0, wrapped = False)

class CenterScreen(object):
  def __init__(self, a, b):
    self.a = a
    self.b = b
    self.body = InertialBody(Vector(), halfLife = 1)
  def update(self, t):
    a = self.a.x
    b = self.b.x
    c = (a - b).min() / 2. + b
    o = (c - self.body.x).min()
    if o: self.body.update(t, o.normal() * 50)
    global centre
    centre = (self.body.x[0], self.body.x[1]/2)
  def render(self, screen):
    #addch(screen, self.body.x[0], self.body.x[1]/2, 'x')
    pass

def newGame(players):
  global objects, ship1, ship2
  objects = []

  objects.extend([Wave() for n in range(100)])

  config = dict(up=b'\x1bOA', down=b'\x1bOB', left=b'\x1bOD', right=b'\x1bOC', fire=b'/')
  ship1 = Ship(config, 30, 30, 'a')
  objects.append(ship1)

  if players == 2:
    config = dict(up=b'w', down=b's', left=b'a', right=b'd', fire=b'q')
    ship2 = Ship(config, size[1] - 30, size[0] * 2 - 30, 'p')
    objects.append(ship2)
  else:
    cp = ComputerPlayer(size[1] - 30, size[0] * 2 - 30, ship1.body, 'p')
    ship2 = cp.ship

  #for i in range(5):
  #	objects.append(Chaser(ship1.body))
  #	objects.append(Chaser(ship2.body))

  #objects.append(CenterScreen(ship1.body, ship2.body))
  sb = StatusBar()
  objects.append(sb)
  return sb

if False:
  # old way, does not work on MacOS
  stdin = os.open('/dev/stdin', os.O_RDONLY + os.O_NONBLOCK)
else:
  import sys, fcntl
  stdin = sys.stdin
  fcntl.fcntl(stdin, fcntl.F_SETFL, fcntl.fcntl(stdin, fcntl.F_GETFL) | os.O_NONBLOCK)

def getkeys():
  try: return os.read(stdin.fileno(), 1024)
  except OSError: return ''

objects = []

def play(s):
  setupScreen(s)

  global screen
  screen = s

  lastTime = time.time()
  startNewGame1 = Key(b'n')
  startNewGame2 = Key(b'N')
  secsPerFrame = 1/60.
  sb = None
  while True:
    timeToNext = time.time() - lastTime
    if timeToNext < secsPerFrame:
      time.sleep(secsPerFrame - timeToNext)
    global frames
    frames += 1
    for key in keys.values(): key.pressed = False
    str = getkeys()
    while str:
      for char, key in keys.items():
        if str.startswith(char):
          str = str[len(char):]
          key.pressed = True
          break
      else:
        str = str[1:]
    thisTime = time.time()
    elapsed = thisTime - lastTime
    lastTime = thisTime
    if startNewGame1: sb = newGame(1)
    if startNewGame2: sb = newGame(2)
    if callback:
      v = callback()
      if not v: break
      if sb: sb.centre = v
    for o in objects[:]:
      o.update(elapsed)
    global erase
    erase = False
    for o in objects:
      o.render(screen)
    screen.refresh()
    erase = True
    for o in objects:
      o.render(screen)

def main(cb = None):
  global callback, frames, firstTime
  callback = cb
  frames = 0
  firstTime = time.time()
  try:
    try:
      curses.wrapper(play)
    except KeyboardInterrupt:
      pass
  finally:
    print('%f frames per second' % (frames / (time.time() - firstTime)))

if __name__ == '__main__':
  main()

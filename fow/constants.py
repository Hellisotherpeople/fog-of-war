"""Global constants: screen layout, colours, directions, tuning knobs."""
from __future__ import annotations

TITLE = "FOG OF WAR"
SUBTITLE = "a Second World War roguelike"

# ---------------------------------------------------------------- screen
SCREEN_W = 120
SCREEN_H = 50
PANEL_W = 26                      # right-hand condition/kit panel
LOG_H = 8                         # bottom log height
VIEW_W = SCREEN_W - PANEL_W       # map viewport width
VIEW_H = SCREEN_H - LOG_H         # map viewport height

MAP_W = 180
MAP_H = 120

# ---------------------------------------------------------------- time
TURN_SECONDS = 1                  # one world turn is one second
BASE_SPEED = 100                  # moves gained per turn
STRATEGIC_TICK = 600              # turns between strategic resolutions (10 minutes)
SIDE_BRAIN_TICK = 4               # turns between side dijkstra-map refreshes

# ---------------------------------------------------------------- sides
ALLIES = "allies"
AXIS = "axis"
SIDES = (ALLIES, AXIS)


def other_side(side: str) -> str:
    return AXIS if side == ALLIES else ALLIES


# ---------------------------------------------------------------- directions
DIRS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
DIRS4 = [(0, -1), (-1, 0), (1, 0), (0, 1)]
COMPASS = {(0, -1): "N", (1, -1): "NE", (1, 0): "E", (1, 1): "SE",
           (0, 1): "S", (-1, 1): "SW", (-1, 0): "W", (-1, -1): "NW"}
COMPASS_WORD = {"N": "north", "S": "south", "E": "east", "W": "west", "NE": "north-east", "NW": "north-west",
                "SE": "south-east", "SW": "south-west"}
# octant index 0..7 starting east, counter-clockwise in screen coordinates
OCTANT_VEC = [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1)]

BIG = 10 ** 8                     # "unreachable" for dijkstra maps

# ---------------------------------------------------------------- colours
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (128, 128, 128)
LGREY = (190, 190, 190)
DGREY = (70, 70, 70)
VDGREY = (35, 35, 35)
RED = (220, 40, 40)
LRED = (255, 110, 110)
DRED = (120, 10, 10)
ORANGE = (255, 150, 30)
YELLOW = (240, 220, 60)
LYELLOW = (255, 245, 150)
GREEN = (60, 190, 60)
LGREEN = (140, 230, 120)
DGREEN = (20, 90, 20)
CYAN = (70, 200, 220)
LCYAN = (160, 235, 245)
BLUE = (60, 110, 230)
LBLUE = (130, 170, 255)
DBLUE = (20, 40, 110)
MAGENTA = (210, 80, 210)
BROWN = (140, 95, 50)
LBROWN = (190, 150, 95)
KHAKI = (190, 180, 120)
OLIVE = (120, 130, 60)
SAND = (215, 195, 130)
PAPER = (225, 215, 180)
INK = (40, 30, 20)
BLOOD = (150, 0, 0)

UI_BG = (14, 14, 12)
UI_FRAME = (150, 140, 100)
UI_TEXT = (215, 205, 175)
UI_DIM = (120, 115, 95)
UI_HI = (255, 230, 140)
UI_SEL_BG = (70, 60, 30)

SIDE_COLOR = {ALLIES: (120, 175, 255), AXIS: (255, 120, 100)}
FRIEND_COLOR = (110, 220, 255)
ENEMY_COLOR = (255, 90, 70)
PLAYER_COLOR = (255, 255, 160)

# message categories -> colours
MSG_COLORS = {
    "info": UI_TEXT,
    "combat": (230, 200, 160),
    "hit": (255, 140, 100),
    "hurt": (255, 70, 70),
    "sound": (170, 170, 210),
    "radio": (140, 220, 140),
    "shout": (240, 240, 170),
    "good": (140, 240, 140),
    "warn": (255, 200, 60),
    "think": (175, 165, 140),
    "death": (255, 40, 40),
    "system": (150, 150, 150),
}


def cap(s: str) -> str:
    """Capitalise the first letter only (str.capitalize lowercases the rest)."""
    return s[:1].upper() + s[1:] if s else s

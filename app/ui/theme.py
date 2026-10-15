"""Theme constants for the Pesto Player UI (colors, sizes, layout metrics).

Layout constants live here (never in config.py). Screen is 320x480 portrait.
"""

SCREEN_W = 320
SCREEN_H = 480

# Layout bands
STATUS_H = 24
TAB_H = 56
MINI_H = 48
ROW_H = 56
MIN_TOUCH = 44

TAB_Y = SCREEN_H - TAB_H            # 424
MINI_Y = TAB_Y - MINI_H             # 376
CONTENT_TOP = STATUS_H              # 24
CONTENT_BOTTOM = TAB_Y              # 424 (screens without mini-player)
CONTENT_BOTTOM_MINI = MINI_Y        # 376 (screens with mini-player)

PAD = 12

# Colors
BG = (18, 18, 18)
BG_DARK = (12, 12, 12)
BG_LIGHT = (30, 30, 30)
BG_PRESSED = (44, 44, 44)
PRIMARY = (138, 43, 226)
PRIMARY_DARK = (98, 30, 160)
PRIMARY_LIGHT = (178, 83, 255)
TEXT = (255, 255, 255)
TEXT_DIM = (180, 180, 180)
TEXT_DISABLED = (100, 100, 100)
BORDER = (60, 60, 60)
SUCCESS = (46, 213, 115)
WARNING = (255, 195, 0)
ERROR = (235, 77, 75)
TOAST_BG = (40, 40, 40)

# Font sizes
FS_SMALL = 12
FS_BODY = 15
FS_TITLE = 18
FS_HEADER = 22
FS_BIG = 28

# Gesture thresholds
TAP_SLOP = 10          # px of total travel before a touch becomes a drag
TAP_MAX_MS = 300       # a press longer than this is not a tap
LONG_PRESS_MS = 500

# Frame pacing
FPS_ACTIVE = 30
FPS_IDLE = 10
IDLE_AFTER_S = 1.0

"""
Configuration file for Pesto Player
Contains all constants for GPIO pins, colors, screen dimensions, and settings
"""

# ============================================================================
# SCREEN CONFIGURATION
# ============================================================================
SCREEN_WIDTH = 320   # Portrait mode width
SCREEN_HEIGHT = 480  # Portrait mode height
FPS = 30             # Target frames per second

# Touch target minimum size (finger-friendly)
MIN_TOUCH_SIZE = 60

# ============================================================================
# COLOR SCHEME (Dark theme with white/purple accents)
# ============================================================================
# Background colors
COLOR_BG_DARK = (18, 18, 18)        # Main background
COLOR_BG_DARKER = (12, 12, 12)      # Darker sections
COLOR_BG_LIGHTER = (30, 30, 30)     # Lighter sections (cards)

# Accent colors
COLOR_PRIMARY = (138, 43, 226)      # Purple accent (BlueViolet)
COLOR_PRIMARY_DARK = (98, 30, 160)  # Darker purple for pressed states
COLOR_PRIMARY_LIGHT = (178, 83, 255) # Lighter purple for highlights

# Text colors
COLOR_TEXT_PRIMARY = (255, 255, 255)    # White text
COLOR_TEXT_SECONDARY = (180, 180, 180)  # Gray text
COLOR_TEXT_DISABLED = (100, 100, 100)   # Disabled text

# UI element colors
COLOR_BORDER = (60, 60, 60)         # Border color
COLOR_PROGRESS = (138, 43, 226)     # Progress bar color
COLOR_SUCCESS = (46, 213, 115)      # Success/connected indicator
COLOR_WARNING = (255, 195, 0)       # Warning indicator
COLOR_ERROR = (235, 77, 75)         # Error indicator

# ============================================================================
# GPIO PIN CONFIGURATION (Raspberry Pi)
# ============================================================================
GPIO_POWER_BUTTON = 26    # Power button
GPIO_VOLUME_UP = 5        # Volume up button
GPIO_VOLUME_DOWN = 6      # Volume down button

# GPIO settings
GPIO_BOUNCE_TIME = 0.1    # Bounce time in seconds
GPIO_LONG_PRESS_TIME = 3.0  # Long press duration in seconds

# ============================================================================
# AUDIO CONFIGURATION
# ============================================================================
VOLUME_DEFAULT = 50       # Default volume percentage
VOLUME_STEP = 5           # Volume change step
VOLUME_MIN = 0            # Minimum volume
VOLUME_MAX = 100          # Maximum volume

MUSIC_DIRECTORY = "~/Music"  # Default music directory

# Supported audio formats
SUPPORTED_FORMATS = ['.mp3', '.flac', '.m4a', '.ogg', '.wav']

# ============================================================================
# BATTERY CONFIGURATION
# ============================================================================
BATTERY_I2C_ADDRESS = 0x36        # MAX17048 I2C address
BATTERY_UPDATE_INTERVAL = 10.0    # Update interval in seconds
BATTERY_LOW_WARNING = 15          # Low battery warning percentage
BATTERY_CRITICAL = 5              # Critical battery (shutdown) percentage

# ============================================================================
# MOPIDY CONFIGURATION
# ============================================================================
MOPIDY_HOST = "localhost"
MOPIDY_PORT = 6680
MOPIDY_BASE_URL = f"http://{MOPIDY_HOST}:{MOPIDY_PORT}/mopidy/rpc"

# ============================================================================
# UI LAYOUT CONSTANTS
# ============================================================================

# Status bar (top of screen)
STATUS_BAR_HEIGHT = 30
STATUS_BAR_PADDING = 10

# Now Playing screen layout
ALBUM_ART_SIZE = 280              # Square album art
ALBUM_ART_Y = 50                  # Y position from top

# Control button sizes
BUTTON_LARGE = 80                 # Play/pause button
BUTTON_MEDIUM = 70                # Skip buttons
BUTTON_SMALL = 60                 # Navigation buttons

# Progress bar
PROGRESS_BAR_HEIGHT = 4
PROGRESS_BAR_PADDING = 20

# Bottom navigation bar
NAV_BAR_HEIGHT = 60
NAV_BAR_BUTTON_WIDTH = 100

# Library screen layout
LIST_ITEM_HEIGHT = 70
LIST_PADDING = 10
TAB_HEIGHT = 50

# Settings screen layout
SETTING_ITEM_HEIGHT = 60
SLIDER_WIDTH = 200
SLIDER_HEIGHT = 40

# ============================================================================
# TIMING CONSTANTS
# ============================================================================
METADATA_UPDATE_INTERVAL = 1.0    # Update current song metadata (seconds)
UI_UPDATE_INTERVAL = 0.033        # UI update interval (~30 FPS)
ALBUM_ART_CACHE_SIZE = 20         # Number of album arts to cache

# ============================================================================
# TESTING/DEVELOPMENT MODE
# ============================================================================
TEST_MODE = True  # Set to False when running on actual hardware

# Keyboard mappings for testing (when TEST_MODE = True)
KEY_VOLUME_UP = 'up'              # Arrow up
KEY_VOLUME_DOWN = 'down'          # Arrow down
KEY_POWER = 'escape'              # ESC key

# Mock data for testing
MOCK_BATTERY_LEVEL = 85           # Mock battery percentage
MOCK_SONGS = [
    {
        'title': 'Test Song 1',
        'artist': 'Test Artist 1',
        'album': 'Test Album 1',
        'duration': 240,
        'path': None
    },
    {
        'title': 'Test Song 2',
        'artist': 'Test Artist 2',
        'album': 'Test Album 2',
        'duration': 180,
        'path': None
    }
]

# ============================================================================
# FONT CONFIGURATION
# ============================================================================
# Using pygame's default font for now, can be customized later
FONT_SIZE_LARGE = 24
FONT_SIZE_MEDIUM = 18
FONT_SIZE_SMALL = 14
FONT_SIZE_TINY = 12

# ============================================================================
# BLUETOOTH CONFIGURATION
# ============================================================================
BLUETOOTH_SCAN_TIMEOUT = 30       # Bluetooth scan timeout in seconds
BLUETOOTH_CONNECT_TIMEOUT = 15    # Connection timeout in seconds

# Audio output modes
AUDIO_OUTPUT_SPEAKER = "speaker"
AUDIO_OUTPUT_BLUETOOTH = "bluetooth"

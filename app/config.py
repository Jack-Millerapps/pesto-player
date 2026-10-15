"""
Configuration for Pesto Player: hardware pins, audio, paths and mode detection.

UI layout constants and colours live in ui/theme.py, not here.
"""
import os

# ---------------------------------------------------------------- screen
SCREEN_WIDTH = 320   # portrait
SCREEN_HEIGHT = 480
FPS = 30             # initial frame cap; the ScreenManager lowers it when idle

# ------------------------------------------------------------------ GPIO
GPIO_POWER_BUTTON = 26
GPIO_VOLUME_UP = 5
GPIO_VOLUME_DOWN = 6
GPIO_BOUNCE_TIME = 0.1       # seconds
GPIO_LONG_PRESS_TIME = 3.0   # seconds: long press on power = shutdown

# ----------------------------------------------------------------- audio
VOLUME_DEFAULT = 50
VOLUME_STEP = 5
VOLUME_MIN = 0
VOLUME_MAX = 100

MUSIC_DIRECTORY = os.environ.get("PESTO_MUSIC_DIR", "~/Music")  # env override for tests/dev
SUPPORTED_FORMATS = ['.mp3', '.flac', '.m4a', '.ogg', '.wav', '.opus']  # matched case-insensitively
# pi/uploader/server.py keeps its own copy of this list; test_server.py checks they match.

# --------------------------------------------------------------- battery
BATTERY_I2C_ADDRESS = 0x36   # MAX17048
BATTERY_LOW_WARNING = 15     # percent
BATTERY_CRITICAL = 5         # percent; 3 consecutive readings => shutdown
MOCK_BATTERY_LEVEL = 85      # TEST_MODE only

# ------------------------------------------------------------- bluetooth
# Scaffolding only (hardware/bluetooth.py); Settings shows "not available yet".
BLUETOOTH_SCAN_TIMEOUT = 30
BLUETOOTH_CONNECT_TIMEOUT = 15
AUDIO_OUTPUT_SPEAKER = "speaker"
AUDIO_OUTPUT_BLUETOOTH = "bluetooth"


# ------------------------------------------------------------ test mode
def _detect_test_mode():
    """PESTO_TEST=1/0 forces the mode; otherwise TEST_MODE is on unless we look
    like the real device (a Linux framebuffer and GPIO are both present)."""
    forced = os.environ.get("PESTO_TEST")
    if forced is not None:
        return forced.strip().lower() not in ("0", "false", "no", "")
    return not (os.path.exists("/dev/fb0") and os.path.exists("/dev/gpiomem"))


TEST_MODE = _detect_test_mode()  # auto-detected; override with env PESTO_TEST=0/1

# ----------------------------------------------------- persisted state
STATE_DIR = os.path.expanduser(os.environ.get("PESTO_STATE_DIR", "~/.pesto"))
STATE_FILE = os.path.join(STATE_DIR, "state.json")           # volume, queue, last track
INDEX_FILE = os.path.join(STATE_DIR, "library_index.json")   # metadata cache
PREFS_FILE = os.path.join(STATE_DIR, "prefs.json")           # screen timeout, brightness
PLAYLIST_DIR = os.path.join(STATE_DIR, "playlists")
DIRTY_FLAG = os.path.join(STATE_DIR, "library.dirty")        # touched by the uploader per batch
UPLOADER_PORT = 8080
UPLOADER_INFO_FILE = os.path.join(STATE_DIR, "uploader.json")  # {"token":..,"port":..}
BACKLIGHT_PATH = "/sys/class/backlight"   # optional; brightness/sleep skip it if absent
APP_VERSION = "2.0.0"

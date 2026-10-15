# Pesto Player 🎵

A touchscreen music player designed for Raspberry Pi Zero 2 W with a 4.0" capacitive touchscreen display.

**Status**: Phase 1 Complete ✅
**Version**: 1.0.0 - Phase 1
**Project Type**: School Project

---

## 📋 Table of Contents

- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Testing on Laptop](#testing-on-laptop)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Development](#development)
- [Phase 2 Roadmap](#phase-2-roadmap)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

### Phase 1 (Current)
- ✅ **Touchscreen UI**: Smartphone-like interface (320×480 portrait)
- ✅ **Local Playback**: Play MP3/FLAC files from ~/Music directory
- ✅ **Playback Controls**: Play, pause, skip, previous, seek
- ✅ **Volume Control**: Physical buttons (or keyboard in test mode)
- ✅ **Library Browser**: Scrollable list of all songs
- ✅ **Now Playing Screen**: Album art, song info, progress bar
- ✅ **Settings Screen**: System info and configuration
- ✅ **Mock Mode**: Test on laptop with mouse/keyboard

### Phase 2 (Coming Soon)
- ⏳ Spotify streaming via Mopidy integration
- ⏳ Bluetooth headphone support
- ⏳ Audio output switching (speaker ↔ Bluetooth)
- ⏳ Spotify search and playlists
- ⏳ Album art display from MP3 tags
- ⏳ Playlist management

---

## 🔧 Hardware Requirements

### For Final Deployment (Raspberry Pi)
- **Raspberry Pi Zero 2 W**
- **4.0" Capacitive Touchscreen** (320×480, FT6336U controller)
- **I2S DAC**: PCM5102A
- **Amplifier**: PAM8302
- **Battery Monitor**: MAX17048 (AmpRipper 4000)
- **Physical Buttons**: 3× tactile buttons (Power, Vol+, Vol-)
- **SD Card**: 16GB+ recommended

### For Testing (Laptop)
- **Any computer** with Python 3.8+
- **Mouse**: Simulates touch input
- **Keyboard**: Simulates physical buttons

---

## 💻 Software Requirements

### Core Dependencies
- **Python 3.8+**
- **pygame** (UI rendering)
- **python-vlc** (audio playback)
- **mutagen** (optional, for metadata extraction)

### Raspberry Pi Only
- **gpiozero** (GPIO button handling)
- **adafruit-circuitpython-max1704x** (battery monitor)
- **RPi.GPIO**

---

## 📦 Installation

### 1. Testing on Laptop (Recommended First)

```bash
# Clone or navigate to the project
cd pesto-player

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install pygame python-vlc mutagen

# Optional: Add some test MP3 files
mkdir -p ~/Music
# Copy some MP3 files to ~/Music

# Run the app
python main.py
```

**Controls (Test Mode)**:
- **Mouse** = Touch input
- **Arrow Up/Down** = Volume control
- **ESC or Q** = Exit

### 2. Deploying to Raspberry Pi

```bash
# On Raspberry Pi
cd pesto-player

# Install system dependencies
sudo apt-get update
sudo apt-get install python3-pygame vlc python3-vlc

# Install Python dependencies
pip3 install -r requirements.txt

# Edit config.py - set TEST_MODE to False
nano config.py
# Change: TEST_MODE = False

# Make main.py executable
chmod +x main.py

# Run the app
python3 main.py

# Optional: Set up autostart (add to /etc/rc.local or systemd)
```

---

## 🧪 Testing on Laptop

The app is designed to run on your laptop first for development and testing!

### Quick Start

1. **Install minimal dependencies**:
   ```bash
   pip install pygame
   ```

2. **Run with mock data**:
   ```bash
   python main.py
   ```
   - The app will use mock songs if ~/Music is empty
   - Audio playback will be simulated
   - Battery level will be mocked at 85%

3. **Test with real music**:
   - Add MP3 files to `~/Music` directory
   - Install VLC: `pip install python-vlc`
   - Restart the app to scan your music

### Test Mode Features

- **Mock Audio Player**: Simulates playback if VLC is not installed
- **Mock Library**: Shows sample songs if ~/Music is empty
- **Mock Battery**: Shows 85% battery level
- **Keyboard Controls**:
  - ↑/↓ = Volume up/down
  - ESC = Exit
  - Q = Quick exit
  - Mouse = Touch input

---

## 📁 Project Structure

```
pesto-player/
├── main.py              # ⭐ Entry point - START HERE
├── config.py            # All configuration constants
├── requirements.txt     # Python dependencies
├── README.md           # This file
│
├── player/             # Audio and library management
│   ├── audio.py        # AudioPlayer class (VLC + mock)
│   ├── library.py      # Music library scanner
│   ├── mopidy_client.py # Spotify integration (Phase 2)
│   └── playlist.py     # Playlist management (Phase 2)
│
├── hardware/           # Hardware interfaces
│   ├── buttons.py      # GPIO buttons (+ keyboard mock)
│   ├── battery.py      # Battery monitor (+ mock)
│   ├── bluetooth.py    # Bluetooth manager (Phase 2)
│   └── touch.py        # Touch controller (Phase 2)
│
├── ui/                 # User interface
│   ├── screen_manager.py  # Screen navigation
│   ├── widgets.py      # Reusable UI components
│   ├── now_playing.py  # Main playback screen
│   ├── library.py      # Music library browser
│   └── settings.py     # Settings and about
│
└── assets/            # Resources
    └── fonts/         # Custom fonts (future)
```

---

## 🎮 Usage

### Navigation

1. **Now Playing Screen** (Main screen)
   - Large album art display
   - Song title, artist, album
   - Progress bar (drag to seek)
   - Play/Pause/Skip buttons
   - Navigate to Library or Settings

2. **Library Screen**
   - Browse all songs
   - Tap a song to play it
   - Two tabs: "Local Files" and "Spotify" (Phase 2)
   - Scrollable list

3. **Settings Screen**
   - View battery level
   - Check song count
   - System information
   - Audio output selection (Phase 2)

### Physical Buttons (Production Mode)

- **Power Button** (GPIO 26):
  - Short press: Wake/sleep screen
  - Long press (3s): Shutdown

- **Volume Up** (GPIO 5): Increase volume by 5%
- **Volume Down** (GPIO 6): Decrease volume by 5%

---

## 🛠️ Development

### Configuration

Edit `config.py` to customize:

```python
# Display settings
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 480
FPS = 30

# Colors
COLOR_PRIMARY = (138, 43, 226)  # Purple accent
COLOR_BG_DARK = (18, 18, 18)    # Dark background

# Testing
TEST_MODE = True  # Set to False for production

# GPIO pins
GPIO_POWER_BUTTON = 26
GPIO_VOLUME_UP = 5
GPIO_VOLUME_DOWN = 6

# Music directory
MUSIC_DIRECTORY = "~/Music"
```

### Adding New Screens

1. Create a new file in `ui/` (e.g., `ui/playlist_screen.py`)
2. Subclass `Screen` from `screen_manager.py`
3. Implement `draw()`, `handle_touch()`, and `update()` methods
4. Register the screen in `main.py`:

```python
self.playlist_screen = PlaylistScreen(self.screen_manager, ...)
self.screen_manager.register_screen('playlist', self.playlist_screen)
```

### Code Style

- **Docstrings**: All classes and non-trivial functions
- **Comments**: Explain "why", not "what"
- **Constants**: Use config.py, not magic numbers
- **Naming**:
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`

---

## 🚀 Phase 2 Roadmap

### Planned Features

1. **Spotify Integration**
   - Install Mopidy + mopidy-spotify
   - Search Spotify catalog
   - Play Spotify tracks
   - Access your playlists

2. **Bluetooth Audio**
   - Pair Bluetooth headphones
   - Switch between speaker and Bluetooth
   - Show connection status

3. **Enhanced UI**
   - Display album art from MP3 tags
   - Custom fonts
   - Smooth transitions
   - Loading animations

4. **Playlist Management**
   - Create custom playlists
   - Save/load playlists
   - Reorder songs

5. **Advanced Features**
   - Equalizer settings
   - Sleep timer
   - Shuffle and repeat modes
   - Search functionality

---

## 🐛 Troubleshooting

### "No module named 'pygame'"
```bash
pip install pygame
```

### "No module named 'vlc'"
```bash
pip install python-vlc
# Also install VLC media player system-wide
```

### VLC Errors on Laptop
- The app will automatically use MockAudioPlayer if VLC fails
- You'll still see the UI and can test navigation
- To fix: Install VLC system-wide, then `pip install python-vlc`

### Empty Library / No Music Found
- Add MP3 files to `~/Music` directory
- Or the app will use mock songs for demonstration
- Check `config.MUSIC_DIRECTORY` setting

### Touch Not Working on Raspberry Pi
- Phase 1 uses pygame mouse events (works automatically)
- Phase 2 will add direct I2C touch support
- Make sure display drivers are installed

### Screen Size Issues
- Edit `config.py` to match your display resolution
- Default: 320×480 (portrait)
- Common alternatives: 480×320 (landscape), 480×800, 720×480

---

## 📝 Testing Checklist

- [ ] App launches without errors
- [ ] Library screen shows songs (real or mock)
- [ ] Can play a song from library
- [ ] Play/pause button works
- [ ] Skip forward/backward works
- [ ] Progress bar shows correct position
- [ ] Can drag progress bar to seek
- [ ] Volume up/down changes volume
- [ ] Can navigate between all screens
- [ ] Settings screen shows correct info
- [ ] ESC key exits the app

---

## 📄 License

This is a school project. Feel free to use and modify for educational purposes.

---

## 👤 Author

School Project - Pesto Player
Version 1.0.0 - Phase 1

---

## 🙏 Acknowledgments

- **pygame** - UI framework
- **python-vlc** - Audio playback
- **mutagen** - Metadata extraction
- Raspberry Pi Foundation
- Open source community

---

**Ready to test?** Run `python main.py` and enjoy your music! 🎵

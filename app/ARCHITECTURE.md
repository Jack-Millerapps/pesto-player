# Pesto Player - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                             │
│                    (Application Entry)                      │
│  - Initializes all subsystems                              │
│  - Main event loop                                         │
│  - Coordinates UI ↔ Player ↔ Hardware                     │
└────────┬──────────────────┬──────────────────┬─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│   UI System     │ │Player System │ │Hardware System  │
├─────────────────┤ ├──────────────┤ ├─────────────────┤
│ScreenManager    │ │ AudioPlayer  │ │ ButtonHandler   │
│ StatusBar       │ │ MusicLibrary │ │ BatteryMonitor  │
│                 │ │              │ │                 │
│ Screens:        │ │ Future:      │ │ Future:         │
│ - NowPlaying    │ │ - Mopidy     │ │ - TouchCtrl     │
│ - Library       │ │ - Spotify    │ │ - Bluetooth     │
│ - Settings      │ │ - Playlists  │ │                 │
│                 │ │              │ │                 │
│ Widgets:        │ │              │ │                 │
│ - Button        │ │              │ │                 │
│ - IconButton    │ │              │ │                 │
│ - ProgressBar   │ │              │ │                 │
│ - ScrollList    │ │              │ │                 │
└─────────────────┘ └──────────────┘ └─────────────────┘
```

## Data Flow

### Song Selection Flow
```
User clicks song in Library
    ↓
LibraryScreen._on_song_click()
    ↓
AudioPlayer.set_queue(tracks)
    ↓
AudioPlayer.play(track)
    ↓
VLC starts playback
    ↓
Callback: on_track_change(track)
    ↓
NowPlayingScreen updates display
```

### Touch Event Flow
```
User touches screen
    ↓
pygame.MOUSEBUTTONDOWN event
    ↓
main.py handles event
    ↓
ScreenManager.handle_touch(pos, 'down')
    ↓
Current screen's handle_touch()
    ↓
Widget checks if touch is within bounds
    ↓
Widget executes callback
    ↓
Action performed (play song, change screen, etc.)
```

### Volume Control Flow
```
User presses Volume Up (or Arrow key)
    ↓
ButtonHandler detects press
    ↓
Calls callback: _on_volume_up()
    ↓
AudioPlayer.volume_up()
    ↓
VLC updates volume
    ↓
Console shows: "Volume: 55%"
```

## Module Responsibilities

### config.py
- All configuration constants
- Screen dimensions, colors, GPIO pins
- TEST_MODE flag
- File paths and settings

### main.py
- Application entry point
- Initialize pygame
- Create all subsystems
- Main event loop (30 FPS)
- Event routing
- Cleanup

### UI System

#### screen_manager.py
- **Screen**: Base class for all screens
- **ScreenManager**: Handles screen navigation
- **StatusBar**: Top bar with battery/Bluetooth

#### widgets.py
- **Button**: Clickable button with text
- **IconButton**: Circular button with icon (play/pause/skip)
- **ProgressBar**: Seekable progress bar
- **ListItem**: Song list item
- **ScrollableList**: Scrollable list container
- **Label**: Text label

#### now_playing.py
- **NowPlayingScreen**: Main playback screen
- Shows album art, song info, controls
- Progress bar with seek functionality
- Navigation to Library/Settings

#### library.py
- **LibraryScreen**: Music browser
- Scrollable song list
- Tab bar (Local/Spotify)
- Plays song on click

#### settings.py
- **SettingsScreen**: Settings and info
- Shows battery, volume, song count
- Future: Audio output selection

### Player System

#### audio.py
- **AudioPlayer**: VLC-based audio player
  - Playback control (play/pause/stop)
  - Volume management
  - Queue management
  - Seeking
  - Track info

- **MockAudioPlayer**: Simulated player for testing
  - Same interface as AudioPlayer
  - Uses timestamps instead of VLC

#### library.py
- **MusicLibrary**: Music file scanner
  - Scans ~/Music directory
  - Extracts metadata with mutagen
  - Builds artist/album indexes
  - Search functionality

- **MockMusicLibrary**: Fake library for testing
  - Returns sample songs
  - Same interface as MusicLibrary

### Hardware System

#### buttons.py
- **ButtonHandler**: GPIO button interface
  - Power, Volume Up/Down
  - Long press detection
  - Callback system

- **MockButtonHandler**: Keyboard simulation
  - Arrow keys → Volume
  - ESC → Power

#### battery.py
- **BatteryMonitor**: MAX17048 I2C reader
  - Read battery percentage
  - Low battery detection

- **MockBatteryMonitor**: Fixed 85% for testing

## Design Patterns Used

### 1. **Observer Pattern** (Callbacks)
```python
audio_player.on_track_change = callback_function
```
UI updates when player state changes

### 2. **State Pattern** (Screen Management)
```python
screen_manager.show_screen('library')
```
Different screens = different states

### 3. **Strategy Pattern** (Mock vs Real)
```python
if config.TEST_MODE:
    player = MockAudioPlayer()
else:
    player = AudioPlayer()
```
Same interface, different implementations

### 4. **Composite Pattern** (UI Widgets)
```python
screen contains widgets
widgets handle their own rendering
```
Hierarchical UI composition

## Testing Strategy

### Mock Objects
- All hardware modules have mock versions
- Same interface as real versions
- Allows testing without hardware

### TEST_MODE Flag
```python
config.TEST_MODE = True   # Laptop testing
config.TEST_MODE = False  # Raspberry Pi
```

### Keyboard Simulation
- Arrow keys → Volume buttons
- ESC → Power button
- Mouse → Touch screen

## Future Architecture (Phase 2)

### Mopidy Integration
```
MopidyClient (HTTP API)
    ↓
Search Spotify
Get Playlists
Control Playback
    ↓
Unified with AudioPlayer
```

### Bluetooth Manager
```
BluetoothManager
    ↓
Scan for devices
Pair devices
Switch audio output
    ↓
Update StatusBar icon
```

### Enhanced UI
```
Album art from files
Custom fonts
Smooth transitions
Loading animations
```

## Key Design Decisions

### Why pygame?
- Cross-platform (works on laptop + Pi)
- Simple 2D graphics
- Built-in event handling
- Good performance on limited hardware

### Why VLC?
- Supports many formats (MP3, FLAC, etc.)
- Robust and stable
- Easy Python bindings
- Hardware accelerated

### Why separate mock classes?
- Test on laptop without Pi hardware
- Develop UI before hardware arrives
- Faster iteration cycle
- Same code runs on both platforms

### Why 30 FPS?
- Smooth enough for touch UI
- Low CPU usage on Pi Zero 2 W
- Good balance for battery life

### Why portrait mode?
- Natural for music player (like smartphone)
- Better for scrolling lists
- Matches typical music player UI
- Easier one-handed use

## File Organization

```
config.py           → Configuration (edit this!)
main.py            → Entry point (start here)

ui/
  screen_manager.py → Navigation system
  widgets.py        → Reusable components
  now_playing.py    → Main screen
  library.py        → Music browser
  settings.py       → Settings screen

player/
  audio.py          → Audio playback
  library.py        → Music scanning

hardware/
  buttons.py        → Physical buttons
  battery.py        → Battery monitor
```

## Performance Considerations

### Frame Rate
- Target: 30 FPS
- Main loop: ~33ms per frame
- UI updates: Every frame
- Metadata updates: Every 1 second

### Memory
- Album art cache: 20 images max
- Song list: Loaded on demand
- VLC buffers audio automatically

### CPU Usage
- pygame rendering: Low
- VLC decoding: Medium
- I2C reads: Very low
- Touch polling: Low

## Error Handling Strategy

1. **Graceful Degradation**
   - No VLC? Use mock player
   - No music? Show mock songs
   - No I2C? Use mock battery

2. **User Feedback**
   - Print to console (for debugging)
   - Show on-screen messages (future)
   - Don't crash on errors

3. **Safe Defaults**
   - TEST_MODE = True
   - Mock data always available
   - All features have fallbacks

---

This architecture is designed to be:
- ✅ **Modular**: Each component is independent
- ✅ **Testable**: Mock versions of everything
- ✅ **Extensible**: Easy to add features
- ✅ **Maintainable**: Clear separation of concerns

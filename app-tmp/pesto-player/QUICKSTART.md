# Pesto Player - Quick Start Guide 🚀

Get up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
# Install pygame (required)
pip3 install pygame

# Optional: Install VLC for real audio playback
pip3 install python-vlc

# Optional: Install mutagen for MP3 metadata
pip3 install mutagen
```

## Step 2: Test Imports (Optional)

```bash
cd pesto-player
python3 test_imports.py
```

This checks if all dependencies are installed correctly.

## Step 3: Run the App!

```bash
python3 main.py
```

That's it! The app should launch in a 320×480 window.

## Controls (Test Mode)

- **Mouse** = Touch screen (click and drag)
- **Arrow Up** = Volume up
- **Arrow Down** = Volume down
- **ESC** or **Q** = Exit app

## What You'll See

### Initial Screen: Now Playing
- Large gray square = Album art placeholder
- "No Track Playing" message
- Play/Pause/Skip buttons (inactive until you select a song)
- Library and Settings buttons at bottom

### Navigate to Library
1. Click "Library" button
2. You'll see either:
   - Your MP3 files (if ~/Music has music)
   - Mock songs (if ~/Music is empty)
3. Click any song to play it
4. Returns to Now Playing screen

### Try the Controls
- Click Play/Pause button
- Click progress bar to seek
- Use Arrow keys to change volume
- Navigate to Settings to see info

## Adding Your Music

```bash
# Create music directory if it doesn't exist
mkdir -p ~/Music

# Copy your MP3 files
cp /path/to/your/music/*.mp3 ~/Music/

# Restart the app
python3 main.py
```

The app will automatically scan ~/Music on startup!

## Troubleshooting

### "No module named 'pygame'"
→ Run: `pip3 install pygame`

### App uses mock songs even though I have music
→ Check that files are in `~/Music` (not subdirectories)
→ Or edit `config.py` to change `MUSIC_DIRECTORY`

### No sound when playing
→ Install VLC: `pip3 install python-vlc`
→ Or use mock mode (you'll see playback simulation)

### Window is too small/large
→ Edit `config.py`:
```python
SCREEN_WIDTH = 640   # Double size
SCREEN_HEIGHT = 960
```

## Next Steps

1. **Explore the UI**: Click around, try all buttons
2. **Test playback**: Play songs, seek, skip
3. **Check Settings**: View system info
4. **Read README.md**: Full documentation
5. **Customize**: Edit `config.py` for colors, layout, etc.

## Need Help?

- Check `README.md` for full documentation
- Review `config.py` for all settings
- Look at source code comments for explanations

---

**Enjoy your music! 🎵**

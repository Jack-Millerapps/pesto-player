# Pesto Player (app)

Local-music touchscreen player for a Raspberry Pi Zero 2 W (320x480 portrait). Plays mp3, flac, m4a, ogg, wav and opus from `~/Music`. Spotify/Mopidy streaming was removed.

## Features
- Tabs: Now Playing, Library, Queue, Settings; mini-player on other screens; hardware volume HUD.
- Library: Songs (kinetic list, alphabet rail), Artists, Albums, Playlists, Search with on-screen keyboard.
- Queue with reorder/remove, shuffle, repeat, error-skip for bad files.
- Add music over Wi-Fi: Library > Add music shows a QR/URL; upload from a phone browser.
- Settings: volume, shuffle/repeat, screen timeout, brightness (if the panel has a backlight node), sleep timer, rescan, storage, Wi-Fi, battery, shutdown/restart/exit.
- Power button: short = sleep/wake, hold 3 s = shutdown.
- State (volume, queue, last track) persists in `~/.pesto/`.

## Run on a laptop
```
pip install -r requirements.txt
python main.py          # mouse = touch, Up/Down = volume, ESC = power button, Q = quit
```
With no `~/Music` it shows a small demo library; with no VLC it simulates playback. Set `PESTO_MUSIC_DIR` to point at a folder.

## Run on the Pi
Use `pi/pesto_fb_launch.py` (see the top-level README). `TEST_MODE` turns itself off when `/dev/fb0` and GPIO exist; `PESTO_TEST=0` forces hardware mode.

## Layout
```
main.py            app loop and wiring
config.py          pins, paths, mode detection
player/            library, audio, playlist, prefs
hardware/          battery, buttons, system (network/disk/display power), bluetooth scaffolding
ui/                screens and widgets (theme.py holds layout constants)
tests/             pytest (headless)
```
See `ARCHITECTURE.md` for how the pieces fit and `QUICKSTART.md` for a short start guide.

## Tests
From the repo root: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest app/tests pi/uploader`.

## Troubleshooting
- No sound on the Pi: check `python3 -c "import vlc"` and the audio group; otherwise the app falls back to simulated (silent) playback and logs it at start.
- Songs missing after copying files by hand: Settings > Rescan library.
- Shutdown button says "failed": install `pi/systemd/pesto-power.sudoers.example`.
- Add music shows "No Wi-Fi": the Pi has no IP yet; the QR appears once it connects.

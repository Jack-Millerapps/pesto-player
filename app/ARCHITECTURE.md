# Pesto Player architecture

Local-music player: pygame UI at 320x480 portrait, Raspberry Pi Zero 2 W, no network services except the LAN uploader.

```
main.py (PestoPlayer: loop, power, sleep, wiring)
 |- ui/            ScreenManager shell (status bar, tab bar, mini-player, toast, sheet, overlays)
 |    screens: now_playing, queue, library hub -> songs/artists/albums/playlists/search (+ details),
 |             add_music, settings; overlays: volume_hud
 |- player/        library.py (threaded scan, cached index), audio.py (queue/shuffle/repeat on a
 |                 VLC or simulated backend), playlist.py, prefs.py
 |- hardware/      battery.py (MAX17048 / sysfs / unknown), buttons.py (GPIO), system.py (network,
 |                 disk, backlight sleep, shutdown), bluetooth.py (scaffolding only)
pi/uploader/server.py   separate process (pesto-uploader.service): Flask upload page on :8080
```

## Data flow
- `MusicLibrary.start_scan()` walks `~/Music` on a thread, reading tags only for files whose (path, mtime, size) changed (index in `~/.pesto/library_index.json`). Hidden dirs such as `.incoming` are skipped. Results are swapped in atomically.
- `AudioPlayer` owns the queue. `set_queue(tracks, i)` loads the queue and starts track i. Unplayable files call `on_error` (toast) and are skipped; if every track fails it stops. `update()` polls the backend at most 5 Hz; `get_state()` returns cached values. Volume, queue, shuffle, repeat and last track persist in `~/.pesto/state.json` (debounced, atomic) and are restored after the first scan.
- Tracks are dicts with a stable `id` (sha1 of the path), `path`, `title`, `artist`, `album`, `duration`, `track_no`.
- Uploads: phone -> uploader -> `~/Music/.incoming/*.part` -> rename into `~/Music` -> touch `~/.pesto/library.dirty`. The Add music screen polls that file at 1 Hz and rescans once per batch.

## Why it is shaped this way
- Backends are objects (`VlcBackend`, `SimulatedBackend`) so queue logic is tested without VLC; `import vlc` is guarded so the app starts anywhere.
- The uploader is a separate service so a large upload cannot starve the UI and can be memory-capped (`MemoryMax=64M`). Its token is regenerated at each start, written 0600 to `~/.pesto/uploader.json`, and shown in the QR.
- Power button: short = sleep/wake (backlight via sysfs when present, otherwise the app blanks and stops drawing), long = real shutdown. The systemd unit uses `Restart=on-failure`, so exit/shutdown (status 0) is not restarted; Settings > Restart exits with status 3 (`RestartForceExitStatus=3`).
- `TEST_MODE` is auto-detected (needs `/dev/fb0` and `/dev/gpiomem` to count as hardware); `PESTO_TEST=0/1` overrides. A demo library is used only in TEST_MODE when `~/Music` does not exist.

## Rendering and performance
Screens draw into the shared surface clipped to the content rect; the ScreenManager redraws dirty regions and returns rects, which `main.py` passes to `pygame.display.update(rects)` and the launcher (`pi/pesto_fb_launch.py`) pushes as partial rows to `/dev/fb0`. Frame rate drops to 10 fps when idle. Fonts and rendered text are cached (`ui/text_cache.py`); the font is bundled (`assets/fonts`). VLC is polled at 5 Hz.

## Tests
`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest app/tests pi/uploader` from the repo root. `tests/test_smoke.py` boots `main.py` with the mock library/player and draws every screen. Do not call `pygame.quit()` between tests (cached fonts dangle).

## Not verified without hardware
Touch, framebuffer push speed, real VLC audio, backlight sleep, GPIO buttons, shutdown permissions, uploader memory use and phone uploads.

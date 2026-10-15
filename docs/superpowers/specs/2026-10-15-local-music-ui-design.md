# Pesto Player: local-music pygame UI redesign

Date: 2026-10-15. Status: design approved by Jack in chat; spec awaiting review.

## Goal
Drop Spotify/Mopidy. Make the pygame UI (`app/`, 320x480 portrait, ST7796 via /dev/fb0, FT6336 touch, Pi Zero 2 W) a usable local-music player, with an easy way to add downloaded songs. `web-ui/` is untouched.

## Done means
- Every screen fits 320x480; all controls reachable; touch targets >= 44 px.
- Scrolling a list never plays a song; flick scrolling works.
- App runs on the Pi without editing source (TEST_MODE auto-detected), scan is non-blocking.
- Songs can be added from a phone over Wi-Fi via a QR/URL on an "Add music" screen.
- No Spotify/Mopidy remnants. Bluetooth scaffolding is kept as a Settings row.
- Unverified until run on hardware; acceptance on the Pi is a separate manual step.

## Screens
Persistent bottom tab bar (56 px): Now Playing, Library, Queue, Settings. 24 px status bar. 48 px mini-player above the tab bar on non-Now-Playing screens. Transient volume HUD for hardware buttons. Toast for errors.
- Now Playing: ~200 px art (async, LRU, cover.jpg fallback, letter-tile placeholder), marquee title, seek bar with 44 px hit zone (seek on release, time bubble), shuffle/prev/play/next/repeat.
- Library hub: Songs, Artists, Albums, Playlists, Search, Add music.
- Songs: virtualised kinetic list, 56 px rows, thumbnail, current-track marker, alphabet rail, long-press sheet (play next / add to queue / add to playlist).
- Artists, Albums (2-col grid), detail pages with Play/Shuffle.
- Playlists (JSON/m3u in ~/.pesto/playlists) and Queue (reorder, remove, save as playlist).
- Search: on-screen keyboard, chips All/Songs/Artists/Albums.
- Settings: volume slider, output, shuffle/repeat defaults, screen timeout/brightness, sleep timer, rescan, storage, IP, real battery, version, shutdown/restart/exit with confirm. No TEST MODE banner in production.
- Add music: destination, free space, track count, SSID/IP, QR + URL (~140 px), rescan with progress, status line for uploads.

## Add-music ingest
Primary: `pesto-uploader.service` (separate systemd unit, user pesto, MemoryMax=64M), Flask page on :8080. Per-session token in the URL/QR. Allowed extensions = SUPPORTED_FORMATS (case-insensitive, add .opus). secure_filename; write to ~/Music/.incoming/*.part then rename; check free space; clean stale .part at start; delete list on the page. After a batch it touches ~/.pesto/library.dirty; the Add music screen polls its mtime (~1 Hz) and rescans in a background thread once per batch.
Secondary (optional, later): USB-stick auto-import via udev + systemd, rsync --ignore-existing into ~/Music/Imported.
Out of scope: yt-dlp / URL ripping (cannot rip Spotify; YouTube ripping breaches ToS and usually copyright; heavy on the Pi). May return later as a clearly opt-in feature for content the user has rights to.

## Backend/perf requirements
- Scan on a background thread, persisted index keyed by (path, mtime, size), case-insensitive extensions, sorted data, lower-cased search index.
- Player: shuffle, repeat, error state (handle State.Error), consistent auto-advance, guarded `import vlc` with mock fallback, stable track ids, persisted volume/queue/last track.
- Power button: short = sleep/wake with backlight, long = shutdown (not exit-and-restart under Restart=always).
- Render: text/font cache, bundled TTF, no per-frame font/surface creation, VLC polled at 4-5 Hz, dirty-region redraw, partial-row framebuffer push in the launcher, idle cap ~10 fps, touch-motion coalescing, button cancel on drag-out.

## Remove
`player/mopidy_client.py`; MOPIDY block in `config.py`; Spotify tab/code in `ui/library.py`; Mopidy mentions in `audio.py`, `requirements.txt`, `ARCHITECTURE.md`, `README.md`; unused `hardware/touch.py` and dead config constants.

## Work split (file ownership, no overlap)
- A (UI framework + perf): `ui/widgets.py`, `ui/screen_manager.py`, new `ui/theme.py`, `ui/text_cache.py`, `ui/keyboard.py`, `pi/pesto_fb_launch.py`.
- B (playback UI): `ui/now_playing.py`, new `ui/queue.py`, `ui/mini_player.py`, `ui/volume_hud.py`.
- C (browsing): `ui/library.py` (hub), new `ui/songs.py`, `artists.py`, `albums.py`, `playlists.py`, `search.py`.
- D (backend/settings/ingest/glue): `player/*`, `hardware/*`, `ui/settings.py`, new `ui/add_music.py`, new `pi/uploader/*`, `pi/systemd/*`, `main.py`, `config.py`, docs, `requirements.txt`, `test_imports.py`.
Frozen interfaces (D and A publish first): AudioPlayer `get_state()/shuffle/repeat/get_queue()/on_error`, tracks as dicts with stable `id`; library `get_artists()/get_albums()/tracks_for_*()/search()/on_scan_progress`; `ScreenManager.register(name, screen, tab=...)`. D integrates `main.py` last.
Models: Sonnet builds; Opus does final adversarial review. Layout constants live in A's `ui/theme.py` or each file, never `config.py` except D.

## Risks / not verified
No hardware run yet; RAM figures for the uploader are estimates; SPI ceiling ~13 fps means animation must stay minimal.

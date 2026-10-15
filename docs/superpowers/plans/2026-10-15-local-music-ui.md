# Pesto Player local-music UI Implementation Plan

> **For agentic workers:** use superpowers:subagent-driven-development. Steps use checkbox syntax. Builders write the code test-first (TDD); this plan fixes interfaces, files, tests and order, not the code itself.

**Goal:** Rebuild the pygame UI as a usable local-music player with Wi-Fi song upload.
**Architecture:** Persistent tab-bar shell (A) hosting screens (B, C), over a threaded library/player backend and an out-of-process uploader (D). Contracts below are frozen before parallel work.
**Tech Stack:** Python 3, pygame, python-vlc, mutagen, Flask, qrcode, pytest. Pi Zero 2 W, 320x480, /dev/fb0.
**Spec:** `docs/superpowers/specs/2026-10-15-local-music-ui-design.md`

## Global Constraints
- Screen 320x480 portrait; touch targets >= 44 px; status bar 24 px, tab bar 56 px, mini-player 48 px.
- All code under `app/` (run from `app/`), uploader under `pi/uploader/`. `web-ui/` is not touched.
- Formats: .mp3 .flac .m4a .ogg .wav .opus, matched case-insensitively.
- No per-frame font/surface creation; VLC polled <= 5 Hz; idle cap ~10 fps.
- No network services except the uploader (LAN, tokened). No paid tools. No credentials in files.
- Tests run headless: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest app/tests`. Mock player/library are used when VLC or a display is missing.
- Each builder commits only files it owns. `config.py` is owned by D only.

## Review Focus
- Empty library / empty queue: every screen shows an empty state, no crash.
- Track with missing tags, non-ASCII or 200-char title: shows filename fallback, ellipsis/marquee, no overflow.
- Scroll gesture ending on a row never triggers play; tap does.
- Corrupt/unplayable file or vanished file mid-play: toast, skip to next, no stall.
- Upload of wrong extension, duplicate name, oversize/low disk, interrupted transfer: rejected or cleaned with a clear message; half-written files never scanned.
- Power on without VLC/display/GPIO/Wi-Fi: app still starts.

## Frozen interfaces (Task 0, D+A publish stubs first; everyone codes to these)
```python
# player/library.py (D)
Track = dict  # keys: id:str(stable hash of path), path, title, artist, album, duration:float|None, track_no:int|None
class MusicLibrary:
    def start_scan(self, on_progress=None, on_done=None) -> None   # background thread
    def is_scanning(self) -> bool
    def get_tracks(self) -> list[Track]            # sorted by title (casefold)
    def get_artists(self) -> list[dict]            # {name, album_count, track_count}
    def get_albums(self, artist: str|None=None) -> list[dict]  # {title, artist, track_count, art_path|None}
    def tracks_for_artist(self, name) -> list[Track]
    def tracks_for_album(self, title, artist) -> list[Track]
    def search(self, query: str, kind: str="all") -> dict   # {songs, artists, albums}
    def get_art(self, track: Track, size: int) -> "pygame.Surface|None"  # sidecar cover or embedded; cached
# player/audio.py (D)
class AudioPlayer:
    shuffle: bool; repeat: str  # "off"|"all"|"one"
    on_error: callable|None     # fn(message:str)
    def get_state(self) -> dict  # {track, playing, position, duration, volume, shuffle, repeat, queue_index}
    def get_queue(self) -> list[Track]
    def set_queue(self, tracks, start_index=0); def enqueue(self, track); def play_next(self, track)
    def remove_from_queue(self, index); def move_in_queue(self, src, dst)
    def play(); pause(); toggle(); next(); prev(); seek(fraction:float); set_volume(0..100)
# player/playlist.py (D)
class PlaylistStore: list_names(); load(name)->list[Track]; save(name, tracks); delete(name); add(name, track)
# ui/screen_manager.py (A)
ScreenManager.register(name:str, screen:Screen, tab:str|None=None)
ScreenManager.show(name); push(name, **kw); pop()   # push/pop only inside Library tab
ScreenManager.toast(msg:str, kind:str="info"); ScreenManager.show_sheet(actions:list[tuple[str,callable]])
Screen: on_enter(**kw); on_leave(); handle_touch(pos, kind)  # kind in down|move|up|cancel
        update(dt); draw(surface); dirty: bool  # set True to request redraw
# ui/widgets.py (A)
ScrollList(rect, row_h, draw_row(surface, rect, item, index, state), on_tap(item,index), on_long_press(item,index), items=[])
Slider, TabBar, Marquee, Button(cancel on drag-out); ui/text_cache.py: get_font(size,bold=False), render(text,size,color)->Surface (LRU), ellipsize(text,size,max_w)
ui/keyboard.py: Keyboard(rect, on_key, on_enter, on_close)
ui/theme.py: colors, sizes, TAB_H=56, STATUS_H=24, MINI_H=48, ROW_H=56
```

## Task 0: Contracts and shared scaffolding (Builder D, then A, before B/C start)
**Files:** D: `app/player/library.py`, `audio.py`, `playlist.py` stubs matching signatures; `app/tests/conftest.py` with mock Track fixtures. A: `app/ui/theme.py`, `text_cache.py`, stub signatures in `widgets.py`/`screen_manager.py`.
- [ ] D writes stubs returning empty data; A writes theme + signatures. Both commit. Lead then releases B and C.

## Task A: UI framework and performance (Builder A, Sonnet)
**Files:** `app/ui/widgets.py`, `screen_manager.py`, `theme.py`, `text_cache.py`, `keyboard.py`, `pi/pesto_fb_launch.py`; tests `app/tests/test_widgets.py`, `test_screen_manager.py`.
- [ ] Tests first: ScrollList only draws visible rows (count draw_row calls); tap vs drag uses total travel > 10 px or > 300 ms => no `on_tap`; flick velocity decays and stops on new down; long-press fires at 500 ms; Button resets on drag-out/cancel; text_cache returns same Surface for same key; ellipsize respects pixel width.
- [ ] Implement widgets, TabBar, Slider, Marquee, Keyboard, toast, action sheet, tab-aware nav (no unbounded stack), remove per-Screen full surface, dirty-flag redraw, idle fps cap, bundled TTF (DejaVuSans, in `app/assets/fonts/`, license file alongside).
- [ ] Launcher: push only changed row range to /dev/fb0; coalesce MOUSEMOTION. Keep a full-push fallback flag.
- [ ] Commit per feature.

## Task B: Playback UI (Builder B, Sonnet)
**Files:** `app/ui/now_playing.py`, `queue.py`, `mini_player.py`, `volume_hud.py`; tests `app/tests/test_now_playing.py`.
- [ ] Tests first: layout test asserts every control rect lies within 0..480 and does not overlap tab bar; seek commits on release only; time label re-renders only when the second changes; empty state renders; long title uses Marquee.
- [ ] Implement Now Playing (art async + LRU via `library.get_art`, letter-tile fallback, shuffle/repeat), Queue (reorder, remove, clear, save as playlist), mini-player, volume HUD (1.2 s). Poll `get_state()` at <= 5 Hz.
- [ ] Commit per screen.

## Task C: Library browsing (Builder C, Sonnet)
**Files:** `app/ui/library.py` (hub), `songs.py`, `artists.py`, `albums.py`, `playlists.py`, `search.py`; tests `app/tests/test_browse.py`.
- [ ] Remove all Spotify code in `ui/library.py` (tabs, buttons, `_draw_spotify_tab`, docstrings).
- [ ] Tests first with mock library: Songs tap sets queue to list+index and plays; scroll-then-release does not play; alphabet rail jumps; Artists/Albums detail shows Play/Shuffle; Search filters via `library.search`; long-press sheet offers Play next / Add to queue / Add to playlist; empty states show Add music button.
- [ ] Implement screens; no O(n) `index()` per tap (use the item index passed by ScrollList).
- [ ] Commit per screen.

## Task D: Backend, Settings, Add music, uploader, glue (Builder D, Sonnet; review gate Opus)
**Files:** `app/player/*`, `app/hardware/*`, `app/ui/settings.py`, `app/ui/add_music.py`, `app/main.py`, `app/config.py`, `app/requirements.txt`, docs (`ARCHITECTURE.md`, `README.md`, `test_imports.py`), `pi/uploader/server.py`, `pi/systemd/pesto-uploader.service`; delete `player/mopidy_client.py`, `hardware/touch.py`; tests `app/tests/test_library.py`, `test_audio.py`, `pi/uploader/test_server.py`.
- [ ] Tests first: scan is non-blocking and emits progress; index cache keyed (path,mtime,size) skips unchanged files; `.MP3` found; missing tags fall back to filename; `search` is case-insensitive; shuffle/repeat/auto-advance/error-skip logic with a fake backend; `import vlc` failure falls back to mock; TEST_MODE auto-detect (env var `PESTO_TEST`, else detect display/GPIO).
- [ ] Uploader tests (Flask test client): rejects bad extension, bad/missing token, path traversal names; writes via `.incoming/*.part` then rename; refuses when free space low; touches `~/.pesto/library.dirty`; stale `.part` cleaned at start.
- [ ] Implement backend, persisted state (volume, queue, last track in `~/.pesto/state.json`), power button (short sleep/wake with backlight, long shutdown), real battery, Settings with real controls, Add music screen (QR via `qrcode`, SSID/IP, polls dirty mtime ~1 Hz, background rescan with progress), uploader + systemd unit (`MemoryMax=64M`, user pesto).
- [ ] Remove Mopidy/Spotify remnants per spec (config block, audio.py comment, requirements, docs) and dead constants.
- [ ] Final: wire `main.py` registering all screens and tabs (after A/B/C land). Smoke test: app boots headless with mock library, each screen draws one frame without exception.
- [ ] Commit per feature.

## Task E: Review and integration (Opus reviewer, read-only, then fixes routed back to owners)
- [ ] Run full test suite headless; render each screen to PNG headlessly and inspect for overflow at 320x480.
- [ ] Review against Review Focus and the spec; report findings as severity + file:line. Not verified until run on the Pi (manual: deploy, touch, audio, upload from phone).

## Order
Task 0 -> A and D in parallel -> B and C in parallel (after A's widgets and D's stubs) -> D final wiring -> E. Execution: subagent-driven; lead verifies each report before releasing the next stage. Plan approval required from builders D (backend/power-button/uploader are risky): they stay read-only until Jarvis approves their approach, approving only plans that include the tests listed above.

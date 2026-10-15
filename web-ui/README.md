# Pesto Player — web UI

The mobile-style web interface for the Pesto Player device. It talks to the Flask
server in the parent folder (`../web_server.py`) over REST + socket.io and works in
two modes:

- **Connected** — live library, playback control (play/seek/skip/shuffle/repeat/volume),
  queue management, live progress, and device battery in the header.
- **This device** — when no player is reachable, six bundled Kevin MacLeod recordings
  play through a native browser audio element. No music account or hardware is required.

Originally scaffolded from the [Figma design](https://www.figma.com/design/psO5xGt81y3T0wude7wEzi/Pesto-Player-app).

## Development

```bash
npm i
npm run dev
```

The dev server runs at http://localhost:5173 and expects the player backend at
http://localhost:5000 through Vite’s development proxy. Without a backend it falls back to
the included music automatically.

## Deploying to the player

```bash
npm run build
```

This builds into `../web_build`, which `web_server.py` serves as its static folder.

## Layout

- `src/app/player/PlayerProvider.tsx` — player state: socket status feed, smooth
  device progress, online/offline detection, browser audio routing, and likes.
- `src/app/player/BrowserAudio.ts` — native audio playback, media events, and error handling.
- `src/app/services/api.ts` — typed client for the Flask API + socket.io.
- `src/app/hooks/useLibrary.ts` — device library data with bundled music when disconnected.
- `src/app/components/` — pages (Home/Search/Library), players (Mini/Full),
  collection sheet, shared track rows.
- `src/styles/theme.css` — the Pesto identity tokens (basil/pesto/cream/pine palette,
  Bricolage Grotesque + Outfit type).

## Complete app flows

- **Home:** featured mixes, album shelf, recently played songs, personal mixes,
  and access to the full song library.
- **Search:** songs, albums, artists, and playlists; result filters; saved recent
  searches; browse tiles that open real collections from the current library.
- **Library:** create personal playlists, select songs, rename/edit/delete mixes,
  sort collections, browse artists, and play liked songs.
- **Song menus:** like/unlike, add to queue, and save to an existing or new
  personal playlist. A song cannot be added twice to the same personal playlist.
- **Player:** playback, seek, volume, repeat, shuffle, queue inspection, and clearing
  upcoming songs. Duplicate song occurrences remain visible in the queue.
- **Connection details:** actual connection/battery status, current audio output, setup guidance, and a retry action.
- **Accessibility:** native modal focus containment and Escape handling,
  keyboard-operable controls, live action feedback, reduced motion, and
  mobile controls of at least 44px in the player.

Personal playlists, likes, recent songs, and recent searches live in browser
storage. They are not synced to a cloud account or written to device playlists.
Included recordings: Carefree, Monkeys Spinning Monkeys, Cipher, Wallpaper,
Sneaky Snitch, and Local Forecast - Elevator. All are by Kevin MacLeod
(incompetech.com), licensed CC BY 4.0. Original MP3 files and credits are in
`public/music/`; credits are also linked from Home and each song menu. The files
are served with the app and loaded on demand, not streamed from a third party.
Existing placeholder tracks in saved playlists and likes are migrated to the
playable catalog. Device-library songs still use the configured device output.

## API routing

Requests use the page's origin by default. During development, Vite proxies
`/api` and `/socket.io` to `http://localhost:5000`. Production uses the Flask
server serving `web_build`. `VITE_API_URL` can override the backend origin.
For a phone, open the player's network address rather than `localhost`.

A connected player with an empty library stays empty and provides a refresh
action. A failed library request offers a retry rather than displaying included
songs as if they belonged to the device.

## Validation

```bash
npm test
npm run build
# From the repository root:
python3 -m unittest test_web_play_context.py
```

The audio tests cover media-driven playback, seeking, volume, buffering, end
events, failed playback, stale promises, and cleanup. The queue tests cover ordering, repeated songs, shuffle visibility, and empty/end
states. The backend contract tests validate playlist playback context and ensure
bad requests or audio failures do not replace the existing queue. They isolate
the route logic without requiring Flask or audio hardware; they are not a live
hardware integration test.

Browser checks include playlist creation and persistence after reload, editing
and deleting a temporary playlist, song menus, search, queue clearing, native
nested dialogs, and 320×480 playback controls.

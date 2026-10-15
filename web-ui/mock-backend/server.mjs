// Throwaway mock of the Pesto Player Flask backend, written ONLY from what
// src/app/services/api.ts calls (REST + socket.io 'status' event). It is a test
// aid, not a statement of what the real web_server.py does.
//
//   node server.mjs            -> http://localhost:5050   (PORT env overrides;
//                                 macOS reserves :5000 for AirPlay Receiver)
//
// Test knobs (mock-only, under /__mock):
//   POST /__mock/config {"tracks":1500,"latencyMs":800,"failRate":0.3,"longNames":true,"empty":true}
//   POST /__mock/down      all REST -> 503 and sockets are dropped/refused
//   POST /__mock/up        recover
//   POST /__mock/kick      drop transports once (client sees 'transport close', auto-reconnects)
//   POST /__mock/server-disconnect   server-initiated disconnect ('io server disconnect')
//   POST /__mock/flap {"ms":2000}  drop sockets every ms until /__mock/flap {"ms":0}
//   GET  /__mock/stats     request counters + connected socket count
import http from 'node:http';
import { Server } from 'socket.io';

const dropTransport = () => { for (const [, sk] of io.sockets.sockets) sk.conn.close(); }; // client sees 'transport close' -> auto-reconnects (like a crashed/restarted server)
const PORT = Number(process.env.PORT || 5050);
const cfg = { tracks: 24, latencyMs: 0, failRate: 0, longNames: false, empty: false, down: false };
const stats = { requests: 0, byPath: {}, failed: 0 };

let tracks = [], albums = [], artists = [], playlists = [];
function build() {
  const covers = ['carefree', 'cipher', 'kitchen', 'local-forecast', 'monkeys-spinning-monkeys', 'pressed', 'signal', 'sneaky-snitch', 'static', 'wallpaper', 'windowsill'];
  const n = cfg.empty ? 0 : cfg.tracks;
  const long = 'An Extraordinarily Long Track Title That Just Keeps Going And Going Past Every Reasonable Boundary ';
  tracks = Array.from({ length: n }, (_, i) => {
    const a = i % Math.max(1, Math.ceil(n / 12));
    return {
      id: `t${i}`,
      title: cfg.longNames ? `${long}${i}` : `Track ${i + 1}`,
      artist: cfg.longNames ? `Artist With A Silly Long Name Number ${a} feat. Lots Of Other People` : `Artist ${a}`,
      album: `Album ${a}`,
      duration: 60 + (i * 37) % 240,
      coverUrl: `/artwork/${covers[i % covers.length]}.svg`,
      filepath: `/music/t${i}.mp3`,
    };
  });
  const names = [...new Set(tracks.map(t => t.artist))];
  artists = names.map((name, i) => ({ id: `ar${i}`, name, albumCount: 1 }));
  albums = names.map((name, i) => {
    const ts = tracks.filter(t => t.artist === name);
    return { id: `al${i}`, title: ts[0].album, artist: name, coverUrl: ts[0].coverUrl, trackCount: ts.length, tracks: ts };
  });
  playlists = n ? [0, 1, 2].map(i => {
    const ts = tracks.filter((_, k) => k % (i + 2) === 0).slice(0, 40);
    return { id: `pl${i}`, name: cfg.longNames ? `Playlist number ${i} with a ridiculously long name that wraps` : `Playlist ${i + 1}`, trackCount: ts.length, tracks: ts };
  }) : [];
}
build();

const player = { playing: false, position: 0, volume: 70, shuffle: false, repeat: 'off', queue: [], index: 0 };
const cur = () => player.queue[player.index] ?? null;
const status = () => ({
  isPlaying: player.playing, volume: player.volume, position: player.position,
  duration: cur()?.duration ?? 0, shuffle: player.shuffle, repeat: player.repeat,
  currentTrack: cur(), battery: { percentage: 64, status: 'Discharging' },
});

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const path = url.pathname;
  const send = (code, body) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };
  let raw = ''; for await (const c of req) raw += c;
  const body = raw ? JSON.parse(raw) : {};

  if (path.startsWith('/__mock/')) {
    if (path === '/__mock/config') { Object.assign(cfg, body); build(); return send(200, cfg); }
    if (path === '/__mock/down') { cfg.down = true; dropTransport(); return send(200, { down: true }); }
    if (path === '/__mock/up') { cfg.down = false; return send(200, { down: false }); }
    if (path === '/__mock/kick') { dropTransport(); return send(200, {}); }
    if (path === '/__mock/server-disconnect') { io.disconnectSockets(true); return send(200, {}); } // client sees 'io server disconnect' (socket.io does NOT auto-reconnect here)
    if (path === '/__mock/flap') { clearInterval(flap); if (body.ms) flap = setInterval(dropTransport, body.ms); return send(200, { ms: body.ms || 0 }); }
    if (path === '/__mock/stats') return send(200, { ...stats, sockets: io.engine.clientsCount, cfg });
    return send(404, {});
  }
  if (!path.startsWith('/api/')) return send(404, { error: 'not found' });

  stats.requests++; stats.byPath[path] = (stats.byPath[path] || 0) + 1;
  if (cfg.latencyMs) await new Promise(r => setTimeout(r, cfg.latencyMs));
  if (cfg.down) { stats.failed++; return send(503, { error: 'down' }); }
  if (cfg.failRate && Math.random() < cfg.failRate) { stats.failed++; return send(500, { error: 'injected failure' }); }

  const m = req.method;
  const ok = (extra = {}) => { push(); return send(200, { success: true, ...extra }); };
  if (path === '/api/player/status') return send(200, status());
  if (path === '/api/player/play' && m === 'POST') {
    const { trackId, trackIds } = body;
    const ids = trackIds?.length ? trackIds : trackId ? [trackId] : [];
    const list = ids.map(id => tracks.find(t => t.id === id)).filter(Boolean);
    if (trackId && !list.length) return send(404, { success: false, error: 'Unknown track' });
    if (list.length) { player.queue = list; player.index = Math.max(0, list.findIndex(t => t.id === trackId)); player.position = 0; }
    player.playing = !!cur();
    return ok();
  }
  if (path === '/api/player/pause') { player.playing = false; return ok(); }
  if (path === '/api/player/toggle') { if (cur()) player.playing = !player.playing; return ok({ isPlaying: player.playing }); }
  if (path === '/api/player/next') { advance(1); return ok(); }
  if (path === '/api/player/previous') { advance(-1); return ok(); }
  if (path === '/api/player/seek') { player.position = Math.max(0, Math.min(Number(body.position) || 0, cur()?.duration ?? 0)); return ok(); }
  if (path === '/api/player/volume') {
    if (m === 'POST') player.volume = Math.max(0, Math.min(100, Number(body.volume))); return ok({ volume: player.volume });
  }
  if (path === '/api/player/shuffle') { player.shuffle = !player.shuffle; return ok({ shuffle: player.shuffle }); }
  if (path === '/api/player/repeat') { player.repeat = { off: 'all', all: 'one', one: 'off' }[player.repeat]; return ok({ repeat: player.repeat }); }

  if (path === '/api/library/tracks') {
    const limit = Number(url.searchParams.get('limit')) || tracks.length; const offset = Number(url.searchParams.get('offset')) || 0;
    return send(200, { tracks: tracks.slice(offset, offset + limit), total: tracks.length, offset });
  }
  if (path === '/api/library/albums') return send(200, { albums: albums.map(({ tracks: _t, ...a }) => a) });
  if (path === '/api/library/artists') return send(200, { artists });
  if (path.startsWith('/api/library/album/')) {
    const album = albums.find(a => a.id === path.split('/').pop());
    return album ? send(200, { album }) : send(404, { error: 'not found' });
  }
  if (path === '/api/library/search') {
    const q = (url.searchParams.get('q') || '').toLowerCase();
    return send(200, {
      tracks: tracks.filter(t => `${t.title} ${t.artist} ${t.album}`.toLowerCase().includes(q)).slice(0, 100),
      albums: albums.filter(a => a.title.toLowerCase().includes(q)).map(({ tracks: _t, ...a }) => a),
      artists: artists.filter(a => a.name.toLowerCase().includes(q)),
    });
  }
  if (path === '/api/queue' && m === 'GET') return send(200, { queue: player.queue, currentIndex: player.index });
  if (path === '/api/queue/add') { const t = tracks.find(t => t.id === body.trackId); if (!t) return send(404, { success: false, error: 'Unknown track' }); player.queue.push(t); return ok(); }
  if (path === '/api/queue/clear') { player.queue = cur() ? [cur()] : []; player.index = 0; return ok(); }
  if (path === '/api/playlists') return send(200, { playlists: playlists.map(({ tracks: _t, ...p }) => p) });
  if (path.startsWith('/api/playlists/')) {
    const p = playlists.find(p => p.id === path.split('/').pop());
    return p ? send(200, p) : send(404, { error: 'not found' });
  }
  return send(404, { error: 'not implemented in mock' });
});

function advance(dir) {
  if (!player.queue.length) return;
  let i = player.index + dir;
  if (player.shuffle && dir > 0) i = Math.floor(Math.random() * player.queue.length);
  if (i >= player.queue.length) { if (player.repeat === 'all') i = 0; else { player.playing = false; player.position = 0; return; } }
  if (i < 0) i = 0;
  player.index = i; player.position = 0;
}

const io = new Server(server, { cors: { origin: '*' }, allowRequest: (_req, cb) => cb(null, !cfg.down) }); // engine-level refusal: client auto-retries (a middleware error would NOT be retried by socket.io)
const push = () => io.emit('status', status());
io.on('connection', socket => socket.emit('status', status()));
let flap = null;
setInterval(() => {
  if (player.playing && cur()) {
    player.position += 1;
    if (player.position >= cur().duration) {
      if (player.repeat === 'one') player.position = 0; else advance(1);
    }
  }
  if (!cfg.down) push();
}, 1000);

server.listen(PORT, () => console.log(`pesto mock backend on http://localhost:${PORT}`));

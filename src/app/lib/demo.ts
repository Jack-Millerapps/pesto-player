/** Bundled, unmodified CC BY 4.0 recordings. Attribution: /music/credits.html. */
import type { Album, Artist, Playlist, Track } from '../services/api';

export const demoTracks: Track[] = [
  { id: 'km-carefree', title: 'Carefree', artist: 'Kevin MacLeod', album: 'Carefree', duration: 205, coverUrl: '/artwork/carefree.svg', filepath: '', audioUrl: '/music/carefree.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400037', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
  { id: 'km-monkeys-spinning-monkeys', title: 'Monkeys Spinning Monkeys', artist: 'Kevin MacLeod', album: 'Monkeys Spinning Monkeys', duration: 125, coverUrl: '/artwork/monkeys-spinning-monkeys.svg', filepath: '', audioUrl: '/music/monkeys-spinning-monkeys.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400011', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
  { id: 'km-cipher', title: 'Cipher', artist: 'Kevin MacLeod', album: 'Cipher', duration: 231, coverUrl: '/artwork/cipher.svg', filepath: '', audioUrl: '/music/cipher.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100844', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
  { id: 'km-wallpaper', title: 'Wallpaper', artist: 'Kevin MacLeod', album: 'Wallpaper', duration: 220, coverUrl: '/artwork/wallpaper.svg', filepath: '', audioUrl: '/music/wallpaper.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100843', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
  { id: 'km-sneaky-snitch', title: 'Sneaky Snitch', artist: 'Kevin MacLeod', album: 'Sneaky Snitch', duration: 137, coverUrl: '/artwork/sneaky-snitch.svg', filepath: '', audioUrl: '/music/sneaky-snitch.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100772', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
  { id: 'km-local-forecast', title: 'Local Forecast - Elevator', artist: 'Kevin MacLeod', album: 'Local Forecast - Elevator', duration: 189, coverUrl: '/artwork/local-forecast.svg', filepath: '', audioUrl: '/music/local-forecast.mp3', creditUrl: 'https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300012', licenseUrl: 'https://creativecommons.org/licenses/by/4.0/' },
];
export const demoAlbums: Album[] = demoTracks.map(track => ({ id: `album-${track.id}`, title: track.album, artist: track.artist, coverUrl: track.coverUrl, trackCount: 1, tracks: [track] }));
export const demoArtists: Artist[] = [{ id: 'kevin-macleod', name: 'Kevin MacLeod', albumCount: demoAlbums.length }];
const mix = (id: string, name: string, indices: number[]): Playlist => ({ id, name, trackCount: indices.length, tracks: indices.map(index => demoTracks[index]) });
export const demoPlaylists: Playlist[] = [
  mix('dp1', 'Fresh Batch', [0, 1, 2, 3, 4, 5]),
  mix('dp2', 'Slow Stir', [5, 3, 0]),
  mix('dp3', 'Full Blend', [2, 3, 4, 1]),
  mix('dp4', 'Morning Grind', [0, 5, 1, 3]),
];
export const demoPlaylistCovers: Record<string, string> = Object.fromEntries(demoPlaylists.map(playlist => [playlist.id, playlist.tracks![0].coverUrl!]));

// Preserve personal playlists and likes from the original silent starter catalog.
const legacy: Record<string, number> = { d1: 0, d2: 3, d3: 5, d4: 2, d5: 2, d6: 2, d7: 3, d8: 3, d9: 3, d10: 0, d11: 5, d12: 1, d13: 4, d14: 1 };
export function upgradeStarterTrack(track: Track): Track {
  return demoTracks.find(item => item.id === track.id) || (Object.hasOwn(legacy, track.id) ? demoTracks[legacy[track.id]] : track);
}

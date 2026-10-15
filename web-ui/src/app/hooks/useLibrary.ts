import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Album, Artist, Playlist, Track, api } from '../services/api';
import { demoAlbums, demoArtists, demoPlaylists, demoTracks } from '../lib/demo';
import { Connection } from '../player/PlayerProvider';

interface LibraryContent { tracks: Track[]; albums: Album[]; artists: Artist[]; playlists: Playlist[] }
export interface LibraryData extends LibraryContent { loading: boolean; isDemo: boolean; error: string | null; refresh: () => void }
const demoData: LibraryContent = { tracks: demoTracks, albums: demoAlbums, artists: demoArtists, playlists: demoPlaylists };
const emptyData: LibraryContent = { tracks: [], albums: [], artists: [], playlists: [] };
/** How long a dropped socket may stay down before the library falls back to the bundled songs. */
export const OFFLINE_GRACE_MS = 4000;

/** Reports 'online' until the connection has been down for `graceMs`, so a flapping socket doesn't thrash the library. */
export function useSettledConnection(connection: Connection, graceMs = OFFLINE_GRACE_MS): Connection {
  const [settled, setSettled] = useState(connection);
  useEffect(() => {
    if (connection === 'offline' && settled === 'online') {
      const timer = window.setTimeout(() => setSettled('offline'), graceMs);
      return () => window.clearTimeout(timer);
    }
    setSettled(connection);
  }, [connection, settled, graceMs]);
  return settled;
}

export function useLibrary(rawConnection: Connection): LibraryData {
  const connection = useSettledConnection(rawConnection);
  const [data, setData] = useState<LibraryContent>(demoData);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const haveDeviceData = useRef(false);
  const refresh = useCallback(() => setRevision(n => n + 1), []);
  useEffect(() => {
    if (connection === 'connecting') return;
    if (connection === 'offline') { haveDeviceData.current = false; setData(demoData); setIsDemo(true); setLoading(false); setError(null); return; }
    let cancelled = false;
    setError(null); setIsDemo(false);
    // First load shows the loading state; a reload after a reconnect keeps the last device library on screen.
    if (!haveDeviceData.current) { setLoading(true); setData(emptyData); }
    Promise.all([api.getTracks(), api.getAlbums(), api.getArtists(), api.getPlaylists()]).then(([tracks, albums, artists, playlists]) => {
      if (cancelled) return;
      haveDeviceData.current = true;
      setData({ tracks: tracks.tracks, albums: albums.albums, artists: artists.artists, playlists: playlists.playlists });
    }).catch(() => { if (!cancelled) setError('Your library couldn’t load from the player.'); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [connection, revision]);
  return useMemo(() => ({ ...data, loading, isDemo, error, refresh }), [data, loading, isDemo, error, refresh]);
}

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Album, Artist, Playlist, Track, api } from '../services/api';
import { demoAlbums, demoArtists, demoPlaylists, demoTracks } from '../lib/demo';
import { Connection } from '../player/PlayerProvider';

interface LibraryContent { tracks: Track[]; albums: Album[]; artists: Artist[]; playlists: Playlist[] }
export interface LibraryData extends LibraryContent { loading: boolean; isDemo: boolean; error: string | null; refresh: () => void }
const demoData: LibraryContent = { tracks: demoTracks, albums: demoAlbums, artists: demoArtists, playlists: demoPlaylists };
const emptyData: LibraryContent = { tracks: [], albums: [], artists: [], playlists: [] };
export function useLibrary(connection: Connection): LibraryData {
  const [data, setData] = useState<LibraryContent>(demoData);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision(n => n + 1), []);
  useEffect(() => {
    if (connection === 'connecting') return;
    if (connection === 'offline') { setData(demoData); setIsDemo(true); setLoading(false); setError(null); return; }
    let cancelled = false;
    setLoading(true); setError(null); setIsDemo(false); setData(emptyData);
    Promise.all([api.getTracks(), api.getAlbums(), api.getArtists(), api.getPlaylists()]).then(([tracks, albums, artists, playlists]) => {
      if (!cancelled) setData({ tracks: tracks.tracks, albums: albums.albums, artists: artists.artists, playlists: playlists.playlists });
    }).catch(() => { if (!cancelled) setError('Your library couldn’t load from the player.'); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [connection, revision]);
  return useMemo(() => ({ ...data, loading, isDemo, error, refresh }), [data, loading, isDemo, error, refresh]);
}

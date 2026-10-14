import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Playlist, Track } from '../services/api';
import { useFeedback } from './Feedback';
import { upgradeStarterTrack } from '../lib/demo';

export interface PersonalPlaylist extends Playlist { tracks: Track[]; description: string; personal: true }
interface SavedLibrary { playlists: PersonalPlaylist[]; recent: Track[]; searches: string[] }
const STORAGE_KEY = 'pesto.library.v1';
const empty: SavedLibrary = { playlists: [], recent: [], searches: [] };
const isTrack = (item: unknown): item is Track => Boolean(item && typeof item === 'object' && ['id', 'title', 'artist', 'album'].every(key => typeof (item as Record<string, unknown>)[key] === 'string') && typeof (item as Track).duration === 'number');
const migrateTracks = (tracks: Track[]) => [...new Map(tracks.filter(isTrack).map(upgradeStarterTrack).map(track => [track.id, track])).values()];
function readLibrary(): SavedLibrary {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (!saved || !Array.isArray(saved.playlists) || !Array.isArray(saved.recent) || !Array.isArray(saved.searches)) return empty;
    return {
      playlists: saved.playlists.filter((p: PersonalPlaylist) => p && typeof p.id === 'string' && p.id.startsWith('local-') && typeof p.name === 'string' && Array.isArray(p.tracks)).map((p: PersonalPlaylist) => ({ ...p, tracks: migrateTracks(p.tracks), trackCount: migrateTracks(p.tracks).length, description: typeof p.description === 'string' ? p.description : '', personal: true })),
      recent: migrateTracks(saved.recent).slice(0, 20),
      searches: saved.searches.filter((s: unknown) => typeof s === 'string').slice(0, 6),
    };
  } catch { return empty; }
}

interface PersonalContextValue extends SavedLibrary {
  savePlaylist: (name: string, description: string, tracks: Track[], id?: string) => string;
  deletePlaylist: (id: string) => void;
  addTrack: (id: string, track: Track) => void;
  recordPlayed: (track: Track) => void;
  rememberSearch: (query: string) => void;
  clearSearches: () => void;
}
const PersonalContext = createContext<PersonalContextValue | null>(null);
export function PersonalLibraryProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState(readLibrary);
  const { notify } = useFeedback();
  useEffect(() => {
    try {
      const serialized = JSON.stringify(saved);
      if (localStorage.getItem(STORAGE_KEY) !== serialized) localStorage.setItem(STORAGE_KEY, serialized);
    }
    catch { notify('Browser storage is unavailable. Changes will last for this session.'); }
  }, [saved, notify]);
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) setSaved(readLibrary());
    };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);
  const savePlaylist = useCallback((name: string, description: string, tracks: Track[], id?: string) => {
    const playlistId = id || `local-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
    const unique = [...new Map(tracks.map(track => [track.id, track])).values()];
    const playlist: PersonalPlaylist = { id: playlistId, name: name.trim(), description: description.trim(), tracks: unique, trackCount: unique.length, personal: true };
    setSaved(prev => ({ ...prev, playlists: id ? prev.playlists.map(p => p.id === id ? playlist : p) : [playlist, ...prev.playlists] }));
    notify(id ? 'Playlist updated' : 'Playlist created');
    return playlistId;
  }, [notify]);
  const deletePlaylist = useCallback((id: string) => {
    setSaved(prev => ({ ...prev, playlists: prev.playlists.filter(p => p.id !== id) }));
    notify('Playlist deleted');
  }, [notify]);
  const addTrack = useCallback((id: string, track: Track) => {
    setSaved(prev => ({ ...prev, playlists: prev.playlists.map(p => p.id !== id || p.tracks.some(t => t.id === track.id) ? p : { ...p, tracks: [...p.tracks, track], trackCount: p.tracks.length + 1 }) }));
    notify('Song saved to playlist');
  }, [notify]);
  const recordPlayed = useCallback((track: Track) => {
    setSaved(prev => prev.recent[0]?.id === track.id ? prev : { ...prev, recent: [track, ...prev.recent.filter(t => t.id !== track.id)].slice(0, 20) });
  }, []);
  const rememberSearch = useCallback((query: string) => {
    const clean = query.trim().slice(0, 100);
    if (clean) setSaved(prev => ({ ...prev, searches: [clean, ...prev.searches.filter(q => q.toLowerCase() !== clean.toLowerCase())].slice(0, 6) }));
  }, []);
  const clearSearches = useCallback(() => setSaved(prev => ({ ...prev, searches: [] })), []);
  const value = useMemo(() => ({ ...saved, savePlaylist, deletePlaylist, addTrack, recordPlayed, rememberSearch, clearSearches }), [saved, savePlaylist, deletePlaylist, addTrack, recordPlayed, rememberSearch, clearSearches]);
  return <PersonalContext.Provider value={value}>{children}</PersonalContext.Provider>;
}
export function usePersonalLibrary() {
  const value = useContext(PersonalContext);
  if (!value) throw new Error('PersonalLibraryProvider is required');
  return value;
}

import { Edit3, Heart, Play, Shuffle, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Track, api } from '../services/api';
import { usePlayer } from '../player/PlayerProvider';
import { usePersonalLibrary } from '../state/PersonalLibrary';
import { Cover } from './Cover';
import { TrackRow } from './TrackRow';
import { Modal } from './Modal';
import { PlaylistEditor } from './PlaylistEditor';

export interface CollectionRef {
  kind: 'playlist' | 'album' | 'artist' | 'mix';
  id: string;
  title: string;
  subtitle?: string;
  coverUrl?: string;
  tracks?: Track[];
}
interface CollectionSheetProps { collection: CollectionRef; onClose: () => void; libraryTracks?: Track[] }

export function CollectionSheet({ collection, onClose, libraryTracks = [] }: CollectionSheetProps) {
  const { playTrack, toggleShuffle, shuffle } = usePlayer();
  const { playlists } = usePersonalLibrary();
  const personal = playlists.find(p => p.id === collection.id);
  const [loaded, setLoaded] = useState<Track[] | null>(collection.tracks ?? null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(false);
  const tracks = personal?.tracks ?? loaded;
  const title = personal?.name ?? collection.title;

  useEffect(() => {
    if (collection.tracks) { setLoaded(collection.tracks); return; }
    let cancelled = false;
    setFailed(false);
    setLoaded(null);
    const load = collection.kind === 'playlist' ? api.getPlaylist(collection.id).then(p => p.tracks ?? []) : collection.kind === 'album' ? api.getAlbum(collection.id).then(r => r.album.tracks ?? []) : Promise.resolve([]);
    load.then(items => { if (!cancelled) setLoaded(items); }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [collection, attempt]);

  const playAll = (random: boolean) => {
    if (!tracks?.length) return;
    if (shuffle !== random) toggleShuffle();
    playTrack(tracks[random ? Math.floor(Math.random() * tracks.length) : 0], tracks);
  };
  const minutes = tracks ? Math.ceil(tracks.reduce((sum, track) => sum + track.duration, 0) / 60) : 0;
  return <Modal label={title} onClose={onClose} className="collection-overlay collection-dialog">
    <button className="collection-dismiss h-16 shrink-0" onClick={onClose} aria-label="Close collection backdrop" tabIndex={-1} />
    <div className="collection-panel flex min-h-0 flex-1 flex-col rounded-t-[2rem] border-t border-cream/10 bg-basil-900 shadow-2xl">
      <div className="collection-header flex items-start gap-4 p-5 pb-4">
        <Cover src={personal?.tracks[0]?.coverUrl || collection.coverUrl} alt="" className="h-20 w-20 shrink-0 rounded-2xl" iconSize={28} />
        <div className="min-w-0 flex-1 pt-1"><div className="eyebrow">{personal ? 'Your playlist' : collection.kind}</div><h2 className="font-display text-2xl font-bold text-cream">{title}</h2><div className="text-sm text-sage">{personal ? personal.description || 'A mix made by you' : collection.subtitle}</div></div>
        <button onClick={onClose} className="round-control" aria-label="Close collection"><X size={20} /></button>
      </div>
      <div className="collection-meta">{tracks && <span>{tracks.length} songs · {minutes} min</span>}{personal && <button className="text-action" onClick={() => setEditing(true)}><Edit3 size={15} />Edit playlist</button>}</div>
      <div className="collection-actions flex gap-3 px-5 pb-4"><button className="action-primary" onClick={() => playAll(false)} disabled={!tracks?.length}><Play size={16} fill="currentColor" />Play all</button><button className="action-secondary" onClick={() => playAll(true)} disabled={!tracks?.length}><Shuffle size={16} />Shuffle</button></div>
      <div className="collection-tracks min-h-0 flex-1 overflow-y-auto px-3 pb-8">
        {failed && <div className="empty-state"><p>These songs couldn’t load. Check your player connection and try again.</p><button className="action-secondary" onClick={() => setAttempt(n => n + 1)}>Try again</button></div>}
        {!failed && tracks === null && <div className="loading-list" role="status">Loading songs…{[0,1,2].map(n => <div key={n} />)}</div>}
        {tracks?.map((track, index) => <TrackRow key={`${track.id}-${index}`} track={track} context={tracks} />)}
        {tracks?.length === 0 && !failed && <div className="empty-state"><Heart size={32} /><h3>A little room for your favorites.</h3><p>{personal ? 'Add songs and make this mix yours.' : 'There are no songs in this collection yet.'}</p>{personal && <button className="action-primary" onClick={() => setEditing(true)}>Add songs</button>}</div>}
      </div>
    </div>
    {editing && personal && <PlaylistEditor playlist={personal} tracks={libraryTracks} onClose={() => { setEditing(false); if (!playlists.some(p => p.id === collection.id)) onClose(); }} />}
  </Modal>;
}

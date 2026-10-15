import { useState } from 'react';
import { Heart, ListPlus, Plus, Check } from 'lucide-react';
import { Track } from '../services/api';
import { usePlayer } from '../player/PlayerProvider';
import { usePersonalLibrary } from '../state/PersonalLibrary';
import { Sheet } from './Modal';
import { Cover } from './Cover';
import { PlaylistEditor } from './PlaylistEditor';

export function TrackActions({ track, onClose }: { track: Track; onClose: () => void }) {
  const { likes, toggleLike, addToQueue } = usePlayer();
  const { playlists, addTrack } = usePersonalLibrary();
  const [creating, setCreating] = useState(false);
  return <Sheet title="Your song, your way" onClose={onClose}>
    <div className="track-summary"><Cover src={track.coverUrl} alt="" className="h-16 w-16 shrink-0 rounded-xl" /><div><h3>{track.title}</h3><p>{track.artist} · {track.album}</p></div></div>
    <div className="track-action-list"><button onClick={() => toggleLike(track.id)} aria-pressed={likes.has(track.id)}><Heart size={19} fill={likes.has(track.id) ? 'currentColor' : 'none'} />{likes.has(track.id) ? 'Remove from liked songs' : 'Save to liked songs'}</button><button onClick={() => { addToQueue(track); onClose(); }}><ListPlus size={19} />Add to queue</button></div>
    <div className="sheet-section-heading"><h3>Add to a playlist</h3><button className="text-action" onClick={() => setCreating(true)}><Plus size={16} />New</button></div>
    <div className="playlist-picker">{playlists.map(playlist => {
      const added = playlist.tracks.some(t => t.id === track.id);
      return <button key={playlist.id} disabled={added} onClick={() => addTrack(playlist.id, track)}><span className="playlist-dot tone-0">{added ? <Check size={18} /> : <Plus size={18} />}</span><span>{playlist.name}<small>{added ? 'Already added' : `${playlist.trackCount} songs`}</small></span></button>;
    })}{playlists.length === 0 && <p className="empty-copy">Give this song a home. Create your first personal playlist.</p>}</div>
    {track.creditUrl && <p className="music-credit">“{track.title}” by <a href={track.creditUrl} target="_blank" rel="noreferrer">Kevin MacLeod (incompetech.com)</a><br />Licensed under <a href={track.licenseUrl} target="_blank" rel="noreferrer">Creative Commons BY 4.0</a>. Original recording, unmodified.</p>}
    <p className="storage-note">Personal playlists and likes stay in this browser.</p>
    {creating && <PlaylistEditor tracks={[track]} initialTrack={track} onClose={() => { setCreating(false); }} />}
  </Sheet>;
}

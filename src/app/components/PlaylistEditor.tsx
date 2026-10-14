import { useMemo, useState } from 'react';
import { Check, Music2, Search, Trash2 } from 'lucide-react';
import { Track } from '../services/api';
import { PersonalPlaylist, usePersonalLibrary } from '../state/PersonalLibrary';
import { Sheet } from './Modal';
import { Cover } from './Cover';
import { Incremental } from './Incremental';

export function PlaylistEditor({ playlist, tracks, onClose, initialTrack }: { playlist?: PersonalPlaylist; tracks: Track[]; onClose: () => void; initialTrack?: Track }) {
  const { savePlaylist, deletePlaylist } = usePersonalLibrary();
  const [name, setName] = useState(playlist?.name || '');
  const [description, setDescription] = useState(playlist?.description || '');
  const [selected, setSelected] = useState<Track[]>(playlist?.tracks || (initialTrack ? [initialTrack] : []));
  const [query, setQuery] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const available = useMemo(() => [...new Map([...tracks, ...selected].map(t => [t.id, t])).values()].filter(t => `${t.title} ${t.artist}`.toLowerCase().includes(query.toLowerCase())), [tracks, selected, query]);
  const toggle = (track: Track) => setSelected(prev => prev.some(t => t.id === track.id) ? prev.filter(t => t.id !== track.id) : [...prev, track]);
  return <Sheet title={playlist ? 'Make it your mix' : 'Start a fresh mix'} subtitle="Personal playlists are saved in this browser." onClose={onClose} className="playlist-editor">
    <form className="editor-form" onSubmit={event => { event.preventDefault(); if (!name.trim()) return; savePlaylist(name, description, selected, playlist?.id); onClose(); }}>
      <div className="editor-fields"><label>Playlist name<input autoFocus required maxLength={60} value={name} onChange={e => setName(e.target.value)} placeholder="Sunday kind of feeling" /></label><label>Description <span>(optional)</span><input maxLength={160} value={description} onChange={e => setDescription(e.target.value)} placeholder="A few words about your mix" /></label></div>
      <div className="editor-track-heading"><h3>Add songs <span>{selected.length} selected</span></h3><label className="search-field"><Search size={17} /><input aria-label="Find songs for playlist" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a song or artist" /></label></div>
      <div className="editor-track-list"><Incremental items={available} render={track => {
        const checked = selected.some(t => t.id === track.id);
        return <button type="button" className="selectable-track" aria-pressed={checked} key={track.id} onClick={() => toggle(track)}><Cover src={track.coverUrl} alt="" className="h-10 w-10 shrink-0 rounded-lg" /><span><strong>{track.title}</strong><small>{track.artist}</small></span><span className={`selection-check ${checked ? 'selected' : ''}`}>{checked ? <Check size={17} /> : <Music2 size={15} />}</span></button>;
      }} />{available.length === 0 && <p className="empty-copy">No matching songs. Try another name.</p>}</div>
      <div className="editor-footer">{playlist && <button type="button" className="round-control delete-control" aria-label="Delete playlist" onClick={() => setConfirmDelete(true)}><Trash2 size={18} /></button>}<span>{selected.length} songs</span><button className="action-primary" type="submit" disabled={!name.trim()}>{playlist ? 'Save changes' : 'Create playlist'}</button></div>
    </form>
    {confirmDelete && <Sheet title="Delete this playlist?" subtitle={`“${playlist?.name}” will be removed from this browser. Your songs and likes stay saved.`} onClose={() => setConfirmDelete(false)}><div className="confirmation-actions"><button className="action-secondary" onClick={() => setConfirmDelete(false)}>Keep playlist</button><button className="action-primary danger" onClick={() => { deletePlaylist(playlist!.id); onClose(); }}>Delete playlist</button></div></Sheet>}
  </Sheet>;
}

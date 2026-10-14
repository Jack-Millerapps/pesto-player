import { Clock3, Search, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { SearchResults, api } from '../services/api';
import { usePlayer } from '../player/PlayerProvider';
import { LibraryData } from '../hooks/useLibrary';
import { usePersonalLibrary } from '../state/PersonalLibrary';
import { AppHeader } from './AppHeader';
import { Cover } from './Cover';
import { TrackRow } from './TrackRow';
import { CollectionRef } from './CollectionSheet';

export function SearchPage({ library, onOpenCollection }: { library: LibraryData; onOpenCollection: (ref: CollectionRef) => void }) {
  const { connection } = usePlayer();
  const { playlists, searches, rememberSearch, clearSearches } = usePersonalLibrary();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [searching, setSearching] = useState(false);
  const [filter, setFilter] = useState('all');
  const input = useRef<HTMLInputElement>(null);
  const trimmed = query.trim();
  const allPlaylists = [...playlists, ...library.playlists];
  const matchingPlaylists = allPlaylists.filter(p => p.name.toLowerCase().includes(trimmed.toLowerCase()));
  useEffect(() => {
    if (!trimmed) { setResults(null); setSearching(false); return; }
    const q = trimmed.toLowerCase();
    const local = { tracks: library.tracks.filter(t => `${t.title} ${t.artist} ${t.album}`.toLowerCase().includes(q)), albums: library.albums.filter(a => `${a.title} ${a.artist}`.toLowerCase().includes(q)), artists: library.artists.filter(a => a.name.toLowerCase().includes(q)) };
    setResults(local);
    if (connection !== 'online') { setSearching(false); return; }
    setSearching(true);
    let cancelled = false;
    const timer = window.setTimeout(() => api.search(trimmed).then(found => { if (!cancelled) setResults(found); }).catch(() => {}).finally(() => { if (!cancelled) setSearching(false); }), 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [trimmed, connection, library]);
  const open = (ref: CollectionRef) => { rememberSearch(trimmed); onOpenCollection(ref); };
  const total = results ? results.tracks.length + results.albums.length + results.artists.length + matchingPlaylists.length : 0;
  const show = (type: string) => filter === 'all' || filter === type;
  const visibleCount = !results ? 0 : filter === 'songs' ? results.tracks.length : filter === 'albums' ? results.albums.length : filter === 'artists' ? results.artists.length : filter === 'playlists' ? matchingPlaylists.length : total;
  return <div className="page-scroll secondary-page search-page"><AppHeader />
    <div className="page-intro"><div><p className="eyebrow">FOLLOW YOUR EARS</p><h1>Find your next favorite.</h1><p>A song, an artist, a whole new mood.</p></div></div>
    <form className="search-form" onSubmit={e => { e.preventDefault(); rememberSearch(trimmed); input.current?.blur(); }}><label className="search-field"><Search size={20} /><input ref={input} type="search" aria-label="Search your library" placeholder="Songs, artists, albums, playlists" value={query} onChange={e => { setQuery(e.target.value); setFilter('all'); }} />{query && <button type="button" className="round-control" aria-label="Clear search" onClick={() => { setQuery(''); input.current?.focus(); }}><X size={18} /></button>}</label></form>
    {trimmed && <div className="search-content"><div className="filter-pills search-filters" role="group" aria-label="Search filters">{['all','songs','albums','artists','playlists'].map(type => <button key={type} aria-pressed={type === filter} onClick={() => setFilter(type)}>{type.charAt(0).toUpperCase() + type.slice(1)}</button>)}</div><p className="result-count" role="status">{searching ? 'Searching your player…' : `${total} ${total === 1 ? 'result' : 'results'} for “${trimmed}”`}</p>
      {results && <>
        {visibleCount === 0 && !searching && <div className="empty-state"><Search size={34} /><h3>No matches just yet.</h3><p>Try a different name or a shorter word.</p><button className="action-secondary" onClick={() => { setQuery(''); input.current?.focus(); }}>Browse your library</button></div>}
        {show('songs') && results.tracks.length > 0 && <section className="search-results-section"><h2>Songs</h2><div onClick={() => rememberSearch(trimmed)}>{results.tracks.map(track => <TrackRow key={track.id} track={track} context={results.tracks} />)}</div></section>}
        {show('albums') && results.albums.length > 0 && <section className="search-results-section"><h2>Albums</h2><div className="library-album-grid">{results.albums.map(album => <button className="album-card" key={album.id} onClick={() => open({ kind:'album', id:album.id, title:album.title, subtitle:album.artist, coverUrl:album.coverUrl, tracks:album.tracks })}><div className="album-art"><Cover src={album.coverUrl} alt="" className="aspect-square w-full" /></div><strong>{album.title}</strong><span>{album.artist}</span></button>)}</div></section>}
        {show('artists') && results.artists.length > 0 && <section className="search-results-section"><h2>Artists</h2>{results.artists.map((artist, index) => <button className="library-item" key={artist.id} onClick={() => open({ kind:'artist', id:artist.id, title:artist.name, subtitle:`${artist.albumCount} albums`, tracks:library.tracks.filter(t => t.artist === artist.name), coverUrl:library.tracks.find(t => t.artist === artist.name)?.coverUrl })}><span className={`artist-avatar tone-${index % 4}`}>{artist.name.charAt(0)}</span><div><strong>{artist.name}</strong><small>{artist.albumCount} albums</small></div></button>)}</section>}
        {show('playlists') && matchingPlaylists.length > 0 && <section className="search-results-section"><h2>Playlists</h2>{matchingPlaylists.map(playlist => <button className="library-item" key={playlist.id} onClick={() => open({ kind:'playlist', id:playlist.id, title:playlist.name, tracks:playlist.tracks, coverUrl:playlist.tracks?.[0]?.coverUrl })}><Cover src={playlist.tracks?.[0]?.coverUrl} alt="" className="h-14 w-14 shrink-0 rounded-xl" /><div><strong>{playlist.name}</strong><small>{playlist.trackCount} songs</small></div></button>)}</section>}
      </>}
    </div>}
    {!trimmed && <div className="search-content">
      {searches.length > 0 && <section className="recent-searches"><div className="sheet-section-heading"><h2>Recent searches</h2><button className="text-action" onClick={clearSearches}>Clear</button></div><div className="recent-search-chips">{searches.map(term => <button key={term} onClick={() => setQuery(term)}><Clock3 size={15} />{term}</button>)}</div></section>}
      <section className="browse-section"><div className="section-heading"><h2>Pick a starting point</h2></div><div className="browse-mixes">{allPlaylists.map((playlist, index) => <button className={`browse-mix tone-${index % 4}`} key={playlist.id} onClick={() => onOpenCollection({kind:'playlist',id:playlist.id,title:playlist.name,subtitle:`${playlist.trackCount} songs`,tracks:playlist.tracks,coverUrl:playlist.tracks?.[0]?.coverUrl})}><strong>{playlist.name}</strong><span>{playlist.trackCount} songs</span><i aria-hidden>{['✳','≈','✹','◒'][index % 4]}</i></button>)}</div></section>
      <section className="search-results-section"><h2>Artists in your corner</h2><div className="artist-shelf">{library.artists.map((artist,index) => <button key={artist.id} onClick={() => onOpenCollection({kind:'artist',id:artist.id,title:artist.name,subtitle:`${artist.albumCount} albums`,tracks:library.tracks.filter(t => t.artist === artist.name),coverUrl:library.tracks.find(t => t.artist === artist.name)?.coverUrl})}><span className={`artist-avatar tone-${index % 4}`}>{artist.name.charAt(0)}</span><strong>{artist.name}</strong></button>)}</div></section>
    </div>}
  </div>;
}

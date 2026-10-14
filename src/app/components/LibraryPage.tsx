import { ArrowUpDown, ChevronRight, Heart, Library, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { usePlayer } from '../player/PlayerProvider';
import { LibraryData } from '../hooks/useLibrary';
import { demoPlaylistCovers } from '../lib/demo';
import { usePersonalLibrary } from '../state/PersonalLibrary';
import { AppHeader } from './AppHeader';
import { Cover } from './Cover';
import { CollectionRef } from './CollectionSheet';
import { TrackRow } from './TrackRow';
import { PlaylistEditor } from './PlaylistEditor';

type Filter = 'playlists' | 'albums' | 'artists' | 'liked';
const filters: { id: Filter; label: string }[] = [{ id: 'playlists', label: 'Playlists' }, { id: 'albums', label: 'Albums' }, { id: 'artists', label: 'Artists' }, { id: 'liked', label: 'Liked' }];
export function LibraryPage({ library, onOpenCollection }: { library: LibraryData; onOpenCollection: (ref: CollectionRef) => void }) {
  const [filter, setFilter] = useState<Filter>('playlists');
  const [sort, setSort] = useState('original');
  const [creating, setCreating] = useState(false);
  const { likes, playTrack } = usePlayer();
  const { playlists: personal } = usePersonalLibrary();
  const liked = useMemo(() => {
    const tracks = library.tracks.filter(t => likes.has(t.id));
    return sort === 'name' ? tracks.sort((a, b) => a.title.localeCompare(b.title)) : tracks;
  }, [library.tracks, likes, sort]);
  const artists = useMemo(() => sort === 'name' ? [...library.artists].sort((a, b) => a.name.localeCompare(b.name)) : library.artists, [library.artists, sort]);
  const playlists = useMemo(() => {
    const items = [...personal, ...library.playlists];
    return sort === 'name' ? items.sort((a,b) => a.name.localeCompare(b.name)) : items;
  }, [personal, library.playlists, sort]);
  const albums = useMemo(() => sort === 'name' ? [...library.albums].sort((a,b) => a.title.localeCompare(b.title)) : library.albums, [library.albums, sort]);
  return <div className="page-scroll secondary-page library-page"><AppHeader />
    <div className="page-intro"><div><p className="eyebrow">THE GOOD STUFF, ALL TOGETHER</p><h1>Your library</h1><p>{library.tracks.length} songs · {library.albums.length} albums · {playlists.length} playlists</p></div><button className="round-control create-playlist-button" aria-label="Create playlist" onClick={() => setCreating(true)}><Plus size={22} /></button></div>
    <div className="library-shortcuts"><button className="liked-shortcut" onClick={() => setFilter('liked')}><span><Heart size={23} fill="currentColor" /></span><div><strong>Liked songs</strong><small>{liked.length ? `${liked.length} ${liked.length === 1 ? 'favorite' : 'favorites'}, one happy place` : 'Keep your favorites close'}</small></div><ChevronRight size={18} /></button></div>
    <div className="library-toolbar"><div className="filter-pills" role="group" aria-label="Library filters">{filters.map(item => <button key={item.id} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}</button>)}</div><label className="sort-control"><ArrowUpDown size={15} /><select aria-label="Sort library" value={sort} onChange={e => setSort(e.target.value)}><option value="original">Default order</option><option value="name">A–Z</option></select></label></div>
    {library.loading && <p className="empty-copy" role="status">Loading your library…</p>}
    {filter === 'playlists' && <div className="library-list"><button className="new-playlist-row" onClick={() => setCreating(true)}><span><Plus size={23} /></span><div><strong>Make your own mix</strong><small>Start a personal playlist</small></div></button>{playlists.map(playlist => <button className="library-item" key={playlist.id} onClick={() => onOpenCollection({ kind: 'playlist', id: playlist.id, title: playlist.name, subtitle: `${playlist.trackCount} songs`, coverUrl: demoPlaylistCovers[playlist.id] || playlist.tracks?.[0]?.coverUrl, tracks: playlist.tracks })}><Cover src={demoPlaylistCovers[playlist.id] || playlist.tracks?.[0]?.coverUrl} alt="" className="h-14 w-14 shrink-0 rounded-xl" /><div><strong>{playlist.name}</strong><small>{playlist.trackCount} songs · {playlist.id.startsWith('local-') ? 'Made by you' : library.isDemo ? 'Pesto selects' : 'On your player'}</small></div><ChevronRight size={18} /></button>)}</div>}
    {filter === 'albums' && <div className="library-album-grid">{albums.map(album => <button className="album-card" key={album.id} onClick={() => onOpenCollection({ kind:'album', id:album.id, title:album.title, subtitle:album.artist, coverUrl:album.coverUrl, tracks:album.tracks })}><div className="album-art"><Cover src={album.coverUrl} alt="" className="aspect-square w-full" /></div><strong>{album.title}</strong><span>{album.artist}</span></button>)}{!albums.length && <p className="empty-copy">Albums will appear when songs are added to your player.</p>}</div>}
    {filter === 'artists' && <div className="library-list">{artists.map((artist, index) => <button className="library-item artist-item" key={artist.id} onClick={() => onOpenCollection({ kind:'artist', id:artist.id, title:artist.name, subtitle:`${artist.albumCount} albums in your library`, tracks:library.tracks.filter(t => t.artist === artist.name), coverUrl:library.tracks.find(t => t.artist === artist.name)?.coverUrl })}><span className={`artist-avatar tone-${index % 4}`}>{artist.name.charAt(0)}</span><div><strong>{artist.name}</strong><small>{artist.albumCount} {artist.albumCount === 1 ? 'album' : 'albums'}</small></div><ChevronRight size={18} /></button>)}{!library.artists.length && <p className="empty-copy">Artists will appear when songs are added to your player.</p>}</div>}
    {filter === 'liked' && <div className="library-list">{liked.length ? <><div className="liked-heading"><span>{liked.length} saved songs</span><button className="action-primary" onClick={() => playTrack(liked[0], liked)}>Play favorites</button></div>{liked.map(track => <TrackRow key={track.id} track={track} context={liked} />)}</> : <div className="empty-state"><Heart size={34} /><h3>Meet your future favorites.</h3><p>Open a song’s menu and tap “Save to liked songs.” You’ll find it here.</p><button className="action-secondary" onClick={() => setFilter('albums')}><Library size={16} />Browse albums</button></div>}</div>}
    <p className="storage-note library-storage">Personal playlists and likes are saved in this browser.</p>
    {creating && <PlaylistEditor tracks={library.tracks} onClose={() => setCreating(false)} />}
  </div>;
}

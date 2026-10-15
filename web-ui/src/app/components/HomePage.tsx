import { ArrowDownRight, ArrowRight, Disc3, Headphones, Play, Sparkles } from 'lucide-react';
import { CollectionRef } from './CollectionSheet';
import { Cover } from './Cover';
import { TrackRow } from './TrackRow';
import { AppHeader } from './AppHeader';
import { LibraryData } from '../hooks/useLibrary';
import { demoPlaylistCovers } from '../lib/demo';
import { greetingForHour } from '../lib/format';
import { usePlayer } from '../player/PlayerProvider';
import { usePersonalLibrary } from '../state/PersonalLibrary';
interface HomePageProps {
  library: LibraryData;
  onOpenCollection: (ref: CollectionRef) => void;
}
export function HomePage({
  library,
  onOpenCollection
}: HomePageProps) {
  const {
    tracks,
    albums,
    playlists,
    loading,
    isDemo
  } = library;
  const {
    playTrack
  } = usePlayer();
  const { recent, playlists: personal } = usePersonalLibrary();
  const recentTracks = recent.filter(t => library.tracks.some(item => item.id === t.id));
  const featured = playlists[0];
  const featuredTracks = featured?.tracks;
  const openFeatured = () => {
    if (featured) onOpenCollection({
      kind: 'playlist',
      id: featured.id,
      title: featured.name,
      subtitle: `${featured.trackCount} songs`,
      tracks: featured.tracks,
      coverUrl: demoPlaylistCovers[featured.id] || featured.tracks?.[0]?.coverUrl
    });
  };
  const startFeatured = () => {
    if (featuredTracks?.length) playTrack(featuredTracks[0], featuredTracks);else openFeatured();
  };
  return <div className="page-scroll home-page">
      <AppHeader />
      <div className="home-content">
        <div className="page-heading"><div><p className="eyebrow">{greetingForHour(new Date().getHours())}</p><h1>Life sounds better<br className="mobile-break" /> with pesto<span className="heading-star">✳</span></h1></div><span className="sound-tag"><Headphones size={15} /> Made for your ears</span></div>
        {loading ? <div className="home-loading" role="status">Finding your next favorite…</div> : <>
          {featured && <section className="featured-mix" aria-label="Featured playlist">
            <div className="featured-copy"><span className="feature-label"><Sparkles size={14} /> FRESH FROM YOUR LIBRARY</span><h2>A fresh spin<br />on your day.</h2><p>{featured.name} · {featured.trackCount} songs to get you going.</p><button className="primary-play" onClick={startFeatured}><Play size={17} fill="currentColor" />Play the mix<ArrowRight size={17} /></button></div>
            <div className="record-scene" aria-hidden="true"><div className="record-sleeve"><span>pesto<br />selects.</span><div className="sleeve-flower">✳</div><small>FRESHLY PICKED SOUNDS</small></div><div className="vinyl-record"><div className="record-label"><span>fresh<br />batch</span><i /></div></div><span className="record-sticker">100%<br />good stuff</span></div>
          </section>}
          {playlists.length > 0 && <section className="mix-section" aria-labelledby="mix-heading"><div className="section-heading"><h2 id="mix-heading">A mix for every mood</h2><span>Pick your flavor <ArrowDownRight size={16} /></span></div><div className="mood-grid">
            {playlists.slice(0, 4).map((playlist, index) => <button className={`mood-tile tone-${index}`} key={playlist.id} onClick={() => onOpenCollection({
              kind: 'playlist',
              id: playlist.id,
              title: playlist.name,
              subtitle: `${playlist.trackCount} songs`,
              coverUrl: demoPlaylistCovers[playlist.id] || playlist.tracks?.[0]?.coverUrl,
              tracks: playlist.tracks
            })}><span className="mood-symbol" aria-hidden>{['✳', '≈', '✹', '◒'][index]}</span><span className="mood-info"><strong>{playlist.name}</strong><small>{playlist.trackCount} songs</small></span><ArrowRight className="mood-arrow" size={18} /></button>)}
          </div></section>}
          {albums.length > 0 && <section className="album-section" aria-labelledby="albums-heading"><div className="section-heading"><h2 id="albums-heading">Worth a whole listen<span className="small-flower" aria-hidden>✳</span></h2><span>{albums.length} albums in rotation</span></div><div className="album-shelf">{albums.map(album => <button key={album.id} className="album-card" onClick={() => onOpenCollection({
              kind: 'album',
              id: album.id,
              title: album.title,
              subtitle: album.artist,
              coverUrl: album.coverUrl,
              tracks: album.tracks
            })}><div className="album-art"><Cover src={album.coverUrl} alt="" className="aspect-square w-full" iconSize={34} /><span className="album-open"><ArrowRight size={21} /></span></div><strong>{album.title}</strong><span>{album.artist}</span></button>)}</div></section>}
          {recentTracks.length > 0 && <section className="songs-section"><div className="section-heading"><h2>Back for another spin</h2><span>Recently played</span></div><div className="recently-played">{recentTracks.slice(0, 4).map(track => <button key={track.id} onClick={() => playTrack(track, recentTracks)}><Cover src={track.coverUrl} alt="" className="h-12 w-12 shrink-0 rounded-xl" /><span><strong>{track.title}</strong><small>{track.artist}</small></span><Play size={16} /></button>)}</div></section>}
          {personal.length > 0 && <section className="mix-section"><div className="section-heading"><h2>Made by you</h2><span>Your personal mixes</span></div><div className="mood-grid">{personal.slice(0, 4).map((playlist,index) => <button key={playlist.id} className={`mood-tile tone-${index % 4}`} onClick={() => onOpenCollection({ kind:'playlist', id:playlist.id, title:playlist.name, tracks:playlist.tracks, coverUrl:playlist.tracks[0]?.coverUrl })}><span className="mood-symbol" aria-hidden>♫</span><span className="mood-info"><strong>{playlist.name}</strong><small>{playlist.trackCount} songs</small></span></button>)}</div></section>}
          {tracks.length === 0 && !library.error && <div className="empty-state"><Headphones size={36} /><h2>Your music belongs here.</h2><p>Add songs to your Pesto Player, then refresh your library.</p><button className="action-primary" onClick={library.refresh}>Refresh library</button></div>}
          {tracks.length > 0 && <section className="songs-section" aria-labelledby="songs-heading"><div className="section-heading"><h2 id="songs-heading">Good things on repeat</h2><button className="text-action" onClick={() => onOpenCollection({ kind: 'mix', id: 'all-songs', title: 'All your songs', tracks })}>All {tracks.length} songs <ArrowRight size={15} /></button></div><div className="home-tracks">{tracks.slice(0, 10).map(track => <TrackRow key={track.id} track={track} context={tracks} />)}</div></section>}
          {isDemo && <div className="demo-note"><span className="demo-pill">PRESS PLAY</span><p>Six real songs by Kevin MacLeod, ready to play on this device. <a href="/music/credits.html" target="_blank" rel="noreferrer">Music credits ↗</a></p></div>}
        </>}
      </div>
    </div>;
}

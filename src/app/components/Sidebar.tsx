import { ArrowUpRight, Disc3, Headphones, Home, Leaf, Library, Search } from 'lucide-react';
import { Tab } from './BottomNav';
import { LibraryData } from '../hooks/useLibrary';
import { CollectionRef } from './CollectionSheet';
interface SidebarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  library: LibraryData;
  onOpenCollection: (collection: CollectionRef) => void;
}
export function Sidebar({
  activeTab,
  onTabChange,
  library,
  onOpenCollection
}: SidebarProps) {
  return <aside className="pesto-sidebar">
      <div className="sidebar-brand"><span className="brand-icon"><Leaf size={26} /></span><span>pesto<span className="brand-period">.</span></span></div>
      <p className="brand-tagline">A little player. A lot of soul.</p>
      <nav aria-label="Main navigation" className="sidebar-nav">
        {[{
        id: 'home' as const,
        label: 'Home',
        Icon: Home
      }, {
        id: 'search' as const,
        label: 'Search',
        Icon: Search
      }, {
        id: 'library' as const,
        label: 'Your library',
        Icon: Library
      }].map(({
        id,
        label,
        Icon
      }) => <button key={id} aria-current={activeTab === id ? 'page' : undefined} onClick={() => onTabChange(id)}><Icon size={20} /><span>{label}</span>{activeTab === id && <span className="nav-dot" />}</button>)}
      </nav>
      <div className="sidebar-shelf">
        <p className="eyebrow">YOUR ROTATION</p>
        {library.playlists.map((playlist, index) => <button key={playlist.id} onClick={() => onOpenCollection({
        kind: 'playlist',
        id: playlist.id,
        title: playlist.name,
        subtitle: `${playlist.trackCount} songs`,
        tracks: playlist.tracks,
        coverUrl: playlist.tracks?.[0]?.coverUrl
      })}><span className={`playlist-dot tone-${index % 4}`}><Disc3 size={17} /></span><span>{playlist.name}</span></button>)}
      </div>
      <div className="sidebar-bottom"><Headphones size={30} /><h2>Find your<br />happy frequency.</h2><button onClick={() => onTabChange('library')}>Explore your library <ArrowUpRight size={16} /></button></div>
      <div className="sidebar-footer"><Leaf size={13} /> Freshly picked. Always yours.</div>
    </aside>;
}

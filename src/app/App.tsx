import { useEffect, useState } from 'react';
import { FeedbackProvider } from './state/Feedback';
import { PersonalLibraryProvider, usePersonalLibrary } from './state/PersonalLibrary';
import { Sidebar } from './components/Sidebar';
import { HomePage } from './components/HomePage';
import { SearchPage } from './components/SearchPage';
import { LibraryPage } from './components/LibraryPage';
import { BottomNav, Tab } from './components/BottomNav';
import { MiniPlayer } from './components/MiniPlayer';
import { FullPlayer } from './components/FullPlayer';
import { CollectionRef, CollectionSheet } from './components/CollectionSheet';
import { PlayerProvider, usePlayer } from './player/PlayerProvider';
import { useLibrary } from './hooks/useLibrary';

function AppShell() {
  const { connection, currentTrack, isPlaying } = usePlayer();
  const library = useLibrary(connection);
  const { recordPlayed, playlists } = usePersonalLibrary();
  useEffect(() => { if (currentTrack && isPlaying) recordPlayed(currentTrack); }, [currentTrack?.id, isPlaying, recordPlayed]);
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [playerExpanded, setPlayerExpanded] = useState(false);
  const [collection, setCollection] = useState<CollectionRef | null>(null);

  // If the track goes away (e.g. device queue ends), fold the player back up
  useEffect(() => {
    if (!currentTrack) setPlayerExpanded(false);
  }, [currentTrack]);

  useEffect(() => {
    if (collection?.id.startsWith('local-') && !playlists.some(p => p.id === collection.id)) setCollection(null);
  }, [collection, playlists]);

  return (
    <div className="pesto-stage">
      {/* Responsive player workspace */}
      <div className={`pesto-app${currentTrack ? ' has-track' : ''}`}>
        <div className="contents">
          <Sidebar activeTab={activeTab} onTabChange={setActiveTab} library={library} onOpenCollection={setCollection} />
          <main className="pesto-main">
            {library.error && <div className="library-error" role="alert"><span>{library.error}</span><button onClick={library.refresh}>Try again</button></div>}
            {activeTab === 'home' && (
              <HomePage library={library} onOpenCollection={setCollection} />
            )}
            {activeTab === 'search' && (
              <SearchPage library={library} onOpenCollection={setCollection} />
            )}
            {activeTab === 'library' && (
              <LibraryPage library={library} onOpenCollection={setCollection} />
            )}
          </main>

          <MiniPlayer onExpand={() => setPlayerExpanded(true)} />
          <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        {collection && (
          <CollectionSheet collection={collection} libraryTracks={library.tracks} onClose={() => setCollection(null)} />
        )}

        {playerExpanded && currentTrack && (
          <FullPlayer onClose={() => setPlayerExpanded(false)} />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <FeedbackProvider>
      <PersonalLibraryProvider>
        <PlayerProvider><AppShell /></PlayerProvider>
      </PersonalLibraryProvider>
    </FeedbackProvider>
  );
}

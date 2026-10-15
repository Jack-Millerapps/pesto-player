import { Headphones, Pause, Play, SkipForward } from 'lucide-react';
import { usePlayer, usePosition } from '../player/PlayerProvider';
import { Cover } from './Cover';

interface MiniPlayerProps {
  onExpand: () => void;
}

export function MiniPlayer({ onExpand }: MiniPlayerProps) {
  const { currentTrack, isPlaying, duration, togglePlay, next } = usePlayer();
  const position = usePosition();

  if (!currentTrack) return <div className="mini-player mini-player-empty"><span className="empty-player-icon"><Headphones size={22} /></span><div><strong>Your next favorite is waiting.</strong><span>Pick a song and make yourself at home.</span></div><span className="empty-player-flower" aria-hidden>✳</span></div>;

  const progress = duration > 0 ? Math.min(position / duration, 1) : 0;

  return (
    <div className="mini-player absolute bottom-[calc(72px+env(safe-area-inset-bottom))] left-3 right-3 z-30 overflow-hidden rounded-2xl border border-cream/10 bg-basil-800/95 shadow-2xl backdrop-blur-xl">
      <div className="mini-player-controls flex items-center gap-3 p-2.5 pr-3">
        <button
          onClick={onExpand}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          aria-label={`Open player: ${currentTrack.title} by ${currentTrack.artist}`}
        >
          <Cover
            src={currentTrack.coverUrl}
            alt=""
            className="h-11 w-11 shrink-0 rounded-xl"
            iconSize={16}
          />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-cream">{currentTrack.title}</div>
            <div className="truncate text-xs text-sage">{currentTrack.artist}</div>
          </div>
        </button>

        <button
          onClick={togglePlay}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-pesto text-basil-950 transition-colors hover:bg-pesto-bright"
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? (
            <Pause size={18} fill="currentColor" />
          ) : (
            <Play size={18} fill="currentColor" className="ml-0.5" />
          )}
        </button>
        <button
          onClick={next}
          className="mini-player-next tap-44 ml-1 shrink-0 p-1 text-cream transition-transform hover:scale-110"
          aria-label="Next track"
        >
          <SkipForward size={20} fill="currentColor" />
        </button>
      </div>

      <div className="h-[3px] bg-cream/10">
        {/* transform (compositor-only), not width: animating width re-ran layout every frame, ~25% of a throttled CPU */}
        <div
          className="h-full origin-left bg-pesto transition-transform duration-500 ease-linear"
          style={{ transform: `scaleX(${progress})` }}
        />
      </div>
    </div>
  );
}

import { MoreHorizontal } from 'lucide-react';
import { memo, useState } from 'react';
import { TrackActions } from './TrackActions';
import { Track } from '../services/api';
import { useNowPlaying } from '../player/PlayerProvider';
import { formatDuration } from '../lib/format';
import { Cover } from './Cover';

function EqualizerBars() {
  return (
    <div className="flex h-4 items-end gap-[3px]" aria-hidden>
      {[0, 1, 2].map((bar) => (
        <span
          key={bar}
          className="pesto-eq-bar w-[3px] rounded-full bg-pesto"
          style={{ height: '100%', animationDelay: `${bar * 0.18}s` }}
        />
      ))}
    </div>
  );
}

interface TrackRowProps {
  track: Track;
  /** The list this row belongs to, used as the playback queue. */
  context?: Track[];
  /** Start the playback queue at this index of `context` (lets lists share one stable array). */
  contextFrom?: number;
  showQueueButton?: boolean;
}

export const TrackRow = memo(function TrackRow({ track, context, contextFrom = 0, showQueueButton = true }: TrackRowProps) {
  const { currentId, isPlaying, playTrack } = useNowPlaying();
  const [menuOpen, setMenuOpen] = useState(false);
  const isCurrent = currentId === track.id;

  return (
    <div
      className={`track-row group flex w-full items-center gap-3 rounded-2xl p-2.5 pr-3 transition-colors ${
        isCurrent ? 'bg-pesto/10' : 'hover:bg-cream/5'
      }`}
    >
      <button
        onClick={() => playTrack(track, contextFrom ? context?.slice(contextFrom) : context)}
        className="flex min-w-0 flex-1 items-center gap-3 text-left"
        aria-label={`Play ${track.title} by ${track.artist}`}
      >
        <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-xl">
          <Cover src={track.coverUrl} alt="" className="h-full w-full" iconSize={18} />
          {isCurrent && isPlaying && (
            <div className="absolute inset-0 flex items-center justify-center bg-basil-950/60">
              <EqualizerBars />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div
            className={`truncate text-[15px] font-medium ${
              isCurrent ? 'text-pesto-bright' : 'text-cream'
            }`}
          >
            {track.title}
          </div>
          <div className="truncate text-[13px] text-sage">{track.artist}</div>
        </div>
      </button>

      <span className="text-xs tabular-nums text-sage">{formatDuration(track.duration)}</span>

      {showQueueButton && (
        <button
          onClick={() => setMenuOpen(true)}
          className="tap-44 rounded-full p-1.5 text-sage transition-colors hover:bg-cream/10 hover:text-cream"
          aria-label={`More options for ${track.title}`}
        >
          <MoreHorizontal size={20} />
        </button>
      )}
      {menuOpen && <TrackActions track={track} onClose={() => setMenuOpen(false)} />}
    </div>
  );
});

import {
  ChevronDown,
  Heart,
  ListMusic,
  Pause,
  Play,
  Repeat,
  Repeat1,
  Shuffle,
  SkipBack,
  SkipForward,
  Volume2,
} from 'lucide-react';
import { CSSProperties, memo, useEffect, useMemo, useRef, useState } from 'react';
import { Track } from '../services/api';

/**
 * Staged slider value that always resolves: commits on release, and for
 * input events with no pointer (screen readers, some keyboards) via a
 * short debounce; pointercancel/blur can never strand a pending value.
 */
function usePendingSlider(commit: (value: number) => void) {
  const [pending, setPending] = useState<number | null>(null);
  const draggingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => clearTimer, []);

  const stage = (value: number) => {
    setPending(value);
    if (!draggingRef.current) {
      clearTimer();
      timerRef.current = window.setTimeout(() => {
        commit(value);
        setPending(null);
      }, 250);
    }
  };

  const resolve = (value: number | null, shouldCommit: boolean) => {
    draggingRef.current = false;
    clearTimer();
    if (value !== null && shouldCommit) commit(value);
    setPending(null);
  };

  return {
    pending,
    handlers: (current: number | null) => ({
      onChange: (event: React.ChangeEvent<HTMLInputElement>) => stage(Number(event.target.value)),
      onPointerDown: () => {
        draggingRef.current = true;
        clearTimer();
      },
      onPointerUp: () => resolve(current, true),
      onPointerCancel: () => resolve(current, false),
      onKeyUp: () => resolve(current, true),
      onBlur: () => resolve(current, true),
    }),
  };
}
import { usePlayer, usePosition } from '../player/PlayerProvider';
import { formatDuration } from '../lib/format';
import { Cover } from './Cover';
import { TrackRow } from './TrackRow';
import { Modal } from './Modal';

/** Progress ring drawn around the circular album art. */
function ProgressRing({ progress }: { progress: number }) {
  const radius = 48.5;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(progress, 0), 1);
  return (
    <svg
      viewBox="0 0 100 100"
      className="absolute inset-0 h-full w-full -rotate-90"
      aria-hidden
    >
      <circle
        cx="50"
        cy="50"
        r={radius}
        fill="none"
        stroke="color-mix(in srgb, var(--color-cream) 12%, transparent)"
        strokeWidth="1.6"
      />
      <circle
        cx="50"
        cy="50"
        r={radius}
        fill="none"
        stroke="var(--color-pesto)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - clamped)}
      />
    </svg>
  );
}

/** Memoized so the per-tick position updates of the full player don't re-render every queue row. */
const QueueList = memo(function QueueList({ upcoming }: { upcoming: Track[] }) {
  return <>{upcoming.map((track, index) => (
    <TrackRow key={`${track.id}-${index}`} track={track} context={upcoming} contextFrom={index} showQueueButton={false} />
  ))}</>;
});

interface FullPlayerProps {
  onClose: () => void;
}

export function FullPlayer({ onClose }: FullPlayerProps) {
  const {
    currentTrack,
    isPlaying,
    duration,
    volume,
    shuffle,
    repeat,
    queue,
    clearQueue,
    buffering,
    likes,
    togglePlay,
    next,
    previous,
    seek,
    setVolume,
    toggleShuffle,
    toggleRepeat,
    toggleLike,
  } = usePlayer();
  const position = usePosition();

  const { pending: scrub, handlers: scrubHandlers } = usePendingSlider(seek);
  const { pending: localVolume, handlers: volumeHandlers } = usePendingSlider(setVolume);
  const [showQueue, setShowQueue] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const currentId = currentTrack?.id;
  const upcoming = useMemo(() => queue[0]?.id === currentId ? queue.slice(1) : queue, [queue, currentId]);

  if (!currentTrack) return null;

  const shownPosition = scrub ?? position;
  const shownVolume = localVolume ?? volume;
  const progress = duration > 0 ? shownPosition / duration : 0;
  const liked = likes.has(currentTrack.id);

  const rangeFill = (value: number, max: number): CSSProperties =>
    ({ '--range-fill': `${max > 0 ? (value / max) * 100 : 0}%` }) as CSSProperties;

  return (
    <Modal
      label="Now playing"
      onClose={onClose}
      className="full-player absolute inset-0 z-50 flex flex-col overflow-hidden bg-basil-950"
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        {/* Ambient backdrop from the cover art. Desktop only: a full-screen blur on a scaled layer is far too costly for the Pi Zero 2 W (phone/tablet layout hides it). */}
        {currentTrack.coverUrl && (
          <div
            className="pointer-events-none absolute inset-0 hidden scale-125 bg-cover bg-center opacity-25 blur-3xl lg:block"
            style={{ backgroundImage: `url(${currentTrack.coverUrl})` }}
            aria-hidden
          />
        )}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-basil-950/40 via-basil-950/70 to-basil-950" aria-hidden />

      </div>

      <div className="full-player-content relative flex h-full flex-col">
        {/* Header */}
        <div className="player-header flex items-center justify-between px-5 pb-2 pt-12">
          <button
            ref={closeRef}
            onClick={onClose}
            className="rounded-full p-2 text-cream transition-colors hover:bg-cream/10"
            aria-label="Close player"
          >
            <ChevronDown size={26} />
          </button>
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-sage">
            {buffering ? 'Loading audio…' : 'Now playing'}
          </span>
          <button
            onClick={() => setShowQueue((prev) => !prev)}
            className={`rounded-full p-2 transition-colors hover:bg-cream/10 ${
              showQueue ? 'text-pesto' : 'text-cream'
            }`}
            aria-label={showQueue ? 'Hide queue' : 'Show queue'}
            aria-pressed={showQueue}
          >
            <ListMusic size={22} />
          </button>
        </div>

        {showQueue ? (
          /* Queue view */
          <div className="player-queue min-h-0 flex-1 overflow-y-auto px-3 pb-4">
            <div className="queue-heading"><h2 className="font-display text-lg font-bold text-cream">Up next · {upcoming.length}</h2>{upcoming.length > 0 && <button className="text-action" onClick={clearQueue}>Clear queue</button>}</div>
            {upcoming.length > 0 ? (
              <QueueList upcoming={upcoming} />
            ) : (
              <p className="px-2 py-8 text-center text-sm text-sage">
                The queue is empty. Open any song’s menu to add it to the queue.
              </p>
            )}
          </div>
        ) : (
          /* Artwork with progress ring */
          <div className="player-artwork flex min-h-0 flex-1 items-center justify-center px-10">
            <div className="player-disc relative">
              <ProgressRing progress={progress} />
              <div className="absolute inset-[7%] overflow-hidden rounded-full shadow-2xl">
                <Cover
                  src={currentTrack.coverUrl}
                  alt={`Cover of ${currentTrack.album}`}
                  className="h-full w-full"
                  iconSize={48}
                />
              </div>
            </div>
          </div>
        )}

        {/* Track info */}
        <div className="player-track-info flex items-start justify-between gap-4 px-7 pb-4">
          <div className="min-w-0 flex-1">
            <h1 className="player-song-title font-display text-[26px] font-bold leading-tight text-cream">
              {currentTrack.title}
            </h1>
            <p className="truncate text-[15px] text-sage">{currentTrack.artist}</p>
          </div>
          <button
            onClick={() => toggleLike(currentTrack.id)}
            className={`tap-44 mt-1 rounded-full p-1.5 transition-colors ${
              liked ? 'text-pine' : 'text-sage hover:text-cream'
            }`}
            aria-label={liked ? 'Remove from liked songs' : 'Add to liked songs'}
            aria-pressed={liked}
          >
            <Heart size={24} fill={liked ? 'currentColor' : 'none'} />
          </button>
        </div>

        {/* Scrubber */}
        <div className="player-seek px-7 pb-1">
          <input
            type="range"
            className="pesto-range"
            min={0}
            max={Math.max(duration, 1)}
            step={1}
            value={Math.min(shownPosition, duration || shownPosition)}
            style={rangeFill(shownPosition, duration)}
            {...scrubHandlers(scrub)}
            aria-label="Seek"
          />
          <div className="flex justify-between text-xs tabular-nums text-sage">
            <span>{formatDuration(shownPosition)}</span>
            <span>{formatDuration(duration)}</span>
          </div>
        </div>

        {/* Transport controls */}
        <div className="player-transport flex items-center justify-between px-8 pb-5 pt-2">
          <button
            onClick={toggleShuffle}
            className={`tap-44 p-2 transition-colors ${shuffle ? 'text-pesto' : 'text-sage hover:text-cream'}`}
            aria-label="Toggle shuffle"
            aria-pressed={shuffle}
          >
            <Shuffle size={22} />
          </button>
          <button
            onClick={previous}
            className="p-2 text-cream transition-transform hover:scale-110"
            aria-label="Previous track"
          >
            <SkipBack size={30} fill="currentColor" />
          </button>
          <button
            onClick={togglePlay}
            className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-pesto text-basil-950 shadow-xl shadow-pesto/20 transition-colors hover:bg-pesto-bright"
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause size={32} fill="currentColor" />
            ) : (
              <Play size={32} fill="currentColor" className="ml-1" />
            )}
          </button>
          <button
            onClick={next}
            className="p-2 text-cream transition-transform hover:scale-110"
            aria-label="Next track"
          >
            <SkipForward size={30} fill="currentColor" />
          </button>
          <button
            onClick={toggleRepeat}
            className={`tap-44 p-2 transition-colors ${
              repeat !== 'off' ? 'text-pesto' : 'text-sage hover:text-cream'
            }`}
            aria-label={`Repeat: ${repeat}`}
          >
            {repeat === 'one' ? <Repeat1 size={22} /> : <Repeat size={22} />}
          </button>
        </div>

        {/* Volume */}
        <div className="player-volume flex items-center gap-3 px-8 pb-10">
          <Volume2 size={18} className="shrink-0 text-sage" aria-hidden />
          <input
            type="range"
            className="pesto-range"
            min={0}
            max={100}
            step={1}
            value={shownVolume}
            style={rangeFill(shownVolume, 100)}
            {...volumeHandlers(localVolume)}
            aria-label="Volume"
          />
        </div>
      </div>
    </Modal>
  );
}

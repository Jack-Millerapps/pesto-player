import type { Track } from '../services/api';

export interface AudioSnapshot { playing: boolean; position: number; duration: number; loading: boolean }
type AudioPort = Pick<HTMLAudioElement, 'src' | 'currentTime' | 'duration' | 'volume' | 'paused' | 'ended' | 'readyState' | 'load' | 'play' | 'pause' | 'addEventListener' | 'removeEventListener'>;

/** One persistent audio element; all playback state comes from media events. */
export class BrowserAudio {
  private generation = 0;
  private waiting = false;
  private loadedId: string | null = null;
  private listeners: [string, EventListener][] = [];
  constructor(private audio: AudioPort, private onChange: (state: AudioSnapshot) => void, private onEnded: () => void, private onError: (message: string) => void) {
    const listen = (type: string, listener: EventListener) => { audio.addEventListener(type, listener); this.listeners.push([type, listener]); };
    for (const event of ['timeupdate', 'durationchange', 'loadedmetadata', 'play', 'pause', 'seeked', 'volumechange']) listen(event, () => this.publish());
    listen('waiting', () => { this.waiting = true; this.publish(); });
    listen('playing', () => { this.waiting = false; this.publish(); });
    listen('canplay', () => { this.waiting = false; this.publish(); });
    listen('ended', () => { this.publish(); this.onEnded(); });
    listen('error', () => { if (this.loadedId) { this.waiting = false; this.audio.pause(); this.onError('This song couldn’t load. Try playing it again.'); this.publish(); } });
  }
  private publish() {
    this.onChange({ playing: !this.audio.paused && !this.audio.ended, position: this.audio.currentTime || 0, duration: Number.isFinite(this.audio.duration) ? this.audio.duration : 0, loading: this.waiting && !this.audio.paused });
  }
  hasTrack() { return this.loadedId !== null; }
  load(track: Track) {
    this.generation++;
    this.audio.pause();
    this.loadedId = track.id;
    this.audio.src = track.audioUrl || '';
    this.waiting = true;
    this.audio.load();
  }
  play(track?: Track) {
    if (track) this.load(track);
    const generation = this.generation;
    if (!this.loadedId) return;
    this.audio.play().catch((error: Error) => {
      if (generation !== this.generation || error.name === 'AbortError') return;
      this.waiting = false;
      this.onError(error.name === 'NotAllowedError' ? 'Tap Play to allow audio in this browser.' : 'This song couldn’t play. Try again.');
      this.publish();
    });
  }
  pause() { this.generation++; this.audio.pause(); this.waiting = false; this.publish(); }
  seek(position: number) {
    const duration = this.audio.duration;
    if (!Number.isFinite(duration) || duration <= 0) return;
    this.audio.currentTime = Math.max(0, Math.min(position, duration));
    this.publish();
  }
  volume(value: number) { this.audio.volume = Math.max(0, Math.min(value, 100)) / 100; }
  dispose() {
    this.generation++;
    for (const [type, listener] of this.listeners) this.audio.removeEventListener(type, listener);
    this.audio.pause();
    this.audio.src = '';
    this.audio.load();
  }
}

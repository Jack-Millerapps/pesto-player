import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api, PlayerStatus, Track } from '../services/api';
import { demoTracks, upgradeStarterTrack } from '../lib/demo';
import { useFeedback } from '../state/Feedback';
import { visibleQueue } from '../lib/queue';
import { BrowserAudio } from './BrowserAudio';

export type Connection = 'connecting' | 'online' | 'offline';
export type RepeatMode = 'off' | 'all' | 'one';
interface PlayerContextValue {
  connection: Connection; playbackSource: 'browser' | 'device'; buffering: boolean;
  isPlaying: boolean; currentTrack: Track | null; duration: number; volume: number;
  shuffle: boolean; repeat: RepeatMode; battery: PlayerStatus['battery'] | null; queue: Track[]; likes: Set<string>;
  playTrack: (track: Track, context?: Track[]) => void; togglePlay: () => void; next: () => void; previous: () => void;
  seek: (position: number) => void; setVolume: (volume: number) => void; toggleShuffle: () => void; toggleRepeat: () => void;
  toggleLike: (id: string) => void; addToQueue: (track: Track) => void; clearQueue: () => void; reconnect: () => Promise<void>;
}
const PlayerContext = createContext<PlayerContextValue | null>(null);
// Playback position changes 2-4x per second. Keeping it out of the main context means only the
// few components that draw it (mini player bar, full player slider) re-render on each tick instead
// of every song row in a 1,000-song list.
const PositionContext = createContext(0);
// Minimal slice for list rows: they only need to know which song is current and whether it plays.
interface NowPlayingValue { currentId: string | null; isPlaying: boolean; playTrack: PlayerContextValue['playTrack'] }
const NowPlayingContext = createContext<NowPlayingValue | null>(null);
const sameBattery = (a: PlayerStatus['battery'] | null, b: PlayerStatus['battery'] | null) => a === b || (!!a && !!b && a.percentage === b.percentage && a.status === b.status && a.color === b.color);
const LIKES_KEY = 'pesto.likes';
function loadLikes(): Set<string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(LIKES_KEY) || '[]');
    return new Set(Array.isArray(parsed) ? parsed.filter(id => typeof id === 'string').map(id => upgradeStarterTrack({ id } as Track).id) : []);
  } catch { return new Set(); }
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const { notify } = useFeedback();
  const [connection, setConnection] = useState<Connection>('connecting');
  const [playbackSource, setPlaybackSource] = useState<'browser' | 'device'>('browser');
  const [isPlaying, setIsPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(70);
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState<RepeatMode>('off');
  const [battery, setBattery] = useState<PlayerStatus['battery'] | null>(null);
  const [queue, setQueue] = useState<Track[]>([]);
  const [likes, setLikes] = useState(loadLikes);
  const audioElement = useRef<HTMLAudioElement>(null);
  const audio = useRef<BrowserAudio | null>(null);
  const source = useRef<'browser' | 'device'>('browser');
  const state = useRef({ connection, isPlaying, position, volume, shuffle, repeat });
  state.current = { connection, isPlaying, position, volume, shuffle, repeat };
  const browserQueue = useRef<{ tracks: Track[]; index: number; played: Set<number> }>({ tracks: [], index: 0, played: new Set() });
  const advanceRef = useRef<() => void>(() => {});
  const base = useRef({ position: 0, at: 0, duration: 0 });
  const command = useRef<{ until: number; matches: (status: PlayerStatus) => boolean } | null>(null);
  const setSource = useCallback((value: 'browser' | 'device') => { source.current = value; setPlaybackSource(value); }, []);

  useEffect(() => {
    const engine = new BrowserAudio(audioElement.current!, snapshot => {
      if (source.current !== 'browser') return;
      setIsPlaying(snapshot.playing); setPosition(snapshot.position); setBuffering(snapshot.loading);
      if (snapshot.duration > 0) setDuration(snapshot.duration);
    }, () => { if (source.current === 'browser') advanceRef.current(); }, notify);
    engine.volume(state.current.volume);
    audio.current = engine;
    return () => { engine.dispose(); audio.current = null; };
  }, [notify]);

  const applyStatus = useCallback((status: PlayerStatus) => {
    // Socket status arrives every second with fresh objects; keep references stable so context consumers don't re-render.
    setBattery(prev => sameBattery(prev, status.battery ?? null) ? prev : status.battery ?? null);
    // Connecting a device must not interrupt a starter song already playing here.
    if (source.current === 'browser' && audio.current?.hasTrack()) return;
    if (command.current && Date.now() < command.current.until && !command.current.matches(status)) return;
    command.current = null;
    setSource('device'); setIsPlaying(status.isPlaying); setCurrentTrack(prev => prev?.id === status.currentTrack?.id ? prev : status.currentTrack);
    setPosition(status.position); setDuration(status.duration); setVolumeState(status.volume); setBuffering(false);
    if (typeof status.shuffle === 'boolean') setShuffle(status.shuffle);
    if (status.repeat) setRepeat(status.repeat);
    base.current = { position: status.position, at: Date.now(), duration: status.duration };
  }, [setSource]);
  const commandFailed = useCallback(() => {
    command.current = null;
    notify('The player couldn’t complete that action. Check its connection and try again.');
    api.getPlayerStatus().then(applyStatus).catch(() => { if (source.current === 'device') setIsPlaying(false); setConnection('offline'); });
  }, [applyStatus, notify]);
  const reconnect = useCallback(async () => {
    try { const status = await api.getPlayerStatus(); setConnection('online'); applyStatus(status); notify('Player connected'); }
    catch { notify('No player found. The included songs still play right here.'); }
  }, [applyStatus, notify]);
  useEffect(() => {
    const offStatus = api.onStatusUpdate(status => { setConnection('online'); applyStatus(status); });
    const offConnection = api.onConnectionChange(connected => {
      setConnection(connected ? 'online' : 'offline');
      if (connected) api.getPlayerStatus().then(applyStatus).catch(() => {});
      else if (source.current === 'device') setIsPlaying(false);
    });
    api.getPlayerStatus().then(status => { setConnection('online'); applyStatus(status); }).catch(() => setConnection(prev => prev === 'online' ? prev : 'offline'));
    return () => { offStatus(); offConnection(); };
  }, [applyStatus]);
  useEffect(() => {
    if (connection !== 'online' || playbackSource !== 'device') return;
    let cancelled = false;
    api.getQueue().then(({ queue, currentIndex }) => { if (!cancelled) setQueue(queue.slice(Math.max(0, currentIndex))); }).catch(() => {});
    return () => { cancelled = true; };
  }, [connection, playbackSource, currentTrack?.id]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (source.current === 'device' && state.current.isPlaying && base.current.at) {
        setPosition(Math.min(base.current.position + (Date.now() - base.current.at) / 1000, base.current.duration || Infinity));
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, []);

  const startBrowserTrack = useCallback((track: Track) => {
    setSource('browser'); setCurrentTrack(track); setDuration(track.duration); setPosition(0); setIsPlaying(false); setBuffering(true);
    audio.current?.volume(state.current.volume);
    // Called directly from the user's gesture to satisfy mobile autoplay rules.
    audio.current?.play(track);
  }, [setSource]);
  const browserAdvance = useCallback((direction: 1 | -1, automatic = false) => {
    const q = browserQueue.current;
    if (!q.tracks.length) return;
    if (automatic && state.current.repeat === 'one') { audio.current?.seek(0); audio.current?.play(); return; }
    let index = q.index + direction;
    if (direction === 1 && state.current.shuffle && q.tracks.length > 1) {
      let available = q.tracks.map((_, i) => i).filter(i => !q.played.has(i));
      if (!available.length && state.current.repeat === 'all') { q.played = new Set([q.index]); available = q.tracks.map((_, i) => i).filter(i => i !== q.index); }
      index = available.length ? available[Math.floor(Math.random() * available.length)] : q.tracks.length;
    }
    if (index >= q.tracks.length) {
      if (state.current.repeat !== 'all') { audio.current?.pause(); return; }
      index = 0;
    }
    if (index < 0) index = 0;
    q.index = index; q.played.add(index);
    startBrowserTrack(q.tracks[index]);
    setQueue(visibleQueue(q.tracks, index, q.played, state.current.shuffle));
  }, [startBrowserTrack]);
  advanceRef.current = () => browserAdvance(1, true);

  const playTrack = useCallback((input: Track, context?: Track[]) => {
    const track = upgradeStarterTrack(input);
    if (track.audioUrl) {
      const tracks = (context?.length ? context : [track]).map(upgradeStarterTrack).filter(t => t.audioUrl);
      const index = Math.max(0, tracks.findIndex(t => t.id === track.id));
      browserQueue.current = { tracks, index, played: new Set([index]) };
      setQueue(visibleQueue(tracks, index, new Set([index]), state.current.shuffle));
      startBrowserTrack(tracks[index]);
      return;
    }
    if (state.current.connection !== 'online') { notify('Connect your Pesto Player to play this device song.'); return; }
    audio.current?.pause(); setSource('device'); setCurrentTrack(track); setDuration(track.duration); setPosition(0); setIsPlaying(true); setBuffering(false);
    base.current = { position: 0, duration: track.duration, at: Date.now() };
    command.current = { until: Date.now() + 1500, matches: status => status.currentTrack?.id === track.id };
    api.play(track.id, context?.map(t => t.id)).catch(commandFailed);
  }, [startBrowserTrack, setSource, notify, commandFailed]);
  const togglePlay = useCallback(() => {
    if (!currentTrack) { playTrack(demoTracks[0], demoTracks); return; }
    if (source.current === 'device') {
      if (state.current.connection === 'online') api.togglePlay().catch(commandFailed);
      else notify('Reconnect your player to resume this song.');
      return;
    }
    if (state.current.isPlaying) audio.current?.pause(); else audio.current?.play();
  }, [currentTrack, playTrack, commandFailed, notify]);
  const next = useCallback(() => { if (source.current === 'device') api.next().catch(commandFailed); else browserAdvance(1); }, [browserAdvance, commandFailed]);
  const previous = useCallback(() => {
    if (source.current === 'device') api.previous().catch(commandFailed);
    else if (state.current.position > 3) audio.current?.seek(0);
    else browserAdvance(-1);
  }, [browserAdvance, commandFailed]);
  const seek = useCallback((position: number) => {
    if (source.current === 'browser') audio.current?.seek(position);
    else {
      setPosition(position); base.current = { ...base.current, position, at: Date.now() };
      command.current = { until: Date.now() + 1500, matches: status => Math.abs(status.position - position) < 2 };
      api.seek(position).catch(commandFailed);
    }
  }, [commandFailed]);
  const setVolume = useCallback((volume: number) => {
    setVolumeState(volume);
    if (source.current === 'browser') audio.current?.volume(volume);
    else api.setVolume(volume).then(result => setVolumeState(result.volume)).catch(commandFailed);
  }, [commandFailed]);
  const toggleShuffle = useCallback(() => {
    const target = !state.current.shuffle;
    state.current.shuffle = target; setShuffle(target);
    if (source.current === 'device') api.toggleShuffle().catch(commandFailed);
    else { const q = browserQueue.current; q.played = new Set([q.index]); setQueue(visibleQueue(q.tracks, q.index, q.played, target)); }
  }, [commandFailed]);
  const toggleRepeat = useCallback(() => {
    const target = state.current.repeat === 'off' ? 'all' : state.current.repeat === 'all' ? 'one' : 'off';
    state.current.repeat = target; setRepeat(target);
    if (source.current === 'device') api.toggleRepeat().catch(commandFailed);
  }, [commandFailed]);
  useEffect(() => { try { localStorage.setItem(LIKES_KEY, JSON.stringify([...likes])); } catch { notify('Likes are saved for this session only.'); } }, [likes, notify]);
  const toggleLike = useCallback((id: string) => setLikes(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; }), []);
  const addToQueue = useCallback((input: Track) => {
    const track = upgradeStarterTrack(input);
    if (track.audioUrl) {
      if (source.current === 'device' && currentTrack) { notify('Play an included song first to start a browser queue.'); return; }
      const q = browserQueue.current; q.tracks = [...q.tracks, track];
      if (q.tracks.length === 1) { q.index = 0; q.played = new Set([0]); setSource('browser'); setCurrentTrack(track); setDuration(track.duration); audio.current?.load(track); }
      setQueue(visibleQueue(q.tracks, q.index, q.played, state.current.shuffle)); notify('Added to queue');
    } else if (state.current.connection === 'online' && source.current === 'device') {
      api.addToQueue(track.id).then(() => api.getQueue()).then(({ queue, currentIndex }) => { setQueue(queue.slice(Math.max(0, currentIndex))); notify('Added to queue'); }).catch(commandFailed);
    } else notify('Connect to your player and play a device song to use its queue.');
  }, [currentTrack, setSource, notify, commandFailed]);
  const clearQueue = useCallback(() => {
    if (source.current === 'device') { api.clearQueue().then(() => { setQueue([]); notify('Queue cleared'); }).catch(commandFailed); return; }
    const current = browserQueue.current.tracks[browserQueue.current.index];
    browserQueue.current = { tracks: current ? [current] : [], index: 0, played: new Set([0]) };
    setQueue(current ? [current] : []); notify('Upcoming songs cleared');
  }, [commandFailed, notify]);
  const value = useMemo(() => ({ connection, playbackSource, buffering, isPlaying, currentTrack, duration, volume, shuffle, repeat, battery, queue, likes, playTrack, togglePlay, next, previous, seek, setVolume, toggleShuffle, toggleRepeat, toggleLike, addToQueue, clearQueue, reconnect }), [connection, playbackSource, buffering, isPlaying, currentTrack, duration, volume, shuffle, repeat, battery, queue, likes, playTrack, togglePlay, next, previous, seek, setVolume, toggleShuffle, toggleRepeat, toggleLike, addToQueue, clearQueue, reconnect]);
  const currentId = currentTrack?.id ?? null;
  const nowPlaying = useMemo(() => ({ currentId, isPlaying, playTrack }), [currentId, isPlaying, playTrack]);
  return <PlayerContext.Provider value={value}><NowPlayingContext.Provider value={nowPlaying}><PositionContext.Provider value={position}><audio ref={audioElement} preload="metadata" playsInline hidden aria-hidden="true" />{children}</PositionContext.Provider></NowPlayingContext.Provider></PlayerContext.Provider>;
}
export function usePosition(): number { return useContext(PositionContext); }
export function useNowPlaying(): NowPlayingValue {
  const value = useContext(NowPlayingContext);
  if (!value) throw new Error('PlayerProvider is required');
  return value;
}
export function usePlayer(): PlayerContextValue {
  const value = useContext(PlayerContext);
  if (!value) throw new Error('PlayerProvider is required');
  return value;
}

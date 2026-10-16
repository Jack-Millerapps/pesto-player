"""
Audio player for Pesto Player (local files only).

AudioPlayer holds the queue / shuffle / repeat / error logic and talks to a small
Backend object, so the logic is testable without VLC:

- VlcBackend: python-vlc (imported defensively; `vlc` is None if unavailable)
- SimulatedBackend: wall-clock fake used on dev machines with no VLC

create_player() picks VLC when it initialises, otherwise the simulated backend.

Semantics worth knowing (UI authors):
- set_queue(tracks, start_index=0) loads the queue AND starts playing start_index.
- A file that can't be played (missing, corrupt, backend error) calls
  on_error(message) and the player skips to the next track; if every track in a
  row fails it stops instead of looping.
- get_state() returns values cached by update(), which polls the backend at most
  poll_interval (0.2 s = 5 Hz); it is cheap to call every frame.
- Volume, queue, shuffle/repeat and the current track are saved to
  config.STATE_FILE (debounced, atomic) and restored by restore_state(library).
- Output changes (Bluetooth, see hardware/bluetooth.py): pause_for_output_change()
  pauses and makes the next play() reopen the track at the same position (a stream
  whose sink vanished may be dead); reopen_output() does that immediately while
  playing, so a fresh stream lands on the new default sink.
"""

import json
import os
import random
import time

import config

try:
    import vlc
except Exception:  # ImportError, or libvlc missing (OSError/AttributeError)
    vlc = None


# ============================================================================
# BACKENDS
# ============================================================================
class VlcBackend:
    def __init__(self):
        if vlc is None:
            raise RuntimeError("python-vlc / libvlc not available")
        try:  # system service: libpulse needs XDG_RUNTIME_DIR to find PipeWire
            from hardware.bluetooth import ensure_user_audio_env
            ensure_user_audio_env()
        except Exception as e:
            print(f"Audio: could not set up the user audio session env: {e}")
        self._media = None
        self._instance = vlc.Instance("--no-xlib", "--quiet")
        if self._instance is None:
            raise RuntimeError("libvlc instance could not be created")
        self._player = self._instance.media_player_new()

    def load(self, path, duration_hint=None):
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return False
        self._media = self._instance.media_new(path)
        self._player.set_media(self._media)
        return True

    def set_start(self, seconds):
        """Start the loaded media at `seconds` (must be called before play())."""
        if self._media is not None and seconds > 0:
            self._media.add_option(":start-time=%.2f" % seconds)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.set_pause(1)

    def resume(self):
        self._player.set_pause(0)

    def stop(self):
        self._player.stop()

    def state(self):
        s = self._player.get_state()
        S = vlc.State
        if s == S.Playing:
            return "playing"
        if s == S.Paused:
            return "paused"
        if s == S.Ended:
            return "ended"
        if s == S.Error:
            return "error"
        if s in (S.Opening, S.Buffering):
            return "opening"
        return "stopped"

    def time_s(self):
        t = self._player.get_time()
        return t / 1000.0 if t and t > 0 else 0.0

    def length_s(self):
        n = self._player.get_length()
        return n / 1000.0 if n and n > 0 else 0.0

    def set_fraction(self, f):
        self._player.set_position(f)

    def set_volume(self, v):
        self._player.audio_set_volume(int(v))

    def release(self):
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass


class SimulatedBackend:
    """Pretends to play: position follows the clock, ends at the duration."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._state = "stopped"
        self._length = 180.0
        self._base = 0.0      # position when last (re)started / paused
        self._started = 0.0

    def load(self, path, duration_hint=None):
        self._length = float(duration_hint) if duration_hint else 180.0
        self._base = 0.0
        self._state = "stopped"
        return True

    def set_start(self, seconds):
        self._base = max(0.0, min(self._length, float(seconds)))

    def play(self):
        self._started = self._clock()
        self._state = "playing"

    def pause(self):
        if self._state == "playing":
            self._base = self.time_s()
            self._state = "paused"

    def resume(self):
        if self._state == "paused":
            self._started = self._clock()
            self._state = "playing"

    def stop(self):
        self._state = "stopped"
        self._base = 0.0

    def state(self):
        if self._state == "playing" and self.time_s() >= self._length:
            self._state = "ended"
        return self._state

    def time_s(self):
        if self._state == "playing":
            return min(self._length, self._base + self._clock() - self._started)
        return self._base

    def length_s(self):
        return self._length

    def set_fraction(self, f):
        self._base = f * self._length
        self._started = self._clock()

    def set_volume(self, v):
        pass

    def release(self):
        pass


# ============================================================================
# AUDIO PLAYER
# ============================================================================
class AudioPlayer:
    def __init__(self, backend=None, rng=None):
        self._backend = backend if backend is not None else VlcBackend()
        self._rng = rng or random.Random()
        self.poll_interval = 0.2
        self.save_interval = 5.0

        self._queue = []
        self._order = []      # play order as indices into _queue
        self._pos = -1        # position within _order; -1 = nothing loaded
        self._playing = False
        self._loaded = False
        self._ended = False   # queue ran out; next play() should pick up newly added tracks
        self._reopen = False  # audio output changed while paused: reload on next play()
        self._shuffle = False
        self._repeat = "off"
        self._volume = config.VOLUME_DEFAULT
        self._backend.set_volume(self._volume)

        self._cache = {"position": 0.0, "duration": 0.0}
        self._last_poll = 0.0
        self._dirty = False
        self._last_save = time.time()

        self.on_error = None
        self.on_track_change = None
        self.on_playback_state_change = None
        # Callables run from update() (main thread, ~5 Hz, also while the screen is
        # asleep). ui/bluetooth.py uses one to pause when a BT speaker drops.
        self.tick_hooks = []

    # ---------------------------------------------------------- properties
    @property
    def shuffle(self):
        return self._shuffle

    @shuffle.setter
    def shuffle(self, value):
        value = bool(value)
        if value != self._shuffle:
            self._shuffle = value
            self._rebuild_order()
            self._dirty = True

    @property
    def repeat(self):
        return self._repeat

    @repeat.setter
    def repeat(self, value):
        if value in ("off", "all", "one"):
            self._repeat = value
            self._dirty = True

    # --------------------------------------------------------------- state
    @property
    def _cur_index(self):
        if 0 <= self._pos < len(self._order):
            return self._order[self._pos]
        return -1

    def _current(self):
        i = self._cur_index
        return self._queue[i] if 0 <= i < len(self._queue) else None

    def get_state(self):
        track = self._current()
        dur = (track or {}).get("duration") or self._cache["duration"] or 0.0
        return {
            "track": track,
            "playing": self._playing,
            "position": self._cache["position"],
            "duration": float(dur),
            "volume": self._volume,
            "shuffle": self._shuffle,
            "repeat": self._repeat,
            "queue_index": self._cur_index,
        }

    def get_queue(self):
        return list(self._queue)

    # ------------------------------------------------------- order helpers
    def _rebuild_order(self):
        """Recompute play order, keeping the current track current."""
        n = len(self._queue)
        cur = self._cur_index
        if not self._shuffle:
            self._order = list(range(n))
            self._pos = cur if cur >= 0 else -1
            return
        rest = [i for i in range(n) if i != cur]
        self._rng.shuffle(rest)
        if cur >= 0:
            self._order = [cur] + rest
            self._pos = 0
        else:
            self._order = rest
            self._pos = -1

    # --------------------------------------------------------------- queue
    def set_queue(self, tracks, start_index=0):
        self._queue = list(tracks)
        self._order, self._pos = [], -1
        self._loaded = False
        if not self._queue:
            self._stop_backend()
            self._dirty = True
            return
        start = max(0, min(start_index, len(self._queue) - 1))
        self._pos = start  # temporary: identity order so _rebuild keeps `start`
        self._order = list(range(len(self._queue)))
        self._rebuild_order()
        self._dirty = True
        self._start_current(direction=1)

    def enqueue(self, track):
        self._queue.append(track)
        if self._cur_index >= 0 or not self._order:
            self._order.append(len(self._queue) - 1)
        if self._ended and not self._playing:
            self._pos = len(self._order) - 1   # play() now starts the new track
            self._ended = False
        self._dirty = True

    def play_next(self, track):
        if self._pos < 0:
            self._queue.append(track)
            self._order.append(len(self._queue) - 1)
            self._dirty = True
            return
        cur = self._cur_index
        self._queue.insert(cur + 1, track)
        self._order = [i + 1 if i > cur else i for i in self._order]
        self._order.insert(self._pos + 1, cur + 1)
        if self._ended and not self._playing:
            self._pos += 1
            self._ended = False
        self._dirty = True

    def remove_from_queue(self, index):
        if not 0 <= index < len(self._queue):
            return
        cur = self._cur_index
        removing_current = index == cur
        was_playing = self._playing
        self._queue.pop(index)
        old_pos = self._pos
        new_order = []
        for pos, i in enumerate(self._order):
            if i == index:
                if pos < old_pos:
                    old_pos -= 1
                elif pos == old_pos:
                    pass
                continue
            new_order.append(i - 1 if i > index else i)
        self._order = new_order
        self._dirty = True
        if removing_current:
            if not self._order:
                self._pos = -1
                self._stop_backend()
                return
            self._pos = min(old_pos, len(self._order) - 1)
            self._loaded = False
            if was_playing:
                self._start_current(direction=1)
            else:
                self._playing = False
        else:
            self._pos = old_pos

    def move_in_queue(self, src, dst):
        n = len(self._queue)
        if not (0 <= src < n and 0 <= dst < n) or src == dst:
            return
        item = self._queue.pop(src)
        self._queue.insert(dst, item)

        def remap(i):
            if i == src:
                return dst
            if src < dst and src < i <= dst:
                return i - 1
            if dst < src and dst <= i < src:
                return i + 1
            return i

        self._order = [remap(i) for i in self._order]
        self._dirty = True

    # ------------------------------------------------------------ playback
    def _start_current(self, direction=1, failures=0, start_s=0.0):
        """Load and play the track at self._pos (from start_s seconds); on failure
        skip in `direction`."""
        track = self._current()
        if track is None:
            self._stop_backend()
            return False
        ok = False
        try:
            ok = self._backend.load(track.get("path") or "", track.get("duration"))
        except Exception as e:
            print(f"Audio: load error: {e}")
        if not ok:
            self._report(f"Can't play: {track.get('title') or track.get('path')}")
            return self._skip_failed(direction, failures + 1)
        if start_s > 0 and hasattr(self._backend, "set_start"):
            try:
                self._backend.set_start(start_s)
            except Exception as e:
                print(f"Audio: set_start error: {e}")
                start_s = 0.0
        else:
            start_s = 0.0
        self._reopen = False
        try:
            self._backend.play()
        except Exception as e:
            print(f"Audio: play error: {e}")
            self._report(f"Can't play: {track.get('title')}")
            return self._skip_failed(direction, failures + 1)
        self._loaded = True
        self._ended = False
        self._set_playing(True)
        self._cache = {"position": float(start_s), "duration": track.get("duration") or 0.0}
        self._last_poll = 0.0
        self._dirty = True
        if self.on_track_change and not start_s:
            self.on_track_change(track)
        return True

    def _skip_failed(self, direction, failures):
        if failures >= len(self._queue):
            self._stop_backend()
            return False
        nxt = self._pos + direction
        if 0 <= nxt < len(self._order):
            self._pos = nxt
        elif self._repeat == "all" and self._order:
            self._pos = 0 if direction > 0 else len(self._order) - 1
        else:
            self._stop_backend()
            return False
        return self._start_current(direction, failures)

    def _stop_backend(self):
        try:
            self._backend.stop()
        except Exception:
            pass
        self._loaded = False
        self._cache["position"] = 0.0
        self._set_playing(False)

    def _set_playing(self, value):
        if value != self._playing:
            self._playing = value
            if self.on_playback_state_change:
                self.on_playback_state_change(value)

    def _report(self, message):
        print(f"Audio: {message}")
        if self.on_error:
            try:
                self.on_error(message)
            except Exception as e:
                print(f"Audio: on_error callback failed: {e}")

    def play(self):
        if not self._queue:
            return
        if self._pos < 0:
            self._pos = 0 if self._order else -1
        if self._pos < 0:
            return
        if self._reopen and self._loaded:
            self._start_current(start_s=self._cache.get("position", 0.0))
            return
        if self._loaded and self._backend.state() not in ("ended", "error", "stopped"):
            if hasattr(self._backend, "resume"):
                self._backend.resume()
            else:
                self._backend.play()
            self._set_playing(True)
        else:
            self._start_current()

    def pause(self):
        if self._playing:
            self._backend.pause()
            self._poll(force=True)
            self._set_playing(False)
            self._dirty = True

    def pause_for_output_change(self):
        """The audio device went away (e.g. Bluetooth speaker dropped): pause, and
        reopen the stream at the same spot on the next play()."""
        was = self._playing
        if was:
            self.pause()
        if self._loaded:
            self._reopen = True
        return was

    def reopen_output(self):
        """Restart the current track at the current position so the new stream
        opens on the (new) default output. No-op unless playing."""
        if not (self._playing and self._loaded):
            return False
        self._poll(force=True)
        return self._start_current(start_s=self._cache.get("position", 0.0))

    def toggle(self):
        if self._playing:
            self.pause()
        else:
            self.play()

    def _advance(self, auto):
        """Move to the next track. auto=True when a track ended by itself."""
        if not self._order:
            return
        if auto and self._repeat == "one":
            self._start_current()
            return
        nxt = self._pos + 1
        if nxt < len(self._order):
            self._pos = nxt
            self._start_current(direction=1)
        elif self._repeat == "all":
            if self._shuffle:
                self._rebuild_order_wrap()
            self._pos = 0
            self._start_current(direction=1)
        else:
            self._stop_backend()  # end of queue: stay on last track, stopped
            self._ended = True

    def _rebuild_order_wrap(self):
        n = len(self._queue)
        self._order = list(range(n))
        self._rng.shuffle(self._order)

    def next(self):
        self._advance(auto=False)

    def prev(self):
        if not self._order:
            return
        self._poll(force=True)
        if self._cache["position"] > 3.0 or self._pos <= 0 and self._repeat != "all":
            self.seek(0.0)
            return
        if self._pos <= 0:
            self._pos = len(self._order) - 1
        else:
            self._pos -= 1
        self._start_current(direction=-1)

    def seek(self, fraction):
        if not self._loaded and self._cur_index < 0:
            return
        fraction = max(0.0, min(1.0, float(fraction)))
        try:
            self._backend.set_fraction(fraction)
        except Exception as e:
            print(f"Audio: seek error: {e}")
            return
        dur = self.get_state()["duration"] or self._backend.length_s()
        self._cache["position"] = fraction * dur

    def set_volume(self, volume):
        self._volume = int(max(config.VOLUME_MIN, min(config.VOLUME_MAX, volume)))
        self._backend.set_volume(self._volume)
        self._dirty = True

    def volume_up(self):
        self.set_volume(self._volume + config.VOLUME_STEP)

    def volume_down(self):
        self.set_volume(self._volume - config.VOLUME_STEP)

    def get_volume(self):
        return self._volume

    # --------------------------------------------------------------- update
    def _poll(self, force=False):
        now = time.time()
        if not force and now - self._last_poll < self.poll_interval:
            return False
        self._last_poll = now
        if self._loaded:
            self._cache["position"] = self._backend.time_s()
            length = self._backend.length_s()
            if length:
                self._cache["duration"] = length
        return True

    def update(self):
        """Call every frame; real work happens at most every poll_interval."""
        if not self._poll():
            return
        for fn in list(self.tick_hooks):
            try:
                fn()
            except Exception as e:
                print(f"Audio: tick hook failed: {type(e).__name__}: {e}")
        if self._loaded and self._playing:
            st = self._backend.state()
            if st == "ended":
                self._advance(auto=True)
            elif st == "error":
                track = self._current()
                self._report(f"Playback error: {(track or {}).get('title', 'track')}")
                self._skip_current_after_error()
        if self._dirty and time.time() - self._last_save >= self.save_interval:
            self.save_state()

    def _skip_current_after_error(self):
        nxt = self._pos + 1
        if nxt < len(self._order):
            self._pos = nxt
            self._start_current(direction=1, failures=1)
        elif self._repeat == "all" and len(self._order) > 1:
            self._pos = 0
            self._start_current(direction=1, failures=1)
        else:
            self._stop_backend()

    # ---------------------------------------------------------- persistence
    def save_state(self):
        track = self._current()
        data = {
            "volume": self._volume,
            "shuffle": self._shuffle,
            "repeat": self._repeat,
            "queue": [t.get("path") for t in self._queue],
            "index": self._cur_index,
            "last_track": (track or {}).get("path"),
        }
        try:
            os.makedirs(os.path.dirname(config.STATE_FILE), exist_ok=True)
            tmp = config.STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, config.STATE_FILE)
            self._dirty = False
        except OSError as e:
            print(f"Audio: could not save state: {e}")
        self._last_save = time.time()

    def restore_state(self, library):
        """Restore volume/queue/last track (paused). Tracks no longer in the
        library are dropped. Safe on missing or corrupt state."""
        try:
            with open(config.STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
        except (OSError, ValueError):
            return
        try:
            self.set_volume(data.get("volume", self._volume))
            self.repeat = data.get("repeat", "off")
            by_path = {t["path"]: t for t in library.get_tracks()}
            paths = [p for p in data.get("queue", []) if isinstance(p, str)]
            last = data.get("last_track")
            queue = [by_path[p] for p in paths if p in by_path]
            if not queue:
                self._shuffle = bool(data.get("shuffle"))
                return
            self._queue = queue
            self._shuffle = False
            self._order = list(range(len(queue)))
            idx = next((i for i, t in enumerate(queue) if t["path"] == last), 0)
            self._pos = idx
            self.shuffle = bool(data.get("shuffle"))
            self._loaded = False
            self._playing = False
            self._dirty = False
        except Exception as e:
            print(f"Audio: restore failed: {e}")

    # -------------------------------------------------------------- cleanup
    def cleanup(self):
        self.save_state()
        try:
            self._backend.release()
        except Exception:
            pass


class MockAudioPlayer(AudioPlayer):
    """AudioPlayer on the simulated backend (no VLC needed)."""

    def __init__(self):
        super().__init__(backend=SimulatedBackend())


def create_player():
    """VLC-backed player if python-vlc + libvlc work, otherwise the simulated one."""
    try:
        return AudioPlayer(backend=VlcBackend())
    except Exception as e:
        print(f"Audio: VLC unavailable ({e}); using simulated playback")
        return MockAudioPlayer()

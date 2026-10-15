import json
import random

import pytest

from player import audio as audiomod
from player.audio import AudioPlayer, SimulatedBackend, create_player
from conftest import make_track


class FakeBackend:
    """Scriptable backend: tests flip `st` to 'ended'/'error'."""

    def __init__(self):
        self.st = "stopped"
        self.t = 0.0
        self.length = 100.0
        self.loaded = []
        self.bad = set()
        self.vol = None
        self.frac = None

    def load(self, path, duration_hint=None):
        self.loaded.append(path)
        return path not in self.bad

    def play(self):
        self.st = "playing"

    def pause(self):
        self.st = "paused"

    def stop(self):
        self.st = "stopped"

    def state(self):
        return self.st

    def time_s(self):
        return self.t

    def length_s(self):
        return self.length

    def set_fraction(self, f):
        self.frac = f
        self.t = f * self.length

    def set_volume(self, v):
        self.vol = v

    def release(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(audiomod.config, "STATE_FILE", str(tmp_path / "state.json"))
    be = FakeBackend()
    p = AudioPlayer(backend=be, rng=random.Random(1))
    p.poll_interval = 0
    errs = []
    p.on_error = errs.append
    return p, be, errs


def tr(n):
    return make_track(f"T{n}", path=f"/m/{n}.mp3")


def test_set_queue_starts_at_index(env):
    p, be, _ = env
    q = [tr(i) for i in range(4)]
    p.set_queue(q, start_index=2)
    s = p.get_state()
    assert s["playing"] and s["queue_index"] == 2 and s["track"]["path"] == "/m/2.mp3"
    assert be.loaded[-1] == "/m/2.mp3"


def test_empty_queue_is_safe(env):
    p, be, _ = env
    p.next(); p.prev(); p.toggle(); p.play(); p.seek(0.5)
    s = p.get_state()
    assert s["track"] is None and not s["playing"] and s["queue_index"] == -1
    assert p.get_queue() == []


def test_auto_advance_and_stop_at_end(env):
    p, be, _ = env
    p.set_queue([tr(0), tr(1)])
    be.st = "ended"; p.update()
    assert p.get_state()["queue_index"] == 1 and p.get_state()["playing"]
    be.st = "ended"; p.update()
    s = p.get_state()
    assert not s["playing"] and s["queue_index"] == 1  # stays on last, stopped


def test_repeat_all_wraps_and_repeat_one_replays(env):
    p, be, _ = env
    p.set_queue([tr(0), tr(1)], start_index=1)
    p.repeat = "all"
    be.st = "ended"; p.update()
    assert p.get_state()["queue_index"] == 0 and p.get_state()["playing"]
    p.repeat = "one"
    be.st = "ended"; p.update()
    assert p.get_state()["queue_index"] == 0
    p.next()  # manual next ignores repeat-one
    assert p.get_state()["queue_index"] == 1


def test_prev_restarts_when_past_3s_else_goes_back(env):
    p, be, _ = env
    p.set_queue([tr(0), tr(1), tr(2)], start_index=1)
    be.t = 10; p.prev()
    assert p.get_state()["queue_index"] == 1 and be.frac == 0
    be.t = 1; p.prev()
    assert p.get_state()["queue_index"] == 0


def test_shuffle_visits_every_track_once(env):
    p, be, _ = env
    p.shuffle = True
    p.set_queue([tr(i) for i in range(6)], start_index=3)
    seen = [p.get_state()["queue_index"]]
    assert seen[0] == 3
    for _ in range(5):
        p.next()
        seen.append(p.get_state()["queue_index"])
    assert sorted(seen) == list(range(6))
    p.next()  # end of shuffled order, repeat off: stops
    assert not p.get_state()["playing"]


def test_unplayable_file_toasts_and_skips(env):
    p, be, errs = env
    be.bad.add("/m/1.mp3")
    p.set_queue([tr(0), tr(1), tr(2)])
    p.next()
    assert p.get_state()["queue_index"] == 2 and p.get_state()["playing"]
    assert len(errs) == 1 and "T1" in errs[0]


def test_backend_error_state_skips(env):
    p, be, errs = env
    p.set_queue([tr(0), tr(1)])
    be.st = "error"; p.update()
    assert p.get_state()["queue_index"] == 1 and errs


def test_all_bad_does_not_loop_forever(env):
    p, be, errs = env
    for i in range(3):
        be.bad.add(f"/m/{i}.mp3")
    p.repeat = "all"
    p.set_queue([tr(0), tr(1), tr(2)])
    assert not p.get_state()["playing"]
    assert len(errs) >= 1


def test_queue_edits(env):
    p, be, _ = env
    q = [tr(i) for i in range(4)]
    p.set_queue(q, start_index=1)
    p.enqueue(tr(9))
    assert p.get_queue()[-1]["path"] == "/m/9.mp3"
    p.play_next(tr(8))
    assert p.get_queue()[2]["path"] == "/m/8.mp3"
    p.move_in_queue(2, 0)
    assert p.get_queue()[0]["path"] == "/m/8.mp3"
    assert p.get_state()["track"]["path"] == "/m/1.mp3"
    assert p.get_state()["queue_index"] == 2  # current track followed the move
    p.remove_from_queue(0)
    assert p.get_state()["queue_index"] == 1 and p.get_state()["track"]["path"] == "/m/1.mp3"
    p.remove_from_queue(1)  # removing the playing track advances
    assert p.get_state()["track"]["path"] != "/m/1.mp3"


def test_seek_volume_clamp(env):
    p, be, _ = env
    p.set_queue([tr(0)])
    p.seek(2.0); assert be.frac == 1.0
    p.seek(-1); assert be.frac == 0.0
    p.set_volume(150); assert p.get_state()["volume"] == 100 and be.vol == 100
    p.set_volume(-5); assert p.get_state()["volume"] == 0


def test_toggle_pause_resume(env):
    p, be, _ = env
    p.set_queue([tr(0)])
    p.toggle(); assert be.st == "paused" and not p.get_state()["playing"]
    p.toggle(); assert be.st == "playing" and p.get_state()["playing"]


def test_state_persists_and_restores(env, tmp_path):
    p, be, _ = env
    q = [tr(i) for i in range(3)]
    p.set_queue(q, start_index=2)
    p.set_volume(33)
    p.repeat = "all"
    p.shuffle = False
    p.save_state()
    data = json.load(open(audiomod.config.STATE_FILE))
    assert data["volume"] == 33 and data["queue"] == ["/m/0.mp3", "/m/1.mp3", "/m/2.mp3"]

    class Lib:
        def get_tracks(self):
            return q[:2] + [tr(2)]

    p2 = AudioPlayer(backend=FakeBackend())
    p2.restore_state(Lib())
    s = p2.get_state()
    assert s["volume"] == 33 and s["repeat"] == "all" and s["queue_index"] == 2
    assert not s["playing"] and len(p2.get_queue()) == 3


def test_restore_ignores_corrupt_or_missing(env):
    p, _, _ = env
    open(audiomod.config.STATE_FILE, "w").write("{oops")
    p.restore_state(type("L", (), {"get_tracks": lambda s: []})())
    assert p.get_queue() == []


def test_vlc_import_failure_falls_back_to_simulated(monkeypatch):
    monkeypatch.setattr(audiomod, "vlc", None)
    pl = create_player()
    assert isinstance(pl._backend, SimulatedBackend)


def test_simulated_backend_plays_and_ends():
    clock = [0.0]
    b = SimulatedBackend(clock=lambda: clock[0])
    assert b.load("/mock/x.mp3", duration_hint=10)
    b.play(); clock[0] = 4; assert b.time_s() == 4 and b.state() == "playing"
    clock[0] = 11; assert b.state() == "ended"


def test_enqueue_after_queue_ended_plays_new_track(env):
    p, be, _ = env
    p.set_queue([tr(0), tr(1)], start_index=1)
    be.st = "ended"; p.update()
    assert not p.get_state()["playing"]
    p.enqueue(tr(7))
    p.play()
    assert p.get_state()["track"]["path"] == "/m/7.mp3" and p.get_state()["playing"]


def test_play_next_after_queue_ended_plays_it(env):
    p, be, _ = env
    p.set_queue([tr(0)])
    be.st = "ended"; p.update()
    p.play_next(tr(5))
    p.play()
    assert p.get_state()["track"]["path"] == "/m/5.mp3"

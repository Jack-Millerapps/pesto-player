import json
import os
import time

import pygame
import pytest

import config
import main as mainmod
from player.prefs import Prefs
from ui import add_music
from hardware import system
from ui.add_music import AddMusicScreen, qr_surface, read_uploader_info
from ui.settings import SettingsScreen, ROWS


class FakeSM:
    def __init__(self):
        self.toasts, self.sheets = [], []

    def toast(self, m, kind="info"):
        self.toasts.append((m, kind))

    def show_sheet(self, actions):
        self.sheets.append(actions)

    def show(self, *a, **k):
        pass

    def push(self, *a, **k):
        pass

    def pop(self):
        return True


class FakeLib:
    def __init__(self):
        self.scans = 0
        self.scanning = False
        self.cb = None

    def start_scan(self, on_progress=None, on_done=None):
        self.scans += 1
        self.scanning = True
        self.cb = (on_progress, on_done)

    def finish(self):
        self.scanning = False
        self.cb[1]()

    def is_scanning(self):
        return self.scanning

    def get_tracks(self):
        return [1, 2, 3]


class FakeNet:
    ip, ssid = "10.0.0.5", "Home"

    def refresh(self):
        pass


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((320, 480))


def make_add(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIRTY_FLAG", str(tmp_path / "library.dirty"))
    monkeypatch.setattr(config, "UPLOADER_INFO_FILE", str(tmp_path / "uploader.json"))
    monkeypatch.setattr(add_music.config, "MUSIC_DIRECTORY", str(tmp_path))
    (tmp_path / "uploader.json").write_text(json.dumps({"token": "TOK", "port": 8080}))
    lib = FakeLib()
    s = AddMusicScreen(FakeSM(), None, lib, FakeNet())
    return s, lib


def test_url_contains_token_and_qr_renders(tmp_path, monkeypatch):
    s, _ = make_add(tmp_path, monkeypatch)
    s.on_enter()
    s.update(1.0)
    assert s.build_url() == "http://10.0.0.5:8080/?t=TOK"
    assert s._qr is not None and s._qr.get_width() <= 160
    s.draw(pygame.display.get_surface())
    assert qr_surface("") is None


def test_uploader_not_running_shows_status(tmp_path, monkeypatch):
    s, _ = make_add(tmp_path, monkeypatch)
    os.remove(str(tmp_path / "uploader.json"))
    s.update(1.0)
    assert "isn't running" in s.status and s._qr is None
    assert read_uploader_info(str(tmp_path / "nope"))[0] is None
    s.draw(pygame.display.get_surface())


def test_dirty_flag_triggers_one_rescan_per_batch(tmp_path, monkeypatch):
    s, lib = make_add(tmp_path, monkeypatch)
    s.update(1.0)
    assert lib.scans == 0                       # nothing uploaded yet
    flag = tmp_path / "library.dirty"
    flag.write_text("")
    os.utime(str(flag), (time.time() + 5, time.time() + 5))
    s.update(1.0)
    assert lib.scans == 1
    s.update(1.0); s.update(1.0)
    assert lib.scans == 1                       # same batch, no repeat while scanning
    lib.finish()
    s.update(1.0)
    assert lib.scans == 1 and "Library updated: 3" in s.status
    os.utime(str(flag), (time.time() + 10, time.time() + 10))   # second batch
    s.update(1.0)
    assert lib.scans == 2


def test_upload_during_scan_rescans_after(tmp_path, monkeypatch):
    s, lib = make_add(tmp_path, monkeypatch)
    s.rescan()
    flag = tmp_path / "library.dirty"
    flag.write_text("")
    os.utime(str(flag), (time.time() + 5, time.time() + 5))
    s.update(1.0)
    assert lib.scans == 1                       # deferred while scanning
    lib.finish()
    s.update(1.0)
    assert lib.scans == 2


def make_settings(tmp_path, audio=None):
    from player.audio import MockAudioPlayer
    sm = FakeSM()
    hooks = {"shutdown": lambda: None, "exit": lambda: None, "restart": lambda: None}
    a = audio or MockAudioPlayer()
    s = SettingsScreen(sm, a, FakeLib(), Prefs(str(tmp_path / "p.json")), hooks, None, None, FakeNet())
    return s, sm, a


def tap(s, key, x=200):
    item = next(r for r in ROWS if r[0] == key)
    s._down_pos = (x, 0)
    s._on_tap(item, ROWS.index(item))


def test_settings_controls_change_state(tmp_path):
    s, sm, a = make_settings(tmp_path)
    tap(s, "volume", x=130); assert a.get_volume() == 0
    tap(s, "volume", x=300); assert a.get_volume() == 100
    tap(s, "shuffle"); assert a.shuffle is True
    tap(s, "repeat"); assert a.repeat == "all"
    tap(s, "repeat"); tap(s, "repeat"); assert a.repeat == "off"
    t0 = s.prefs.screen_timeout
    tap(s, "timeout"); assert s.prefs.screen_timeout != t0
    assert json.load(open(str(tmp_path / "p.json")))["screen_timeout"] == s.prefs.screen_timeout
    tap(s, "sleep"); assert s.prefs.sleep_timer_min == 15
    assert s.value_text("battery") == "No sensor"


def test_settings_danger_rows_need_confirm_sheet(tmp_path):
    s, sm, _ = make_settings(tmp_path)
    called = []
    s.hooks["shutdown"] = lambda: called.append(1)
    tap(s, "shutdown")
    assert called == [] and len(sm.sheets) == 1
    sm.sheets[0][0][1]()
    assert called == [1]


def test_settings_rescan_row(tmp_path):
    s, sm, _ = make_settings(tmp_path)
    tap(s, "rescan")
    assert s.library.scans == 1 and s.value_text("rescan") == "Scanning..."
    tap(s, "rescan"); assert s.library.scans == 1
    s.library.finish()
    assert s.value_text("rescan") == "3 songs"


def test_prefs_sleep_timer_expires_once():
    now = [1000.0]
    p = Prefs("/nonexistent-dir/x.json", clock=lambda: now[0])
    p.cycle_sleep_timer()
    assert p.sleep_timer_remaining() == 15 * 60 and not p.sleep_timer_expired()
    now[0] += 15 * 60
    assert p.sleep_timer_expired() and not p.sleep_timer_expired()
    assert p.sleep_timer_remaining() is None


def test_volume_label_tap_does_not_mute_and_draw_uses_cache(tmp_path, monkeypatch):
    s, sm, a = make_settings(tmp_path)
    a.set_volume(60)
    tap(s, "volume", x=20)
    assert a.get_volume() == 60
    s._refresh()
    calls = []
    monkeypatch.setattr(s, "_state", lambda: calls.append(1) or {})
    monkeypatch.setattr(type(s), "value_text", lambda self, k: calls.append(1) or "")
    surf = pygame.display.get_surface()
    for _ in range(3):
        s.draw(surf)
    assert calls == []        # drawing never recomputes state / disk usage


def test_url_is_wrapped_not_truncated_and_caption_matches_case():
    url = "http://192.168.100.100:8080/?t=" + "A1b2C3d4E5f6G7h8I9j0Kl"
    lines = add_music.wrap_chars(url, 12, 296)
    assert "".join(lines) == url and 1 <= len(lines) <= 2
    from ui import text_cache
    assert all(text_cache.text_width(l, 12) <= 296 for l in lines)
    assert "Scan" in add_music.caption_for(True, "10.0.0.5")
    assert "Wi-Fi" in add_music.caption_for(False, None).split("(")[0]
    c = add_music.caption_for(False, "10.0.0.5")
    assert "Connect to Wi-Fi" not in c and "Uploader" in c


class _R:
    def __init__(self, out, rc=0):
        self.stdout, self.returncode = out, rc


def test_get_tailscale_ip_parses_and_guards():
    assert system.get_tailscale_ip(lambda *a, **k: _R("100.101.102.103\n")) == "100.101.102.103"
    ipout = "5: tailscale0    inet 100.64.1.2/32 scope global tailscale0"
    assert system.get_tailscale_ip(lambda c, **k: _R(ipout) if c[0] == "ip" else _R("", 1)) == "100.64.1.2"
    assert system.get_tailscale_ip(lambda *a, **k: _R("192.168.1.9\n")) is None   # not CGNAT
    assert system.get_tailscale_ip(lambda *a, **k: _R("100.128.0.1\n")) is None   # just outside /10

    def boom(*a, **k):
        raise FileNotFoundError("tailscale")
    assert system.get_tailscale_ip(boom) is None


class FakeTsNet(FakeNet):
    ts_ip = "100.101.102.103"


def test_toggle_between_home_and_tailscale(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIRTY_FLAG", str(tmp_path / "library.dirty"))
    monkeypatch.setattr(config, "UPLOADER_INFO_FILE", str(tmp_path / "uploader.json"))
    monkeypatch.setattr(add_music.config, "MUSIC_DIRECTORY", str(tmp_path))
    (tmp_path / "uploader.json").write_text(json.dumps({"token": "TOK", "port": 8080}))
    s = AddMusicScreen(FakeSM(), None, FakeLib(), FakeTsNet())
    s.on_enter(); s.update(1.0)
    assert s.mode_btn.enabled and s._qr_url == "http://10.0.0.5:8080/?t=TOK"
    s.mode_btn.handle_touch(s.mode_btn.rect.center, "down")
    s.mode_btn.handle_touch(s.mode_btn.rect.center, "up")
    s.update(1.0)
    assert s.anywhere and s._qr_url == "http://100.101.102.103:8080/?t=TOK" and s._qr is not None
    assert s.mode_btn.text == "Anywhere"
    assert "any network" in add_music.caption_for(True, "x", True)
    s.draw(pygame.display.get_surface())
    s.net.ts_ip = None                          # Tailscale went away: fall back to LAN
    s.update(1.0)
    assert not s.anywhere and not s.mode_btn.enabled and s._qr_url == "http://10.0.0.5:8080/?t=TOK"
    s.draw(pygame.display.get_surface())


def test_no_tailscale_hides_toggle(tmp_path, monkeypatch):
    s, _ = make_add(tmp_path, monkeypatch)       # FakeNet has no ts_ip attribute at all
    s.on_enter(); s.update(1.0)
    assert not s.mode_btn.enabled

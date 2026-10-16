"""Bluetooth output: parsers, manager state machine (mock BlueZ), audio routing via
a fake pactl, the main-thread event hook, and the Settings > Bluetooth screen."""
import json
import os
import time

import pygame
import pytest

from hardware import bluetooth as bt
from hardware.bluetooth import (AudioRouter, BluetoothCtl, BluetoothManager, MockBluetooth,
                                MockRouter)
from player.audio import AudioPlayer, SimulatedBackend
from ui import bluetooth as btui
from ui.screen_manager import Screen, ScreenManager

SPK = "AA:BB:CC:00:00:01"
HP = "AA:BB:CC:00:00:02"
FAR = "AA:BB:CC:00:00:03"
PHONE = "AA:BB:CC:00:00:04"


@pytest.fixture(scope="module", autouse=True)
def _pg():
    pygame.init()
    pygame.display.set_mode((320, 480))
    yield


def make(tmp_path, mock=None, router=None, name="bt.json"):
    mock = mock or MockBluetooth()
    router = router or MockRouter()
    m = BluetoothManager(mock, router, state_file=str(tmp_path / name), threaded=False)
    return m, mock, router


def started(tmp_path, **kw):
    m, mock, router = make(tmp_path, **kw)
    m.start()
    m.pump()
    return m, mock, router


def scanned(tmp_path, **kw):
    m, mock, router = started(tmp_path, **kw)
    m.start_scan()
    m.pump()
    return m, mock, router


def kinds(events):
    return [e[0] for e in events]


# ------------------------------------------------------------------ parsers
def test_parse_devices_strips_ansi_prompts_and_nameless():
    text = ("\x1b[0;94m[bluetooth]\x1b[0m# Device AA:BB:CC:00:00:01 JBL Flip 5\n"
            "[\x1b[0;92mNEW\x1b[0m] Device aa:bb:cc:00:00:02 Kitchen Headphones\n"
            "Device AA:BB:CC:00:00:05 AA-BB-CC-00-00-05\n"
            "[\x1b[0;91mDEL\x1b[0m] Device AA:BB:CC:00:00:09 Gone\n"
            "Device AA:BB:CC:00:00:01 JBL Flip 5\n")
    assert bt.parse_devices(text) == [(SPK, "JBL Flip 5"), (HP, "Kitchen Headphones"),
                                      ("AA:BB:CC:00:00:05", None)]


def test_parse_info():
    text = """Device AA:BB:CC:00:00:01 (public)
\tName: JBL Flip 5
\tAlias: JBL Flip 5
\tClass: 0x00240414
\tIcon: audio-card
\tPaired: yes
\tTrusted: no
\tConnected: yes
\tUUID: Audio Sink                (0000110b-0000-1000-8000-00805f9b34fb)
"""
    d = bt.parse_info(text)
    assert d == {"name": "JBL Flip 5", "paired": True, "trusted": False, "connected": True,
                 "icon": "audio-card", "audio": True}
    assert bt.parse_info("Device AA:BB:CC:00:00:01 not available") is None
    phone = bt.parse_info("Device X\n\tAlias: Pixel\n\tIcon: phone\n\tPaired: no\n")
    assert phone["name"] == "Pixel" and phone["audio"] is False


def test_find_sink_and_ids():
    sinks = ("47\talsa_output.platform-hdmi.stereo\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
             "81\tbluez_output.AA_BB_CC_00_00_01.1\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n")
    assert bt.find_sink(sinks, SPK) == "bluez_output.AA_BB_CC_00_00_01.1"
    assert bt.find_sink(sinks, HP) is None
    assert bt.first_non_bt_sink(sinks) == "alsa_output.platform-hdmi.stereo"
    assert bt.parse_ids("12\t47\t...\n13\t47\t...\n\n") == ["12", "13"]


def test_friendly_errors_and_ok_precedence():
    assert "blocked" in bt.friendly_error("Failed to set power on: org.bluez.Error.Blocked")
    assert "setup.sh" in bt.friendly_error("org.bluez.Error.NotAvailable br-connection-profile-unavailable")
    assert "nearby" in bt.friendly_error("Failed to connect: org.bluez.Error.Failed br-connection-page-timeout")
    assert bt._ok(1, "[CHG] Device X Failed: x\nPairing successful", ("pairing successful",))
    assert not bt._ok(0, "Failed to pair: org.bluez.Error.AuthenticationFailed", ("pairing successful",))


def test_ensure_user_audio_env(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(os.path, "isdir", lambda p: p == "/run/user/%d" % os.getuid())
    assert bt.ensure_user_audio_env() == "/run/user/%d" % os.getuid()
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/elsewhere")
    assert bt.ensure_user_audio_env() == "/elsewhere"


# ------------------------------------------------------- real-backend shims
class FakeRunner:
    def __init__(self, replies):
        self.replies = replies          # list of (match-substring, rc, out)
        self.calls = []

    def __call__(self, argv, timeout):
        cmd = " ".join(argv[1:])
        self.calls.append(cmd)
        for key, rc, out in self.replies:
            if key in cmd:
                return rc, out
        return 0, ""


def test_bluetoothctl_commands_and_paired_fallback():
    r = FakeRunner([("devices Paired", 0, ""),
                    ("paired-devices", 0, "Device AA:BB:CC:00:00:01 JBL"),
                    ("pair", 0, "Attempting to pair with AA:BB:CC:00:00:01\nPairing successful"),
                    ("connect", 1, "Failed to connect: org.bluez.Error.Failed"),
                    ("show", 0, "Controller B8:27:EB:00:00:00 (public)\n\tPowered: yes")])
    c = BluetoothCtl(exe="bluetoothctl", runner=r)
    assert c.available() and c.powered()
    assert c.paired() == [(SPK, "JBL")]
    assert c.pair(SPK)[0] is True
    assert "--agent NoInputNoOutput pair %s" % SPK in r.calls
    assert c.connect(SPK)[0] is False


def test_bluetoothctl_missing_binary_is_unavailable():
    c = BluetoothCtl(exe="/nonexistent/bluetoothctl")
    assert c.available() is False


def test_audio_router_sets_default_and_moves_streams():
    sinks = "1\talsa_output.hdmi\tPipeWire\n2\tbluez_output.AA_BB_CC_00_00_01.1\tPipeWire\n"
    r = FakeRunner([("list short sinks", 0, sinks), ("list short sink-inputs", 0, "7\t1\t...\n")])
    a = AudioRouter(runner=r, sleep=lambda s: None)
    a.exe = "pactl"
    assert a.route_to(SPK, wait_s=0) is True
    assert "set-default-sink bluez_output.AA_BB_CC_00_00_01.1" in r.calls
    assert "move-sink-input 7 bluez_output.AA_BB_CC_00_00_01.1" in r.calls
    assert a.route_default() is True
    assert "set-default-sink alsa_output.hdmi" in r.calls


def test_audio_router_gives_up_and_requests_a2dp_when_no_sink():
    r = FakeRunner([("list short sinks", 0, "1\talsa_output.hdmi\tPipeWire\n")])
    a = AudioRouter(runner=r, sleep=lambda s: None)
    a.exe = "pactl"
    assert a.route_to(HP, wait_s=0) is False
    assert "set-card-profile bluez_card.AA_BB_CC_00_00_02 a2dp-sink" in r.calls
    a.exe = None
    assert a.route_to(HP) is False and a.route_default() is False


# ------------------------------------------------------------------ manager
def test_startup_powers_on_and_scan_lists_named_devices_audio_first(tmp_path):
    m, mock, _ = scanned(tmp_path)
    assert m.available is True and m.powered is True and not m.scanning
    names = [d["name"] for d in m.device_list()]
    assert "Someone's Phone" == names[-1]                 # non-audio last
    assert len(names) == 4                                # nameless device hidden
    assert m.devices[PHONE]["audio"] is False and m.devices[SPK]["audio"] is True


def test_connect_pairs_trusts_connects_routes_and_remembers(tmp_path):
    m, mock, router = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    assert ("pair", SPK) in mock.calls and ("trust", SPK) in mock.calls
    assert m.connected_mac == SPK and m.busy is None
    assert router.calls[-1] == ("to", SPK)
    ev = m.poll_events()
    assert ("connected", "Pesto Test Speaker", True) in ev
    saved = json.load(open(str(tmp_path / "bt.json")))
    assert saved["last_device"] == SPK and saved["enabled"] is True
    assert m.device_list()[0]["mac"] == SPK               # connected first
    assert m.snapshot()["connected_name"] == "Pesto Test Speaker"


def test_auto_reconnect_last_device_at_startup(tmp_path):
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    mock.drop(SPK)                                        # app restarts; speaker idle
    m2, _, router2 = started(tmp_path, mock=mock)
    assert m2.connected_mac == SPK
    assert router2.calls == [("to", SPK)]
    assert kinds(m2.poll_events()) == ["connected"]


def test_auto_reconnect_failure_is_silent(tmp_path):
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    mock.drop(SPK)
    mock.known[SPK]["name"] = "Out of Range Speaker"      # will fail to connect
    m2, _, _ = started(tmp_path, mock=mock)
    assert m2.connected_mac is None
    assert "error" not in kinds(m2.poll_events())


def test_connect_failure_reports_error(tmp_path):
    m, _, router = scanned(tmp_path)
    m.connect(FAR)
    m.pump()
    assert m.connected_mac is None and m.busy is None
    ev = m.poll_events()
    assert ev and ev[-1][0] == "error" and "nearby" in ev[-1][1]
    assert router.calls == []


def test_switching_devices_disconnects_the_first(tmp_path):
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.connect(HP)
    m.pump()
    assert m.connected_mac == HP
    assert mock.known[SPK]["connected"] is False and ("disconnect", SPK) in mock.calls


def test_drop_is_noticed_by_poll_and_device_reconnect_too(tmp_path):
    m, mock, router = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    m.poll_events()
    mock.drop(SPK)
    m.poll()
    assert m.connected_mac is None
    assert m.poll_events() == [("disconnected", "Pesto Test Speaker", False)]
    assert router.calls[-1] == ("default",)
    mock.device_connects(SPK)                             # speaker turned back on
    m.poll()
    assert m.connected_mac == SPK and kinds(m.poll_events()) == ["connected"]


def test_user_disconnect_and_forget(tmp_path):
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    m.poll_events()
    m.disconnect()
    m.pump()
    assert m.poll_events() == [("disconnected", "Pesto Test Speaker", True)]
    m.forget(SPK)
    m.pump()
    assert SPK not in m.devices and SPK not in mock.known
    assert json.load(open(str(tmp_path / "bt.json")))["last_device"] is None


def test_power_off_disconnects_and_is_remembered(tmp_path):
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    m.poll_events()
    m.set_powered(False)
    m.pump()
    assert not m.powered and m.connected_mac is None
    assert m.poll_events() == [("disconnected", "Pesto Test Speaker", True)]
    m2, _, _ = started(tmp_path, mock=mock)
    assert m2.enabled is False and m2.powered is False and m2.connected_mac is None
    m2.set_powered(True)                                  # on again -> reconnects last
    m2.pump()
    assert m2.powered and m2.connected_mac == SPK


def test_unavailable_adapter(tmp_path):
    m, _, _ = started(tmp_path, mock=MockBluetooth(available=False))
    assert m.available is False
    m.connect(SPK)
    m.pump()
    assert kinds(m.poll_events()) == ["error"]
    m.poll()                                              # re-probe is rate limited; no crash


def test_worker_survives_backend_exceptions(tmp_path):
    m, mock, _ = scanned(tmp_path)

    def boom(mac):
        raise OSError("dbus went away")
    mock.connect = boom
    m.connect(SPK)
    m.pump()                                              # must not raise
    assert m.busy is None and m.connected_mac is None


def test_threaded_worker_connects_in_background(tmp_path):
    mock = MockBluetooth()
    m = BluetoothManager(mock, MockRouter(), state_file=str(tmp_path / "t.json"), threaded=True)
    m.start()
    m.start_scan()
    deadline = time.time() + 5
    while SPK not in m.devices and time.time() < deadline:
        time.sleep(0.01)
    m.connect(SPK)
    while m.connected_mac != SPK and time.time() < deadline:
        time.sleep(0.01)
    m.stop()
    assert m.connected_mac == SPK


def test_corrupt_state_file_is_ignored(tmp_path):
    (tmp_path / "bt.json").write_text("{nope")
    m, _, _ = make(tmp_path)
    assert m.enabled is True and m.last_device is None


# ------------------------------------------------- audio + event hook
class ToastSM:
    def __init__(self):
        self.toasts = []
        self.status_bar = type("SB", (), {"v": None,
                                          "set_bluetooth_connected": lambda s, v: setattr(s, "v", v)})()

    def toast(self, m, kind="info"):
        self.toasts.append((m, kind))


def playing_player(clock):
    from conftest import make_track
    p = AudioPlayer(backend=SimulatedBackend(clock=clock))
    p.poll_interval = 0
    p.set_queue([make_track("A", duration=200.0), make_track("B")], 0)
    return p


def test_drop_mid_playback_pauses_and_resumes_at_same_spot(tmp_path):
    t = [1000.0]
    clock = lambda: t[0]
    p = playing_player(clock)
    m, mock, _ = scanned(tmp_path)
    m.connect(SPK)
    m.pump()
    sm = ToastSM()
    hook = btui.BluetoothEvents(sm, m, p)
    p.tick_hooks.append(hook)
    p.update()
    assert sm.toasts[-1] == ("Playing on Pesto Test Speaker", "success") and sm.status_bar.v is True
    t[0] += 42.0
    p.update()
    mock.drop(SPK)
    m.poll()
    p.update()                                            # hook runs inside update()
    assert p.get_state()["playing"] is False
    assert sm.toasts[-1] == ("Pesto Test Speaker disconnected - paused", "warn")
    assert sm.status_bar.v is False
    pos = p.get_state()["position"]
    assert 41.0 <= pos <= 43.0
    p.play()                                              # reopened at the same spot
    st = p.get_state()
    assert st["playing"] and abs(st["position"] - pos) < 0.01
    assert st["track"]["title"] == "A"


def test_connect_without_routing_reopens_stream(tmp_path):
    t = [0.0]
    p = playing_player(lambda: t[0])
    m, _, _ = scanned(tmp_path, router=MockRouter(ok=False))
    reopened = []
    p.reopen_output = lambda: reopened.append(True)
    hook = btui.BluetoothEvents(ToastSM(), m, p)
    m.connect(SPK)
    m.pump()
    hook()
    assert reopened == [True]


def test_hook_errors_never_break_audio_update():
    p = AudioPlayer(backend=SimulatedBackend())
    p.poll_interval = 0

    def bad():
        raise RuntimeError("x")
    p.tick_hooks.append(bad)
    p.update()                                            # must not raise


# ---------------------------------------------------------------- screen
class SheetSM(ScreenManager):
    def __init__(self):
        super().__init__(pygame.Surface((320, 480)))
        self.sheets = []

    def show_sheet(self, actions):
        self.sheets.append(actions)
        super().show_sheet(actions)


def screen_with(tmp_path, mock=None):
    sm = SheetSM()
    sm.register("settings", Screen(sm), tab="settings")
    m, mock, router = make(tmp_path, mock=mock)
    p = AudioPlayer(backend=SimulatedBackend())
    btui.install(sm, p, manager=m)
    m.pump()
    return sm, m, mock, sm._screens["bluetooth"][0]


def frame(sm, n=2):
    for _ in range(n):
        sm.update(1 / 30)
        sm.draw()


def tap(sm, pos):
    sm.handle_touch(pos, "down")
    sm.handle_touch(pos, "up")


def test_bluetooth_is_a_settings_child_reached_by_push(tmp_path):
    sm, m, _, scr = screen_with(tmp_path)
    assert sm._tab_root["settings"] == "settings"
    sm.show("settings")
    sm.push("bluetooth")
    assert sm.current_name() == "bluetooth" and sm.tab_bar is not None
    frame(sm)
    tap(sm, scr.back.rect.center)
    assert sm.current_name() == "settings"


def test_screen_draws_every_state_and_taps_work(tmp_path):
    sm, m, mock, scr = screen_with(tmp_path)
    sm.show("bluetooth")
    frame(sm)                                             # powered, empty
    m.start_scan()
    m.scanning = True
    m.version += 1
    frame(sm)                                             # scanning, empty
    m.scanning = False
    m.pump()
    frame(sm)
    assert len(scr.list.items) == 4
    # tap the first (unpaired) row -> connect
    row = scr.list.rect.y + theme_row_h() // 2
    tap(sm, (100, row))
    assert not m._q.empty()
    m.busy = ("pairing", scr.list.items[0]["mac"])
    m.version += 1
    frame(sm)                                             # busy row + card
    m.busy = None
    m.pump()
    frame(sm)
    assert m.connected_mac is not None
    assert scr.disconnect_btn.enabled
    tap(sm, (100, row))                                   # connected row -> sheet
    assert sm.sheets and sm.sheets[-1][0][0] == "Disconnect"
    sm._close_sheet()
    tap(sm, scr.disconnect_btn.rect.center)
    m.pump()
    assert m.connected_mac is None
    frame(sm)
    tap(sm, scr.toggle_rect.center)                       # power off
    m.pump()
    frame(sm)
    assert m.powered is False and scr.list.items == []
    m.available = False
    m.version += 1
    frame(sm)                                             # unavailable state


def test_screen_unavailable_adapter_draws(tmp_path):
    sm, m, _, scr = screen_with(tmp_path, mock=MockBluetooth(available=False))
    sm.show("bluetooth")
    m.pump()                                              # the on_enter refresh
    frame(sm)
    tap(sm, scr.toggle_rect.center)
    assert m._q.empty()                                   # nothing queued, toast instead
    assert sm.toast_text == "No Bluetooth adapter found"


def theme_row_h():
    from ui import theme
    return theme.ROW_H


# ---------------------------------------------------------------- settings
def test_settings_row_shows_device_and_pushes(tmp_path):
    from player.prefs import Prefs
    from ui.settings import ROWS, SettingsScreen

    class Net:
        ssid, ip = "x", "1.2.3.4"

        def refresh(self):
            pass

    sm = SheetSM()
    m, mock, _ = make(tmp_path)
    p = AudioPlayer(backend=SimulatedBackend())
    btui.install(sm, p, manager=m)
    s = SettingsScreen(sm, p, None, Prefs(str(tmp_path / "p.json")), {}, None, None, Net(), bluetooth=m)
    sm.register("settings", s, tab="settings")
    m.pump()
    assert s.value_text("output") == "Speaker"
    m.start_scan()
    m.connect(SPK)
    m.pump()
    assert s.value_text("output") == "Pesto Test Speaker" and s.sub_text("output") == "Connected"
    sm.show("settings")
    item = next(r for r in ROWS if r[0] == "output")
    s._on_tap(item, ROWS.index(item))
    assert sm.current_name() == "bluetooth"


def test_app_registers_and_draws_bluetooth_screen():
    import main as mainmod
    app = mainmod.PestoPlayer()
    sm = app.screen_manager
    assert "bluetooth" in sm._screens
    sm.show("settings")
    sm.push("bluetooth")
    for _ in range(3):
        app.step(1 / 30)
    assert sm.current_name() == "bluetooth"
    assert any(isinstance(h, btui.BluetoothEvents) for h in app.audio_player.tick_hooks)

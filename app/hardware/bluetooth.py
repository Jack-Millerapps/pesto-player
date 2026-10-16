"""
Bluetooth audio OUTPUT (A2DP: Pi -> speaker/headphones) for Pesto Player.

Pieces (all pygame-free, so they are unit-tested headless):
- BluetoothCtl   one-shot `bluetoothctl` commands (BlueZ's own CLI, ships with Pi OS).
- AudioRouter    points PipeWire's default sink at the BT device with `pactl`
                 (pulseaudio-utils, talking to pipewire-pulse) and moves live streams.
- MockBluetooth / MockRouter   in-memory stand-ins used in TEST_MODE and tests.
- BluetoothManager   thread-safe facade for the UI. Every blocking call runs on ONE
                 worker thread (commands are serialised through a queue); the UI only
                 reads snapshot() and drains poll_events() on the main thread.

Why one-shot bluetoothctl and not D-Bus: python3-dbus needs a GLib main loop (and
python3-gi) just to register a pairing agent, which is a lot of RAM and moving parts
on a 512 MB Zero 2 W. `bluetoothctl --agent NoInputNoOutput pair MAC` registers a
"just works" agent for exactly the duration of the pair call, and each command is a
short process with a hard timeout, so a wedged BlueZ can never freeze the UI. A
persistent interactive bluetoothctl would give push events, but its readline output
is block-buffered on a pipe; polling `info MAC` every few seconds is simpler and good
enough to notice a dropped speaker.

Why the service can reach the audio server: PipeWire runs as a *user* service.
pi/bluetooth/setup.sh enables linger for `pesto` so user@UID (and pipewire,
pipewire-pulse, wireplumber) start at boot without a login. This app is a system
service with no session environment, so ensure_user_audio_env() fills in
XDG_RUNTIME_DIR=/run/user/<uid> before VLC or pactl look for the pulse socket.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from collections import deque

import config

MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|[\x01\x02\r]")
PROMPT_RE = re.compile(r"^\[[^\]]+\][#>]\s*")
DEVICE_LINE_RE = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s*(.*)$")
AUDIO_ICONS = ("audio-card", "audio-headset", "audio-headphones", "audio-speakers")
AUDIO_UUID_HINTS = ("audio sink", "0000110b", "advanced audio")


# ============================================================================
# helpers
# ============================================================================
def ensure_user_audio_env():
    """Point XDG_RUNTIME_DIR at /run/user/<uid> if it is unset and exists.

    A system service (pesto-player.service) has no login session, so libpulse
    (inside VLC) and pactl would not find the PipeWire pulse socket otherwise."""
    if os.environ.get("XDG_RUNTIME_DIR") or not hasattr(os, "getuid"):
        return os.environ.get("XDG_RUNTIME_DIR")
    path = "/run/user/%d" % os.getuid()
    if os.path.isdir(path):
        os.environ["XDG_RUNTIME_DIR"] = path
        return path
    return None


def clean_output(text):
    """Strip ANSI colour codes and bluetoothctl prompts from command output."""
    lines = []
    for raw in (text or "").splitlines():
        line = ANSI_RE.sub("", raw)
        while True:
            stripped = PROMPT_RE.sub("", line)
            if stripped == line:
                break
            line = stripped
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def normalize_mac(mac):
    m = MAC_RE.search(mac or "")
    return m.group(1).upper() if m else None


def parse_devices(text):
    """`bluetoothctl devices` output -> [(MAC, name)]. Nameless devices (BlueZ
    reports the MAC with dashes as the name) are kept with name None."""
    out, seen = [], set()
    for line in clean_output(text).splitlines():
        m = DEVICE_LINE_RE.search(line)
        if not m or line.startswith("[DEL]"):
            continue
        mac = normalize_mac(m.group(1))
        if not mac or mac in seen:
            continue
        seen.add(mac)
        name = m.group(2).strip()
        if not name or name.replace("-", ":").upper() == mac:
            name = None
        out.append((mac, name))
    return out


def parse_info(text):
    """`bluetoothctl info MAC` output -> dict, or None if the device is unknown."""
    text = clean_output(text)
    if not text or "not available" in text.lower() or "Device " not in text:
        return None
    d = {"name": None, "paired": False, "trusted": False, "connected": False,
         "icon": None, "audio": False}
    alias = None
    for line in text.splitlines():
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "name":
            d["name"] = val
        elif key == "alias":
            alias = val
        elif key in ("paired", "trusted", "connected"):
            d[key] = val.lower().startswith("yes")
        elif key == "icon":
            d["icon"] = val
        elif key == "uuid" and any(h in line.lower() for h in AUDIO_UUID_HINTS):
            d["audio"] = True
    if d["icon"] in AUDIO_ICONS:
        d["audio"] = True
    d["name"] = d["name"] or alias
    return d


def friendly_error(text):
    """Map BlueZ error text to something that fits a toast."""
    t = (text or "").lower()
    if "blocked" in t or "rfkill" in t:
        return "Bluetooth is blocked (run pi/bluetooth/setup.sh)"
    if "profile-unavailable" in t or "profile unavailable" in t:
        return "No audio service for Bluetooth (run pi/bluetooth/setup.sh)"
    if "not available" in t or "does not exist" in t:
        return "Device not found - is it in pairing mode?"
    if "authenticationfailed" in t or "authentication failed" in t or "authenticationrejected" in t:
        return "Pairing was rejected - put the device in pairing mode"
    if "page-timeout" in t or "timeout" in t or "timed out" in t:
        return "Device didn't answer - is it on and nearby?"
    if "inprogress" in t or "in progress" in t or "busy" in t:
        return "Bluetooth is busy - try again"
    if "no default controller" in t:
        return "No Bluetooth adapter found"
    return "Bluetooth error"


def find_sink(pactl_short_sinks, mac):
    """Name of the PipeWire/pulse sink for this BT device in `pactl list short sinks`."""
    key = ("bluez_output." + mac.replace(":", "_")).upper()
    for line in (pactl_short_sinks or "").splitlines():
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) >= 2 and parts[1].upper().startswith(key):
            return parts[1]
    return None


def first_non_bt_sink(pactl_short_sinks):
    for line in (pactl_short_sinks or "").splitlines():
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) >= 2 and not parts[1].startswith("bluez_"):
            return parts[1]
    return None


def parse_ids(pactl_short):
    ids = []
    for line in (pactl_short or "").splitlines():
        first = line.split("\t")[0].split()[0] if line.strip() else ""
        if first.isdigit():
            ids.append(first)
    return ids


def _run(argv, timeout):
    """Run argv; returns (returncode, cleaned combined output). Never raises."""
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout,
                           universal_newlines=True, errors="replace")
        return p.returncode, clean_output(p.stdout)
    except subprocess.TimeoutExpired as e:
        out = e.output.decode("utf-8", "replace") if isinstance(e.output, bytes) else (e.output or "")
        return 124, clean_output(out) + "\ntimed out"
    except (OSError, ValueError) as e:
        return 127, str(e)


def _ok(rc, out, success_words=()):
    """Success words win (bluetoothctl prints unrelated [CHG] lines around them);
    otherwise any failure text or a non-zero exit is a failure."""
    low = out.lower()
    if success_words and any(w in low for w in success_words):
        return True
    if "failed" in low or "error" in low or "not available" in low:
        return False
    return rc == 0


# ============================================================================
# real backends
# ============================================================================
class BluetoothCtl:
    """One-shot bluetoothctl commands. Each call blocks (worker thread only)."""

    def __init__(self, exe="bluetoothctl", runner=None, popen=subprocess.Popen):
        self.exe = shutil.which(exe) or exe
        self._run = runner or _run
        self._popen = popen

    def _cmd(self, *args, timeout=10):
        return self._run([self.exe] + list(args), timeout)

    def available(self):
        rc, out = self._cmd("show", timeout=6)
        return rc != 127 and "Controller" in out

    def powered(self):
        rc, out = self._cmd("show", timeout=6)
        return bool(re.search(r"Powered:\s*yes", out))

    def power(self, on):
        rc, out = self._cmd("power", "on" if on else "off", timeout=8)
        return _ok(rc, out, ("succeeded",)), out

    def devices(self):
        rc, out = self._cmd("devices", timeout=6)
        return parse_devices(out)

    def paired(self):
        """Candidate bonded devices: `devices Paired` (BlueZ >= 5.65) with a fallback
        to the older `paired-devices`. An older bluetoothctl may ignore the filter and
        list everything, so the manager confirms each one with info()."""
        rc, out = self._cmd("devices", "Paired", timeout=6)
        devs = parse_devices(out) if rc == 0 else []
        if not devs:
            rc2, out2 = self._cmd("paired-devices", timeout=6)
            if rc2 == 0:
                devs = parse_devices(out2)
        return devs[:12]

    def info(self, mac):
        rc, out = self._cmd("info", mac, timeout=6)
        return parse_info(out)

    def scan(self, seconds, should_stop, on_tick, tick_s=2.0):
        """Discover for `seconds` (discovery lives as long as the bluetoothctl process),
        calling on_tick(devices) every tick_s. Stops early when should_stop()."""
        try:
            proc = self._popen([self.exe, "--timeout", str(int(seconds)), "scan", "on"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        except OSError as e:
            return False, str(e)
        deadline = time.monotonic() + seconds + 2
        try:
            while time.monotonic() < deadline and proc.poll() is None:
                end = time.monotonic() + tick_s
                while time.monotonic() < end:
                    if should_stop() or proc.poll() is not None:
                        break
                    time.sleep(0.2)
                on_tick(self.devices())
                if should_stop():
                    break
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        on_tick(self.devices())
        return True, ""

    def pair(self, mac):
        rc, out = self._run([self.exe, "--agent", "NoInputNoOutput", "pair", mac],
                            config.BLUETOOTH_PAIR_TIMEOUT)
        low = out.lower()
        if "alreadyexists" in low or "already exists" in low:
            return True, out
        return _ok(rc, out, ("pairing successful",)), out

    def trust(self, mac):
        rc, out = self._cmd("trust", mac, timeout=6)
        return _ok(rc, out, ("succeeded",)), out

    def connect(self, mac):
        rc, out = self._cmd("connect", mac, timeout=config.BLUETOOTH_CONNECT_TIMEOUT)
        return _ok(rc, out, ("connection successful",)), out

    def disconnect(self, mac):
        rc, out = self._cmd("disconnect", mac, timeout=8)
        return _ok(rc, out, ("successful",)), out

    def remove(self, mac):
        rc, out = self._cmd("remove", mac, timeout=8)
        return _ok(rc, out, ("removed",)), out


class AudioRouter:
    """Make the BT device the default PipeWire sink and move playing streams to it.

    WirePlumber usually switches by itself when a BT sink appears, but its choice is
    remembered per-user and can stick to the old sink; setting it explicitly is the
    deterministic path. Without pactl, route_to() returns False and the caller
    restarts the VLC stream so it opens on whatever the default now is."""

    def __init__(self, exe="pactl", runner=None, sleep=time.sleep):
        self.exe = shutil.which(exe)
        self._run = runner or _run
        self._sleep = sleep

    def available(self):
        return bool(self.exe)

    def _p(self, *args):
        ensure_user_audio_env()
        return self._run([self.exe] + list(args), 6)

    def _move_all(self, sink):
        rc, out = self._p("list", "short", "sink-inputs")
        for sid in parse_ids(out if rc == 0 else ""):
            self._p("move-sink-input", sid, sink)

    def route_to(self, mac, wait_s=None):
        if not self.available():
            return False
        wait_s = config.BLUETOOTH_SINK_WAIT if wait_s is None else wait_s
        card = "bluez_card." + mac.replace(":", "_").upper()
        tried_profile = False
        deadline = time.monotonic() + wait_s
        while True:
            rc, out = self._p("list", "short", "sinks")
            sink = find_sink(out, mac) if rc == 0 else None
            if sink:
                self._p("set-default-sink", sink)
                self._move_all(sink)
                return True
            if not tried_profile and time.monotonic() > deadline - wait_s / 2:
                tried_profile = True       # device came up in a headset profile: ask for A2DP
                self._p("set-card-profile", card, "a2dp-sink")
            if time.monotonic() >= deadline:
                return False
            self._sleep(0.5)

    def route_default(self):
        if not self.available():
            return False
        rc, out = self._p("list", "short", "sinks")
        sink = first_non_bt_sink(out) if rc == 0 else None
        if not sink:
            return False
        self._p("set-default-sink", sink)
        self._move_all(sink)
        return True


# ============================================================================
# mocks (TEST_MODE / tests)
# ============================================================================
class MockBluetooth:
    """In-memory BlueZ. `delay` slows every call a little so the UI looks real in
    TEST_MODE; tests use delay=0. "Out of Range Speaker" always fails to connect."""

    DEFAULT_DEVICES = [
        ("AA:BB:CC:00:00:01", "Pesto Test Speaker", "audio-card"),
        ("AA:BB:CC:00:00:02", "Kitchen Headphones", "audio-headphones"),
        ("AA:BB:CC:00:00:03", "Out of Range Speaker", "audio-card"),
        ("AA:BB:CC:00:00:04", "Someone's Phone", "phone"),
        ("AA:BB:CC:00:00:05", None, None),
    ]

    def __init__(self, delay=0.0, available=True, devices=None):
        self.delay = delay
        self._available = available
        self._powered = False
        self._nearby = list(devices or self.DEFAULT_DEVICES)
        self.known = {}       # mac -> dict(name, icon, paired, trusted, connected)
        self.calls = []

    def _wait(self, n=1.0):
        if self.delay:
            time.sleep(self.delay * n)

    def available(self):
        return self._available

    def powered(self):
        return self._powered

    def power(self, on):
        self.calls.append(("power", on))
        self._wait()
        if not self._available:
            return False, "No default controller available"
        self._powered = bool(on)
        if not on:
            for d in self.known.values():
                d["connected"] = False
        return True, "Changing power succeeded"

    def devices(self):
        return [(m, d["name"]) for m, d in self.known.items()]

    def paired(self):
        return [(m, d["name"]) for m, d in self.known.items() if d["paired"]]

    def info(self, mac):
        d = self.known.get(mac)
        if d is None:
            return None
        return {"name": d["name"], "paired": d["paired"], "trusted": d["trusted"],
                "connected": d["connected"], "icon": d["icon"],
                "audio": (d["icon"] or "").startswith("audio")}

    def scan(self, seconds, should_stop, on_tick, tick_s=2.0):
        self.calls.append(("scan",))
        for mac, name, icon in self._nearby:
            if should_stop():
                break
            self._wait(2)
            self.known.setdefault(mac, {"name": name, "icon": icon, "paired": False,
                                        "trusted": False, "connected": False})
            on_tick(self.devices())
        on_tick(self.devices())
        return True, ""

    def pair(self, mac):
        self.calls.append(("pair", mac))
        self._wait(3)
        d = self.known.get(mac)
        if d is None:
            return False, "Device %s not available" % mac
        d["paired"] = True
        return True, "Pairing successful"

    def trust(self, mac):
        self.calls.append(("trust", mac))
        d = self.known.get(mac)
        if d is None:
            return False, "Device %s not available" % mac
        d["trusted"] = True
        return True, "trust succeeded"

    def connect(self, mac):
        self.calls.append(("connect", mac))
        self._wait(3)
        d = self.known.get(mac)
        if d is None or not self._powered:
            return False, "Device %s not available" % mac
        if d["name"] == "Out of Range Speaker":
            return False, "Failed to connect: org.bluez.Error.Failed br-connection-page-timeout"
        d["connected"] = True
        return True, "Connection successful"

    def disconnect(self, mac):
        self.calls.append(("disconnect", mac))
        d = self.known.get(mac)
        if d:
            d["connected"] = False
        return True, "Successful disconnected"

    def remove(self, mac):
        self.calls.append(("remove", mac))
        self.known.pop(mac, None)
        return True, "Device has been removed"

    # test helpers
    def drop(self, mac):
        """Simulate the speaker switching off / walking out of range."""
        if mac in self.known:
            self.known[mac]["connected"] = False

    def device_connects(self, mac):
        """Simulate a trusted device reconnecting by itself."""
        if mac in self.known and self._powered:
            self.known[mac]["connected"] = True


class MockRouter:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def available(self):
        return self.ok

    def route_to(self, mac, wait_s=None):
        self.calls.append(("to", mac))
        return self.ok

    def route_default(self):
        self.calls.append(("default",))
        return self.ok


# ============================================================================
# manager
# ============================================================================
class BluetoothManager:
    """Thread-safe Bluetooth state + command queue.

    UI (main thread): set_powered / start_scan / stop_scan / connect / disconnect /
    forget enqueue work and return at once; snapshot() and device_list() read
    state; poll_events() drains events:
        ("connected", name, routed)        routed=False -> caller should reopen audio
        ("disconnected", name, by_user)    by_user=False -> link dropped (pause!)
        ("error", message) / ("info", message)
    `version` increments on every state change (cheap dirty check for screens).

    threaded=False runs nothing in the background: tests call pump() and poll().
    """

    def __init__(self, ctl, router, state_file=None, threaded=True):
        self.ctl = ctl
        self.router = router
        self.state_file = state_file or config.BLUETOOTH_STATE_FILE
        self.threaded = threaded
        self._lock = threading.RLock()
        self._q = queue.Queue()
        self._events = deque()
        self._stop_scan = threading.Event()
        self._shutdown = threading.Event()
        self._thread = None
        self._started = False
        self.version = 0
        self.available = None          # None = not probed yet
        self.powered = False
        self.scanning = False
        self.busy = None               # (action, mac) while a command runs
        self.devices = {}              # mac -> {name, paired, trusted, connected, audio}
        self.connected_mac = None
        self._last_probe = time.monotonic()
        self.enabled, self.last_device, self._names = self._load()

    # ------------------------------------------------------------ persistence
    def _load(self):
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            names = d.get("names") if isinstance(d.get("names"), dict) else {}
            return bool(d.get("enabled", True)), normalize_mac(d.get("last_device")), names
        except (OSError, ValueError, AttributeError):
            return True, None, {}

    def _save(self):
        data = {"enabled": self.enabled, "last_device": self.last_device,
                "names": {m: n for m, n in self._names.items() if n}}
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            tmp = self.state_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.state_file)
        except OSError as e:
            print("Bluetooth: could not save state: %s" % e)

    # ------------------------------------------------------------ public (UI)
    def start(self):
        """Probe the adapter and auto-reconnect the last device (in the background)."""
        if self._started:
            return
        self._started = True
        self._q.put(("startup",))
        if self.threaded:
            self._thread = threading.Thread(target=self._loop, name="bluetooth", daemon=True)
            self._thread.start()

    def stop(self):
        self._shutdown.set()
        self._stop_scan.set()

    def set_powered(self, on):
        self._q.put(("power", bool(on)))

    def start_scan(self):
        self._stop_scan.clear()
        self._q.put(("scan",))

    def stop_scan(self):
        self._stop_scan.set()

    def connect(self, mac):
        self._stop_scan.set()             # a tap during a scan ends the scan first
        self._q.put(("connect", mac))

    def disconnect(self):
        self._q.put(("disconnect",))

    def forget(self, mac):
        self._stop_scan.set()
        self._q.put(("forget", mac))

    def refresh(self):
        self._q.put(("refresh",))

    def poll_events(self):
        with self._lock:
            out = list(self._events)
            self._events.clear()
        return out

    def snapshot(self):
        with self._lock:
            return {"available": self.available, "powered": self.powered,
                    "scanning": self.scanning, "busy": self.busy,
                    "connected_mac": self.connected_mac,
                    "connected_name": self.name_of(self.connected_mac) if self.connected_mac else None,
                    "version": self.version}

    def name_of(self, mac):
        with self._lock:
            d = self.devices.get(mac) or {}
            return d.get("name") or self._names.get(mac) or mac

    def device_list(self):
        """Devices for the UI: connected, then paired, then audio, then the rest by
        name. Nameless devices are hidden (nobody can tell which one is theirs)."""
        with self._lock:
            items = []
            for mac, d in self.devices.items():
                if not d.get("name"):
                    continue
                items.append(dict(d, mac=mac))
        items.sort(key=lambda d: (not d.get("connected"), not d.get("paired"),
                                  not d.get("audio"), (d.get("name") or "").lower()))
        return items

    # -------------------------------------------------------------- internals
    def _bump(self, **changes):
        with self._lock:
            for k, v in changes.items():
                setattr(self, k, v)
            self.version += 1

    def _event(self, *ev):
        with self._lock:
            self._events.append(ev)
            self.version += 1

    def _merge(self, mac, **fields):
        with self._lock:
            d = self.devices.setdefault(mac, {"name": None, "paired": False, "trusted": False,
                                              "connected": False, "audio": None})
            for k, v in fields.items():
                if v is not None or k not in ("name", "audio"):
                    d[k] = v
            if d.get("name"):
                self._names[mac] = d["name"]
            self.version += 1
            return d

    def _loop(self):
        while not self._shutdown.is_set():
            try:
                cmd = self._q.get(timeout=self._poll_interval())
            except queue.Empty:
                self._safe(self.poll)
                continue
            self._safe(self._exec, cmd)

    def _poll_interval(self):
        return config.BLUETOOTH_POLL_CONNECTED_S if self.connected_mac else config.BLUETOOTH_POLL_IDLE_S

    def _safe(self, fn, *a):
        try:
            fn(*a)
        except Exception as e:                     # never let the worker die
            print("Bluetooth: %s failed: %s: %s" % (getattr(fn, "__name__", fn), type(e).__name__, e))
            self._bump(busy=None, scanning=False)

    def pump(self):
        """Run every queued command now (threaded=False / tests)."""
        while True:
            try:
                cmd = self._q.get_nowait()
            except queue.Empty:
                return
            self._safe(self._exec, cmd)

    def _exec(self, cmd):
        name, args = cmd[0], cmd[1:]
        if name != "startup" and not self.available:
            self._startup(auto=False)          # bluetoothd may have come up since
            if not self.available:
                if name != "refresh":
                    self._event("error", "Bluetooth isn't available on this device")
                return
        getattr(self, "_do_" + name)(*args)

    # -------------------------------------------------------------- commands
    def _do_startup(self):
        self._startup(auto=True)

    def _startup(self, auto):
        ok = bool(self.ctl.available())
        self._bump(available=ok)
        if not ok:
            print("Bluetooth: no adapter / bluetoothctl (see pi/bluetooth/setup.sh)")
            return
        self._load_paired()
        if not auto:
            self._bump(powered=self.ctl.powered())
            return
        if not self.enabled:
            if self.ctl.powered():
                self.ctl.power(False)
            self._bump(powered=False)
            return
        ok, out = self.ctl.power(True)
        self._bump(powered=ok)
        if not ok:
            print("Bluetooth: power on failed: %s" % out)
            return
        for mac, d in list(self.devices.items()):
            if d.get("connected"):                 # already up (e.g. app restart)
                self._became_connected(mac)
                return
        if self.last_device and self.last_device in self.devices:
            self._do_connect(self.last_device, auto=True)

    def _load_paired(self):
        for mac, name in self.ctl.paired():
            info = self.ctl.info(mac)
            if not info or not info.get("paired"):
                continue
            self._merge(mac, name=name or info.get("name") or self._names.get(mac), paired=True,
                        trusted=info.get("trusted", False), connected=info.get("connected", False),
                        audio=info.get("audio"))

    def _do_refresh(self):
        self._bump(powered=self.ctl.powered())
        self._load_paired()

    def _do_power(self, on):
        self._bump(busy=("power", None))
        try:
            ok, out = self.ctl.power(on)
            if not ok:
                self._event("error", friendly_error(out))
                return
            self.enabled = on
            self._save()
            self._bump(powered=on)
            if not on and self.connected_mac:
                name = self.name_of(self.connected_mac)
                self._merge(self.connected_mac, connected=False)
                self._bump(connected_mac=None)
                self.router.route_default()
                self._event("disconnected", name, True)
            if on and self.last_device and not self.connected_mac:
                self._do_connect(self.last_device, auto=True)
        finally:
            self._bump(busy=None)

    def _ensure_powered(self):
        if self.powered:
            return True
        ok, out = self.ctl.power(True)
        if ok:
            self.enabled = True
            self._save()
        self._bump(powered=ok)
        if not ok:
            self._event("error", friendly_error(out))
        return ok

    def _do_scan(self):
        if self._stop_scan.is_set() or not self._ensure_powered():
            return
        self._bump(scanning=True)
        try:
            def tick(devs):
                for mac, name in devs:
                    self._merge(mac, name=name)
            self.ctl.scan(config.BLUETOOTH_SCAN_TIMEOUT,
                          lambda: self._stop_scan.is_set() or self._shutdown.is_set()
                          or not self._q.empty(), tick)
        finally:
            self._bump(scanning=False)
        # one `info` per named, not-yet-classified device to learn audio vs phone etc.
        todo = [m for m, d in list(self.devices.items()) if d.get("name") and d.get("audio") is None]
        for mac in todo[:16]:
            if not self._q.empty():
                break
            info = self.ctl.info(mac)
            if info:
                self._merge(mac, name=info["name"], paired=info["paired"], trusted=info["trusted"],
                            connected=info["connected"], audio=info["audio"])

    def _do_connect(self, mac, auto=False):
        mac = normalize_mac(mac)
        if not mac:
            return
        if mac == self.connected_mac:
            return
        self._bump(busy=("connecting", mac))
        try:
            if not self._ensure_powered():
                return
            if self.connected_mac:                       # one output at a time
                self._do_disconnect(quiet=True)
            info = self.ctl.info(mac)
            if not (info and info["paired"]):
                self._bump(busy=("pairing", mac))
                ok, out = self.ctl.pair(mac)
                if not ok and "not available" in out.lower() and not auto:
                    self._short_rescan(mac)              # BlueZ forgot it since the scan
                    ok, out = self.ctl.pair(mac)
                if not ok:
                    self._fail(auto, "Pairing failed: " + friendly_error(out), out)
                    return
                self._merge(mac, paired=True)
                self._bump(busy=("connecting", mac))
            self.ctl.trust(mac)                          # lets it reconnect by itself later
            self._merge(mac, trusted=True)
            ok, out = self.ctl.connect(mac)
            if not ok and not auto:
                time.sleep(1.0 if self.threaded else 0)   # first A2DP attempt often races
                ok, out = self.ctl.connect(mac)
            info = self.ctl.info(mac) or {}
            if not (ok or info.get("connected")):
                self._fail(auto, "Couldn't connect: " + friendly_error(out), out)
                return
            self._merge(mac, name=info.get("name"), connected=True)
            self._became_connected(mac)
        finally:
            self._bump(busy=None)

    def _short_rescan(self, mac):
        seen = []

        def tick(devs):
            for m, n in devs:
                self._merge(m, name=n)
                if m == mac:
                    seen.append(m)
        self.ctl.scan(8, lambda: bool(seen), tick, tick_s=1.0)

    def _became_connected(self, mac):
        self._merge(mac, connected=True)
        self.last_device = mac
        self._save()
        self._bump(connected_mac=mac)
        routed = bool(self.router.route_to(mac))
        self._event("connected", self.name_of(mac), routed)

    def _fail(self, auto, message, raw):
        print("Bluetooth: %s (%s)" % (message, (raw or "").replace("\n", " | ")[:200]))
        if not auto:
            self._event("error", message)

    def _do_disconnect(self, quiet=False):
        mac = self.connected_mac
        if not mac:
            return
        name = self.name_of(mac)
        self.ctl.disconnect(mac)
        self._merge(mac, connected=False)
        self._bump(connected_mac=None)
        self.router.route_default()
        if not quiet:
            self._event("disconnected", name, True)

    def _do_forget(self, mac):
        mac = normalize_mac(mac)
        if not mac:
            return
        name = self.name_of(mac)
        self._bump(busy=("forgetting", mac))
        try:
            if mac == self.connected_mac:
                self._do_disconnect(quiet=True)
            ok, out = self.ctl.remove(mac)
            with self._lock:
                self.devices.pop(mac, None)
                self._names.pop(mac, None)
                self.version += 1
            if self.last_device == mac:
                self.last_device = None
            self._save()
            if ok:
                self._event("info", "Forgot %s" % name)
            else:
                self._event("error", "Couldn't forget: " + friendly_error(out))
        finally:
            self._bump(busy=None)

    # ------------------------------------------------------------------ poll
    def poll(self):
        """Notice drops and device-initiated reconnects. Runs on the worker when the
        queue is idle (every BLUETOOTH_POLL_* seconds)."""
        if not self.available:
            # bluetoothd/hciuart can come up after this service at boot: re-probe.
            now = time.monotonic()
            if now - self._last_probe >= config.BLUETOOTH_REPROBE_S:
                self._last_probe = now
                self._startup(auto=True)
            return
        mac = self.connected_mac
        if mac:
            info = self.ctl.info(mac)
            if info is not None and info["connected"]:
                return
            name = self.name_of(mac)
            self._merge(mac, connected=False)
            self._bump(connected_mac=None)
            self.router.route_default()
            self._event("disconnected", name, False)
            return
        powered = self.ctl.powered()
        if powered != self.powered:
            self._bump(powered=powered)
        if not powered:
            return
        candidates = [m for m, d in self.devices.items() if d.get("paired") and d.get("trusted")]
        if self.last_device in candidates:
            candidates.remove(self.last_device)
            candidates.insert(0, self.last_device)
        for m in candidates[:4]:
            info = self.ctl.info(m)
            if info and info["connected"]:
                self._became_connected(m)
                return


def create_bluetooth_manager(threaded=True):
    """Real BlueZ manager on the device, an in-memory one in TEST_MODE."""
    if config.TEST_MODE:
        return BluetoothManager(MockBluetooth(delay=0.15), MockRouter(), threaded=threaded)
    ensure_user_audio_env()
    return BluetoothManager(BluetoothCtl(), AudioRouter(), threaded=threaded)

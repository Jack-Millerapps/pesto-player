"""
System helpers for Pesto Player: network info, disk space, display power, shutdown.

Everything here is best-effort and never raises: the app must start and run with
no Wi-Fi, no backlight node, no systemd. In TEST_MODE nothing touches the system
(shutdown/reboot only log).

Display sleep: the panel's backlight wiring is not known to the software. We use
a /sys/class/backlight node when one exists (also used for the brightness
setting); the app additionally blanks and stops drawing while asleep, so sleep is
at minimum a black screen and an idle CPU.
"""

import glob
import ipaddress
import os
import shutil
import socket
import subprocess
import threading

import config


# ---------------------------------------------------------------- network
def get_ip():
    """LAN IPv4 of the default route, or None. Sends no packets."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        return None if ip.startswith("127.") or ip == "0.0.0.0" else ip
    except OSError:
        return None
    finally:
        if s:
            s.close()


def get_ssid(runner=subprocess.run):
    try:
        out = runner(["iwgetid", "-r"], capture_output=True, text=True, timeout=2)
        ssid = (out.stdout or "").strip()
        return ssid or None
    except Exception:
        return None


_CGNAT = ipaddress.ip_network("100.64.0.0/10")   # Tailscale's address range


def _tailscale_addr(text):
    """First line of text if it is an IPv4 in 100.64.0.0/10, else None."""
    for line in (text or "").split():
        try:
            a = ipaddress.ip_address(line.strip())
        except ValueError:
            continue
        if a.version == 4 and a in _CGNAT:
            return str(a)
    return None


def get_tailscale_ip(runner=subprocess.run):
    """This device's Tailscale IPv4 (100.64.0.0/10), or None if Tailscale is absent/down.

    Tries `tailscale ip -4`, then the tailscale0 interface. Never raises."""
    for cmd in (["tailscale", "ip", "-4"], ["ip", "-4", "-o", "addr", "show", "tailscale0"]):
        try:
            out = runner(cmd, capture_output=True, text=True, timeout=2)
            text = (out.stdout or "").replace("/", " ") if out.returncode == 0 else ""
            ip = _tailscale_addr(text)
            if ip:
                return ip
        except Exception:
            continue
    return None


class NetInfo:
    """ip/ssid/ts_ip refreshed on a background thread (iwgetid can be slow)."""

    def __init__(self):
        self.ip = None
        self.ts_ip = None
        self.ssid = None
        self._busy = False

    def refresh(self):
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                self.ip, self.ssid = get_ip(), get_ssid()
                self.ts_ip = get_tailscale_ip()
            finally:
                self._busy = False

        threading.Thread(target=work, name="netinfo", daemon=True).start()


# ------------------------------------------------------------------ disk
def disk_info(path):
    """(free_bytes, total_bytes) for the filesystem holding path, or (None, None)."""
    path = os.path.expanduser(path)
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    try:
        u = shutil.disk_usage(path)
        return u.free, u.total
    except OSError:
        return None, None


def human_bytes(n):
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ----------------------------------------------------------- display power
class DisplayPower:
    """Backlight brightness (0-100) and sleep/wake via sysfs when available."""

    def __init__(self, base=None):
        base = base or config.BACKLIGHT_PATH
        nodes = sorted(glob.glob(os.path.join(base, "*")))
        self._node = nodes[0] if nodes else None
        self._max = 0
        self._saved = None
        self.asleep = False
        if self._node:
            try:
                with open(os.path.join(self._node, "max_brightness")) as f:
                    self._max = int(f.read().strip())
            except (OSError, ValueError):
                self._node = None

    @property
    def has_backlight(self):
        return self._node is not None and self._max > 0

    def get_brightness(self):
        if not self.has_backlight:
            return None
        try:
            with open(os.path.join(self._node, "brightness")) as f:
                return round(100 * int(f.read().strip()) / self._max)
        except (OSError, ValueError):
            return None

    def set_brightness(self, pct):
        if not self.has_backlight:
            return False
        value = max(0, min(self._max, round(self._max * max(5, min(100, pct)) / 100)))
        return self._write(value)

    def _write(self, value):
        try:
            with open(os.path.join(self._node, "brightness"), "w") as f:
                f.write(str(value))
            return True
        except OSError as e:
            print(f"Display: cannot write brightness: {e}")
            return False

    def sleep(self):
        if self.asleep:
            return
        self.asleep = True
        if self.has_backlight:
            self._saved = self.get_brightness()
            self._write(0)

    def wake(self):
        if not self.asleep:
            return
        self.asleep = False
        if self.has_backlight:
            self.set_brightness(self._saved if self._saved else 100)


# ------------------------------------------------------- shutdown / reboot
def _power_command(action, runner):
    """Run `systemctl <action>`; fall back to passwordless `sudo -n`. True on success."""
    if config.TEST_MODE:
        print(f"[TEST_MODE] would run system {action}")
        return False
    for cmd in (["systemctl", action], ["sudo", "-n", "systemctl", action]):
        try:
            r = runner(cmd, capture_output=True, timeout=10)
            if r.returncode == 0:
                return True
        except Exception as e:
            print(f"System {action} via {cmd[0]} failed: {e}")
    return False


def shutdown(runner=subprocess.run):
    return _power_command("poweroff", runner)


def reboot(runner=subprocess.run):
    return _power_command("reboot", runner)

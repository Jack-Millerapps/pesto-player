"""Add music screen: shows where songs go, a QR/URL for the Wi-Fi uploader, and
rescans the library (in a background thread) when the uploader reports a finished
batch by touching config.DIRTY_FLAG.

The uploader (pi/uploader/server.py) runs as a separate service and writes its
per-session token to config.UPLOADER_INFO_FILE; this screen only reads it.
"""
import json
import os
import time

import pygame

import config
from hardware.system import NetInfo, disk_info, human_bytes
from ui import text_cache, theme
from ui.screen_manager import Screen
from ui.widgets import Button

try:
    import qrcode
except Exception:  # optional: without it only the URL text is shown
    qrcode = None

QR_SIZE = 144
POLL_S = 1.0
NET_REFRESH_S = 15.0
HEADER_H = 44


def qr_surface(text, size=QR_SIZE):
    """Black-on-white QR as a pygame Surface of about size x size, or None."""
    if qrcode is None or not text:
        return None
    try:
        qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(text)
        qr.make(fit=True)
        m = qr.get_matrix()
    except Exception as e:
        print(f"QR: {e}")
        return None
    n = len(m)
    box = max(1, size // n)
    surf = pygame.Surface((n * box, n * box))
    surf.fill((255, 255, 255))
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on:
                surf.fill((0, 0, 0), (x * box, y * box, box, box))
    return surf


def wrap_chars(text, size, max_w):
    """Split text (no spaces, e.g. a URL) into lines no wider than max_w pixels."""
    lines, cur = [], ""
    for ch in text:
        if cur and text_cache.text_width(cur + ch, size) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def caption_for(has_qr, ip, anywhere=False):
    """Caption under the QR box, matching the actual situation."""
    if has_qr:
        if anywhere:
            return "Scan from any network (needs Tailscale app)"
        return "Scan with your phone camera (same Wi-Fi)"
    if not ip:
        return "Connect to Wi-Fi to add songs from a phone"
    return "Uploader isn't running (pesto-uploader service)"


def read_uploader_info(path=None):
    try:
        with open(path or config.UPLOADER_INFO_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        token, port = str(d["token"]), int(d.get("port", config.UPLOADER_PORT))
        return token, port
    except (OSError, ValueError, KeyError, TypeError):
        return None, config.UPLOADER_PORT


class AddMusicScreen(Screen):
    has_mini_player = False

    def __init__(self, screen_manager, audio_player, music_library, netinfo=None,
                 clock=time.monotonic):
        super().__init__(screen_manager)
        self.audio_player = audio_player
        self.library = music_library
        self.net = netinfo or NetInfo()
        self._clock = clock
        self.music_dir = os.path.expanduser(config.MUSIC_DIRECTORY)
        self.back = Button((4, theme.STATUS_H, theme.MIN_TOUCH, HEADER_H), icon="back", style="ghost",
                           on_click=self._on_back)
        self.rescan_btn = Button((theme.PAD, 352, theme.SCREEN_W - 2 * theme.PAD, theme.MIN_TOUCH),
                                 "Rescan library", self.rescan)
        # Only shown/active when a Tailscale address exists; flips LAN <-> tailnet URL.
        self.mode_btn = Button((theme.SCREEN_W - theme.PAD - 124, theme.STATUS_H, 124, HEADER_H),
                               "Home Wi-Fi", self._toggle_mode, style="ghost", enabled=False)
        self.widgets = [self.back, self.mode_btn, self.rescan_btn]
        self.anywhere = False
        self.status = ""
        self.status_kind = "info"
        self._progress = None
        self._token = None
        self._port = config.UPLOADER_PORT
        self._url = None
        self._qr = None
        self._qr_url = None
        self._poll_t = 0.0
        self._net_t = 0.0
        self._seen_mtime = self._dirty_mtime()
        self._pending_rescan = False
        self._info = ("", "", "", "", False)
        self._scanning_shown = False

    # ----------------------------------------------------------- helpers
    @staticmethod
    def _dirty_mtime():
        try:
            return os.stat(config.DIRTY_FLAG).st_mtime
        except OSError:
            return 0.0

    def _on_back(self):
        if not self.screen_manager.pop():
            self.screen_manager.show("library")

    def _scanning(self):
        try:
            return self.library.is_scanning()
        except Exception:
            return False

    def _ts_ip(self):
        return getattr(self.net, "ts_ip", None)

    def _toggle_mode(self):
        self.anywhere = not self.anywhere
        self._sync_mode()
        self._poll_t = POLL_S                  # rebuild QR on next update
        self.dirty = True

    def _sync_mode(self):
        """Keep the toggle in step with Tailscale presence (it may come and go)."""
        has = bool(self._ts_ip())
        if not has:
            self.anywhere = False
        self.mode_btn.enabled = has
        self.mode_btn.text = "Anywhere" if self.anywhere else "Home Wi-Fi"

    def build_url(self, ip=None):
        if ip is None:
            ip = self._ts_ip() if self.anywhere else self.net.ip
        if not ip or not self._token:
            return None
        return "http://%s:%d/?t=%s" % (ip, self._port, self._token)

    def _set_status(self, text, kind="info"):
        if text != self.status or kind != self.status_kind:
            self.status, self.status_kind = text, kind
            self.dirty = True

    # ---------------------------------------------------------- rescan
    def rescan(self):
        if self._scanning():
            return
        self._progress = (0, 0)
        self._set_status("Scanning...")
        self.rescan_btn.enabled = False
        self.library.start_scan(on_progress=self._on_progress, on_done=self._on_done)
        self.dirty = True

    def _on_progress(self, done, total):      # background thread
        self._progress = (done, total)

    def _on_done(self):                        # background thread
        self._progress = None
        self._finished = True

    _finished = False

    # ------------------------------------------------------------ lifecycle
    def on_enter(self, **kw):
        self.net.refresh()
        self._net_t = 0.0
        self._poll_t = POLL_S                  # poll immediately
        self.dirty = True

    def on_leave(self):
        for w in self.widgets:
            w.handle_touch((0, 0), "cancel")

    def update(self, dt):
        if self._scanning() and self._progress is not None:
            done, total = self._progress
            self._set_status("Scanning... %d/%d" % (done, total) if total else "Scanning...")
        if self._finished and not self._scanning():
            self._finished = False
            self.rescan_btn.enabled = True
            n = len(self.library.get_tracks())
            self._set_status("Library updated: %d song%s" % (n, "" if n == 1 else "s"), "success")
            self.dirty = True
        self._poll_t += dt
        self._net_t += dt
        if self._net_t >= NET_REFRESH_S:
            self._net_t = 0.0
            self.net.refresh()
        if self._poll_t >= POLL_S:
            self._poll_t = 0.0
            self._poll()

    def _poll(self):
        self._sync_mode()
        token, port = read_uploader_info()
        if (token, port) != (self._token, self._port):
            self._token, self._port = token, port
            self.dirty = True
        url = self.build_url()
        if url != self._qr_url:
            self._qr_url = url
            self._qr = qr_surface(url) if url else None
            self.dirty = True
        free, _total = disk_info(self.music_dir)
        try:
            n = len(self.library.get_tracks())
        except Exception:
            n = 0
        info = (human_bytes(free), "%d" % n, "%s|%s" % (self.net.ssid or "", self.net.ip or ""),
                self._ts_ip() or "", self.anywhere)
        if info != self._info:
            self._info = info
            self.dirty = True
        mtime = self._dirty_mtime()
        if mtime > self._seen_mtime:           # uploader finished a batch
            self._pending_rescan = True
        if self._pending_rescan and not self._scanning():
            self._seen_mtime = mtime
            self._pending_rescan = False
            self.rescan()
            self._set_status("New songs uploaded - scanning...")
        if not token and not self.status:
            self._set_status("Uploader isn't running", "warn")
        elif token and self.status == "Uploader isn't running":
            self._set_status("")

    # ---------------------------------------------------------------- touch
    def handle_touch(self, pos, kind):
        handled = False
        for w in self.widgets:
            handled = w.handle_touch(pos, kind) or handled
        if any(w.dirty for w in self.widgets):
            self.dirty = True
        return handled

    # ----------------------------------------------------------------- draw
    def draw(self, surface):
        self.back.draw(surface)
        if self.mode_btn.enabled:
            self.mode_btn.draw(surface)
        t = text_cache.render("Add music", theme.FS_HEADER, theme.TEXT, bold=True)
        surface.blit(t, (theme.MIN_TOUCH + 8, theme.STATUS_H + (HEADER_H - t.get_height()) // 2))
        x = theme.PAD
        free, count, net, ts_ip, anywhere = self._info
        ssid, _, ip = net.partition("|")
        dest = text_cache.ellipsize("Saving to " + config.MUSIC_DIRECTORY, theme.FS_SMALL, 296)
        lines = [dest,
                 "Free space: %s   Songs: %s" % (free or "?", count or "0"),
                 text_cache.ellipsize("Wi-Fi: %s   IP: %s" % (ssid or "not connected", ip or "-"),
                                      theme.FS_SMALL, 296)]
        if ts_ip and anywhere:
            lines[2] = text_cache.ellipsize("Tailscale IP: " + ts_ip, theme.FS_SMALL, 296)
        for i, line in enumerate(lines):
            surface.blit(text_cache.render(line, theme.FS_SMALL, theme.TEXT_DIM), (x, 72 + i * 18))
        qy = 130
        if self._qr is not None:
            r = self._qr.get_rect(midtop=(theme.SCREEN_W // 2, qy))
            surface.blit(self._qr, r)
        else:
            box = pygame.Rect(0, 0, QR_SIZE, QR_SIZE)
            box.midtop = (theme.SCREEN_W // 2, qy)
            pygame.draw.rect(surface, theme.BG_LIGHT, box, border_radius=8)
            msg = "No Wi-Fi" if not (self._ts_ip() if self.anywhere else self.net.ip) else "Uploader off"
            m = text_cache.render(msg, theme.FS_BODY, theme.TEXT_DIM)
            surface.blit(m, m.get_rect(center=box.center))
        cap = caption_for(self._qr is not None, self._ts_ip() if self.anywhere else self.net.ip,
                          self.anywhere)
        c = text_cache.render(text_cache.ellipsize(cap, theme.FS_SMALL, 296), theme.FS_SMALL, theme.TEXT_DIM)
        surface.blit(c, c.get_rect(midtop=(theme.SCREEN_W // 2, qy + QR_SIZE + 4)))
        if self._qr_url:
            # Never ellipsized: the full URL (with token) must be typeable if the scan fails.
            for i, line in enumerate(wrap_chars(self._qr_url, theme.FS_SMALL, 296)[:3]):
                u = text_cache.render(line, theme.FS_SMALL, theme.PRIMARY_LIGHT)
                surface.blit(u, u.get_rect(midtop=(theme.SCREEN_W // 2, qy + QR_SIZE + 20 + i * 13)))
        col = {"success": theme.SUCCESS, "warn": theme.WARNING, "error": theme.ERROR}.get(
            self.status_kind, theme.TEXT)
        if self.status:
            s = text_cache.render(text_cache.ellipsize(self.status, theme.FS_BODY, 296), theme.FS_BODY, col)
            surface.blit(s, s.get_rect(midtop=(theme.SCREEN_W // 2, 332)))
        self.rescan_btn.draw(surface)
        self.dirty = False

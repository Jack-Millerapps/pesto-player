"""Settings screen: a scrolling list of real controls (volume, output, shuffle,
repeat, screen timeout, brightness, sleep timer, rescan, storage, network,
battery, version, shutdown/restart/exit with confirm).

Rows are 56 px tall (touch friendly). The volume row is a tap-to-set bar (a scroll
drag must never change volume, so there is no drag slider in a scrolling list).
Anything that needs the whole app (shutdown, restart, exit, brightness) goes
through `hooks`, a dict of callables supplied by main.py.
"""
import pygame

import config
from hardware.system import NetInfo, disk_info, human_bytes
from player.prefs import Prefs
from ui import text_cache, theme
from ui.screen_manager import Screen
from ui.widgets import ScrollList

ROWS = [
    ("volume", "Volume"), ("output", "Audio output"), ("shuffle", "Shuffle"),
    ("repeat", "Repeat"), ("timeout", "Screen timeout"), ("brightness", "Brightness"),
    ("sleep", "Sleep timer"), ("rescan", "Rescan library"), ("add_music", "Add music"),
    ("storage", "Storage"), ("network", "Wi-Fi"), ("battery", "Battery"),
    ("version", "Version"), ("shutdown", "Shut down"), ("restart", "Restart app"),
    ("exit", "Exit app"),
]
NAV_KEYS = {"add_music", "output"}
DANGER_KEYS = {"shutdown", "restart", "exit"}
VOL_BAR_X0, VOL_BAR_X1 = 130, 300
TIMEOUT_LABEL = {0: "Never", 30: "30 s", 60: "1 min", 120: "2 min", 300: "5 min"}


class SettingsScreen(Screen):
    def __init__(self, screen_manager, audio_player, music_library, prefs=None, hooks=None,
                 battery=None, display=None, netinfo=None):
        super().__init__(screen_manager)
        self.audio_player = audio_player
        self.library = music_library
        self.prefs = prefs or Prefs()
        self.hooks = hooks or {}
        self.battery = battery
        self.display = display
        self.net = netinfo or NetInfo()
        self._down_pos = (0, 0)
        self._poll_t = 0.0
        self._cache = {}
        self._scan_text = None
        top = theme.STATUS_H
        self.list = ScrollList((0, top, theme.SCREEN_W, theme.CONTENT_BOTTOM_MINI - top),
                               theme.ROW_H, self._draw_row, self._on_tap, items=ROWS)

    # ------------------------------------------------------------- values
    def _state(self):
        try:
            return self.audio_player.get_state()
        except Exception:
            return {}

    def value_text(self, key):
        st = self._state()
        if key == "volume":
            return "%d%%" % st.get("volume", 0)
        if key == "output":
            return "Speaker"
        if key == "shuffle":
            return "On" if st.get("shuffle") else "Off"
        if key == "repeat":
            return {"off": "Off", "all": "All", "one": "One"}.get(st.get("repeat"), "Off")
        if key == "timeout":
            return TIMEOUT_LABEL.get(self.prefs.screen_timeout, "")
        if key == "brightness":
            if self.display is not None and not self.display.has_backlight:
                return "Not adjustable"
            return "%d%%" % self.prefs.brightness
        if key == "sleep":
            rem = self.prefs.sleep_timer_remaining()
            return "Off" if rem is None else "%d min left" % max(1, int(rem // 60) + (1 if rem % 60 else 0))
        if key == "rescan":
            if self._scan_text:
                return self._scan_text
            try:
                return "Scanning..." if self.library.is_scanning() else "%d songs" % len(self.library.get_tracks())
            except Exception:
                return ""
        if key == "storage":
            free, total = disk_info(config.MUSIC_DIRECTORY)
            return "%s free of %s" % (human_bytes(free), human_bytes(total)) if total else "Unknown"
        if key == "network":
            return self.net.ssid or "Not connected"
        if key == "battery":
            lvl = self.battery.get_level() if self.battery is not None else None
            return "No sensor" if lvl is None else "%d%%" % lvl
        if key == "version":
            return config.APP_VERSION
        return ""

    def sub_text(self, key):
        if key == "network":
            return self.net.ip or ""
        return ""

    # ------------------------------------------------------------- drawing
    def _draw_row(self, surface, rect, item, index, state):
        key, label = item
        if state.get("pressed"):
            pygame.draw.rect(surface, theme.BG_PRESSED, rect)
        color = theme.ERROR if key in DANGER_KEYS and key == "shutdown" else theme.TEXT
        x = rect.x + theme.PAD
        lbl = text_cache.render(label, theme.FS_BODY, color)
        surface.blit(lbl, (x, rect.centery - lbl.get_height() // 2))
        if key == "volume":
            vol = self._state().get("volume", 0)
            bar = pygame.Rect(VOL_BAR_X0, rect.centery - 3, VOL_BAR_X1 - VOL_BAR_X0, 6)
            pygame.draw.rect(surface, theme.BORDER, bar, border_radius=3)
            fill = bar.copy()
            fill.w = int(bar.w * vol / 100.0)
            if fill.w:
                pygame.draw.rect(surface, theme.PRIMARY, fill, border_radius=3)
            pygame.draw.circle(surface, theme.TEXT, (bar.x + fill.w, bar.centery), 8)
        elif key in DANGER_KEYS:
            pass
        else:
            val = self.value_text(key)
            sub = self.sub_text(key)
            max_w = rect.w - 2 * theme.PAD - lbl.get_width() - 24 - (14 if key in NAV_KEYS else 0)
            if key == "shuffle":
                self._draw_toggle(surface, rect, self._state().get("shuffle", False))
            elif val:
                v = text_cache.render(text_cache.ellipsize(val, theme.FS_BODY, max(40, max_w)),
                                      theme.FS_BODY, theme.PRIMARY_LIGHT if key != "version" else theme.TEXT_DIM)
                right = rect.right - theme.PAD - (14 if key in NAV_KEYS else 0)
                if sub:
                    s = text_cache.render(sub, theme.FS_SMALL, theme.TEXT_DIM)
                    surface.blit(v, v.get_rect(topright=(right, rect.centery - 18)))
                    surface.blit(s, s.get_rect(topright=(right, rect.centery + 2)))
                else:
                    surface.blit(v, v.get_rect(midright=(right, rect.centery)))
            if key in NAV_KEYS:
                cx, cy = rect.right - theme.PAD - 4, rect.centery
                pygame.draw.lines(surface, theme.TEXT_DIM, False,
                                  [(cx - 4, cy - 6), (cx, cy), (cx - 4, cy + 6)], 2)
        pygame.draw.line(surface, theme.BORDER, (rect.x + theme.PAD, rect.bottom - 1),
                         (rect.right, rect.bottom - 1))

    @staticmethod
    def _draw_toggle(surface, rect, on):
        pill = pygame.Rect(0, 0, 44, 24)
        pill.midright = (rect.right - theme.PAD, rect.centery)
        pygame.draw.rect(surface, theme.PRIMARY if on else theme.BORDER, pill, border_radius=12)
        cx = pill.right - 12 if on else pill.left + 12
        pygame.draw.circle(surface, theme.TEXT, (cx, pill.centery), 9)

    def draw(self, surface):
        self.list.draw(surface)
        self.dirty = False

    # --------------------------------------------------------------- touch
    def handle_touch(self, pos, kind):
        if kind == "down":
            self._down_pos = pos
        handled = self.list.handle_touch(pos, kind)
        if self.list.dirty:
            self.dirty = True
        return handled

    def _on_tap(self, item, index):
        key = item[0]
        a = self.audio_player
        sm = self.screen_manager
        if key == "volume":
            x = self._down_pos[0]
            vol = round(100.0 * (x - VOL_BAR_X0) / (VOL_BAR_X1 - VOL_BAR_X0))
            a.set_volume(max(0, min(100, vol)))
        elif key == "output":
            sm.toast("Bluetooth output isn't available yet")
        elif key == "shuffle":
            a.shuffle = not a.shuffle
        elif key == "repeat":
            a.repeat = {"off": "all", "all": "one", "one": "off"}.get(a.repeat, "off")
        elif key == "timeout":
            self.prefs.cycle_timeout()
        elif key == "brightness":
            if self.display is not None and not self.display.has_backlight:
                sm.toast("This screen has no brightness control")
            else:
                self.prefs.cycle_brightness()
                fn = self.hooks.get("brightness")
                if fn:
                    fn(self.prefs.brightness)
        elif key == "sleep":
            self.prefs.cycle_sleep_timer()
        elif key == "rescan":
            self._rescan()
        elif key == "add_music":
            sm.show("library")
            sm.push("add_music")
        elif key in DANGER_KEYS:
            self._confirm(key)
        self.dirty = True

    def _rescan(self):
        try:
            if self.library.is_scanning():
                return

            def prog(done, total):
                self._scan_text = "%d/%d" % (done, total) if total else "Scanning..."
                self.dirty = True

            def done():
                self._scan_text = None
                self.dirty = True

            self._scan_text = "Scanning..."
            self.library.start_scan(on_progress=prog, on_done=done)
        except Exception as e:
            self.screen_manager.toast("Scan failed: %s" % e, "error")

    def _confirm(self, key):
        labels = {"shutdown": "Shut down now", "restart": "Restart app now", "exit": "Exit app now"}
        fn = self.hooks.get(key)
        if fn is None:
            self.screen_manager.toast("Not available", "warn")
            return
        self.screen_manager.show_sheet([(labels[key], fn)])

    # -------------------------------------------------------------- update
    def on_enter(self, **kw):
        self.net.refresh()
        self._poll_t = 0.0
        self.dirty = True

    def on_leave(self):
        self.list.handle_touch((0, 0), "cancel")

    def update(self, dt):
        self.list.update(dt)
        if self.list.dirty:
            self.dirty = True
        self._poll_t += dt
        if self._poll_t >= 1.0:
            self._poll_t = 0.0
            snap = tuple(self.value_text(k) + self.sub_text(k) for k, _ in ROWS)
            if snap != self._cache.get("snap"):
                self._cache["snap"] = snap
                self.dirty = True

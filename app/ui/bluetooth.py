"""Settings > Bluetooth: turn Bluetooth on/off, scan, tap a speaker/headphones to
pair + trust + connect, see what is connected, disconnect, forget.

All Bluetooth work happens on BluetoothManager's worker thread
(hardware/bluetooth.py); this screen only reads manager.snapshot() /
device_list() and redraws when manager.version changes.

BluetoothEvents runs on the main thread from AudioPlayer.update() (so it also runs
while the screen is asleep and music is playing): it turns manager events into
toasts, the status-bar BT indicator, a pause when the speaker drops mid-song, and a
stream reopen when audio could not be moved to the new output.

install(sm, audio_player) wires all of it; SettingsScreen calls it, so main.py does
not need to know about Bluetooth.
"""
import pygame

from ui import text_cache, theme
from ui.screen_manager import Screen, draw_bt_glyph
from ui.widgets import Button, ScrollList

HEADER_H = 44
CARD_Y = theme.STATUS_H + HEADER_H + 4          # 72
CARD_H = 60
SECTION_Y = CARD_Y + CARD_H + 6                 # 138
LIST_Y = SECTION_Y + theme.MIN_TOUCH + 2        # 184
TOGGLE_W = 76
BUSY_LABEL = {"pairing": "Pairing...", "connecting": "Connecting...",
              "forgetting": "Forgetting...", "power": "Working..."}


class BluetoothEvents:
    """Main-thread consumer of BluetoothManager events (see module docstring)."""

    def __init__(self, screen_manager, manager, audio_player):
        self.sm = screen_manager
        self.bt = manager
        self.audio = audio_player

    def _toast(self, msg, kind="info"):
        try:
            self.sm.toast(msg, kind)
        except Exception:
            pass

    def _playing(self):
        try:
            return bool(self.audio.get_state().get("playing"))
        except Exception:
            return False

    def __call__(self):
        for ev in self.bt.poll_events():
            kind = ev[0]
            if kind == "connected":
                _, name, routed = ev
                self._toast("Playing on %s" % name, "success")
                if not routed and self._playing():
                    self.audio.reopen_output()      # new stream opens on the new default
            elif kind == "disconnected":
                _, name, by_user = ev
                if by_user:
                    self._toast("Disconnected from %s" % name)
                    if self._playing() and not self.bt.router.available():
                        self.audio.reopen_output()
                else:
                    was = self.audio.pause_for_output_change()
                    self._toast("%s disconnected%s" % (name, " - paused" if was else ""), "warn")
            elif kind == "error":
                self._toast(ev[1], "error")
            elif kind == "info":
                self._toast(ev[1])
        sb = getattr(self.sm, "status_bar", None)
        if sb is not None:
            sb.set_bluetooth_connected(self.bt.connected_mac is not None)


class BluetoothScreen(Screen):
    has_mini_player = False

    def __init__(self, screen_manager, manager):
        super().__init__(screen_manager)
        self.bt = manager
        self._ver = -1
        self._snap = manager.snapshot()
        self._dots = 0
        self._dots_t = 0.0
        top = theme.STATUS_H
        self.back = Button((4, top, theme.MIN_TOUCH, HEADER_H), icon="back", style="ghost",
                           on_click=self._on_back)
        self.toggle_rect = pygame.Rect(theme.SCREEN_W - TOGGLE_W, top, TOGGLE_W, HEADER_H)
        self._toggle_down = False
        self.disconnect_btn = Button((theme.SCREEN_W - theme.PAD - 8 - 104, CARD_Y + (CARD_H - theme.MIN_TOUCH) // 2,
                                      104, theme.MIN_TOUCH), "Disconnect", self._disconnect,
                                     style="secondary")
        self.scan_btn = Button((theme.SCREEN_W - theme.PAD - 96, SECTION_Y, 96, theme.MIN_TOUCH),
                               "Scan", self._toggle_scan)
        self.widgets = [self.back, self.disconnect_btn, self.scan_btn]
        self.list = ScrollList((0, LIST_Y, theme.SCREEN_W, theme.CONTENT_BOTTOM - LIST_Y),
                               theme.ROW_H, self._draw_row, self._on_tap,
                               on_long_press=self._on_long_press)
        self._sync(force=True)

    # ------------------------------------------------------------- state
    def _sync(self, force=False):
        v = self.bt.version
        if v == self._ver and not force:
            return False
        self._ver = v
        self._snap = self.bt.snapshot()
        s = self._snap
        self.list.set_items(self.bt.device_list() if s["powered"] and s["available"] else [])
        self.disconnect_btn.enabled = bool(s["connected_mac"]) and not s["busy"]
        self.scan_btn.enabled = bool(s["available"]) and not s["busy"]
        self.scan_btn.text = "Stop" if s["scanning"] else "Scan"
        self.scan_btn.style = "secondary" if s["scanning"] else "primary"
        self.dirty = True
        return True

    def _busy_for(self, mac):
        b = self._snap.get("busy")
        return BUSY_LABEL.get(b[0], "Working...") if b and b[1] == mac else None

    # ------------------------------------------------------------- actions
    def _on_back(self):
        if not self.screen_manager.pop():
            self.screen_manager.show("settings")

    def _toggle_power(self):
        s = self._snap
        if s["available"] is False:
            self.screen_manager.toast("No Bluetooth adapter found", "error")
            return
        if s["busy"]:
            self.screen_manager.toast("One moment - Bluetooth is busy", "warn")
            return
        self.bt.set_powered(not s["powered"])

    def _toggle_scan(self):
        if self._snap["scanning"]:
            self.bt.stop_scan()
        else:
            self.bt.start_scan()

    def _disconnect(self):
        self.bt.disconnect()

    def _on_tap(self, item, index):
        if self._snap.get("busy"):
            self.screen_manager.toast("One moment - Bluetooth is busy", "warn")
            return
        mac, name = item["mac"], item.get("name") or item["mac"]
        if item.get("connected"):
            self.screen_manager.show_sheet([("Disconnect", self.bt.disconnect),
                                            ("Forget %s" % name, lambda: self.bt.forget(mac))])
        elif item.get("paired"):
            self.screen_manager.show_sheet([("Connect", lambda: self.bt.connect(mac)),
                                            ("Forget %s" % name, lambda: self.bt.forget(mac))])
        else:
            self.bt.connect(mac)
            self.dirty = True

    def _on_long_press(self, item, index):
        if item.get("paired") and not self._snap.get("busy"):
            name = item.get("name") or item["mac"]
            self.screen_manager.show_sheet([("Forget %s" % name, lambda: self.bt.forget(item["mac"]))])

    # ------------------------------------------------------------- drawing
    def _draw_header(self, surface):
        self.back.draw(surface)
        t = text_cache.render("Bluetooth", theme.FS_HEADER, theme.TEXT, bold=True)
        surface.blit(t, (56, theme.STATUS_H + (HEADER_H - t.get_height()) // 2))
        s = self._snap
        on = bool(s["powered"])
        pill = pygame.Rect(0, 0, 44, 24)
        pill.center = self.toggle_rect.center
        col = theme.PRIMARY if on else theme.BORDER
        if s["available"] is False:
            col = theme.BG_PRESSED
        if self._toggle_down:
            pygame.draw.rect(surface, theme.BG_PRESSED, self.toggle_rect, border_radius=8)
        pygame.draw.rect(surface, col, pill, border_radius=12)
        pygame.draw.circle(surface, theme.TEXT if s["available"] is not False else theme.TEXT_DISABLED,
                           (pill.right - 12 if on else pill.left + 12, pill.centery), 9)

    def _status_lines(self):
        s = self._snap
        if s["available"] is None:
            return "Checking Bluetooth...", "", theme.TEXT_DIM
        if s["available"] is False:
            return "Bluetooth unavailable", "Run pi/bluetooth/setup.sh on the Pi", theme.ERROR
        busy = s.get("busy")
        if busy and busy[1]:
            return BUSY_LABEL.get(busy[0], "Working..."), self.bt.name_of(busy[1]), theme.PRIMARY_LIGHT
        if not s["powered"]:
            return "Bluetooth is off", "Music plays on the speaker", theme.TEXT_DIM
        if s["connected_mac"]:
            return s["connected_name"] or "Connected", "Connected - music plays here", theme.SUCCESS
        return "Not connected", "Music plays on the speaker", theme.TEXT

    def _draw_card(self, surface):
        card = pygame.Rect(theme.PAD, CARD_Y, theme.SCREEN_W - 2 * theme.PAD, CARD_H)
        pygame.draw.rect(surface, theme.BG_LIGHT, card, border_radius=10)
        line1, line2, col = self._status_lines()
        connected = bool(self._snap["connected_mac"])
        draw_bt_glyph(surface, (card.x + 22, card.centery), 10,
                      theme.SUCCESS if connected else theme.TEXT_DIM)
        x = card.x + 42
        right = (self.disconnect_btn.rect.x - 8) if connected else card.right - 10
        img = text_cache.render(text_cache.ellipsize(line1, theme.FS_TITLE, right - x, True),
                                theme.FS_TITLE, col, bold=True)
        if line2:
            sub = text_cache.render(text_cache.ellipsize(line2, theme.FS_SMALL, right - x),
                                    theme.FS_SMALL, theme.TEXT_DIM)
            surface.blit(img, (x, card.centery - img.get_height() + 1))
            surface.blit(sub, (x, card.centery + 3))
        else:
            surface.blit(img, (x, card.centery - img.get_height() // 2))
        if connected:
            self.disconnect_btn.draw(surface)

    def _draw_section(self, surface):
        s = self._snap
        if s["scanning"]:
            label = "Searching" + "." * (1 + self._dots % 3)
        else:
            label = "DEVICES"
        img = text_cache.render(label, theme.FS_SMALL, theme.TEXT_DIM, bold=True)
        surface.blit(img, (theme.PAD + 4, SECTION_Y + (theme.MIN_TOUCH - img.get_height()) // 2))
        if s["available"]:
            self.scan_btn.draw(surface)

    def _empty_text(self):
        s = self._snap
        if not s["available"]:
            return [] if s["available"] is None else ["Needs BlueZ + PipeWire on the Pi.",
                                                      "See pi/bluetooth/README.md"]
        if not s["powered"]:
            return ["Turn Bluetooth on to find", "speakers and headphones."]
        if s["scanning"]:
            return ["Looking for devices...", "Put yours in pairing mode."]
        return ["Tap Scan, then put your speaker", "or headphones in pairing mode."]

    def _draw_row(self, surface, rect, item, index, state):
        if state.get("pressed"):
            pygame.draw.rect(surface, theme.BG_PRESSED, rect)
        mac = item["mac"]
        busy = self._busy_for(mac)
        if busy:
            sub, sub_col = busy, theme.PRIMARY_LIGHT
        elif item.get("connected"):
            sub, sub_col = "Connected", theme.SUCCESS
        elif item.get("paired"):
            sub, sub_col = "Paired - tap for options", theme.TEXT_DIM
        elif item.get("audio") is False:
            sub, sub_col = "Not a speaker or headphones", theme.TEXT_DISABLED
        else:
            sub, sub_col = "Tap to pair and connect", theme.TEXT_DIM
        name_col = theme.TEXT if item.get("audio") is not False else theme.TEXT_DIM
        x = rect.x + theme.PAD
        if item.get("paired"):
            draw_bt_glyph(surface, (x + 6, rect.centery), 8,
                          theme.SUCCESS if item.get("connected") else theme.PRIMARY_LIGHT)
            x += 22
        max_w = rect.right - theme.PAD - x - 18
        n = text_cache.render(text_cache.ellipsize(item.get("name") or mac, theme.FS_BODY, max_w),
                              theme.FS_BODY, name_col)
        s = text_cache.render(text_cache.ellipsize(sub, theme.FS_SMALL, max_w), theme.FS_SMALL, sub_col)
        surface.blit(n, (x, rect.centery - n.get_height() + 1))
        surface.blit(s, (x, rect.centery + 3))
        if item.get("paired"):
            cy = rect.centery
            for dx in (-8, 0, 8):
                pygame.draw.circle(surface, theme.TEXT_DIM, (rect.right - theme.PAD - 8 + dx, cy), 2)
        pygame.draw.line(surface, theme.BORDER, (rect.x + theme.PAD, rect.bottom - 1),
                         (rect.right, rect.bottom - 1))

    def draw(self, surface):
        self._draw_header(surface)
        self._draw_card(surface)
        self._draw_section(surface)
        pygame.draw.line(surface, theme.BORDER, (0, LIST_Y - 1), (theme.SCREEN_W, LIST_Y - 1))
        if self.list.items:
            self.list.draw(surface)
        else:
            y = LIST_Y + 28
            for line in self._empty_text():
                img = text_cache.render(line, theme.FS_BODY, theme.TEXT_DIM)
                surface.blit(img, img.get_rect(midtop=(theme.SCREEN_W // 2, y)))
                y += img.get_height() + 6
        self.dirty = False

    # --------------------------------------------------------------- touch
    def handle_touch(self, pos, kind):
        handled = False
        for w in self.widgets:
            if w is self.disconnect_btn and not self._snap["connected_mac"]:
                continue
            if w is self.scan_btn and not self._snap["available"]:
                continue
            if w.handle_touch(pos, kind):
                handled = True
                break
        if not handled:
            if kind == "down" and self.toggle_rect.collidepoint(pos):
                self._toggle_down = True
                handled = True
            elif self._toggle_down and kind in ("up", "cancel", "move"):
                if kind == "up":
                    self._toggle_down = False
                    if self.toggle_rect.collidepoint(pos):
                        self._toggle_power()
                elif kind == "cancel" or not self.toggle_rect.collidepoint(pos):
                    self._toggle_down = False
                handled = True
            else:
                handled = self.list.handle_touch(pos, kind)
        if any(w.dirty for w in self.widgets) or self.list.dirty or handled:
            self.dirty = True
        return handled

    # -------------------------------------------------------------- update
    def on_enter(self, **kw):
        self.bt.refresh()
        self._sync(force=True)

    def on_leave(self):
        self.list.handle_touch((0, 0), "cancel")
        self._toggle_down = False
        if self._snap.get("scanning"):
            self.bt.stop_scan()

    def update(self, dt):
        self.list.update(dt)
        if self.list.dirty:
            self.dirty = True
        self._sync()
        if self._snap.get("scanning"):
            self._dots_t += dt
            if self._dots_t >= 0.5:
                self._dots_t = 0.0
                self._dots += 1
                self.dirty = True


def install(screen_manager, audio_player, manager=None):
    """Create the manager (unless given), register the Bluetooth screen as a child of
    the Settings tab, hook event handling into the audio player, and start the
    manager (probe + auto-reconnect run on its worker thread). Returns the manager."""
    if manager is None:
        from hardware.bluetooth import create_bluetooth_manager
        manager = create_bluetooth_manager()
    screen = BluetoothScreen(screen_manager, manager)
    if hasattr(screen_manager, "register"):
        screen_manager.register("bluetooth", screen, tab="settings", child=True)
    hooks = getattr(audio_player, "tick_hooks", None)
    if hooks is not None:
        hooks.append(BluetoothEvents(screen_manager, manager, audio_player))
    manager.start()
    return manager

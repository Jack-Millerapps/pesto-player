#!/usr/bin/env python3
"""
Pesto Player - main entry point (local music, 320x480 portrait, Pi Zero 2 W).

Mouse = touch in TEST_MODE; Up/Down = volume; ESC = power button (sleep/wake);
Q = quit. TEST_MODE is auto-detected (see config.py); set PESTO_TEST=0/1 to force.

Exit codes: 0 = clean exit or shutdown (systemd does not restart), 3 = restart
requested from Settings (pesto-player.service has RestartForceExitStatus=3).

Screens from the UI modules are imported defensively: a missing/broken module is
skipped with a log line so the rest of the app still starts.
"""

import importlib
import os
import queue
import sys
import time
import traceback

import pygame

import config
from hardware import system
from hardware.battery import BatteryMonitor, MockBatteryMonitor
from hardware.buttons import ButtonHandler, MockButtonHandler
from player.audio import create_player
from player.library import MockMusicLibrary, MusicLibrary
from player.playlist import PlaylistStore
from player.prefs import Prefs
from ui.screen_manager import ScreenManager

EXIT_OK = 0
EXIT_RESTART = 3
BATTERY_POLL_S = 10.0


def _load(module, attr):
    """Import ui.<module>.<attr> or return None (logged)."""
    try:
        return getattr(importlib.import_module("ui." + module), attr)
    except Exception as e:
        print(f"UI: skipping {module}.{attr}: {type(e).__name__}: {e}")
        return None


class _HudAdapter:
    """ScreenManager overlays expose `active`; VolumeHUD exposes `visible`."""

    def __init__(self, hud):
        self.hud = hud

    @property
    def active(self):
        return getattr(self.hud, "active", getattr(self.hud, "visible", False))

    @property
    def dirty(self):
        return self.hud.dirty

    @dirty.setter
    def dirty(self, v):
        self.hud.dirty = v

    def update(self, dt):
        self.hud.update(dt)

    def draw(self, surface):
        self.hud.draw(surface)


class PestoPlayer:
    def __init__(self):
        print("=" * 60)
        print("PESTO PLAYER" + ("  [TEST MODE]" if config.TEST_MODE else ""))
        print("=" * 60)
        pygame.init()
        pygame.display.set_caption("Pesto Player")
        size = (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.screen = pygame.display.set_mode(size if config.TEST_MODE else size,
                                              0 if config.TEST_MODE else pygame.FULLSCREEN)
        if not config.TEST_MODE:
            pygame.mouse.set_visible(False)

        self.clock = pygame.time.Clock()
        self.running = True
        self.exit_code = EXIT_OK
        self.asleep = False
        self._wake_swallow = False
        self._last_input = time.time()
        self._battery_t = BATTERY_POLL_S
        self._critical_count = 0
        self._low_warned = False
        self._scan_done = False
        self._restored = False
        self._mouse_down = False
        self._events = queue.SimpleQueue()   # GPIO callbacks (other thread) -> main thread
        self._last_error_toast = 0.0

        self.prefs = Prefs()
        self.display_power = system.DisplayPower()
        self.net = system.NetInfo()
        self._init_audio()
        self._init_library()
        self._init_hardware()
        self._init_ui()
        self._start_initial_scan()
        print("Initialization complete.")

    # ---------------------------------------------------------------- init
    def _init_audio(self):
        self.audio_player = create_player()
        self.audio_player.on_error = self._on_audio_error

    def _init_library(self):
        music_dir = os.path.expanduser(config.MUSIC_DIRECTORY)
        if os.path.isdir(music_dir):
            self.music_library = MusicLibrary(music_dir)
        elif config.TEST_MODE:
            print(f"Music dir {music_dir} not found; using demo library (TEST_MODE)")
            self.music_library = MockMusicLibrary()
        else:
            try:
                os.makedirs(music_dir, exist_ok=True)  # so the uploader has somewhere to write
            except OSError as e:
                print(f"Cannot create {music_dir}: {e}")
            self.music_library = MusicLibrary(music_dir)
        self.playlist_store = PlaylistStore()

    def _init_hardware(self):
        self.battery = MockBatteryMonitor() if config.TEST_MODE else BatteryMonitor()
        self.buttons = MockButtonHandler() if config.TEST_MODE else ButtonHandler()
        # Callbacks may run on gpiozero's thread: they only enqueue; step() handles
        # them on the main thread (pygame/ScreenManager are not thread-safe).
        for name in ("volume_up", "volume_down", "power_short", "power_long"):
            self.buttons.set_callback(name, lambda n=name: self._events.put(n))

    def _init_ui(self):
        sm = self.screen_manager = ScreenManager(self.screen)
        args = (sm, self.audio_player, self.music_library)

        NowPlaying = _load("now_playing", "NowPlayingScreen")
        if NowPlaying:
            sm.register("now_playing", NowPlaying(*args), tab="now_playing")
        reg = _load("library", "register_library_screens")
        if reg:
            reg(sm, self.audio_player, self.music_library, self.playlist_store)
        Queue = _load("queue", "QueueScreen")
        if Queue:
            try:
                sm.register("queue", Queue(*args, playlist_store=self.playlist_store), tab="queue")
            except TypeError:
                sm.register("queue", Queue(*args), tab="queue")
        Mini = _load("mini_player", "MiniPlayer")
        if Mini:
            sm.mini_player = Mini(*args)
        Hud = _load("volume_hud", "VolumeHUD")
        self.volume_hud = Hud() if Hud else None
        if self.volume_hud:
            sm.add_overlay(_HudAdapter(self.volume_hud))

        Add = _load("add_music", "AddMusicScreen")
        if Add:
            sm.register("add_music", Add(sm, self.audio_player, self.music_library, self.net), tab="library")
        Settings = _load("settings", "SettingsScreen")
        if Settings:
            hooks = {"shutdown": self._do_shutdown, "restart": self._do_restart,
                     "exit": self._do_exit, "brightness": self._apply_brightness}
            sm.register("settings", Settings(sm, self.audio_player, self.music_library, self.prefs,
                                             hooks, self.battery, self.display_power, self.net),
                        tab="settings")
        if "now_playing" in sm._screens:
            sm.show("now_playing")
        elif sm._screens:
            sm.show(next(iter(sm._screens)))
        self._update_battery(force=True)
        if self.prefs.brightness and self.display_power.has_backlight:
            self._apply_brightness(self.prefs.brightness)

    def _start_initial_scan(self):
        def done():
            self._scan_done = True
        self.music_library.start_scan(on_done=done)

    # ------------------------------------------------------------ main loop
    def run(self):
        print("Starting main loop...")
        dt = 1.0 / config.FPS
        while self.running:
            self.step(dt)
            fps = 5 if self.asleep else self.screen_manager.target_fps()
            dt = self.clock.tick(fps) / 1000.0
        self._cleanup()
        return self.exit_code

    def step(self, dt):
        """One guarded frame. An error in any callback/screen is logged and toasted
        but never kills the app (systemd would restart-loop on a bad restored item)."""
        try:
            self._step(dt)
        except Exception as e:
            traceback.print_exc()
            self._recover_display()
            now = time.time()
            if now - self._last_error_toast > 5.0:
                self._last_error_toast = now
                try:
                    self.screen_manager.toast("Something went wrong", "error")
                except Exception:
                    pass

    def _recover_display(self):
        """After a failed frame the surface may be half-drawn with a leftover clip:
        reset the clip and make the next frame repaint everything."""
        try:
            self.screen.set_clip(None)
            sm = self.screen_manager
            sm._full = True              # ScreenManager has no public "invalidate" yet
            cur = sm.current_screen()
            if cur is not None:
                cur.dirty = True
        except Exception:
            traceback.print_exc()

    def _drain_button_events(self):
        handlers = {"volume_up": lambda: self._volume_step(+1),
                    "volume_down": lambda: self._volume_step(-1),
                    "power_short": self._on_power_short,
                    "power_long": self._on_power_long}
        while True:
            try:
                name = self._events.get_nowait()
            except queue.Empty:
                return
            try:
                handlers[name]()
            except Exception:
                traceback.print_exc()

    def _step(self, dt):
        """One frame: events, updates, draw. Separate from run() so tests can drive it."""
        self._handle_events()
        self._drain_button_events()
        self.audio_player.update()
        self.buttons.update()
        if self._scan_done:
            self._scan_done = False
            if not self._restored:
                self._restored = True
                self.audio_player.restore_state(self.music_library)
            self.screen_manager.current_screen().dirty = True
        self._update_battery()
        self._update_timers()
        if self.asleep:
            return
        self.screen_manager.update(dt)
        rects = self.screen_manager.draw()
        if rects:
            bounds = self.screen.get_rect()
            pygame.display.update([r.clip(bounds) for r in rects])

    def _handle_events(self):
        sm = self.screen_manager
        moved = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._touch_activity()
                if self._wake_swallow:
                    continue
                self._mouse_down = True
                sm.handle_touch(event.pos, "down")
            elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                moved = event.pos          # coalesce: only the last motion per frame
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if moved is not None and self._mouse_down:
                    sm.handle_touch(moved, "move")
                    moved = None
                self._wake_swallow = False
                if self._mouse_down:
                    self._mouse_down = False
                    sm.handle_touch(event.pos, "up")
            elif event.type == pygame.KEYDOWN:
                self._touch_activity()
                if config.TEST_MODE:
                    if isinstance(self.buttons, MockButtonHandler):
                        self.buttons.handle_key(event.key)
                    if event.key == pygame.K_q:
                        self.running = False
        if moved is not None and self._mouse_down:
            sm.handle_touch(moved, "move")

    # ------------------------------------------------------ sleep / wake
    def _touch_activity(self):
        self._last_input = time.time()
        if self.asleep:
            self._wake()
            self._wake_swallow = True       # the waking touch must not press anything

    def _sleep(self):
        if self.asleep:
            return
        self.asleep = True
        self.display_power.sleep()
        self.screen.fill((0, 0, 0))
        pygame.display.update()

    def _wake(self):
        if not self.asleep:
            return
        self.asleep = False
        self._last_input = time.time()
        self.display_power.wake()
        self.screen_manager._full = True
        cur = self.screen_manager.current_screen()
        if cur:
            cur.dirty = True

    def _update_timers(self):
        if self.prefs.sleep_timer_expired():
            self.audio_player.pause()
            self._sleep()
        t = self.prefs.screen_timeout
        if t and not self.asleep and time.time() - self._last_input >= t:
            self._sleep()

    # ------------------------------------------------------------ battery
    def _update_battery(self, force=False):
        self._battery_t += self.clock.get_time() / 1000.0 if not force else BATTERY_POLL_S
        if self._battery_t < BATTERY_POLL_S:
            return
        self._battery_t = 0.0
        self.battery.update()
        lvl = self.battery.get_level()
        self.screen_manager.status_bar.set_battery_level(lvl)   # None hides the percentage
        if lvl is None:
            return
        if self.battery.is_critical():
            self._critical_count += 1
            if self._critical_count >= 3 and not config.TEST_MODE:
                self.screen_manager.toast("Battery critical - shutting down", "error")
                self._do_shutdown()
        else:
            self._critical_count = 0
        if self.battery.is_low() and not self._low_warned:
            self._low_warned = True
            self.screen_manager.toast("Battery low", "warn")
        elif not self.battery.is_low():
            self._low_warned = False

    # ------------------------------------------------------- callbacks
    def _on_audio_error(self, message):
        self.screen_manager.toast(message, "error")

    def _volume_step(self, direction):
        was_asleep = self.asleep
        self._touch_activity()
        self._wake_swallow = False
        if direction > 0:
            self.audio_player.volume_up()
        else:
            self.audio_player.volume_down()
        if self.volume_hud and not was_asleep:
            self.volume_hud.show(self.audio_player.get_volume())

    def _on_power_short(self):
        if self.asleep:
            self._touch_activity()
            self._wake_swallow = False
        else:
            self._sleep()

    def _on_power_long(self):
        self._do_shutdown()

    def _apply_brightness(self, pct):
        self.display_power.set_brightness(pct)

    def _do_shutdown(self):
        self._wake()
        if config.TEST_MODE:
            print("[TEST_MODE] shutdown requested: exiting instead")
            self.exit_code = EXIT_OK
            self.running = False
            return
        self.audio_player.save_state()
        if system.shutdown():
            self.exit_code = EXIT_OK        # status 0: systemd must not restart us
            self.running = False
        else:
            self.screen_manager.toast("Shutdown failed (see pi/systemd/pesto-power.sudoers.example)", "error")

    def _do_restart(self):
        self.exit_code = EXIT_RESTART
        self.running = False

    def _do_exit(self):
        self.exit_code = EXIT_OK
        self.running = False

    # ----------------------------------------------------------- cleanup
    def _cleanup(self):
        print("Shutting down...")
        try:
            self.audio_player.cleanup()
            self.buttons.cleanup()
            self.display_power.wake()
        finally:
            pygame.quit()


def main():
    try:
        app = PestoPlayer()
        code = app.run()
    except KeyboardInterrupt:
        print("Interrupted")
        code = EXIT_OK
    except Exception:
        import traceback
        traceback.print_exc()
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()

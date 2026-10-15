"""Boot main.py headless with the mock library/player and draw every screen."""
import os

import pygame
import pytest

import config
import main as mainmod


@pytest.fixture
def app():
    a = mainmod.PestoPlayer()
    yield a
    # no pygame.quit(): text_cache keeps Font objects that would dangle (segfault)


def test_boots_with_mock_library_and_player(app):
    assert config.TEST_MODE
    sm = app.screen_manager
    for name in ("now_playing", "library", "queue", "settings", "add_music", "songs", "artists",
                 "albums", "playlists", "search", "artist_detail", "album_detail", "playlist_detail"):
        assert name in sm._screens, f"{name} not registered"
    assert sm.mini_player is not None and app.volume_hud is not None
    assert len(app.music_library.get_tracks()) == 5


def _frame(app, n=2):
    for _ in range(n):
        app.step(1 / 30)


def test_every_screen_draws_empty_and_with_queue(app):
    sm = app.screen_manager
    kw = {"artist_detail": {"artist_name": "Queen"},
          "album_detail": {"title": "Imagine", "artist": "John Lennon"},
          "playlist_detail": {}}
    for populated in (False, True):
        if populated:
            app.audio_player.set_queue(app.music_library.get_tracks(), 0)
        for name in list(sm._screens):
            sm.show(name, **kw.get(name, {}))
            _frame(app)
            assert sm.current_name() == name


def test_all_screens_draw_with_real_empty_library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MUSIC_DIRECTORY", str(tmp_path))
    a = mainmod.PestoPlayer()
    for name in list(a.screen_manager._screens):
        a.screen_manager.show(name)
        _frame(a)


def test_volume_buttons_and_power_sleep_wake(app):
    v = app.audio_player.get_volume()
    app._volume_step(+1)
    assert app.audio_player.get_volume() == v + config.VOLUME_STEP
    app._on_power_short()
    assert app.asleep
    _frame(app)
    app._on_power_short()
    assert not app.asleep


def test_restart_and_exit_codes(app):
    app._do_restart()
    assert app.exit_code == 3 and not app.running
    app.running = True
    app._do_exit()
    assert app.exit_code == 0 and not app.running


def test_touch_while_asleep_wakes_without_pressing(app):
    app._sleep()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(160, 450), button=1))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(160, 450), button=1))
    _frame(app)
    assert not app.asleep
    assert app.screen_manager.current_name() == "now_playing"   # tab tap was swallowed

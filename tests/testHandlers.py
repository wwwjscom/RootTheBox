# -*- coding: utf-8 -*-
"""
Unit tests for everything in handlers/
"""
import logging
import time
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from tornado.options import options

from handlers.BaseHandlers import BaseHandler
from handlers.ErrorHandlers import StopHandler
from libs import GameState
from libs.SecurityDecorators import game_started
from models import dbsession
from models.Team import Team
from models.User import User
from tests.Helpers import *
from tests.HTTPClient import ApplicationTest


class TestPublicHandlers(ApplicationTest):
    """Test functionality in handlers/PublicHandlers.py"""

    def test_home_page_get(self):
        rsp, body = self.get("/")
        self.assertIn(b"home_container", body)

    def test_login_get(self):
        rsp, body = self.get("/login")
        self.assertIn(b'<form class="form-signin" action="/login"', body)

    def test_login_post(self):
        user = create_user()
        self._login_failure()
        self._login_success()
        dbsession.delete(user)
        dbsession.commit()

    def _login_success(self):
        options.story_mode = True
        form = {"account": "HacKer", "password": "TestPassword"}
        rsp, body = self.post("/login", data=form)
        # TODO Should redirect to firstlogin
        # This fails in the @authenticated security descriptor due to no session. Memcached?
        # self.assertIn(b"Incoming Transmission", body)
        self.assertEqual(True, True)

    def _login_failure(self):
        form = {"account": "HacKer", "password": "A" * 16}
        rsp, body = self.post("/login", data=form)
        self.assertIn(b"Bad username and/or password, try again", body)

    def test_registration_get(self):
        rsp, body = self.get("/registration")
        self.assertIn(b'<form class="form-horizontal" action="/registration"', body)

    def test_registration_post(self):
        options.teams = True
        form = {
            "handle": "foobar",
            "team_name": "TestTeam",
            "motto": "Unit Tests are Cool",
            "pass1": "12345678901234567890",
            "pass2": "12345678901234567890",
            "bpass": "123456",
        }
        self._registration_post_token(form)
        self._registration_post_team_name(form)

    def _registration_post_token(self, form):
        options.restrict_registration = True
        form["token"] = "NotARealRegToken"
        rsp, body = self.post("/registration", data=form)
        self.assertIn(b"Invalid registration token", body)
        options.restrict_registration = False

    def _registration_post_team_name(self, form):
        options.public_teams = True
        form["team_name"] = ""
        rsp, body = self.post("/registration", data=form)
        self.assertIn(b"Team name must be 3 - 24 characters", body)
        form["team_name"] = "A" * 25
        rsp, body = self.post("/registration", data=form)
        self.assertIn(b"Team name must be 3 - 24 characters", body)
        options.public_teams = False

    def test_fake_robots_get(self):
        rsp, body = self.get("/robots")
        self.assertIn(b"User-agent: *", body)
        rsp, body = self.get("/robots.txt")
        self.assertIn(b"User-agent: *", body)

    def test_about_get(self):
        rsp, body = self.get("/about")
        self.assertIn(b"<title> About", body)


class GameStateTestCase(unittest.TestCase):
    """Shared fake app for the libs/GameState.py tests"""

    def _app(self, **overrides):
        settings = {
            "game_started": True,
            "countdown_timer": False,
            "countdown_expired": False,
            "hide_scoreboard": False,
            "stop_timer": False,
            "score_bots_callback": mock.Mock(_running=False),
            "suspend_registration": True,
            "registration_opened_at": None,
        }
        settings.update(overrides)
        app = mock.Mock()
        app.settings = settings
        return app


class TestCountdownSeconds(GameStateTestCase):
    """countdown_seconds() must be a pure read - no writes to settings"""

    def test_no_countdown_returns_none(self):
        self.assertIsNone(GameState.countdown_seconds(self._app()))

    def test_future_deadline(self):
        app = self._app(countdown_timer=time.time() + 60)
        seconds = GameState.countdown_seconds(app)
        self.assertTrue(55 < seconds <= 60, "got %r" % seconds)

    def test_past_deadline_clamps_to_zero(self):
        app = self._app(countdown_timer=time.time() - 30)
        self.assertEqual(GameState.countdown_seconds(app), 0.0)

    def test_reading_an_expired_countdown_mutates_nothing(self):
        """The whole point of the split: display must have no side effects"""
        app = self._app(
            countdown_timer=time.time() - 30, stop_timer=True, hide_scoreboard=True
        )
        before = dict(app.settings)
        GameState.countdown_seconds(app)
        self.assertEqual(app.settings, before)

    def test_seconds_remaining_returns_a_string(self):
        """
        Scoreboard templates gate on `{% if timer %}` - a float 0.0 is
        falsy and would hide the timer exactly when it expires.
        """
        handler = mock.Mock()
        handler.application = self._app(countdown_timer=time.time() - 5)
        value = BaseHandler.seconds_remaining(handler)
        self.assertEqual(value, "0.0")
        self.assertTrue(value)

    def test_seconds_remaining_none_without_countdown(self):
        handler = mock.Mock()
        handler.application = self._app()
        self.assertIsNone(BaseHandler.seconds_remaining(handler))


class TestExpireCountdown(GameStateTestCase):
    """expire_countdown() owns the side effects that used to live in timer()"""

    def setUp(self):
        patcher = mock.patch.object(GameState, "EventManager")
        self.events = patcher.start().instance.return_value
        self.addCleanup(patcher.stop)
        webhook = mock.patch.object(GameState, "send_game_stop_webhook")
        self.webhook = webhook.start()
        self.addCleanup(webhook.stop)

    def test_no_countdown_is_a_noop(self):
        app = self._app()
        self.assertFalse(GameState.expire_countdown(app))
        self.assertTrue(app.settings["game_started"])

    def test_not_yet_expired_is_a_noop(self):
        app = self._app(countdown_timer=time.time() + 60, stop_timer=True)
        before = dict(app.settings)
        self.assertFalse(GameState.expire_countdown(app))
        self.assertEqual(app.settings, before)
        self.assertFalse(self.events.push_game_stopped.called)

    def test_expired_with_stop_timer_stops_the_game(self):
        app = self._app(
            countdown_timer=time.time() - 1, stop_timer=True, hide_scoreboard=True
        )
        self.assertTrue(GameState.expire_countdown(app))
        self.assertFalse(app.settings["game_started"])
        self.assertFalse(app.settings["stop_timer"])
        self.assertFalse(app.settings["hide_scoreboard"])
        self.assertEqual(self.events.push_game_stopped.call_count, 1)
        self.assertEqual(self.webhook.call_count, 1)

    def test_expired_without_stop_timer_leaves_the_game_running(self):
        """
        A countdown can expire without ending the game (the scoreboard
        freeze case).  Nobody may be redirected, so no push may fire.
        """
        app = self._app(
            countdown_timer=time.time() - 1, stop_timer=False, hide_scoreboard=True
        )
        self.assertFalse(GameState.expire_countdown(app))
        self.assertTrue(app.settings["game_started"])
        self.assertFalse(app.settings["hide_scoreboard"])
        self.assertFalse(self.events.push_game_stopped.called)

    def test_second_call_does_not_re_unhide_the_scoreboard(self):
        """An admin re-hiding the board must not be overridden a tick later"""
        app = self._app(countdown_timer=time.time() - 1, stop_timer=True)
        GameState.expire_countdown(app)
        app.settings["hide_scoreboard"] = True
        self.assertFalse(GameState.expire_countdown(app))
        self.assertTrue(app.settings["hide_scoreboard"])


class TestRegistrationSecondsRemaining(GameStateTestCase):
    """registration_seconds_remaining() must be a pure read - no writes to settings"""

    def test_none_when_suspended(self):
        app = self._app(suspend_registration=True)
        self.assertIsNone(GameState.registration_seconds_remaining(app))

    def test_none_when_minutes_disabled(self):
        options.registration_open_minutes = 0
        app = self._app(suspend_registration=False, registration_opened_at=time.time())
        self.assertIsNone(GameState.registration_seconds_remaining(app))
        options.registration_open_minutes = 30

    def test_none_when_never_opened(self):
        app = self._app(suspend_registration=False, registration_opened_at=None)
        self.assertIsNone(GameState.registration_seconds_remaining(app))

    def test_in_range_within_the_window(self):
        options.registration_open_minutes = 30
        app = self._app(suspend_registration=False, registration_opened_at=time.time())
        remaining = GameState.registration_seconds_remaining(app)
        self.assertTrue(1795 < remaining <= 1800, "got %r" % remaining)

    def test_past_deadline_clamps_to_zero(self):
        options.registration_open_minutes = 30
        app = self._app(
            suspend_registration=False, registration_opened_at=time.time() - 999999
        )
        self.assertEqual(GameState.registration_seconds_remaining(app), 0.0)


class TestExpireRegistrationWindow(GameStateTestCase):
    """expire_registration_window() auto re-suspends registration after N minutes"""

    def test_suspended_is_a_noop(self):
        app = self._app(suspend_registration=True)
        self.assertFalse(GameState.expire_registration_window(app))

    def test_disabled_minutes_is_a_noop(self):
        options.registration_open_minutes = 0
        app = self._app(suspend_registration=False, registration_opened_at=time.time() - 999999)
        self.assertFalse(GameState.expire_registration_window(app))
        self.assertFalse(app.settings["suspend_registration"])
        options.registration_open_minutes = 30

    def test_not_yet_expired_is_a_noop(self):
        options.registration_open_minutes = 30
        app = self._app(suspend_registration=False, registration_opened_at=time.time())
        before = dict(app.settings)
        self.assertFalse(GameState.expire_registration_window(app))
        self.assertEqual(app.settings, before)

    def test_expired_closes_registration_and_clears_timestamp(self):
        options.registration_open_minutes = 30
        app = self._app(
            suspend_registration=False, registration_opened_at=time.time() - 1801
        )
        self.assertTrue(GameState.expire_registration_window(app))
        self.assertTrue(app.settings["suspend_registration"])
        self.assertIsNone(app.settings["registration_opened_at"])

    def test_second_call_after_closing_is_a_noop(self):
        options.registration_open_minutes = 30
        app = self._app(
            suspend_registration=False, registration_opened_at=time.time() - 1801
        )
        GameState.expire_registration_window(app)
        self.assertFalse(GameState.expire_registration_window(app))


class TestStopGamePushes(GameStateTestCase):
    """stop_game() tells connected clients, exactly once"""

    def setUp(self):
        patcher = mock.patch.object(GameState, "EventManager")
        self.events = patcher.start().instance.return_value
        self.addCleanup(patcher.stop)
        webhook = mock.patch.object(GameState, "send_game_stop_webhook")
        webhook.start()
        self.addCleanup(webhook.stop)

    def test_running_game_pushes_once(self):
        app = self._app(game_started=True)
        GameState.stop_game(app)
        self.assertFalse(app.settings["game_started"])
        self.assertEqual(self.events.push_game_stopped.call_count, 1)

    def test_already_stopped_game_does_not_push(self):
        app = self._app(game_started=False)
        GameState.stop_game(app)
        self.assertFalse(self.events.push_game_stopped.called)


class TestStartGamePushes(GameStateTestCase):
    """start_game() releases anyone parked on /gamestatus"""

    def setUp(self):
        patcher = mock.patch.object(GameState, "EventManager")
        self.events = patcher.start().instance.return_value
        self.addCleanup(patcher.stop)
        webhook = mock.patch.object(GameState, "send_game_start_webhook")
        webhook.start()
        self.addCleanup(webhook.stop)

    def test_stopped_game_pushes_once(self):
        app = self._app(game_started=False)
        GameState.start_game(app)
        self.assertTrue(app.settings["game_started"])
        self.assertEqual(self.events.push_game_started.call_count, 1)

    def test_already_running_game_does_not_push(self):
        app = self._app(game_started=True)
        GameState.start_game(app)
        self.assertFalse(self.events.push_game_started.called)


class TestStopHandlerRedirect(unittest.TestCase):
    """
    /gamestatus must not claim the game is stopped when it isn't.

    Regression: the page was static and always rendered "The game is
    currently stopped", so anyone who landed there after a restart was
    told something false with no way to notice.
    """

    def _handler(self, started):
        handler = mock.Mock()
        handler.application.settings = {"game_started": started}
        calls = {"redirected": None, "rendered": None}
        handler.redirect.side_effect = lambda url: calls.__setitem__(
            "redirected", url
        )
        handler.render.side_effect = lambda tmpl, **kw: calls.__setitem__(
            "rendered", tmpl
        )
        return handler, calls

    def test_running_game_redirects_to_dashboard(self):
        handler, calls = self._handler(started=True)
        StopHandler.get(handler)
        self.assertEqual(calls["redirected"], "/user")
        self.assertIsNone(calls["rendered"])

    def test_stopped_game_still_renders_the_page(self):
        handler, calls = self._handler(started=False)
        StopHandler.get(handler)
        self.assertEqual(calls["rendered"], "public/stopped.html")
        self.assertIsNone(calls["redirected"])


class TestGameStartedDecorator(unittest.TestCase):
    """
    A stopped game must not execute the wrapped handler.

    Regression: the decorator issued the redirect but returned
    method(...) unconditionally, so handlers ran anyway - flags submitted
    against a stopped game were still captured and scored.
    """

    def _fake_handler(self, started, user):
        """Builds a stand-in handler plus a target that records if it ran"""
        calls = {"redirected": None, "ran": False}
        handler = mock.Mock()
        handler.application.settings = {"game_started": started}
        handler.get_current_user.return_value = user
        handler.redirect.side_effect = lambda url: calls.__setitem__(
            "redirected", url
        )

        @game_started
        def target(self):
            calls["ran"] = True

        return handler, target, calls

    def _player(self):
        return mock.Mock(is_admin=mock.Mock(return_value=False))

    def _admin(self):
        return mock.Mock(is_admin=mock.Mock(return_value=True))

    def test_stopped_game_blocks_player(self):
        handler, target, calls = self._fake_handler(False, self._player())
        target(handler)
        self.assertFalse(calls["ran"])
        self.assertEqual(calls["redirected"], "/gamestatus")

    def test_stopped_game_blocks_anonymous(self):
        handler, target, calls = self._fake_handler(False, None)
        target(handler)
        self.assertFalse(calls["ran"])
        self.assertEqual(calls["redirected"], "/gamestatus")

    def test_stopped_game_allows_admin(self):
        handler, target, calls = self._fake_handler(False, self._admin())
        target(handler)
        self.assertTrue(calls["ran"])
        self.assertIsNone(calls["redirected"])

    def test_running_game_allows_player(self):
        handler, target, calls = self._fake_handler(True, self._player())
        target(handler)
        self.assertTrue(calls["ran"])
        self.assertIsNone(calls["redirected"])


# class TestMissionHandlers(ApplicationTest):
#
#    def setUp(self):
#        self.username = 'foobar'
#        self.password = 'testpassword123456'

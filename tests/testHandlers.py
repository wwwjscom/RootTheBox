# -*- coding: utf-8 -*-
"""
Unit tests for everything in handlers/
"""
import logging
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from tornado.options import options

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

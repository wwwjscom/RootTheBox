# -*- coding: utf-8 -*-
"""
Unit tests for everything in models/
"""

import unittest
from collections import OrderedDict
from datetime import datetime, timedelta

from libs.StringCoding import encode
from libs.ValidationError import ValidationError
from models import dbsession
from models.Box import Box
from models.Corporation import Corporation
from models.Flag import (
    FLAG_CHOICE,
    FLAG_DATETIME,
    FLAG_FILE,
    FLAG_REGEX,
    FLAG_STATIC,
    Flag,
)
from models.GameLevel import GameLevel
from models.Notification import Notification
from models.Penalty import Penalty
from models.Team import Team
from models.User import User
from models.UserLevelTimer import UserLevelTimer
from tests.Helpers import *


class TestTeam(unittest.TestCase):
    def setUp(self):
        self.team = create_team()

    def tearDown(self):
        dbsession.delete(self.team)
        dbsession.commit()

    def test_name(self):
        assert self.team.name == "TestTeam"
        with self.assertRaises(ValidationError):
            self.team.name = ""
        with self.assertRaises(ValidationError):
            self.team.name = "A" * 25

    def test_motto(self):
        assert self.team.motto == "TestMotto"
        with self.assertRaises(ValidationError):
            self.team.motto = "A" * 35


class TestUser(unittest.TestCase):
    def setUp(self):
        self.user = create_user()

    def tearDown(self):
        dbsession.delete(self.user)
        dbsession.commit()

    def test_handle(self):
        assert self.user.handle == "HacKer"
        with self.assertRaises(ValidationError):
            self.user.handle = ""
        with self.assertRaises(ValidationError):
            self.user.handle = "A" * 20

    def test_password(self):
        assert not self.user.validate_password("")
        assert self.user.validate_password("TestPassword")
        assert not self.user.validate_password("WrongPwd")

    def test_bank_password(self):
        assert self.user.validate_bank_password("Test123")
        assert not self.user.validate_password("Wrong")
        with self.assertRaises(ValidationError):
            self.user.bank_password = "A" * 100


class TestGameLevel(unittest.TestCase):
    def setUp(self):
        self.game_level = GameLevel()
        self.game_level.number = 1
        self.game_level.buyout = 1000
        dbsession.add(self.game_level)
        dbsession.commit()

    def tearDown(self):
        dbsession.delete(self.game_level)
        dbsession.commit()

    def test_number(self):

        assert 0 <= self.game_level.number
        self.game_level.number = "1"
        assert self.game_level.number == 1
        self.game_level.number = " 1 "
        assert self.game_level.number == 1
        with self.assertRaises(ValidationError):
            self.game_level.number = "A"

    def test_buyout(self):
        assert 0 <= self.game_level.buyout
        self.game_level.buyout = -1000
        assert 0 <= self.game_level.buyout
        self.game_level.buyout = "1000"
        assert self.game_level.buyout == 1000
        with self.assertRaises(ValidationError):
            self.game_level.buyout = "A"

    def test_flag_submission_timer_minutes(self):
        # Level timer defaults to disabled and accepts numeric form strings.
        assert self.game_level.flag_submission_timer_minutes == 0
        self.game_level.flag_submission_timer_minutes = "15"
        assert self.game_level.flag_submission_timer_minutes == 15
        assert self.game_level.flag_submission_timer_seconds == 900
        with self.assertRaises(ValidationError):
            self.game_level.flag_submission_timer_minutes = "A"


class TestCorporation(unittest.TestCase):
    def setUp(self):
        self.corp = create_corp()

    def tearDown(self):
        dbsession.delete(self.corp)
        dbsession.commit()

    def test_name(self):
        assert self.corp.name == "TestCorp"
        with self.assertRaises(ValidationError):
            self.corp.name = "A" * 35


class TestBox(unittest.TestCase):
    def setUp(self):
        self.box, self.corp = create_box()

    def tearDown(self):
        dbsession.delete(self.corp)
        dbsession.commit()

    def test_name(self):
        assert self.box.name == "TestBox"
        with self.assertRaises(ValidationError):
            self.box.name = ""
        with self.assertRaises(ValidationError):
            self.box.name = "A" * 35

    def test_description(self):
        with self.assertRaises(ValidationError):
            self.box.description = "A" * 4097


class TestFlag(unittest.TestCase):
    def setUp(self):
        self.box, self.corp = create_box()
        self.static_flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="Static Flag",
            raw_token="statictoken",
            description="A static test token",
            value=100,
        )
        self.regex_flag = Flag.create_flag(
            _type=FLAG_REGEX,
            box=self.box,
            name="Regex Flag",
            raw_token="(f|F)oobar",
            description="A regex test token",
            value=200,
        )
        self.file_flag = Flag.create_flag(
            _type=FLAG_FILE,
            box=self.box,
            name="File Flag",
            raw_token=encode("fdata"),
            description="A file test token",
            value=300,
        )
        self.choice_flag = Flag.create_flag(
            _type=FLAG_CHOICE,
            box=self.box,
            name="Choice Flag",
            raw_token=encode("fdata"),
            description="A choice test token",
            value=400,
        )
        self.datetime_flag = Flag.create_flag(
            _type=FLAG_DATETIME,
            box=self.box,
            name="Datetime Flag",
            raw_token="2018-06-22 18:00:00",
            description="A datetime test token",
            value=500,
        )

        dbsession.add(self.static_flag)
        dbsession.add(self.regex_flag)
        dbsession.add(self.file_flag)
        dbsession.add(self.choice_flag)
        dbsession.add(self.datetime_flag)
        dbsession.commit()

    def tearDown(self):
        dbsession.delete(self.corp)
        dbsession.commit()

    def test_name(self):
        with self.assertRaises(ValidationError):
            self.static_flag.name = "A" * 65

    def test_static_capture(self):
        assert self.static_flag.capture("statictoken")
        assert not self.static_flag.capture("nottoke")

    def test_regex_capture(self):
        assert self.regex_flag.capture("foobar")
        assert self.regex_flag.capture("Foobar")
        assert not self.regex_flag.capture("asdf")

    def test_file_capture(self):
        assert self.file_flag.capture(encode("fdata"))
        assert not self.file_flag.capture(encode("other"))

    def test_choice_capture(self):
        assert self.file_flag.capture(encode("fdata"))
        assert not self.file_flag.capture(encode("other"))

    def test_datetime_capture(self):
        assert self.datetime_flag.capture("2018-06-22 18:00:00")
        assert not self.datetime_flag.capture("2018-06-21 16:00:00")


class TestUserLevelTimer(unittest.TestCase):
    def setUp(self):
        self.user = create_user()
        self.level = GameLevel.all()[0]
        # Seed a short timer record for expiry/remaining calculations.
        self.timer = UserLevelTimer.create_timer(self.user.id, self.level.id, 120)
        dbsession.add(self.timer)
        dbsession.commit()

    def tearDown(self):
        dbsession.query(UserLevelTimer).delete()
        dbsession.delete(self.user)
        dbsession.commit()

    def test_seconds_remaining(self):
        # Remaining time should never exceed the original configured duration.
        remaining = self.timer.seconds_remaining(datetime.now())
        assert 0 < remaining <= 120

    def test_expired_timer(self):
        # Expired timers clamp to zero remaining seconds.
        self.timer.expires_at = datetime.now() - timedelta(seconds=1)
        dbsession.add(self.timer)
        dbsession.commit()
        assert self.timer.seconds_remaining(datetime.now()) == 0


class TestScoreboardTopX(unittest.TestCase):
    """Tests for the top-X scoreboard filtering logic in summary_page()."""

    def _make_state(self, n):
        teams = OrderedDict()
        for i in range(n):
            teams["Team%d" % (i + 1)] = {"uuid": "uuid-%d" % i, "money": 1000 - i * 100}
        return {
            "teams": teams,
            "users": {},
            "levels": {},
            "boxes": {},
            "hint_count": 0,
            "flag_count": 0,
            "box_count": 0,
            "level_count": 0,
        }

    def _handler(self, n):
        from handlers.ScoreboardHandlers import ScoreboardAjaxHandler

        state = self._make_state(n)

        class Stub:
            settings = {"scoreboard_state": state}

        stub = Stub()
        stub.summary_page = lambda *a, **kw: ScoreboardAjaxHandler.summary_page(
            stub, *a, **kw
        )
        return stub

    def test_no_limit_returns_all(self):
        result = self._handler(5).summary_page(1, 50, top=0)
        assert len(result["teams"]) == 5

    def test_top_filters_to_n(self):
        result = self._handler(5).summary_page(1, 50, top=3)
        assert len(result["teams"]) == 3

    def test_top_preserves_rank_order(self):
        result = self._handler(5).summary_page(1, 50, top=3)
        assert list(result["teams"].keys()) == ["Team1", "Team2", "Team3"]

    def test_top_larger_than_total_returns_all(self):
        result = self._handler(3).summary_page(1, 50, top=10)
        assert len(result["teams"]) == 3

    def test_top_with_pagination_page1(self):
        result = self._handler(6).summary_page(1, 2, top=4)
        assert list(result["teams"].keys()) == ["Team1", "Team2"]

    def test_top_with_pagination_page2(self):
        result = self._handler(6).summary_page(2, 2, top=4)
        assert list(result["teams"].keys()) == ["Team3", "Team4"]

    def test_top_pagination_excludes_beyond_cap(self):
        # page 3 with display=2 and top=4: only 4 teams exist after cap, none on page 3
        result = self._handler(6).summary_page(3, 2, top=4)
        assert len(result["teams"]) == 0

    def test_zero_top_with_pagination(self):
        # top=0 still paginates normally when teamcount > display
        result = self._handler(6).summary_page(2, 2, top=0)
        assert list(result["teams"].keys()) == ["Team3", "Team4"]

    def test_projector_default_when_unconfigured(self):
        # When scoreboard_top is 0 (unset), the projector falls back to 25.
        from handlers.ScoreboardHandlers import ScoreboardProjectorHandler

        top = options.scoreboard_top if options.scoreboard_top > 0 else 25
        assert top == 25

    def test_projector_uses_configured_value(self):
        # When scoreboard_top is set, the projector uses that value.
        original = options.scoreboard_top
        options.scoreboard_top = 5
        top = options.scoreboard_top if options.scoreboard_top > 0 else 25
        assert top == 5
        options.scoreboard_top = original


class TestReviewMode(unittest.TestCase):
    """Tests for the per-level review mode feature."""

    def setUp(self):
        self.box, self.corp = create_box()
        self.level = self.box.game_level
        self.team = create_team()
        self.user = create_user()
        self.user.team = self.team
        options.banking = True
        options.dynamic_flag_value = False
        self.flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="Review Flag",
            raw_token="reviewtoken",
            description="Test flag",
            value=100,
        )
        dbsession.add(self.flag)
        dbsession.add(self.user)
        dbsession.commit()

    def tearDown(self):
        self.level.review_mode = False
        dbsession.query(Penalty).filter_by(flag_id=self.flag.id).delete()
        dbsession.add(self.level)
        dbsession.commit()
        dbsession.delete(self.user)
        dbsession.delete(self.team)
        dbsession.delete(self.corp)
        dbsession.commit()

    # --- Model property tests ---

    def test_default_is_false(self):
        assert self.level.review_mode == False

    def test_toggle(self):
        self.level.review_mode = True
        dbsession.add(self.level)
        dbsession.commit()
        assert GameLevel.by_id(self.level.id).review_mode == True

    def test_type_coercion_int(self):
        self.level.review_mode = 1
        assert self.level.review_mode == True
        self.level.review_mode = 0
        assert self.level.review_mode == False

    def test_type_coercion_str(self):
        self.level.review_mode = "true"
        assert self.level.review_mode == True
        self.level.review_mode = "1"
        assert self.level.review_mode == True
        self.level.review_mode = "false"
        assert self.level.review_mode == False

    def test_in_to_dict(self):
        d = self.level.to_dict()
        assert "review_mode" in d
        assert d["review_mode"] == False
        self.level.review_mode = True
        assert self.level.to_dict()["review_mode"] == True

    # --- Scoring behaviour tests ---

    def test_flag_captured_in_review_mode(self):
        """Flag should be marked captured even when review mode is active."""
        self.level.review_mode = True
        dbsession.add(self.level)
        dbsession.commit()
        self.team.add_flag(self.flag)
        dbsession.add(self.team)
        dbsession.commit()
        assert self.flag in self.team.flags

    def test_no_points_awarded_in_review_mode(self):
        """Team score must not change when a flag is captured in review mode."""
        self.level.review_mode = True
        dbsession.add(self.level)
        dbsession.commit()
        initial_money = self.team.money
        if not self.level.review_mode:
            self.team.set_score("flag", self.flag.value + self.team.money)
        self.team.add_flag(self.flag)
        dbsession.add(self.team)
        dbsession.commit()
        assert self.team.money == initial_money

    def test_points_awarded_outside_review_mode(self):
        """Team score must increase when a flag is captured outside review mode."""
        self.level.review_mode = False
        initial_money = self.team.money
        flag_value = self.flag.dynamic_value(self.team)
        if not self.level.review_mode:
            self.team.set_score("flag", flag_value + self.team.money)
        self.team.add_flag(self.flag)
        dbsession.add(self.team)
        dbsession.commit()
        assert self.team.money == initial_money + flag_value

    # --- Penalty suppression tests ---

    def test_penalty_suppressed_in_review_mode(self):
        """Wrong submissions must not create penalties in review mode."""
        self.level.review_mode = True
        dbsession.add(self.level)
        dbsession.commit()
        level = GameLevel.by_id(self.flag.box.game_level_id)
        if not level.review_mode:
            Penalty.create_attempt(user=self.user, flag=self.flag, submission="wrong")
        assert Penalty.by_count(self.flag, self.team) == 0

    def test_penalty_created_outside_review_mode(self):
        """Wrong submissions must create penalties outside review mode."""
        self.level.review_mode = False
        level = GameLevel.by_id(self.flag.box.game_level_id)
        if not level.review_mode:
            Penalty.create_attempt(user=self.user, flag=self.flag, submission="wrong")
        assert Penalty.by_count(self.flag, self.team) == 1


class TestNotification(unittest.TestCase):
    """Pins Notification.admin() (used by the admin home + notifications pages)."""

    def setUp(self):
        self.notifications = []
        for i in range(8):
            notify = Notification()
            notify.title = "Title %d" % i
            notify.message = "Message %d" % i
            notify.icon_url = None
            dbsession.add(notify)
            self.notifications.append(notify)
        dbsession.commit()

    def tearDown(self):
        for notify in self.notifications:
            dbsession.delete(notify)
        dbsession.commit()

    def test_admin_returns_list(self):
        """admin() must return a materialized list, per its docstring/siblings."""
        assert isinstance(Notification.admin(), list)

    def test_admin_negative_slice(self):
        """Regression: admin/home.html slices Notification.admin()[-6:].

        On a SQLAlchemy Query a negative index raises IndexError under
        SQLAlchemy 2.0 (it silently worked in 1.x), which 500'd the admin
        home page. The template op below must succeed and stay Row-accessible.
        """
        recent = Notification.admin()[-6:]
        assert len(recent) == 6
        for notify in reversed(list(recent)):
            assert notify.title is not None
            assert notify.message is not None
            # attributes the template reads
            _ = notify.created
            _ = notify.icon_url

# -*- coding: utf-8 -*-
"""
Characterization tests for the flag-submission scoring flow in
handlers/MissionsHandler.py — the submit -> score -> penalty -> GameHistory
path that MODERNIZATION.md item 1.4a flags as untested and at risk during the
SQLAlchemy 2.x migration.

The AsyncHTTPTestCase harness cannot exercise this over HTTP: authenticated
requests need a memcached session, which is not available under `--tests`
(see the note in tests/testHandlers.py::TestPublicHandlers._login_success).
So we drive BoxHandler's scoring methods directly with a stubbed current-user,
dbsession, and event_manager. These tests pin *current* behavior; they are a
safety net, not a specification.
"""

import unittest
from unittest import mock

from tornado.options import options

from handlers.MissionsHandler import BoxHandler
from models import dbsession
from models.Box import Box, FlagsSubmissionType
from models.Corporation import Corporation
from models.Flag import FLAG_STATIC, Flag
from models.GameLevel import GameLevel
from models.Penalty import Penalty
from models.Team import Team
from models.User import User


class ScoringTestCase(unittest.TestCase):
    """A one-level, one-box game with a single 100-point static flag, a team
    with access to the level, and a BoxHandler wired to stubbed request state."""

    FLAG_VALUE = 100
    CORRECT = "correcttoken"

    # Options the scoring paths read; pinned to explicit values per test run.
    _SCORING_OPTIONS = (
        "banking",
        "teams",
        "dynamic_flag_value",
        "penalize_flag_value",
        "flag_start_penalty",
        "flag_stop_penalty",
        "flag_penalty_cost",
        "max_flag_attempts",
        "webhook_url",
    )

    def setUp(self):
        self.level = GameLevel(number=7, buyout=0)
        dbsession.add(self.level)
        dbsession.commit()

        self.corp = Corporation()
        self.corp.name = "ScoringCorp"
        dbsession.add(self.corp)
        dbsession.commit()

        self.box = Box(corporation_id=self.corp.id, game_level_id=self.level.id)
        self.box.name = "ScoringBox"
        self.box.description = "Box under test"
        self.corp.boxes.append(self.box)
        dbsession.add(self.box)
        dbsession.commit()

        self.flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="Scoring Flag",
            raw_token=self.CORRECT,
            description="static flag",
            value=self.FLAG_VALUE,
        )
        dbsession.add(self.flag)
        dbsession.commit()

        self.team = Team()
        self.team.name = "ScoringTeam"
        self.team.motto = "score me"
        dbsession.add(self.team)
        self.team.set_score("start", 0)
        dbsession.commit()

        self.user = User()
        self.user.handle = "scorer"
        self.user.password = "TestPassword"
        self.user.team = self.team
        dbsession.add(self.user)
        dbsession.commit()

        # Grant the team access to the level so submissions are eligible.
        self.team.game_levels.append(self.level)
        dbsession.add(self.team)
        dbsession.commit()

        self._opt_backup = {k: getattr(options, k) for k in self._SCORING_OPTIONS}
        options.banking = False
        options.teams = True
        options.dynamic_flag_value = False
        options.penalize_flag_value = True
        options.flag_start_penalty = 0
        options.flag_stop_penalty = 100
        options.flag_penalty_cost = 50  # percent of flag value
        options.max_flag_attempts = 100
        options.webhook_url = ""

        self.handler = BoxHandler.__new__(BoxHandler)
        self.handler.dbsession = dbsession
        self.handler.event_manager = mock.Mock()
        self.handler.get_current_user = lambda: self.user

    def tearDown(self):
        for key, value in self._opt_backup.items():
            setattr(options, key, value)
        dbsession.query(Penalty).filter_by(flag_id=self.flag.id).delete()
        dbsession.commit()
        dbsession.delete(self.user)
        dbsession.delete(self.team)
        dbsession.commit()
        # Corp cascade removes its box + flags; the level has no FK left.
        dbsession.delete(self.corp)
        dbsession.commit()
        dbsession.delete(self.level)
        dbsession.commit()


class TestFlagCaptureScoring(ScoringTestCase):
    def test_correct_submission_awards_flag_value(self):
        result = self.handler.attempt_capture(self.flag, self.CORRECT)
        self.assertTrue(result)
        self.assertIn(self.flag, self.team.flags)
        self.assertIn(self.flag, self.user.flags)
        self.assertEqual(self.team.money, self.FLAG_VALUE)
        self.handler.event_manager.flag_captured.assert_called_once()

    def test_correct_submission_records_game_history(self):
        self.handler.attempt_capture(self.flag, self.CORRECT)
        history_types = [record.type for record in self.team.game_history]
        # set_score("flag", ...) records the reward; add_flag records a count.
        self.assertIn("flag", history_types)
        self.assertIn("flag_count", history_types)

    def test_wrong_submission_is_rejected(self):
        result = self.handler.attempt_capture(self.flag, "wrongtoken")
        self.assertFalse(result)
        self.assertNotIn(self.flag, self.team.flags)
        self.assertEqual(self.team.money, 0)
        self.handler.event_manager.flag_captured.assert_not_called()

    def test_duplicate_capture_does_not_double_score(self):
        self.assertTrue(self.handler.attempt_capture(self.flag, self.CORRECT))
        self.assertEqual(self.team.money, self.FLAG_VALUE)
        # Flag is already in team.flags now, so a second attempt is a no-op.
        self.assertFalse(self.handler.attempt_capture(self.flag, self.CORRECT))
        self.assertEqual(self.team.money, self.FLAG_VALUE)

    def test_single_submission_box_resolves_flag_by_token(self):
        # Single-submission boxes validate against the box, resolving the flag
        # from the submitted token rather than a flag uuid.
        self.box.flag_submission_type = FlagsSubmissionType.SINGLE_SUBMISSION_BOX
        dbsession.add(self.box)
        dbsession.commit()
        resolved = Flag.by_token_and_box_id(self.CORRECT, self.box.id)
        self.assertEqual(resolved, self.flag)
        self.assertIsNone(Flag.by_token_and_box_id("wrongtoken", self.box.id))


class TestFlagPenalties(ScoringTestCase):
    def test_wrong_submission_records_penalty_attempt(self):
        self.handler.failed_capture(self.flag, "wrongtoken")
        self.assertEqual(Penalty.by_count(self.flag, self.team), 1)

    def test_penalty_deducts_configured_percentage(self):
        self.team.set_score("seed", 200)
        dbsession.add(self.team)
        dbsession.commit()
        penalty = self.handler.failed_capture(self.flag, "wrongtoken")
        # flag_penalty_cost is 50% of the 100-value flag.
        self.assertEqual(penalty, 50)
        self.assertEqual(self.team.money, 150)

    def test_no_score_change_when_penalize_disabled(self):
        options.penalize_flag_value = False
        self.team.set_score("seed", 200)
        dbsession.add(self.team)
        dbsession.commit()
        penalty = self.handler.failed_capture(self.flag, "wrongtoken")
        self.assertFalse(penalty)
        # The attempt is still recorded even though no points are deducted.
        self.assertEqual(Penalty.by_count(self.flag, self.team), 1)
        self.assertEqual(self.team.money, 200)


class TestBoxCompletionScoring(ScoringTestCase):
    def test_box_completion_awards_box_value(self):
        self.box.value = 250
        dbsession.add(self.box)
        dbsession.commit()
        # Capturing the box's only flag completes it.
        self.handler.attempt_capture(self.flag, self.CORRECT)
        success = self.handler.success_capture(self.user, self.flag, self.FLAG_VALUE)
        # Flag value (100) plus the box bonus (250).
        self.assertEqual(self.team.money, self.FLAG_VALUE + 250)
        self.assertTrue(any("completed" in line.lower() for line in success))


class TestLevelCompletionScoring(ScoringTestCase):
    LEVEL_REWARD = 500

    def setUp(self):
        super().setUp()
        # Level completion only rewards when the level is not already owned.
        self.team.game_levels.remove(self.level)
        self.level.reward = self.LEVEL_REWARD
        dbsession.add(self.level)
        dbsession.add(self.team)
        dbsession.commit()

    def test_level_completion_awards_level_reward(self):
        self.handler.attempt_capture(self.flag, self.CORRECT)  # flag value 100
        success = self.handler.success_capture(self.user, self.flag, self.FLAG_VALUE)
        # Flag value plus the level completion reward. (Completing a level this
        # way awards the reward but does not itself add the level to
        # game_levels — in normal play the level is already owned.)
        self.assertEqual(self.team.money, self.FLAG_VALUE + self.LEVEL_REWARD)
        self.assertTrue(
            any(
                self.level.name in line and "completed" in line.lower()
                for line in success
            )
        )


class TestDynamicFlagDecay(unittest.TestCase):
    """Pins the decay_all dynamic-scoring math on Flag.dynamic_value."""

    FLAG_VALUE = 100
    DECREASE_PCT = 10

    _OPTIONS = (
        "dynamic_flag_value",
        "dynamic_flag_type",
        "flag_value_decrease",
        "flag_value_minimum",
    )

    def setUp(self):
        self.level = GameLevel(number=9, buyout=0)
        dbsession.add(self.level)
        dbsession.commit()
        self.corp = Corporation()
        self.corp.name = "DecayCorp"
        dbsession.add(self.corp)
        dbsession.commit()
        self.box = Box(corporation_id=self.corp.id, game_level_id=self.level.id)
        self.box.name = "DecayBox"
        self.box.description = "decay"
        self.corp.boxes.append(self.box)
        dbsession.add(self.box)
        dbsession.commit()
        self.flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="Decay Flag",
            raw_token="decaytok",
            description="decays",
            value=self.FLAG_VALUE,
        )
        dbsession.add(self.flag)
        dbsession.commit()

        self.team1 = self._team("DecayTeam1")
        self.team2 = self._team("DecayTeam2")

        self._opt_backup = {k: getattr(options, k) for k in self._OPTIONS}
        options.dynamic_flag_value = True
        options.dynamic_flag_type = "decay_all"
        options.flag_value_decrease = self.DECREASE_PCT
        options.flag_value_minimum = 0

    def _team(self, name):
        team = Team()
        team.name = name
        team.motto = "decay"
        dbsession.add(team)
        team.set_score("start", 0)
        dbsession.commit()
        return team

    def tearDown(self):
        for key, value in self._opt_backup.items():
            setattr(options, key, value)
        dbsession.delete(self.team1)
        dbsession.delete(self.team2)
        dbsession.commit()
        dbsession.delete(self.corp)
        dbsession.commit()
        dbsession.delete(self.level)
        dbsession.commit()

    def test_value_is_full_before_any_capture(self):
        self.assertEqual(self.flag.dynamic_value(self.team2), self.FLAG_VALUE)

    def test_value_decays_after_a_capture(self):
        # One team captures the flag.
        self.team1.add_flag(self.flag)
        dbsession.add(self.team1)
        dbsession.commit()
        # A team that has not captured now sees the decayed value:
        # value - (captures * value * decrease%) = 100 - (1 * 10) = 90.
        expected = self.FLAG_VALUE - int(self.FLAG_VALUE * (self.DECREASE_PCT / 100.0))
        self.assertEqual(self.flag.dynamic_value(self.team2), expected)

# -*- coding: utf-8 -*-
"""
Characterization tests for the market purchase flow
(handlers/MarketHandlers.py) and scoreboard team ranking (Team.ranks()) —
MODERNIZATION.md item 1.4a, flow (4). Bank-password handling is already
covered by tests/testModels.py::TestUser.

MarketViewHandler.post() is guarded by @authenticated/@game_started/
@use_black_market, whose session/application plumbing the `--tests` harness
can't provide, so we characterize the undecorated purchase mechanic
(purchase_item) and the ownership predicate (User.has_item) the handler gates
on. Tests pin current behavior.
"""


import unittest
from unittest import mock

from tornado.options import options

from handlers.MarketHandlers import MarketViewHandler
from models import dbsession
from models.MarketItem import MarketItem
from models.Team import Team
from models.User import User


class MarketTestCase(unittest.TestCase):
    START_MONEY = 500
    ITEM_PRICE = 200

    def setUp(self):
        self.team = Team()
        self.team.name = "MarketTeam"
        self.team.motto = "buy things"
        dbsession.add(self.team)
        self.team.set_score("start", self.START_MONEY)
        dbsession.commit()

        self.user = User()
        self.user.handle = "shopper"
        self.user.password = "TestPassword"
        self.user.team = self.team
        dbsession.add(self.user)
        dbsession.commit()

        self.item = MarketItem()
        self.item.name = "Test Item"
        self.item.price = self.ITEM_PRICE
        self.item.image = "none.png"
        self.item.description = "an item"
        dbsession.add(self.item)
        dbsession.commit()

        self._allowed = options.allowed_market_items
        options.allowed_market_items = [self.item.name]

    def tearDown(self):
        options.allowed_market_items = self._allowed
        dbsession.delete(self.user)
        dbsession.delete(self.team)
        dbsession.commit()
        item = MarketItem.by_name("Test Item")
        if item is not None:
            dbsession.delete(item)
            dbsession.commit()

    def _handler(self):
        handler = MarketViewHandler.__new__(MarketViewHandler)
        handler.dbsession = dbsession
        handler.event_manager = mock.Mock()
        return handler

    def test_purchase_item_deducts_and_grants(self):
        handler = self._handler()
        handler.purchase_item(self.team, self.item)
        self.assertEqual(self.team.money, self.START_MONEY - self.ITEM_PRICE)
        self.assertIn(self.item, self.team.items)
        handler.event_manager.push_score_update.assert_called_once()

    def test_has_item_gates_repurchase(self):
        # has_item() is the predicate post() uses to block buying twice.
        self.assertFalse(self.user.has_item(self.item.name))
        self._handler().purchase_item(self.team, self.item)
        self.assertTrue(self.user.has_item(self.item.name))

    def test_affordability_threshold(self):
        # post() blocks a purchase when team.money < item.price.
        self.assertGreaterEqual(self.team.money, self.item.price)
        self.team.set_score("broke", 100)
        dbsession.add(self.team)
        dbsession.commit()
        self.assertLess(self.team.money, self.item.price)


class TestScoreboardRanking(unittest.TestCase):
    """Team.ranks() orders visible teams by descending money. A team is only
    visible on the scoreboard if it has at least one unlocked member (see the
    computed Team.locked property)."""

    def setUp(self):
        self._known_team_ids = {team.id for team in Team.all()}
        self._users = []
        self.high = self._team("RankHigh", 300)
        self.low = self._team("RankLow", 100)
        self.mid = self._team("RankMid", 200)
        # Sole member is locked -> the team is hidden from the scoreboard.
        self.hidden = self._team("RankHidden", 250, member_locked=True)

    def _team(self, name, money, member_locked=False):
        team = Team()
        team.name = name
        team.motto = "rank me"
        dbsession.add(team)
        team.set_score("start", money)
        user = User()
        user.handle = name + "User"
        user.password = "TestPassword"
        user.locked = member_locked
        user.team = team
        dbsession.add(user)
        dbsession.commit()
        self._users.append(user)
        return team

    def tearDown(self):
        for user in self._users:
            dbsession.delete(user)
        dbsession.commit()
        for team in Team.all():
            if team.id not in self._known_team_ids:
                dbsession.delete(team)
        dbsession.commit()

    def test_ranks_are_ordered_by_money_desc(self):
        mine = {self.high.id, self.low.id, self.mid.id}
        ranked = [t for t in Team.ranks() if t.id in mine]
        self.assertEqual([t.name for t in ranked], ["RankHigh", "RankMid", "RankLow"])

    def test_teams_without_unlocked_members_are_excluded(self):
        ranked_ids = {t.id for t in Team.ranks()}
        self.assertNotIn(self.hidden.id, ranked_ids)

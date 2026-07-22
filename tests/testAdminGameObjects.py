# -*- coding: utf-8 -*-
"""
Characterization tests for admin game-object CRUD
(handlers/AdminHandlers/AdminGameObjectHandlers.py) — MODERNIZATION.md item
1.4a, flow (3). ~2,700 lines of admin CRUD are otherwise untested.

Like the scoring tests, the admin handlers can't be exercised over HTTP under
`--tests` (auth needs memcached), so we drive the create/edit/delete methods
directly on bare handler instances with stubbed request plumbing
(get_argument(s), dbsession, config, event_manager, request, redirect, render).

Tests pin current behavior; they are a safety net, not a specification.
"""

import types
import unittest
from unittest import mock

from tornado.options import options

from handlers.AdminHandlers.AdminGameObjectHandlers import (
    AdminCreateHandler,
    AdminDeleteHandler,
    AdminEditHandler,
)
from models import dbsession
from models.Box import Box
from models.Corporation import Corporation
from models.Flag import Flag
from models.GameLevel import GameLevel
from models.Hint import Hint


def make_handler(handler_cls, **arguments):
    """A bare admin handler with request plumbing stubbed. List-valued kwargs
    are served through get_arguments(); the rest through get_argument()."""
    handler = handler_cls.__new__(handler_cls)
    handler.dbsession = dbsession
    handler.event_manager = mock.Mock()
    handler.config = options
    handler.request = types.SimpleNamespace()  # no .files -> no attachments
    handler.redirect = mock.Mock()
    handler.render = mock.Mock()
    multi = {k: v for k, v in arguments.items() if isinstance(v, list)}
    single = {k: v for k, v in arguments.items() if not isinstance(v, list)}
    handler.get_argument = lambda name, default=None, strip=True: single.get(
        name, default
    )
    handler.get_arguments = lambda name, strip=True: multi.get(name, [])
    return handler


class TestAdminGameObjectCrud(unittest.TestCase):
    def setUp(self):
        self._known_corp_ids = {corp.id for corp in Corporation.all()}
        # A model-created level to hang objects on. (create_game_level rewrites
        # the global level linked-list, so it is characterized separately.)
        self.level = GameLevel(number=12, buyout=0)
        dbsession.add(self.level)
        dbsession.commit()

    def tearDown(self):
        for corp in Corporation.all():
            if corp.id not in self._known_corp_ids:
                dbsession.delete(corp)
        dbsession.commit()
        level = GameLevel.by_number(12)
        if level is not None:
            dbsession.delete(level)
            dbsession.commit()

    def test_create_edit_delete_round_trip(self):
        # --- create corporation ---
        make_handler(
            AdminCreateHandler,
            corporation_name="Admin Corp",
            corporation_description="corp desc",
        ).create_corporation()
        corp = Corporation.by_name("Admin Corp")
        self.assertIsNotNone(corp)

        # --- create box on the corp/level ---
        make_handler(
            AdminCreateHandler,
            game_level="12",
            corporation_uuid=corp.uuid,
            name="Admin Box",
            description="box desc",
            flag_submission_type="CLASSIC",
            difficulty="Easy",
            operating_system="Linux",
            capture_message="",
            reward="0",
        ).create_box()
        box = Box.by_name("Admin Box")
        self.assertIsNotNone(box)
        self.assertEqual(box.corporation_id, corp.id)
        self.assertEqual(box.game_level_id, self.level.id)

        # --- create a static flag on the box ---
        make_handler(
            AdminCreateHandler,
            box_uuid=box.uuid,
            token="admintok",
            flag_name="Admin Flag",
            description="flag desc",
            reward="100",
            capture_message="",
        ).create_flag_static()
        flags = {flag.name: flag for flag in box.flags}
        self.assertIn("Admin Flag", flags)
        self.assertTrue(flags["Admin Flag"].capture("admintok"))

        # --- create a hint on the box ---
        make_handler(
            AdminCreateHandler,
            box_uuid=box.uuid,
            price="5",
            description="admin hint",
        ).create_hint()
        hints = [h for h in box.hints if h.flag_id is None]
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].description, "admin hint")

        # --- edit: rename the corporation ---
        make_handler(
            AdminEditHandler,
            uuid=corp.uuid,
            name="Renamed Corp",
            description="corp desc",
        ).edit_corporations()
        self.assertIsNone(Corporation.by_name("Admin Corp"))
        self.assertIsNotNone(Corporation.by_name("Renamed Corp"))

        # --- delete: flag, hint, box, corporation ---
        flag_uuid = flags["Admin Flag"].uuid
        hint_uuid = hints[0].uuid
        box_uuid = box.uuid
        make_handler(AdminDeleteHandler, uuid=flag_uuid).del_flag()
        self.assertIsNone(Flag.by_uuid(flag_uuid))
        make_handler(AdminDeleteHandler, uuid=hint_uuid).del_hint()
        self.assertIsNone(Hint.by_uuid(hint_uuid))
        make_handler(AdminDeleteHandler, uuid=box_uuid).del_box()
        self.assertIsNone(Box.by_uuid(box_uuid))
        make_handler(
            AdminDeleteHandler, uuid=Corporation.by_name("Renamed Corp").uuid
        ).del_corp()
        self.assertIsNone(Corporation.by_name("Renamed Corp"))


class TestAdminCreateGameLevel(unittest.TestCase):
    """create_game_level() re-sorts every level and rewires the next_level_id
    linked list, so snapshot/restore that global state around the test."""

    NEW_NUMBER = 15

    def setUp(self):
        self._level_state = {
            lvl.id: (lvl.number, lvl.next_level_id) for lvl in GameLevel.all()
        }

    def tearDown(self):
        # Restore pre-existing levels first (their snapshot next_level_ids only
        # reference pre-existing rows), then drop any level we created.
        for lvl in GameLevel.all():
            if lvl.id in self._level_state:
                number, next_id = self._level_state[lvl.id]
                lvl.number = number
                lvl.next_level_id = next_id
                dbsession.add(lvl)
        dbsession.commit()
        for lvl in GameLevel.all():
            if lvl.id not in self._level_state:
                dbsession.delete(lvl)
        dbsession.commit()

    def test_create_game_level_persists_and_links(self):
        make_handler(
            AdminCreateHandler,
            level_number=str(self.NEW_NUMBER),
            buyout="0",
            name="CRUD Level",
            description="a level",
            type="none",
            reward="0",
        ).create_game_level()
        level = GameLevel.by_number(self.NEW_NUMBER)
        self.assertIsNotNone(level)
        self.assertEqual(level.name, "CRUD Level")
        # The linked list stays consistent: the last level points to None.
        ordered = sorted(GameLevel.all())
        self.assertIsNone(ordered[-1].next_level_id)

# -*- coding: utf-8 -*-
"""
Unit tests for handlers/MaterialsHandler.py

Regression: game materials for a locked box (or a box whose level/corp is
locked) remained visible/fetchable - has_box_materials() and path_to_dict()
never checked box.locked.
"""
import os
import shutil
import tempfile
import unittest

from unittest import mock

from tornado.options import options

from handlers.MaterialsHandler import MaterialsHandler, has_box_materials
from models import dbsession
from tests.Helpers import create_box


class TestMaterialsHandlerLockFiltering(unittest.TestCase):
    """Locked boxes/levels/corps must not expose their game materials."""

    def setUp(self):
        self.materials_dir = tempfile.mkdtemp()
        self.original_materials_dir = options.game_materials_dir
        self.original_use_box_materials_dir = options.use_box_materials_dir
        options.game_materials_dir = self.materials_dir
        options.use_box_materials_dir = True

        self.locked_box, self.corp = create_box()
        self.locked_box.name = "LockedBox"
        dbsession.commit()
        self.unlocked_box, _ = create_box(corp=self.corp)
        self.unlocked_box.name = "UnlockedBox"
        dbsession.commit()
        self.level = self.locked_box.game_level

        for box in (self.locked_box, self.unlocked_box):
            path = os.path.join(self.materials_dir, box.name)
            os.makedirs(path)
            with open(os.path.join(path, "notes.txt"), "w") as f:
                f.write("some material")

    def tearDown(self):
        self.level.locked = False
        self.corp.locked = False
        dbsession.add(self.level)
        dbsession.commit()
        dbsession.delete(self.unlocked_box)
        dbsession.delete(self.locked_box)
        dbsession.delete(self.corp)
        dbsession.commit()
        shutil.rmtree(self.materials_dir, ignore_errors=True)
        options.game_materials_dir = self.original_materials_dir
        options.use_box_materials_dir = self.original_use_box_materials_dir

    # --- has_box_materials() ---

    def test_has_box_materials_visible_when_unlocked(self):
        self.assertEqual(has_box_materials(self.unlocked_box), "UnlockedBox")

    def test_has_box_materials_hidden_when_box_locked(self):
        self.locked_box.locked = True
        self.assertFalse(has_box_materials(self.locked_box))

    def test_has_box_materials_hidden_when_level_locked(self):
        self.level.locked = True
        self.assertFalse(has_box_materials(self.unlocked_box))

    def test_has_box_materials_hidden_when_corp_locked(self):
        self.corp.locked = True
        self.assertFalse(has_box_materials(self.unlocked_box))

    # --- path_to_dict() ---

    def test_path_to_dict_excludes_locked_box(self):
        self.locked_box.locked = True
        handler = MaterialsHandler.__new__(MaterialsHandler)
        tree = handler.path_to_dict(self.materials_dir)
        names = [child["text"] for child in tree["children"]]
        self.assertIn("UnlockedBox", names)
        self.assertNotIn("LockedBox", names)

    # --- post() ---

    def test_post_rejects_direct_fetch_of_locked_box_subdir(self):
        self.locked_box.locked = True
        handler = mock.Mock()
        handler.application.settings = {"forbidden_url": "/403"}
        handler.show_materials.return_value = True
        handler.path_to_dict.return_value = {
            "text": "LockedBox",
            "type": "directory",
            "children": [],
        }
        calls = {"redirected": None, "written": None}
        handler.redirect.side_effect = lambda url: calls.__setitem__(
            "redirected", url
        )
        handler.write.side_effect = lambda body: calls.__setitem__(
            "written", body
        )
        # Bypass @authenticated - it's exercised elsewhere; this test targets
        # the lock check inside post() itself.
        MaterialsHandler.post.__wrapped__(handler, self.locked_box.name)
        self.assertEqual(calls["redirected"], "/403")
        self.assertIsNone(calls["written"])

# -*- coding: utf-8 -*-
"""
Characterization tests for the ORM relationship behavior that the SQLAlchemy
2.0 migration (MODERNIZATION.md item 1.5) touched. 1.5B dropped five backrefs
(Box.corporation/game_level/category, Flag.box, Hint.flag) that collided with
same-named read-only @property accessors. These tests pin that:

  * the @property accessors still resolve to the right objects,
  * the forward relationships still manage the foreign key without the backref,
  * and the delete cascades we rely on (including in test teardowns) still fire.

Tests pin current behavior; they are a safety net, not a specification.
"""


import unittest

from models import dbsession
from models.Box import Box
from models.Category import Category
from models.Corporation import Corporation
from models.Flag import FLAG_STATIC, Flag
from models.GameLevel import GameLevel
from models.Hint import Hint


class RelationshipFixture(unittest.TestCase):
    """A Corporation -> Box -> Flag graph on its own level/category, with a
    box-level hint and a flag-level hint."""

    LEVEL_NUMBER = 21

    def setUp(self):
        self._known_level_ids = {lvl.id for lvl in GameLevel.all()}
        self._known_cat_ids = {cat.id for cat in Category.all()}

        self.level = GameLevel(number=self.LEVEL_NUMBER, buyout=0)
        dbsession.add(self.level)
        dbsession.commit()

        self.category = Category()
        self.category.category = "RelCategory"
        dbsession.add(self.category)
        dbsession.commit()

        self.corp = Corporation()
        self.corp.name = "RelCorp"
        dbsession.add(self.corp)
        dbsession.commit()

        self.box = Box(corporation_id=self.corp.id, game_level_id=self.level.id)
        self.box.name = "RelBox"
        self.box.description = "relationship box"
        self.box.category_id = self.category.id
        self.corp.boxes.append(self.box)
        dbsession.add(self.box)
        dbsession.commit()

        self.flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="Rel Flag",
            raw_token="reltok",
            description="rel",
            value=100,
        )
        dbsession.add(self.flag)
        dbsession.commit()

        self.box_hint = Hint(box_id=self.box.id)
        self.box_hint.price = 5
        self.box_hint.description = "box hint"
        self.flag_hint = Hint(box_id=self.box.id, flag_id=self.flag.id)
        self.flag_hint.price = 5
        self.flag_hint.description = "flag hint"
        dbsession.add(self.box_hint)
        dbsession.add(self.flag_hint)
        dbsession.commit()

    def tearDown(self):
        # Delete anything still present (a cascade test may have removed some).
        for corp in Corporation.all():
            if corp.name == "RelCorp":
                dbsession.delete(corp)
        dbsession.commit()
        for cat in Category.all():
            if cat.id not in self._known_cat_ids:
                dbsession.delete(cat)
        dbsession.commit()
        for lvl in GameLevel.all():
            if lvl.id not in self._known_level_ids:
                dbsession.delete(lvl)
        dbsession.commit()


class TestRelationshipAccessors(RelationshipFixture):
    # Compare by uuid rather than ==: GameLevel.__eq__ is unreliable (its
    # __cmp__ returns 1, never 0, for equal numbers, so a GameLevel never
    # compares equal to anything — a pre-existing quirk, out of scope for 1.5).

    def test_box_corporation_accessor(self):
        self.assertEqual(self.box.corporation.uuid, self.corp.uuid)

    def test_box_game_level_accessor(self):
        self.assertEqual(self.box.game_level.uuid, self.level.uuid)

    def test_box_category_accessor(self):
        self.assertEqual(self.box.category.uuid, self.category.uuid)

    def test_flag_box_accessor(self):
        self.assertEqual(self.flag.box.uuid, self.box.uuid)

    def test_hint_flag_accessor(self):
        self.assertEqual(self.flag_hint.flag.uuid, self.flag.uuid)
        # A box-level hint has no flag.
        self.assertIsNone(self.box_hint.flag)

    def test_forward_relationships_read_the_fk(self):
        # The forward one-to-many still resolves without the backref.
        self.assertIn(self.box.uuid, [b.uuid for b in self.corp.boxes])
        self.assertIn(self.box.uuid, [b.uuid for b in self.level.boxes])
        self.assertIn(self.flag.uuid, [f.uuid for f in self.box.flags])

    def test_appending_to_boxes_sets_foreign_key(self):
        # Removing the backref must not stop the relationship from managing the
        # FK: appending a new box sets its corporation_id at flush time.
        new_box = Box(game_level_id=self.level.id)
        new_box.name = "RelBox2"
        new_box.description = "second"
        self.corp.boxes.append(new_box)
        dbsession.add(new_box)
        dbsession.flush()
        self.assertEqual(new_box.corporation_id, self.corp.id)
        self.assertEqual(new_box.corporation.uuid, self.corp.uuid)


class TestCascadeDelete(RelationshipFixture):
    def test_delete_corporation_cascades_to_boxes_flags_hints(self):
        box_id = self.box.id
        flag_id = self.flag.id
        box_hint_id = self.box_hint.id
        flag_hint_id = self.flag_hint.id

        dbsession.delete(self.corp)
        dbsession.commit()

        self.assertIsNone(Corporation.by_name("RelCorp"))
        self.assertIsNone(Box.by_id(box_id))
        self.assertIsNone(Flag.by_id(flag_id))
        self.assertIsNone(Hint.by_id(box_hint_id))
        self.assertIsNone(Hint.by_id(flag_hint_id))

    def test_delete_box_cascades_to_flags_and_hints(self):
        box_id = self.box.id
        flag_id = self.flag.id
        flag_hint_id = self.flag_hint.id

        dbsession.delete(self.box)
        dbsession.commit()

        self.assertIsNone(Box.by_id(box_id))
        self.assertIsNone(Flag.by_id(flag_id))
        self.assertIsNone(Hint.by_id(flag_hint_id))
        # The corporation itself survives.
        self.assertIsNotNone(Corporation.by_name("RelCorp"))

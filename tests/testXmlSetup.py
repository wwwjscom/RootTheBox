# -*- coding: utf-8 -*-
"""
Characterization test for the XML game import/export round-trip
(setup/xmlsetup.py + the models' to_xml() methods) — MODERNIZATION.md item
1.4a, flow (1). This path touches nearly every game model at once, so it is a
high-value pin before the SQLAlchemy 2.x migration.

Strategy: build a small game programmatically, serialize it with the same
to_xml() calls AdminExportHandler.export_game_objects() makes, delete it, then
re-import the XML via setup.xmlsetup.import_xml and assert the reconstructed
object graph matches. We serialize only our own objects (not the whole DB) so
the round-trip does not duplicate the bootstrap level, and we clean up anything
new in tearDown to keep the shared test DB stable for other suites.

These tests pin *current* behavior; they are a safety net, not a specification.
"""


import os
import tempfile
import unittest
import xml.etree.cElementTree as ET

from tornado.options import options

from models import dbsession
from models.Box import Box
from models.Category import Category
from models.Corporation import Corporation
from models.Flag import FLAG_REGEX, FLAG_STATIC, Flag
from models.GameLevel import GameLevel
from models.Hint import Hint
from setup.xmlsetup import import_xml


class TestXmlRoundTrip(unittest.TestCase):
    LEVEL_NUMBER = 8
    CORP_NAME = "RoundTrip Corp"
    BOX_NAME = "RoundTripBox"
    CATEGORY = "RoundTripCategory"

    def setUp(self):
        # Remember pre-existing rows so tearDown can delete only what we add
        # (or what the import recreates), leaving the shared DB untouched.
        self._known_level_ids = {lvl.id for lvl in GameLevel.all()}
        self._known_corp_ids = {corp.id for corp in Corporation.all()}
        self._known_category_ids = {cat.id for cat in Category.all()}

        # update_configuration() (triggered only by a <configuration> block,
        # which we never emit) would rewrite the config file; guard anyway.
        self._webhook_url = options.webhook_url
        options.webhook_url = ""

        self.level = GameLevel(number=self.LEVEL_NUMBER, buyout=0)
        dbsession.add(self.level)
        dbsession.commit()

        self.category = Category()
        self.category.category = self.CATEGORY
        dbsession.add(self.category)
        dbsession.commit()

        self.corp = Corporation()
        self.corp.name = self.CORP_NAME
        dbsession.add(self.corp)
        dbsession.commit()

        self.box = Box(corporation_id=self.corp.id, game_level_id=self.level.id)
        self.box.name = self.BOX_NAME
        self.box.description = "Round trip box"
        self.box.operating_system = "Linux"
        self.box.difficulty = "Easy"
        self.box.value = 300
        self.corp.boxes.append(self.box)
        dbsession.add(self.box)
        dbsession.commit()

        self.static_flag = Flag.create_flag(
            _type=FLAG_STATIC,
            box=self.box,
            name="RT Static",
            raw_token="statictok",
            description="static",
            value=50,
        )
        self.regex_flag = Flag.create_flag(
            _type=FLAG_REGEX,
            box=self.box,
            name="RT Regex",
            raw_token="(a|b)+",
            description="regex",
            value=75,
        )
        dbsession.add(self.static_flag)
        dbsession.add(self.regex_flag)
        dbsession.commit()

        self.hint = Hint(box_id=self.box.id)
        self.hint.price = 10
        self.hint.description = "a helpful hint"
        dbsession.add(self.hint)
        dbsession.commit()

    def tearDown(self):
        options.webhook_url = self._webhook_url
        # Delete our objects plus anything the import recreated, bottom-up.
        for corp in Corporation.all():
            if corp.id not in self._known_corp_ids or corp.name == self.CORP_NAME:
                dbsession.delete(corp)
        for cat in Category.all():
            if cat.id not in self._known_category_ids or cat.category == self.CATEGORY:
                dbsession.delete(cat)
        dbsession.commit()
        for lvl in GameLevel.all():
            if lvl.id not in self._known_level_ids or lvl.number == self.LEVEL_NUMBER:
                dbsession.delete(lvl)
        dbsession.commit()

    def _serialize_game(self):
        """Mirror AdminExportHandler.export_game_objects() for our objects only."""
        root = ET.Element("rootthebox")
        root.set("api", "1")
        levels_elem = ET.SubElement(root, "gamelevels")
        self.level.to_xml(levels_elem)
        categories_elem = ET.SubElement(root, "categories")
        self.category.to_xml(categories_elem)
        corps_elem = ET.SubElement(root, "corporations")
        self.corp.to_xml(corps_elem)
        return ET.tostring(root)

    def test_export_import_round_trip(self):
        xml_bytes = self._serialize_game()

        # Tear the game down so the import rebuilds it from scratch.
        dbsession.delete(self.corp)
        dbsession.delete(self.category)
        dbsession.commit()
        dbsession.delete(self.level)
        dbsession.commit()
        self.assertIsNone(Corporation.by_name(self.CORP_NAME))

        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".xml", delete=False
        )
        try:
            tmp.write(xml_bytes)
            tmp.close()
            self.assertTrue(import_xml(tmp.name))
        finally:
            os.unlink(tmp.name)

        # --- level ---
        level = GameLevel.by_number(self.LEVEL_NUMBER)
        self.assertIsNotNone(level)

        # --- category ---
        self.assertIsNotNone(Category.by_category(self.CATEGORY))

        # --- corporation + box ---
        corp = Corporation.by_name(self.CORP_NAME)
        self.assertIsNotNone(corp)
        self.assertEqual(len(corp.boxes), 1)
        box = corp.boxes[0]
        self.assertEqual(box.name, self.BOX_NAME)
        self.assertEqual(box.value, 300)

        # --- flags: names, values, and capture behavior round-trip ---
        flags_by_name = {flag.name: flag for flag in box.flags}
        self.assertEqual(set(flags_by_name), {"RT Static", "RT Regex"})
        static_flag = flags_by_name["RT Static"]
        regex_flag = flags_by_name["RT Regex"]
        self.assertEqual(static_flag.value, 50)
        self.assertEqual(regex_flag.value, 75)
        self.assertTrue(static_flag.capture("statictok"))
        self.assertFalse(static_flag.capture("nope"))
        self.assertTrue(regex_flag.capture("aab"))
        self.assertFalse(regex_flag.capture("zzz"))

        # --- box-level hint ---
        hints = [h for h in box.hints if h.flag_id is None]
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].description, "a helpful hint")
        self.assertEqual(hints[0].price, 10)

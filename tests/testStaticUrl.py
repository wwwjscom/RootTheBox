"""
Static file URLs carry a content hash (?v=...) so browsers pick up new
files after an upgrade (MODERNIZATION.md 2.2).
"""

import re
import unittest

from handlers.StaticFileHandler import versioned_static_url
from tests.HTTPClient import ApplicationTest


class TestVersionedStaticUrl(unittest.TestCase):
    def test_existing_file_gets_content_hash(self):
        url = versioned_static_url("css/main.css")
        self.assertRegex(url, r"^/static/css/main\.css\?v=[0-9a-f]+$")

    def test_missing_file_has_no_hash(self):
        self.assertEqual(
            versioned_static_url("css/does-not-exist.css"),
            "/static/css/does-not-exist.css",
        )


class TestStaticUrlInPages(ApplicationTest):
    def test_page_assets_are_versioned(self):
        _, body = self.get("/login")
        refs = re.findall(rb'(?:href|src)="(/static/[^"]+)"', body)
        self.assertTrue(refs)
        unversioned = [ref for ref in refs if b"?v=" not in ref]
        self.assertEqual(unversioned, [])

    def test_versioned_asset_is_cached_long_term(self):
        response = self.fetch(versioned_static_url("css/main.css"))
        self.assertEqual(response.code, 200)
        self.assertIn("max-age=315360000", response.headers["Cache-Control"])

# -*- coding: utf-8 -*-
"""
Tests for the single-theme setup (MODERNIZATION.md 2.1c): default theme
resolution, the Theme UI module, the settings-page picker, and the migration
that collapses every legacy theme into "Default".
"""

import os
import tempfile
import unittest
from unittest import mock
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, text
from tornado.options import options

from alembic import command
from models import dbsession
from models.BaseModels import DatabaseObject
from models.Theme import Theme
from models.User import User
from modules.AppTheme import AppTheme
from tests.HTTPClient import ApplicationTest

XSRF = "3858f62230ac3c915f300c664312c63f"
DEFAULT_FILES = ["bootstrap.min.css", "rtb.css"]


def _file_names(theme):
    return sorted(str(f) for f in theme)


class TestThemeDefault(unittest.TestCase):
    def setUp(self):
        self._default_theme = options.default_theme

    def tearDown(self):
        options.default_theme = self._default_theme

    def test_seeded_theme_is_default(self):
        self.assertEqual([t.name for t in Theme.all()], ["Default"])
        self.assertEqual(_file_names(Theme.by_name("Default")), DEFAULT_FILES)

    def test_default_resolves_configured_name(self):
        options.default_theme = "Default"
        self.assertEqual(Theme.default().name, "Default")

    def test_default_falls_back_when_configured_theme_missing(self):
        # Existing rootthebox.cfg files still say default_theme = "Cyborg".
        options.default_theme = "Cyborg"
        self.assertEqual(Theme.default().name, "Default")

    def test_new_user_gets_default_theme_with_stale_config(self):
        options.default_theme = "Cyborg"
        user = User(handle="t%s" % uuid4().hex[:8], password="Password123")
        dbsession.add(user)
        dbsession.commit()
        try:
            self.assertEqual(user.theme_id, Theme.by_name("Default").id)
        finally:
            dbsession.delete(user)
            dbsession.commit()


class TestAppTheme(unittest.TestCase):
    def _render(self, session):
        handler = mock.Mock()
        handler.session = session
        handler.render_string = lambda path, **kwargs: kwargs["theme_files"]
        return sorted(str(f) for f in AppTheme(handler).render())

    def test_logged_out_gets_default(self):
        self.assertEqual(self._render(None), DEFAULT_FILES)

    def test_stale_session_theme_is_ignored(self):
        # Sessions from before the upgrade hold dropped themes' file lists.
        session = {"theme": ["cyborg.min.css"], "theme_id": 999999}
        self.assertEqual(self._render(session), DEFAULT_FILES)

    def test_session_theme_id_is_used(self):
        theme_id = Theme.by_name("Default").id
        session = {"theme": ["cyborg.min.css"], "theme_id": theme_id}
        self.assertEqual(self._render(session), DEFAULT_FILES)


class TestThemeInPages(ApplicationTest):
    def test_pages_load_default_theme_css(self):
        _, body = self.get("/login")
        self.assertIn(b"/static/css/themes/bootstrap.min.css", body)
        self.assertIn(b"/static/css/themes/rtb.css", body)
        self.assertIn(b'data-bs-theme="dark"', body)

    def test_picker_hidden_with_single_theme(self):
        handle = "t%s" % uuid4().hex[:8]
        user = User(handle=handle, password="Password123")
        dbsession.add(user)
        dbsession.commit()
        try:
            cookies = {"_xsrf": XSRF}
            login = self.fetch(
                "/login",
                method="POST",
                body="_xsrf=%s&account=%s&password=Password123" % (XSRF, handle),
                headers={"Cookie": "_xsrf=%s" % XSRF},
                follow_redirects=False,
            )
            for header in login.headers.get_list("Set-Cookie"):
                name, value = header.split(";")[0].split("=", 1)
                cookies[name] = value
            self.assertIn("session_id", cookies)
            cookie = "; ".join("%s=%s" % kv for kv in cookies.items())
            page = self.fetch("/user/settings", headers={"Cookie": cookie})
            self.assertEqual(page.code, 200)
            self.assertNotIn(b"/user/settings/theme", page.body)
        finally:
            dbsession.delete(User.by_handle(handle))
            dbsession.commit()


class TestSingleThemeMigration(unittest.TestCase):
    """Legacy DBs: every theme collapses into Default and users follow"""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)
        self.engine = create_engine("sqlite:///%s" % self.db_path)
        DatabaseObject.metadata.create_all(self.engine)
        self.cfg = Config("alembic/alembic.ini")
        self.cfg.attributes["configure_logger"] = False
        self.cfg.set_main_option("sqlalchemy.url", "sqlite:///%s" % self.db_path)

    def tearDown(self):
        self.engine.dispose()
        os.unlink(self.db_path)

    def _seed_legacy(self):
        themes = {"Cyborg": ["cyborg.min.css"], "386": ["386.min.css", "386.js"]}
        with self.engine.begin() as conn:
            for name, files in themes.items():
                theme_id = conn.execute(
                    text("INSERT INTO theme (uuid, _name) VALUES (:u, :n)"),
                    {"u": str(uuid4()), "n": name},
                ).lastrowid
                for f in files:
                    conn.execute(
                        text("INSERT INTO theme_file (theme_id, _file_name) VALUES (:t, :f)"),
                        {"t": theme_id, "f": f},
                    )
                conn.execute(
                    text(
                        "INSERT INTO user (uuid, _locked, _handle, money, theme_id, algorithm) "
                        "VALUES (:u, 0, :h, 0, :t, 'md5')"
                    ),
                    {"u": str(uuid4()), "h": "u_" + name, "t": theme_id},
                )

    def _state(self):
        with self.engine.connect() as conn:
            themes = conn.execute(text("SELECT id, _name FROM theme")).fetchall()
            files = conn.execute(
                text("SELECT _file_name FROM theme_file ORDER BY _file_name")
            ).fetchall()
            user_themes = conn.execute(text("SELECT DISTINCT theme_id FROM user")).fetchall()
        return themes, [f[0] for f in files], [u[0] for u in user_themes]

    def test_legacy_themes_collapse_into_default(self):
        self._seed_legacy()
        command.stamp(self.cfg, "c3d4e5f6a7b8")
        command.upgrade(self.cfg, "head")
        themes, files, user_themes = self._state()
        self.assertEqual([t[1] for t in themes], ["Default"])
        self.assertEqual(files, DEFAULT_FILES)
        self.assertEqual(user_themes, [themes[0][0]])
        # Idempotent: a second run changes nothing.
        command.downgrade(self.cfg, "c3d4e5f6a7b8")
        command.upgrade(self.cfg, "head")
        self.assertEqual(self._state(), (themes, files, user_themes))

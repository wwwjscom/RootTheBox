# -*- coding: utf-8 -*-
"""
Migration-guard tests (MODERNIZATION.md item 1.5 follow-up), motivated by the
add_history raw-execute bug the 2.0 flip surfaced.

Architecture note: Root the Box builds its schema with metadata.create_all()
and *stamps* the alembic head (see setup() / update_db(False) in rootthebox.py);
the migrations are incremental patches applied to pre-existing DBs (the root
revision ALTERs tables, it does not create the base schema). So a literal
"upgrade base -> head on an empty DB" is not a supported path, and a
"migrations-built schema vs models" drift check cannot be constructed. These
tests therefore exercise the paths that DO exist, on SQLAlchemy 2.0:

  #1  the production DB lifecycle (create_all + stamp head + upgrade head), the
      one data-conversion migration against real rows, and chain integrity;
  #2  a no-drift tripwire between the models and the schema create_all builds.
"""

import os
import tempfile
import unittest

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from libs.DatabaseBackup import upgrade_with_backup

# All models are imported by the test bootstrap, so metadata is fully populated.
from models.BaseModels import DatabaseObject


def _alembic_cfg(db_path):
    cfg = Config("alembic/alembic.ini")
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("sqlalchemy.url", "sqlite:///%s" % db_path)
    return cfg


class MigrationTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(self.db_path)  # create_all makes the file
        self.engine = create_engine("sqlite:///%s" % self.db_path)
        self.cfg = _alembic_cfg(self.db_path)

    def tearDown(self):
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _create_all(self):
        DatabaseObject.metadata.create_all(self.engine)

    def _scalar(self, sql):
        with self.engine.connect() as conn:
            return conn.execute(text(sql)).scalar()


class TestMigrationsRunOnSqlAlchemy2(MigrationTestCase):
    def test_production_lifecycle_is_clean(self):
        # Mirror --setup (create_all + stamp head) then --start (upgrade head).
        self._create_all()
        command.stamp(self.cfg, "head")
        command.upgrade(self.cfg, "head")  # no-op at head; must not error on 2.0
        head = ScriptDirectory.from_config(self.cfg).get_current_head()
        self.assertEqual(self._scalar("SELECT version_num FROM alembic_version"), head)

    def test_data_conversion_migration_runs_on_2x(self):
        # Regression guard for the add_history raw-execute bug: ffe623ae412 must
        # convert real team_to_flag rows into game_history under SQLAlchemy 2.0.
        # A raw-string execute silently no-ops on 2.0 (caught + "Continuing"),
        # so a broken migration would leave game_history unchanged.
        self._create_all()
        with self.engine.begin() as conn:
            for team_id, flag_id in [(1, 1), (1, 2), (2, 1)]:
                conn.execute(
                    text("INSERT INTO team_to_flag (team_id, flag_id) VALUES (:t, :f)"),
                    {"t": team_id, "f": flag_id},
                )
        # Pretend the DB predates the snapshot-deletion migration.
        command.stamp(self.cfg, "fe5e615ae090")
        before = self._scalar("SELECT COUNT(*) FROM game_history")
        command.upgrade(self.cfg, "ffe623ae412")
        after = self._scalar("SELECT COUNT(*) FROM game_history")
        self.assertEqual(
            self._scalar("SELECT version_num FROM alembic_version"), "ffe623ae412"
        )
        self.assertGreater(after, before, "team_to_flag rows were not converted")

    def test_flag_order_backfill(self):
        # Seed flags as they exist before the migration: empty orders,
        # duplicates and gaps in box 1; box 2 is already 1..n.
        self._create_all()
        command.stamp(self.cfg, "head")
        command.downgrade(self.cfg, "e5f6a7b8c9d0")  # _order nullable again
        seed = [
            # (id, box_id, _order)
            (1, 1, None),
            (2, 1, 2),
            (3, 1, 2),
            (4, 1, None),
            (5, 1, 5),
            (6, 2, 1),
            (7, 2, 2),
        ]
        with self.engine.begin() as conn:
            for flag_id, box_id, order in seed:
                conn.execute(
                    text(
                        "INSERT INTO flag (id, uuid, box_id, _token, _description,"
                        " _value, _order, _locked)"
                        " VALUES (:id, :uuid, :box, 't', 'd', 1, :order, 0)"
                    ),
                    {
                        "id": flag_id,
                        "uuid": str(flag_id),
                        "box": box_id,
                        "order": order,
                    },
                )

        command.upgrade(self.cfg, "head")

        # Box 1 keeps its visible order (numbered first, ties by id, empty
        # last) but is renumbered 1..n; box 2 is unchanged.
        with self.engine.connect() as conn:
            orders = dict(conn.execute(text("SELECT id, _order FROM flag")).all())
        self.assertEqual(orders, {2: 1, 3: 2, 5: 3, 1: 4, 4: 5, 6: 1, 7: 2})
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE flag SET _order = NULL WHERE id = 1"))

    def test_single_linear_head(self):
        sd = ScriptDirectory.from_config(self.cfg)
        # Exactly one head (no forgotten/forked branches) and a base exists.
        self.assertEqual(len(sd.get_heads()), 1)
        self.assertTrue(any(r.down_revision is None for r in sd.walk_revisions()))


class TestSchemaParity(MigrationTestCase):
    """No-drift tripwire between the models and the schema create_all builds.
    Table/column presence diffs are detected reliably (sqlite type detection is
    noisy, so those are ignored). This cannot catch a model column that lacks a
    migration — under RTB's create_all architecture that class is unobservable
    from tests — but it guards against gross schema divergence and confirms
    autogenerate runs under SQLAlchemy 2.0."""

    # compare_metadata op codes that represent structural (not type) drift.
    _STRUCTURAL = {
        "add_table",
        "remove_table",
        "add_column",
        "remove_column",
    }

    def test_no_structural_drift_between_models_and_created_schema(self):
        self._create_all()
        command.stamp(self.cfg, "head")
        with self.engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            diffs = compare_metadata(ctx, DatabaseObject.metadata)
        structural = [d for d in diffs if self._diff_op(d) in self._STRUCTURAL]
        self.assertEqual(structural, [], "structural schema drift: %r" % structural)

    @staticmethod
    def _diff_op(diff):
        # A diff is either a tuple ("add_column", schema, table, col) or a list
        # of such tuples (grouped table diffs); read the leading op code.
        if isinstance(diff, list):
            return diff[0][0] if diff and diff[0] else None
        return diff[0] if diff else None


class TestBackupBeforeUpgrade(MigrationTestCase):
    """update_db() backs up a SQLite database before migrating it."""

    OLD_REVISION = "e5f6a7b8c9d0"

    def setUp(self):
        # A private directory, so backups/ never collides with other tests.
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "rootthebox.db")
        self.engine = create_engine("sqlite:///%s" % self.db_path)
        self.cfg = _alembic_cfg(self.db_path)
        self.backups = os.path.join(self.tmpdir.name, "backups")

    def tearDown(self):
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _backup_files(self):
        if not os.path.isdir(self.backups):
            return []
        return [os.path.join(self.backups, name) for name in os.listdir(self.backups)]

    def test_backs_up_before_pending_upgrade(self):
        self._create_all()
        command.stamp(self.cfg, "head")
        command.downgrade(self.cfg, self.OLD_REVISION)

        upgrade_with_backup(self.cfg)

        head = ScriptDirectory.from_config(self.cfg).get_current_head()
        self.assertEqual(self._scalar("SELECT version_num FROM alembic_version"), head)
        backups = self._backup_files()
        self.assertEqual(len(backups), 1)
        self.assertIn(self.OLD_REVISION, os.path.basename(backups[0]))
        backup = create_engine("sqlite:///%s" % backups[0])
        with backup.connect() as conn:
            revision = conn.execute(text("SELECT version_num FROM alembic_version"))
            self.assertEqual(revision.scalar(), self.OLD_REVISION)
        backup.dispose()

    def test_no_backup_when_already_at_head(self):
        self._create_all()
        command.stamp(self.cfg, "head")

        upgrade_with_backup(self.cfg)

        self.assertEqual(self._backup_files(), [])

    def test_failed_backup_stops_the_upgrade(self):
        self._create_all()
        command.stamp(self.cfg, "head")
        command.downgrade(self.cfg, self.OLD_REVISION)
        open(self.backups, "w").close()  # a file where the directory should go

        with self.assertRaises(OSError):
            upgrade_with_backup(self.cfg)

        self.assertEqual(
            self._scalar("SELECT version_num FROM alembic_version"), self.OLD_REVISION
        )

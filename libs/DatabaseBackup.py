# -*- coding: utf-8 -*-
"""
Back up the database before Alembic migrates it.

Migrations can't always be undone (a downgrade can't restore data an upgrade
rewrote), so a SQLite database is copied to backups/ next to it before any
pending migration runs. If the copy fails, the upgrade doesn't run.
"""

import logging
import os
import sqlite3
from datetime import datetime

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from alembic import command


def upgrade_with_backup(alembic_cfg):
    """Upgrade the database to head, backing it up first if anything is pending."""
    url = make_url(alembic_cfg.get_main_option("sqlalchemy.url"))
    current = _current_revision(url)
    head = ScriptDirectory.from_config(alembic_cfg).get_current_head()
    if current is not None and current != head:
        if url.get_backend_name() == "sqlite":
            path = _backup_sqlite(url.database, current)
            logging.info("Backed up database to %s before upgrading" % path)
        else:
            logging.warning(
                "Automatic backup only supports SQLite; back up the %s database"
                " yourself before upgrading" % url.get_backend_name()
            )
    command.upgrade(alembic_cfg, "head")


def _current_revision(url):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def _backup_sqlite(db_path, revision):
    """Copy the database with SQLite's backup API, which is safe while it's open."""
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(db_path))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, "%s-%s-%s%s" % (name, revision, stamp, ext))
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path

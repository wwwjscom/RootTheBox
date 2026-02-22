# -*- coding: utf-8 -*-
"""
Per-user level timer model.
"""


from datetime import datetime, timedelta
from math import ceil

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.types import Integer

from models import dbsession
from models.BaseModels import DatabaseObject


class UserLevelTimer(DatabaseObject):

    """Stores a player's submission window for a level."""

    # Timer ownership is scoped to one user and one level.
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    game_level_id = Column(
        Integer, ForeignKey("game_level.id", ondelete="CASCADE"), nullable=False
    )
    # Absolute expiration timestamp used to prevent client-side tampering.
    expires_at = Column(DateTime, nullable=False)

    # A player can only have one timer record per level.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "game_level_id", name="uq_user_level_timer_user_game_level"
        ),
    )

    @classmethod
    def by_user_and_level_id(cls, user_id, game_level_id):
        """Return the timer record for a specific user/level pair."""
        return (
            dbsession.query(cls)
            .filter_by(user_id=user_id, game_level_id=game_level_id)
            .first()
        )

    @classmethod
    def create_timer(cls, user_id, game_level_id, duration_seconds):
        """Start a timer now and compute its expiration from the configured duration."""
        duration_seconds = max(0, int(duration_seconds))
        return cls(
            user_id=user_id,
            game_level_id=game_level_id,
            expires_at=datetime.now() + timedelta(seconds=duration_seconds),
        )

    def seconds_remaining(self, now=None):
        """Return remaining seconds, rounded up, with a floor at 0."""
        if now is None:
            now = datetime.now()
        delta = (self.expires_at - now).total_seconds()
        if delta <= 0:
            return 0
        return int(ceil(delta))

# -*- coding: utf-8 -*-
"""
Created on Jul 18, 2026

    Copyright 2012 Root the Box

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
------------------------------------------------------------------------------

Game start/stop and countdown state, as plain functions taking the Tornado
Application.  These live outside the handlers so the countdown callback can
end the game without a request context.
"""


import logging
import time

from tornado.options import options

from libs.EventManager import EventManager
from libs.WebhookHelpers import send_game_start_webhook, send_game_stop_webhook


def countdown_seconds(app):
    """Seconds left on the countdown, or None if no countdown is set"""
    deadline = app.settings["countdown_timer"]
    if not deadline:
        return None
    return max(0.0, deadline - time.time())


def start_game(app):
    """Start the game and any related callbacks"""
    if not app.settings["game_started"]:
        logging.info("The game is about to begin, good hunting!")
        app.settings["game_started"] = True
        if options.use_bots:
            app.settings["score_bots_callback"].start()
        # Fire game start webhook
        send_game_start_webhook()


def stop_game(app):
    """Stop the game and all callbacks, and tell connected clients"""
    if app.settings["game_started"]:
        logging.info("The game is stopping ...")
        app.settings["game_started"] = False
        if app.settings["score_bots_callback"]._running:
            app.settings["score_bots_callback"].stop()
        # Fire game stop webhook
        send_game_stop_webhook()
        # Players sitting on a mission page need to be sent to /gamestatus
        EventManager.instance().push_game_stopped()


def expire_countdown(app):
    """
    Called on a timer - ends the countdown once its deadline passes.

    Returns True only when this call stopped the game.  Guarded so it does
    nothing on every tick after the deadline, otherwise an admin re-hiding
    the scoreboard would be overridden a second later.
    """
    try:
        if not app.settings["countdown_timer"] or app.settings["countdown_expired"]:
            return False
        if app.settings["countdown_timer"] - time.time() > 0:
            return False
        app.settings["countdown_expired"] = True
        app.settings["hide_scoreboard"] = False
        stopped = False
        if app.settings["stop_timer"]:
            app.settings["stop_timer"] = False
            stop_game(app)
            stopped = True
        # Unhide the scoreboard for everyone watching
        EventManager.instance().push_scoreboard()
        return stopped
    except Exception:
        # Never let a failure kill the periodic callback
        logging.exception("Error expiring the game countdown")
        return False

# -*- coding: utf-8 -*-
"""
    Copyright 2026 Root the Box

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Periodically checks GitHub for newer Root the Box releases so the admin
dashboard can show an update banner.
"""

import logging
import re

import requests
from tornado.options import options

from libs.Sessions import MemcachedConnect

GITHUB_REPO = "wwwjscom/RootTheBox"
CACHE_KEY = "rtb_latest_version"

# Matches CalVer tags like v2026.07.18, with an optional same-day counter
# like v2026.07.18.1
VERSION_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(?:\.\d+)?$")


def _parse_version(version):
    # No fixed component count: tuple comparison of different lengths is
    # still correct here (2026.07.18 < 2026.07.18.1, as intended).
    return tuple(int(part) for part in re.findall(r"\d+", version))


def is_newer_version(latest, current):
    try:
        return _parse_version(latest) > _parse_version(current)
    except (ValueError, TypeError):
        return False


def check_for_updates():
    """Look up the latest released tag on GitHub and cache it in memcached"""
    if not options.check_for_updates:
        return
    try:
        response = requests.get(
            "https://api.github.com/repos/%s/tags" % GITHUB_REPO,
            timeout=10,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "RootTheBox-UpdateCheck",
            },
        )
        response.raise_for_status()
        tags = [
            tag["name"] for tag in response.json() if VERSION_TAG_RE.match(tag["name"])
        ]
        if not tags:
            return
        latest = max(tags, key=_parse_version)
        memcache = MemcachedConnect()
        memcache.set(CACHE_KEY, latest, time=options.update_check_interval // 500)
    except requests.exceptions.RequestException:
        logging.exception("error checking for Root the Box updates")

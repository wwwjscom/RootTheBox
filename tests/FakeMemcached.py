# -*- coding: utf-8 -*-
"""
In-memory stand-in for the python-binary-memcached client, so tests that
drive login and sessions run without a memcached server (CI has none).

It only implements what the app calls: get, set and delete. Anything else
raises AttributeError, so a new call shows up as a failing test rather than
passing silently. Behaviour matches the real client where the app relies on
it (checked against bmemcached + memcached):
  - get returns the value as it was set (a str stays a str) or None.
  - values are copied, as the real client serialises them.
  - keys the real client rejects (over 250 bytes) or silently drops (control
    characters) raise ValueError here; spaces are allowed.
TTLs are accepted and ignored: nothing expires during a test.
"""

import copy

MAX_KEY_BYTES = 250


def _check_key(key):
    if len(key.encode()) > MAX_KEY_BYTES:
        raise ValueError("memcached key over %d bytes" % MAX_KEY_BYTES)
    if any(ord(char) < 32 or ord(char) == 127 for char in key):
        raise ValueError("memcached key contains a control character: %r" % key)


class FakeMemcached(object):
    def __init__(self):
        self._store = {}

    def get(self, key):
        _check_key(key)
        return copy.deepcopy(self._store.get(key))

    def set(self, key, value, time=0):
        _check_key(key)
        self._store[key] = copy.deepcopy(value)
        return True

    def delete(self, key):
        _check_key(key)
        return self._store.pop(key, None) is not None

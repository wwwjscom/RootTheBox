# -*- coding: utf-8 -*-
"""
Unit tests for OIDC (Keycloak) single sign-on: libs/OIDCClient.py and
handlers/OIDCHandlers.py.  The identity provider is never contacted; token
exchange and ID token validation are mocked at the libs.OIDCClient boundary.
"""

import time
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from tornado.options import options
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from handlers import app, oidc_urls, urls
from libs import OIDCClient
from libs.OIDCClient import OIDCError
from models import dbsession
from models.Permission import Permission
from models.Team import Team
from models.User import ADMIN_PERMISSION, User

ISSUER = "http://idp.test/realms/rootthebox"
XSRF = "3858f62230ac3c915f300c664312c63f"

OIDC_OPTIONS = {
    "auth": "oidc",
    "oidc_issuer": ISSUER,
    "oidc_backchannel_url": "",
    "oidc_client_id": "rootthebox",
    "oidc_client_secret": "secret",
    "oidc_redirect_url": "http://localhost:8888/oidc/callback",
    "oidc_roles_claim": "roles",
    "oidc_admin_role": "rtb-admin",
    "oidc_logout": True,
    "teams": True,
    "public_teams": True,
    "max_team_size": 4,
    "story_mode": False,
    "admin_ips": [],
}

DISCOVERY = {
    "issuer": ISSUER,
    "authorization_endpoint": ISSUER + "/protocol/openid-connect/auth",
    "token_endpoint": ISSUER + "/protocol/openid-connect/token",
    "jwks_uri": ISSUER + "/protocol/openid-connect/certs",
    "end_session_endpoint": ISSUER + "/protocol/openid-connect/logout",
}


class OptionsMixin(object):
    """Set the OIDC options for a test and restore them afterwards"""

    def set_options(self, overrides=None):
        values = dict(OIDC_OPTIONS, **(overrides or {}))
        self._saved_options = {name: getattr(options, name) for name in values}
        for name, value in values.items():
            setattr(options, name, value)

    def restore_options(self):
        for name, value in self._saved_options.items():
            setattr(options, name, value)


class TestOIDCClient(OptionsMixin, unittest.TestCase):
    def setUp(self):
        self.set_options()
        OIDCClient.reset_cache()
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        patcher = mock.patch.object(
            OIDCClient, "_signing_key", return_value=self.key.public_key()
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.restore_options()
        OIDCClient.reset_cache()

    def _token(self, key=None, **overrides):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": "rootthebox",
            "sub": "subject-1",
            "iat": now,
            "exp": now + 300,
            "nonce": "n-123",
        }
        claims.update(overrides)
        return jwt.encode(claims, key or self.key, algorithm="RS256")

    def test_valid_token(self):
        claims = OIDCClient.validate_id_token(self._token(), "n-123")
        self.assertEqual(claims["sub"], "subject-1")

    def test_wrong_audience(self):
        with self.assertRaises(OIDCError):
            OIDCClient.validate_id_token(self._token(aud="someone-else"), "n-123")

    def test_wrong_issuer(self):
        with self.assertRaises(OIDCError):
            OIDCClient.validate_id_token(self._token(iss="http://evil"), "n-123")

    def test_expired(self):
        old = int(time.time()) - 3600
        with self.assertRaises(OIDCError):
            OIDCClient.validate_id_token(self._token(iat=old - 300, exp=old), "n-123")

    def test_bad_nonce(self):
        with self.assertRaises(OIDCError):
            OIDCClient.validate_id_token(self._token(), "other-nonce")

    def test_bad_signature(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(OIDCError):
            OIDCClient.validate_id_token(self._token(key=other), "n-123")

    def test_roles_flat_and_dotted(self):
        self.assertEqual(OIDCClient.roles({"roles": ["a", "b"]}), ["a", "b"])
        options.oidc_roles_claim = "realm_access.roles"
        claims = {"realm_access": {"roles": ["rtb-admin"]}}
        self.assertEqual(OIDCClient.roles(claims), ["rtb-admin"])
        self.assertTrue(OIDCClient.is_admin(claims))
        self.assertEqual(OIDCClient.roles({}), [])

    def test_backchannel_rewrites_server_side_endpoints(self):
        options.oidc_backchannel_url = "http://host.docker.internal:8080/realms/rtb"
        options.oidc_issuer = "http://localhost:8080/realms/rtb"
        rewritten = OIDCClient._backchannel(
            "http://localhost:8080/realms/rtb/protocol/openid-connect/token"
        )
        self.assertEqual(
            rewritten,
            "http://host.docker.internal:8080/realms/rtb/protocol/openid-connect/token",
        )

    def test_authorization_url_has_pkce_state_and_nonce(self):
        with mock.patch.object(OIDCClient, "discovery", return_value=DISCOVERY):
            url = OIDCClient.authorization_url("st", "no", "ch")
        query = parse_qs(urlparse(url).query)
        self.assertTrue(url.startswith(DISCOVERY["authorization_endpoint"]))
        self.assertEqual(query["state"], ["st"])
        self.assertEqual(query["nonce"], ["no"])
        self.assertEqual(query["code_challenge"], ["ch"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["response_type"], ["code"])


class TestOIDCModel(unittest.TestCase):
    def test_by_oidc_subject(self):
        user = User(handle="sub_%s" % uuid4().hex[:8], password="Password123")
        user.oidc_subject = "kc-%s" % uuid4().hex
        dbsession.add(user)
        dbsession.commit()
        try:
            self.assertEqual(User.by_oidc_subject(user.oidc_subject).id, user.id)
            self.assertIsNone(User.by_oidc_subject("nope"))
            self.assertIsNone(User.by_oidc_subject(None))
        finally:
            dbsession.delete(user)
            dbsession.commit()


class TestOIDCHandlers(OptionsMixin, AsyncHTTPTestCase):
    """End-to-end SSO flows against the Tornado app with the IdP mocked"""

    def get_app(self):
        return Application(oidc_urls + urls, **app.settings)

    def setUp(self):
        super().setUp()
        self.set_options()
        # get_app() copied app.settings, so this doesn't leak into other tests.
        self._app.settings["suspend_registration"] = False
        self.cookies = {"_xsrf": XSRF}
        self.created = []
        patcher = mock.patch.object(OIDCClient, "discovery", return_value=DISCOVERY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.restore_options()
        dbsession.rollback()
        # Users first; deleting a team also cascades to its members.
        for cls, _id in self.created:
            row = dbsession.get(cls, _id)
            if row is not None:
                dbsession.delete(row)
                dbsession.commit()
        super().tearDown()

    # -- HTTP helpers --------------------------------------------------------
    def _request(self, path, method="GET", data=None):
        headers = {"Cookie": "; ".join("%s=%s" % kv for kv in self.cookies.items())}
        body = None
        if method == "POST":
            fields = dict(data or {}, _xsrf=XSRF)
            body = "&".join("%s=%s" % (k, v) for k, v in fields.items())
        response = self.fetch(
            path, method=method, body=body, headers=headers, follow_redirects=False
        )
        for header in response.headers.get_list("Set-Cookie"):
            name, value = header.split(";")[0].split("=", 1)
            if value.strip('"'):
                self.cookies[name] = value
            else:
                self.cookies.pop(name, None)
        return response

    def _sso(self, claims):
        """Run /login -> IdP (mocked) -> /oidc/callback; return the callback response"""
        login = self._request("/login")
        self.assertEqual(login.code, 302)
        query = parse_qs(urlparse(login.headers["Location"]).query)
        state, nonce = query["state"][0], query["nonce"][0]
        full = dict({"name": "Jane Player", "email": "jane@example.com"}, **claims)
        with (
            mock.patch.object(
                OIDCClient, "exchange_code", return_value={"id_token": "raw-id-token"}
            ) as exchange,
            mock.patch.object(
                OIDCClient, "validate_id_token", return_value=full
            ) as validate,
        ):
            response = self._request("/oidc/callback?state=%s&code=abc" % state)
        if response.code == 302 and exchange.called:
            validate.assert_called_with("raw-id-token", nonce)
        return response

    def _team(self, name=None):
        team = Team()
        team.name = name or "T%s" % uuid4().hex[:8]
        team.motto = ""
        dbsession.add(team)
        dbsession.commit()
        self.created.append((Team, team.id))
        return team

    def _sso_user(self, team=None, admin=False, **fields):
        user = User(handle="u%s" % uuid4().hex[:8], password="Password123")
        user.oidc_subject = "kc-%s" % uuid4().hex
        user.name = fields.get("name", "Old Name")
        user.email = fields.get("email", "old@example.com")
        if team is not None:
            user.team_id = team.id
        dbsession.add(user)
        dbsession.flush()
        if admin:
            dbsession.add(Permission(name=ADMIN_PERMISSION, user_id=user.id))
        dbsession.commit()
        self.created.insert(0, (User, user.id))
        return user

    def _track(self, handle):
        user = User.by_handle(handle)
        if user is not None:
            self.created.insert(0, (User, user.id))
        return user

    # -- Tests -----------------------------------------------------------------
    def test_login_redirects_to_idp(self):
        response = self._request("/login")
        self.assertEqual(response.code, 302)
        location = response.headers["Location"]
        self.assertTrue(location.startswith(DISCOVERY["authorization_endpoint"]))
        query = parse_qs(urlparse(location).query)
        for param in ("state", "nonce", "code_challenge"):
            self.assertIn(param, query)

    def test_callback_rejects_unknown_state(self):
        with mock.patch.object(OIDCClient, "exchange_code") as exchange:
            response = self._request("/oidc/callback?state=bogus&code=abc")
        self.assertEqual(response.code, 200)
        self.assertIn(b"Single sign-on failed", response.body)
        exchange.assert_not_called()
        self.assertNotIn("session_id", self.cookies)

    def test_callback_rejects_invalid_token(self):
        login = self._request("/login")
        state = parse_qs(urlparse(login.headers["Location"]).query)["state"][0]
        with (
            mock.patch.object(
                OIDCClient, "exchange_code", return_value={"id_token": "x"}
            ),
            mock.patch.object(
                OIDCClient, "validate_id_token", side_effect=OIDCError("bad")
            ),
        ):
            response = self._request("/oidc/callback?state=%s&code=abc" % state)
        self.assertIn(b"Single sign-on failed", response.body)
        self.assertNotIn("session_id", self.cookies)

    def test_new_user_is_sent_to_onboarding(self):
        sub = "kc-%s" % uuid4().hex
        response = self._sso({"sub": sub, "preferred_username": "jane.doe"})
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], "/onboarding")
        self.assertIsNone(User.by_oidc_subject(sub))
        self.assertNotIn("session_id", self.cookies)
        page = self._request("/onboarding")
        self.assertEqual(page.code, 200)
        self.assertIn(b'value="jane.doe"', page.body)
        self.assertIn(b"jane@example.com", page.body)

    def test_onboarding_without_pending_identity_redirects_to_login(self):
        response = self._request("/onboarding")
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_onboarding_creates_user_and_joins_team(self):
        team = self._team()
        sub = "kc-%s" % uuid4().hex
        handle = "j%s" % uuid4().hex[:8]
        self._sso({"sub": sub})
        response = self._request(
            "/onboarding", "POST", {"handle": handle, "team-code": team.code}
        )
        user = self._track(handle)
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], "/user")
        self.assertIn("session_id", self.cookies)
        self.assertNotIn("oidc_pending", self.cookies)
        self.assertEqual(user.oidc_subject, sub)
        self.assertEqual(user.team.id, team.id)
        self.assertEqual(user.name, "Jane Player")
        self.assertEqual(user.email, "jane@example.com")
        self.assertFalse(user.is_admin())

    def test_onboarding_creates_new_team(self):
        handle = "j%s" % uuid4().hex[:8]
        team_name = "N%s" % uuid4().hex[:8]
        self._sso({"sub": "kc-%s" % uuid4().hex})
        response = self._request(
            "/onboarding",
            "POST",
            {"handle": handle, "teammode": "create", "team_name": team_name},
        )
        user = self._track(handle)
        self.created.append((Team, Team.by_name(team_name).id))
        self.assertEqual(response.code, 302)
        self.assertEqual(user.team.name, team_name)

    def test_onboarding_rejects_duplicate_handle(self):
        existing = self._sso_user(team=self._team())
        sub = "kc-%s" % uuid4().hex
        self._sso({"sub": sub})
        response = self._request(
            "/onboarding", "POST", {"handle": existing.handle, "team-code": "x"}
        )
        self.assertEqual(response.code, 200)
        self.assertIn(b"already registered", response.body)
        self.assertIsNone(User.by_oidc_subject(sub))

    def test_onboarding_rejects_full_team(self):
        options.max_team_size = 1
        team = self._team()
        code = team.code
        self._sso_user(team=team)
        sub = "kc-%s" % uuid4().hex
        self._sso({"sub": sub})
        response = self._request(
            "/onboarding",
            "POST",
            {"handle": "j%s" % uuid4().hex[:8], "team-code": code},
        )
        self.assertIn(b"already full", response.body)
        self.assertIsNone(User.by_oidc_subject(sub))

    def test_onboarding_respects_suspended_registration(self):
        self._app.settings["suspend_registration"] = True
        sub = "kc-%s" % uuid4().hex
        self._sso({"sub": sub})
        response = self._request(
            "/onboarding", "POST", {"handle": "j%s" % uuid4().hex[:8]}
        )
        self.assertIn(b"not accepting new players", response.body)
        self.assertIsNone(User.by_oidc_subject(sub))

    def test_admin_onboarding_needs_no_team(self):
        handle = "a%s" % uuid4().hex[:8]
        self._sso({"sub": "kc-%s" % uuid4().hex, "roles": ["rtb-admin"]})
        page = self._request("/onboarding")
        self.assertNotIn(b'name="team-code"', page.body)
        response = self._request("/onboarding", "POST", {"handle": handle})
        user = self._track(handle)
        self.assertEqual(response.code, 302)
        self.assertTrue(user.is_admin())
        self.assertIsNone(user.team)

    def test_returning_user_logs_in_and_syncs_profile(self):
        user = self._sso_user(team=self._team())
        logins = user.logins or 0
        response = self._sso(
            {"sub": user.oidc_subject, "name": "New Name", "email": "new@example.com"}
        )
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers["Location"], "/user")
        self.assertIn("session_id", self.cookies)
        dbsession.expire_all()
        user = User.by_id(user.id)
        self.assertEqual(user.name, "New Name")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.logins, logins + 1)

    def test_admin_role_granted_and_revoked(self):
        team = self._team()
        user = self._sso_user(team=team)
        self._sso({"sub": user.oidc_subject, "roles": ["rtb-admin"]})
        dbsession.expire_all()
        self.assertTrue(User.by_id(user.id).is_admin())

        self.cookies = {"_xsrf": XSRF}
        response = self._sso({"sub": user.oidc_subject, "roles": []})
        dbsession.expire_all()
        user = User.by_id(user.id)
        self.assertFalse(user.is_admin())
        # Promotion dropped the team, so the demoted player must pick one again.
        self.assertIsNone(user.team)
        self.assertEqual(response.headers["Location"], "/onboarding")

    def test_locked_user_is_denied(self):
        user = self._sso_user(team=self._team())
        user.locked = True
        dbsession.commit()
        response = self._sso({"sub": user.oidc_subject})
        self.assertEqual(response.code, 200)
        self.assertIn(b"locked", response.body)
        self.assertNotIn("session_id", self.cookies)

    def test_returning_player_without_team_picks_team_only(self):
        user = self._sso_user()
        team = self._team()
        response = self._sso({"sub": user.oidc_subject})
        self.assertEqual(response.headers["Location"], "/onboarding")
        page = self._request("/onboarding")
        self.assertNotIn(b'name="handle"', page.body)
        # A tampered handle field must be ignored for an existing account.
        response = self._request(
            "/onboarding", "POST", {"handle": "hijack", "team-code": team.code}
        )
        self.assertEqual(response.code, 302)
        dbsession.expire_all()
        user = User.by_id(user.id)
        self.assertEqual(user.team.id, team.id)
        self.assertNotEqual(user.handle, "hijack")

    def test_logout_ends_idp_session(self):
        user = self._sso_user(team=self._team())
        self._sso({"sub": user.oidc_subject})
        response = self._request("/logout", "POST")
        self.assertEqual(response.code, 302)
        location = response.headers["Location"]
        self.assertTrue(location.startswith(DISCOVERY["end_session_endpoint"]))
        query = parse_qs(urlparse(location).query)
        self.assertEqual(query["id_token_hint"], ["raw-id-token"])
        self.assertEqual(query["post_logout_redirect_uri"], ["http://localhost:8888/"])

    def test_email_is_managed_by_idp(self):
        user = self._sso_user(team=self._team())
        self._sso({"sub": user.oidc_subject, "email": "kc@example.com"})
        response = self._request(
            "/user/settings/email", "POST", {"email": "other@example.com"}
        )
        self.assertIn(b"managed by your identity provider", response.body)
        dbsession.expire_all()
        self.assertEqual(User.by_id(user.id).email, "kc@example.com")

    def test_admin_onboarding_bypasses_suspended_registration(self):
        # In SSO mode there's no local admin, so the first Keycloak admin must be
        # able to onboard while registration is still suspended (the default).
        self._app.settings["suspend_registration"] = True
        handle = "a%s" % uuid4().hex[:8]
        self._sso({"sub": "kc-%s" % uuid4().hex, "roles": ["rtb-admin"]})
        page = self._request("/onboarding")
        self.assertNotIn(b"not accepting new players", page.body)
        response = self._request("/onboarding", "POST", {"handle": handle})
        user = self._track(handle)
        self.assertEqual(response.code, 302)
        self.assertTrue(user.is_admin())

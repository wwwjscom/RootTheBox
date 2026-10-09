# -*- coding: utf-8 -*-
"""
Handlers for single sign-on via a generic OpenID Connect provider (e.g.
Keycloak), active when options.auth == "oidc".

Flow:
  /login          -> redirect to the IdP (Authorization Code + PKCE)
  /oidc/callback  -> validate the ID token, then either log a returning user
                     straight in, or stash the identity and go to onboarding
  /onboarding     -> new users pick a handle (and team); returning players
                     without a team pick a team.  No RTB session exists
                     until onboarding completes.
"""

import json
import logging
import re
import secrets

from tornado.options import options

from handlers.BaseHandlers import BaseHandler
from handlers.PublicHandlers import RegistrationHandler
from libs import OIDCClient as oidc
from libs.Identicon import identicon
from libs.OIDCClient import OIDCError
from libs.ValidationError import ValidationError
from libs.WebhookHelpers import send_user_registered_webhook
from models.Permission import Permission
from models.User import ADMIN_PERMISSION, User

STATE_PREFIX = "oidc_state_"
PENDING_PREFIX = "oidc_pending_"
PENDING_COOKIE = "oidc_pending"
STATE_TTL = 600  # seconds to complete the IdP login
PENDING_TTL = 1800  # seconds to complete onboarding
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{16,128}$")
HANDLE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{3,16}$")
TEAM_NAME_PATTERN = re.compile(r"^[0-9A-Za-z _\-\.]{3,24}$")
SSO_FAILED = "Single sign-on failed, please try again."


class OIDCMixin(object):
    """Shared helpers for the OIDC handlers"""

    def oidc_error(self, message):
        self.render("public/login.html", info=None, errors=[message])

    def _memcached_json(self, key):
        raw = self.memcached.get(key)
        if raw is None:
            return None
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    def pending_identity(self):
        """The IdP identity waiting on onboarding, or None"""
        token = self.get_secure_cookie(PENDING_COOKIE, max_age_days=1)
        if token is None or not TOKEN_PATTERN.match(token.decode()):
            return None
        return self._memcached_json(PENDING_PREFIX + token.decode())

    def save_pending(self, identity):
        token = secrets.token_urlsafe(32)
        self.memcached.set(PENDING_PREFIX + token, json.dumps(identity), PENDING_TTL)
        flags = {"httponly": True, "path": "/"}
        if self.config.ssl:
            flags["secure"] = True
        self.set_secure_cookie(
            PENDING_COOKIE, token, expires_days=PENDING_TTL / 86400.0, **flags
        )

    def clear_pending(self):
        token = self.get_secure_cookie(PENDING_COOKIE, max_age_days=1)
        if token is not None and TOKEN_PATTERN.match(token.decode()):
            self.memcached.delete(PENDING_PREFIX + token.decode())
        self.clear_cookie(PENDING_COOKIE, path="/")

    def login_denied(self, user):
        """Reason this user may not log in, or None"""
        admin_ips = options.admin_ips
        if user.is_admin() and admin_ips and self.request.remote_ip not in admin_ips:
            logging.warning(
                "Admin SSO login - invalid IP %s.  Valid: %s"
                % (self.request.remote_ip, ",".join(admin_ips))
            )
            return "Administration is restricted via IP.  See 'admin_ips' in configuration."
        if user.locked:
            return "Your account has been locked"
        if user.is_expired():
            return "Your account is expired"
        return None

    def complete_login(self, user, id_token):
        logging.info(
            "Successful SSO login: %s from %s" % (user.handle, self.request.remote_ip)
        )
        self.start_user_session(user)
        # Kept for RP-initiated logout at the IdP.
        self.session["id_token"] = id_token
        self.session.save()
        if self.config.story_mode and user.logins == 1 and not user.is_admin():
            self.redirect("/user/missions/firstlogin")
        else:
            self.redirect("/user")


class OIDCLoginHandler(OIDCMixin, BaseHandler):
    """Sends the browser to the identity provider"""

    def get(self, *args, **kwargs):
        if self.session is not None:
            self.redirect("/user")
            return
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier, challenge = oidc.new_pkce_pair()
        try:
            url = oidc.authorization_url(state, nonce, challenge)
        except OIDCError:
            logging.exception("OIDC login could not start")
            self.oidc_error(SSO_FAILED)
            return
        stored = json.dumps({"nonce": nonce, "verifier": verifier})
        self.memcached.set(STATE_PREFIX + state, stored, STATE_TTL)
        self.redirect(url)


class OIDCCallbackHandler(OIDCMixin, BaseHandler):
    """Handles the identity provider's redirect back to RootTheBox"""

    def get(self, *args, **kwargs):
        if self.get_argument("error", None):
            logging.warning("OIDC provider error: %s" % self.get_argument("error"))
            self.oidc_error(SSO_FAILED)
            return
        identity = self.authenticate()
        if identity is None:
            self.oidc_error(SSO_FAILED)
            return
        user = User.by_oidc_subject(identity["sub"])
        if user is not None:
            self.sync_user(user, identity)
            denied = self.login_denied(user)
            if denied:
                self.oidc_error(denied)
                return
            if user.is_admin() or user.team is not None:
                self.complete_login(user, identity["id_token"])
                return
        self.save_pending(identity)
        self.redirect("/onboarding")

    def authenticate(self):
        """Validate state, redeem the code and return the IdP identity"""
        state = self.get_argument("state", "")
        if not TOKEN_PATTERN.match(state):
            return None
        stored = self._memcached_json(STATE_PREFIX + state)
        if stored is None:
            return None
        self.memcached.delete(STATE_PREFIX + state)  # single use
        try:
            tokens = oidc.exchange_code(self.get_argument("code", ""), stored["verifier"])
            claims = oidc.validate_id_token(tokens["id_token"], stored["nonce"])
        except OIDCError as error:
            logging.warning("OIDC login failed: %s" % error)
            return None
        username = str(claims.get("preferred_username", ""))
        return {
            "sub": str(claims["sub"]),
            "username": username,
            "name": str(claims.get("name") or username)[:64],
            "email": str(claims.get("email", ""))[:64],
            "admin": oidc.is_admin(claims),
            "id_token": tokens["id_token"],
        }

    def sync_user(self, user, identity):
        """The IdP owns name, email and admin rights; refresh them each login"""
        user.name = identity["name"]
        user.email = identity["email"]
        if identity["admin"] and not user.is_admin():
            self.dbsession.add(Permission(name=ADMIN_PERMISSION, user_id=user.id))
            user.team_id = None  # Admins aren't part of a team.
        elif not identity["admin"] and user.is_admin():
            for permission in Permission.by_user_id(user.id):
                if permission.name == ADMIN_PERMISSION:
                    self.dbsession.delete(permission)
        self.dbsession.add(user)
        self.dbsession.commit()
        self.dbsession.expire(user, ["permissions"])


class OnboardingHandler(OIDCMixin, RegistrationHandler):
    """First-login profile setup: handle and team (reuses registration's team logic)"""

    trusted = None

    def get_argument(self, name, *args, **kwargs):
        # get_team()/create_team() read 'handle' and 'playername' from the form;
        # for SSO those come from the account or the identity provider instead.
        if self.trusted and name in self.trusted:
            return self.trusted[name]
        return super().get_argument(name, *args, **kwargs)

    def get(self, *args, **kwargs):
        identity = self.pending_identity()
        if identity is None:
            self.redirect("/login")
            return
        self.render_page(identity)

    def post(self, *args, **kwargs):
        identity = self.pending_identity()
        if identity is None:
            self.redirect("/login")
            return
        user = self.pending_user(identity)
        try:
            if user is None:
                if self.registration_closed(identity):
                    self.render_page(identity)
                    return
                user = self.create_sso_user(identity)
            elif user.team is None and not user.is_admin():
                self.join_team(user)
        except ValidationError as error:
            self.dbsession.rollback()
            self.render_page(identity, [str(error)])
            return
        self.clear_pending()
        self.complete_login(user, identity["id_token"])

    def render_page(self, identity, errors=None):
        user = self.pending_user(identity)
        self.render(
            "public/onboarding.html",
            errors=errors,
            identity=identity,
            new_user=user is None,
            suspend=user is None and self.registration_closed(identity),
            handle=self.suggest_handle(identity),
        )

    def registration_closed(self, identity):
        # IdP admins are exempt: with SSO there is no local admin who could
        # open registration, so the first admin must always get in.
        suspended = self.application.settings["suspend_registration"]
        return suspended and not identity["admin"]

    def pending_user(self, identity):
        """The existing account being onboarded, or None for a new user"""
        return User.by_oidc_subject(identity["sub"])

    @staticmethod
    def suggest_handle(identity):
        handle = re.sub(r"[^a-zA-Z0-9_\-\.]", "", identity["username"].split("@")[0])
        return handle[:16] if len(handle) >= 3 else ""

    def validate_team_fields(self):
        team_name = self.get_argument("team_name", "")
        if team_name and not TEAM_NAME_PATTERN.match(team_name):
            raise ValidationError("Invalid Team Name format")
        if len(self.get_argument("motto", "")) > 32:
            raise ValidationError("Invalid Team Motto format")

    def create_sso_user(self, identity):
        handle = self.get_argument("handle", "").strip()
        if not HANDLE_PATTERN.match(handle):
            raise ValidationError("Invalid handle format")
        if User.by_handle(handle) is not None:
            raise ValidationError("This handle is already registered")
        self.trusted = {"handle": handle, "playername": identity["name"] or handle}
        team = None
        if not identity["admin"]:
            self.validate_team_fields()
            team = self.get_team()
            self.dbsession.add(team)
        password = secrets.token_urlsafe(32)  # never used; SSO only
        user = User()
        user.handle = handle
        user.oidc_subject = identity["sub"]
        user.password = password
        user.bank_password = self.get_argument("bpass", "")
        user.name = identity["name"]
        user.email = identity["email"]
        user.theme = options.default_theme
        user._avatar = identicon(handle, 6)
        self.dbsession.add(user)
        self.dbsession.flush()
        if identity["admin"]:
            self.dbsession.add(Permission(name=ADMIN_PERMISSION, user_id=user.id))
        else:
            team.members.append(user)
        self.dbsession.commit()
        send_user_registered_webhook(user)
        self.after_join(user, password)
        return user

    def join_team(self, user):
        self.trusted = {"handle": user.handle, "playername": user.name or user.handle}
        self.validate_team_fields()
        team = self.get_team()
        self.dbsession.add(team)
        team.members.append(user)
        self.dbsession.commit()
        self.after_join(user)

    def after_join(self, user, password=None):
        if user.team is not None:
            self.event_manager.user_joined_team(user)
            self.event_manager.push_score_update()
        if password and self.chatsession:
            self.chatsession.create_user(user, password)

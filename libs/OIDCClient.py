# -*- coding: utf-8 -*-
"""
Minimal OpenID Connect relying-party client (Authorization Code + PKCE),
used when options.auth == "oidc" (e.g. Keycloak).

The issuer URL is what browsers use and what the ID token's 'iss' claim must
match.  When RootTheBox cannot reach the IdP at that URL (e.g. running in
Docker while the IdP is on the host's localhost), oidc_backchannel_url is
substituted for the issuer prefix on server-to-server requests only.
"""

import hashlib
import hmac
import logging
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import urlencode

import jwt
import requests
from tornado.options import options

TIMEOUT = 10  # seconds, for every request to the IdP
ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384"]

_discovery = None
_jwks_client = None


class OIDCError(Exception):
    """Any failure talking to the IdP or validating its response"""


def reset_cache():
    global _discovery, _jwks_client
    _discovery = None
    _jwks_client = None


def _issuer():
    return options.oidc_issuer.rstrip("/")


def _backchannel(url):
    """Rewrite a public IdP URL to the server-reachable backchannel URL"""
    backchannel = options.oidc_backchannel_url.rstrip("/")
    if backchannel and url.startswith(_issuer()):
        return backchannel + url[len(_issuer()) :]
    return url


def discovery():
    """Fetch (once) the IdP's .well-known/openid-configuration"""
    global _discovery
    if _discovery is None:
        url = _backchannel(_issuer() + "/.well-known/openid-configuration")
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            _discovery = response.json()
        except (requests.RequestException, ValueError) as error:
            raise OIDCError("OIDC discovery failed: %s" % error)
    return _discovery


def new_pkce_pair():
    """Return a (code_verifier, S256 code_challenge) pair"""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(state, nonce, code_challenge):
    params = {
        "response_type": "code",
        "client_id": options.oidc_client_id,
        "redirect_uri": options.oidc_redirect_url,
        "scope": options.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return "%s?%s" % (discovery()["authorization_endpoint"], urlencode(params))


def exchange_code(code, code_verifier):
    """Trade an authorization code for tokens at the token endpoint"""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": options.oidc_redirect_url,
        "client_id": options.oidc_client_id,
        "client_secret": options.oidc_client_secret,
        "code_verifier": code_verifier,
    }
    url = _backchannel(discovery()["token_endpoint"])
    try:
        response = requests.post(url, data=data, timeout=TIMEOUT)
        tokens = response.json()
    except (requests.RequestException, ValueError) as error:
        raise OIDCError("Token request failed: %s" % error)
    if response.status_code != 200 or "id_token" not in tokens:
        raise OIDCError("Token request rejected: %s" % tokens.get("error", "unknown"))
    return tokens


def _signing_key(id_token):
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            _backchannel(discovery()["jwks_uri"]), timeout=TIMEOUT
        )
    return _jwks_client.get_signing_key_from_jwt(id_token).key


def validate_id_token(id_token, nonce):
    """Verify signature, issuer, audience, expiry and nonce; return the claims"""
    try:
        claims = jwt.decode(
            id_token,
            _signing_key(id_token),
            algorithms=ALGORITHMS,
            audience=options.oidc_client_id,
            issuer=_issuer(),
            leeway=30,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except (jwt.PyJWTError, requests.RequestException) as error:
        raise OIDCError("Invalid ID token: %s" % error)
    if not hmac.compare_digest(str(claims.get("nonce", "")), str(nonce)):
        raise OIDCError("Invalid ID token: nonce mismatch")
    return claims


def roles(claims):
    """Roles found at the (dotted) oidc_roles_claim path, or []"""
    value = claims
    for part in options.oidc_roles_claim.split("."):
        if not isinstance(value, dict):
            return []
        value = value.get(part)
    return list(value) if isinstance(value, list) else []


def is_admin(claims):
    return options.oidc_admin_role in roles(claims)


def end_session_url(id_token_hint, post_logout_redirect_uri):
    """RP-initiated logout URL, or None if the IdP doesn't support it"""
    try:
        endpoint = discovery().get("end_session_endpoint")
    except OIDCError:
        logging.exception("Cannot build OIDC logout URL")
        return None
    if not endpoint:
        return None
    params = {
        "client_id": options.oidc_client_id,
        "post_logout_redirect_uri": post_logout_redirect_uri,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    return "%s?%s" % (endpoint, urlencode(params))

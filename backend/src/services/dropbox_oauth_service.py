"""Dropbox OAuth flow with a HMAC-signed state parameter.

The shared whatdoweeat Dropbox app's app-key/secret are server-side env
vars (DROPBOX_APP_KEY, DROPBOX_APP_SECRET). We hand each user the auth
URL to *their* Dropbox account; what comes back is a refresh token only
valid for that user's account, which we store encrypted per-user.

`state` is a HMAC-signed payload encoding {user_id, recipes_path,
expiry}. Dropbox echoes it back unchanged on the callback, so we can
trust it (after re-verifying the HMAC) without keeping any server-side
state between the two requests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests

log = logging.getLogger(__name__)

_AUTH_URL = "https://www.dropbox.com/oauth2/authorize"
_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
_REVOKE_URL = "https://api.dropboxapi.com/2/auth/token/revoke"

_STATE_TTL_SECONDS = 600  # 10 minutes


def _app_key() -> str:
    v = os.getenv("DROPBOX_APP_KEY")
    if not v:
        raise RuntimeError("DROPBOX_APP_KEY is not set")
    return v


def _app_secret() -> str:
    v = os.getenv("DROPBOX_APP_SECRET")
    if not v:
        raise RuntimeError("DROPBOX_APP_SECRET is not set")
    return v


def _backend_url() -> str:
    """Public URL of this backend, used to build the redirect_uri.

    Must exactly match the redirect URI registered in the Dropbox app's
    settings ("OAuth 2 redirect URIs"). If you have multiple
    environments, register all of them in Dropbox.
    """
    v = os.getenv("BACKEND_PUBLIC_URL")
    if not v:
        raise RuntimeError("BACKEND_PUBLIC_URL is not set")
    return v.rstrip("/")


def _frontend_url() -> str:
    """Where to redirect the browser after a successful connect."""
    v = os.getenv("FRONTEND_PUBLIC_URL")
    if not v:
        raise RuntimeError("FRONTEND_PUBLIC_URL is not set")
    return v.rstrip("/")


def redirect_uri() -> str:
    return f"{_backend_url()}/dropbox/callback"


# ---------------------------------------------------------------------------
# Signed state
# ---------------------------------------------------------------------------

def _state_signing_key() -> bytes:
    """Use the encryption key as the HMAC secret. They live together
    operationally (both in DROPBOX_TOKEN_ENC_KEY-related ops) and we
    only need one server-side secret."""
    key = os.getenv("DROPBOX_TOKEN_ENC_KEY")
    if not key:
        raise RuntimeError(
            "DROPBOX_TOKEN_ENC_KEY is not set; cannot sign OAuth state"
        )
    return key.encode()


@dataclass
class OAuthState:
    user_id: str
    recipes_path: str
    expires_at: int  # unix seconds


def _b64encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def encode_state(user_id: str, recipes_path: str) -> str:
    payload = {
        "u": user_id,
        "p": recipes_path,
        "e": int(time.time()) + _STATE_TTL_SECONDS,
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_state_signing_key(), body, hashlib.sha256).digest()
    return f"{_b64encode(body)}.{_b64encode(sig)}"


def decode_state(state: str) -> OAuthState:
    try:
        body_b64, sig_b64 = state.split(".", 1)
        body = _b64decode(body_b64)
        sig = _b64decode(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Malformed state: {exc}") from exc

    expected_sig = hmac.new(_state_signing_key(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("State signature mismatch")

    try:
        payload = json.loads(body.decode())
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"State body not JSON: {exc}") from exc

    if int(payload.get("e", 0)) < int(time.time()):
        raise ValueError("State has expired")

    return OAuthState(
        user_id=payload["u"],
        recipes_path=payload["p"],
        expires_at=int(payload["e"]),
    )


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def build_authorize_url(state: str) -> str:
    params = {
        "client_id": _app_key(),
        "response_type": "code",
        "redirect_uri": redirect_uri(),
        "state": state,
        "token_access_type": "offline",   # refresh tokens
        "scope": "files.metadata.read files.content.read",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


@dataclass
class TokenExchangeResult:
    refresh_token: str
    access_token: str
    expires_in: int


def exchange_code_for_tokens(code: str) -> TokenExchangeResult:
    resp = requests.post(
        _TOKEN_URL,
        data={
            "code": code,
            "grant_type": "authorization_code",
            "client_id": _app_key(),
            "client_secret": _app_secret(),
            "redirect_uri": redirect_uri(),
        },
        timeout=15,
    )
    if resp.status_code != 200:
        log.error(
            "Dropbox token exchange failed: %s %s",
            resp.status_code,
            resp.text,
        )
        raise RuntimeError(f"Dropbox token exchange failed: {resp.status_code}")
    body = resp.json()
    refresh = body.get("refresh_token")
    if not refresh:
        raise RuntimeError(
            "Dropbox didn't return a refresh token; did you set "
            "token_access_type=offline on the auth URL?"
        )
    return TokenExchangeResult(
        refresh_token=refresh,
        access_token=body.get("access_token", ""),
        expires_in=int(body.get("expires_in", 0)),
    )


def revoke_refresh_token(refresh_token: str) -> bool:
    """Best-effort revoke. Returns True on 200, False otherwise."""
    try:
        # The revoke endpoint requires an access token; use the refresh
        # token to mint a fresh access token first.
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": _app_key(),
                "client_secret": _app_secret(),
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        access = resp.json().get("access_token")
        if not access:
            return False
        rev = requests.post(
            _REVOKE_URL,
            headers={"Authorization": f"Bearer {access}"},
            timeout=15,
        )
        return rev.status_code == 200
    except requests.RequestException:
        return False

"""Auth0 JWT validation for the backend.

The frontend authenticates the user with Auth0 and obtains an access
token. It sends that token as `Authorization: Bearer <jwt>` on each
request. We:

  1. Fetch Auth0's signing keys from the tenant's JWKS endpoint
     (cached for a few hours).
  2. Validate the token's signature, issuer, audience, and expiry.
  3. Return the claims (in particular the `email` claim, which we hash
     to derive the user-id used everywhere else in the app).

Required env vars:
  - AUTH0_DOMAIN     (e.g. dev-xxxxx.us.auth0.com)
  - AUTH0_AUDIENCE   (the API identifier you create in the Auth0
                      dashboard, e.g. `https://api.whatdoweeat`).

To get an access token with the right claims, the frontend's
createAuth0() must request `audience: AUTH0_AUDIENCE` and the `email`
scope. See frontend/src/main.ts.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Annotated, Any, Optional

import requests
from fastapi import Depends, Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

log = logging.getLogger(__name__)


_JWKS_TTL_SECONDS = 3600  # 1 hour
_jwks_cache: dict[str, Any] = {}
_jwks_lock = threading.Lock()


def _domain() -> str:
    domain = os.getenv("AUTH0_DOMAIN")
    if not domain:
        raise RuntimeError("AUTH0_DOMAIN is not set")
    return domain.strip().rstrip("/")


def _audience() -> str:
    audience = os.getenv("AUTH0_AUDIENCE")
    if not audience:
        raise RuntimeError("AUTH0_AUDIENCE is not set")
    return audience.strip()


def _fetch_jwks() -> dict:
    domain = _domain()
    now = time.monotonic()
    with _jwks_lock:
        cached = _jwks_cache.get(domain)
        if cached and (now - cached["fetched_at"]) < _JWKS_TTL_SECONDS:
            return cached["jwks"]
        url = f"https://{domain}/.well-known/jwks.json"
        log.info("Fetching JWKS from %s", url)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        _jwks_cache[domain] = {"jwks": jwks, "fetched_at": now}
        return jwks


def _signing_key_for(token: str) -> dict:
    """Return the JWK used to sign this token (matched by `kid`)."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Malformed token") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token has no kid")

    jwks = _fetch_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    # Force a refresh in case the tenant rotated keys; one retry only.
    with _jwks_lock:
        _jwks_cache.pop(_domain(), None)
    jwks = _fetch_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise HTTPException(status_code=401, detail="Unknown signing key")


def verify_token(token: str) -> dict:
    """Validate a Bearer token and return its claims."""
    domain = _domain()
    audience = _audience()
    key = _signing_key_for(token)
    try:
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{domain}/",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

class CurrentUser:
    """The authenticated user, identified by Auth0's `sub` claim.

    `sub` is mandatory in any Auth0-issued JWT and is the stable, unique
    identifier for the user across providers (e.g. `auth0|abc123` for a
    DB connection, `google-oauth2|123456789` for Google sign-in). We use
    it as the user_id in URLs and Mongo, so it stays consistent even if
    the user's email changes.
    """

    def __init__(self, claims: dict):
        self.claims = claims
        sub = claims.get("sub")
        if not sub:
            # Spec-mandatory claim — should never be missing. If it is,
            # something's wrong with Auth0 config.
            raise HTTPException(
                status_code=403,
                detail="Token has no sub claim",
            )
        self.user_id = sub


def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Missing Bearer token"
        )
    token = authorization.split(" ", 1)[1].strip()
    claims = verify_token(token)
    return CurrentUser(claims)


def require_user_id(user_id: str, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Reject if the path's user_id doesn't match the authenticated user.

    Used as a dependency on routes shaped like /user/{user_id}/...; the
    user_id in the path is what the existing app uses to key data, but
    on its own it's just an opaque hash — anyone could put any value
    there. This binds path identity to token identity.
    """
    if user.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="user_id in path does not match authenticated user",
        )
    return user

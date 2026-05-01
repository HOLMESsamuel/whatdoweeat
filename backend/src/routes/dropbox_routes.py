"""Per-user Dropbox connection endpoints.

Flow:
  1. Frontend calls GET /user/{user_id}/dropbox/auth-url with the
     desired recipes_path; we return a Dropbox authorize URL with a
     HMAC-signed state token.
  2. Browser redirects there; user clicks Allow on Dropbox; Dropbox
     redirects back to GET /dropbox/callback?code=…&state=…
  3. We verify the state, exchange the code for a refresh token,
     encrypt it, store {user_id, encrypted_token, recipes_path}, then
     redirect the browser back to the frontend's /recipes page.
  4. GET /user/{user_id}/dropbox/status reports connection state;
     PUT /user/{user_id}/dropbox/path updates the path;
     DELETE /user/{user_id}/dropbox revokes + deletes.

Routes are guarded by Auth0 JWT — the path's user_id must match the
authenticated user (except for /dropbox/callback, which is hit by the
user's browser via Dropbox's redirect and doesn't carry a JWT; we
authenticate it via the signed state instead).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..models.dropbox_credential import DropboxStatus
from ..services.auth_service import (
    CurrentUser,
    require_user_id,
)
from ..services.crypto_service import get_token_encryption
from ..services.db_service import DBService
from ..services.dropbox_oauth_service import (
    build_authorize_url,
    decode_state,
    encode_state,
    exchange_code_for_tokens,
    revoke_refresh_token,
    _frontend_url,
)

log = logging.getLogger(__name__)

router = APIRouter()

# One DB handle per route module — matches the existing pattern in
# user_routes / grocery_list_routes.
_mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = DBService(_mongo_uri, "whatdoweeat")


def _get_db() -> DBService:
    return db


class AuthUrlResponse(BaseModel):
    url: str


class UpdatePathRequest(BaseModel):
    recipes_path: str


@router.get(
    "/user/{user_id}/dropbox/auth-url",
    response_model=AuthUrlResponse,
)
async def get_auth_url(
    user_id: str,
    recipes_path: str = Query(
        default="/ideaverse/Recettes/recette-templated",
        description="Folder inside the user's Dropbox to read recipes from.",
    ),
    user: CurrentUser = Depends(require_user_id),
):
    state = encode_state(user_id=user_id, recipes_path=recipes_path)
    return AuthUrlResponse(url=build_authorize_url(state))


@router.get("/dropbox/callback")
async def dropbox_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
):
    """Hit by Dropbox after the user clicks Allow (or Cancel).

    Authentication is via the signed `state` parameter — the browser's
    Auth0 session isn't reachable here because Dropbox is redirecting
    cross-origin.
    """
    frontend = _frontend_url()
    if error:
        msg = error_description or error
        log.warning("Dropbox callback returned error: %s", msg)
        return RedirectResponse(
            url=f"{frontend}/#/recipes?dropbox_error={msg}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        decoded = decode_state(state)
    except ValueError as exc:
        log.warning("Invalid state on Dropbox callback: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid state: {exc}")

    try:
        tokens = exchange_code_for_tokens(code)
    except RuntimeError as exc:
        log.exception("Dropbox token exchange failed")
        return RedirectResponse(
            url=f"{frontend}/#/recipes?dropbox_error={exc}",
            status_code=302,
        )

    enc = get_token_encryption()
    encrypted = enc.encrypt(tokens.refresh_token)

    await db.upsert_user_dropbox_credentials(
        user_id=decoded.user_id,
        encrypted_refresh_token=encrypted,
        recipes_path=decoded.recipes_path,
    )

    # Tell the in-memory recipe-service cache to drop this user so the
    # next request rebuilds with the fresh credentials.
    from .recipe_routes import invalidate_user_recipe_cache  # local import

    invalidate_user_recipe_cache(decoded.user_id)

    return RedirectResponse(
        url=f"{frontend}/#/recipes?dropbox_connected=1",
        status_code=302,
    )


@router.get(
    "/user/{user_id}/dropbox/status",
    response_model=DropboxStatus,
)
async def get_status(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
):
    creds = await db.get_user_dropbox_credentials(user_id)
    if creds is None:
        return DropboxStatus(connected=False)
    return DropboxStatus(
        connected=True,
        recipes_path=creds.recipes_path,
        connected_at=creds.created_at,
    )


@router.put("/user/{user_id}/dropbox/path")
async def update_path(
    user_id: str,
    request: UpdatePathRequest,
    user: CurrentUser = Depends(require_user_id),
):
    ok = await db.update_user_dropbox_recipes_path(
        user_id=user_id,
        recipes_path=request.recipes_path,
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="No Dropbox connection for this user",
        )
    from .recipe_routes import invalidate_user_recipe_cache

    invalidate_user_recipe_cache(user_id)
    return {"recipes_path": request.recipes_path}


@router.delete("/user/{user_id}/dropbox")
async def disconnect(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
):
    creds = await db.get_user_dropbox_credentials(user_id)
    if creds is None:
        return {"deleted": False}

    # Best-effort revoke of the refresh token on Dropbox's side. If it
    # fails (network blip, token already revoked) we still delete the
    # local copy.
    try:
        plaintext = get_token_encryption().decrypt(creds.encrypted_refresh_token)
        revoke_refresh_token(plaintext)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not revoke Dropbox token on disconnect: %s", exc)

    await db.delete_user_dropbox_credentials(user_id)
    from .recipe_routes import invalidate_user_recipe_cache

    invalidate_user_recipe_cache(user_id)
    return {"deleted": True}

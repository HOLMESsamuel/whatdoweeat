"""Recipe endpoints.

There are two layers, accessed via different routes:

  - Per-user (the public / production path):
      GET  /user/{user_id}/recipes
      GET  /user/{user_id}/recipe/{recipe_id}
    Each user connects their own Dropbox and the backend reads from
    their account using their stored refresh token.

  - Single-tenant fallback (handy for local dev and self-hosted single-
    user deployments):
      GET  /recipes
      GET  /recipe/{recipe_id}
    Reads from RECIPE_SOURCE=local|dropbox env vars. Requires login.
    Returns an empty list when nothing is configured rather than 500ing.

Mutation endpoints stay 405 — recipes are read-only here, edited in
Obsidian.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..models.recipe import Recipe
from ..services.auth_service import CurrentUser, get_current_user, require_user_id
from ..services.crypto_service import get_token_encryption
from ..services.db_service import DBService
from ..services.recipe_file_service import (
    DropboxRecipeSource,
    RecipeFileService,
    RecipeFolderNotFound,
    RecipeSourceAuthError,
    RecipeSourceError,
    build_default_service,
)

log = logging.getLogger(__name__)

router = APIRouter()

# One DB handle per route module — matches the pattern of the other
# route files (user_routes, grocery_list_routes).
_mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = DBService(_mongo_uri, "whatdoweeat")

# ---------------------------------------------------------------------------
# Per-user RecipeFileService cache
# ---------------------------------------------------------------------------

# Each user gets one RecipeFileService for the lifetime of the process
# (or until their credentials change). The service itself caches per-
# file parses by mtime, so request-level work is small.
_user_services: Dict[str, RecipeFileService] = {}
_user_services_lock = threading.Lock()


def invalidate_user_recipe_cache(user_id: str) -> None:
    """Drop a user's cached RecipeFileService so the next request picks
    up new credentials."""
    with _user_services_lock:
        _user_services.pop(user_id, None)


async def reset_user_recipe_cache(user_id: str) -> None:
    """Drop both cache tiers for a user. Needed whenever the account or
    folder changes: cache keys are bare filenames, so a same-named file
    with the same mtime in the new folder would otherwise be served
    from the old folder's parse."""
    invalidate_user_recipe_cache(user_id)
    try:
        await db.delete_recipe_cache_for_user(user_id)
    except Exception:
        log.exception("Failed to purge recipe_cache for user %s", user_id)


async def build_user_dropbox_source(
    user_id: str, recipes_path: Optional[str] = None
) -> Optional[DropboxRecipeSource]:
    """Dropbox source for a connected user, or None if they aren't
    connected (or their token can't be decrypted)."""
    creds = await db.get_user_dropbox_credentials(user_id)
    if creds is None:
        return None
    try:
        refresh_token = get_token_encryption().decrypt(
            creds.encrypted_refresh_token
        )
    except RuntimeError:
        log.exception(
            "Could not decrypt Dropbox token for user %s — they need to "
            "reconnect.",
            user_id,
        )
        return None
    return DropboxRecipeSource(
        app_key=os.environ["DROPBOX_APP_KEY"],
        app_secret=os.environ["DROPBOX_APP_SECRET"],
        refresh_token=refresh_token,
        recipes_path=recipes_path if recipes_path is not None else creds.recipes_path,
    )


async def _build_user_service(user_id: str) -> Optional[RecipeFileService]:
    source = await build_user_dropbox_source(user_id)
    if source is None:
        return None
    service = RecipeFileService(source)
    await _hydrate_from_persistent_cache(user_id, service)
    return service


async def _hydrate_from_persistent_cache(
    user_id: str, service: RecipeFileService
) -> None:
    """Load any previously-parsed recipes for this user from Mongo so the
    first request after a backend restart doesn't re-download every file.
    The mtime-based freshness check in `_refresh` will still catch any
    edits made while the backend was down."""
    docs = await db.get_recipe_cache(user_id)
    if not docs:
        return
    entries: dict = {}
    for doc in docs:
        try:
            recipe_dict = doc.get("recipe")
            recipe = Recipe(**recipe_dict) if recipe_dict else None
            entries[doc["identifier"]] = (float(doc["mtime"]), recipe)
        except Exception:
            # A malformed cache row shouldn't poison the whole hydrate;
            # the file will just be re-fetched on next refresh.
            log.exception(
                "Skipping malformed recipe_cache row for user %s: %s",
                user_id,
                doc.get("identifier"),
            )
    service.hydrate(entries)


async def _flush_pending(user_id: str, service: RecipeFileService) -> None:
    """Mirror any in-memory cache changes from the most recent refresh to
    the persistent cache. Empty-pending is the common case (warm cache,
    nothing changed) and short-circuits cheaply."""
    dirty, removed = service.take_pending()
    if not dirty and not removed:
        return
    with _user_services_lock:
        current = _user_services.get(user_id)
    if current is not service:
        # The cache was reset (path change / reconnect) while this request
        # was in flight; its results belong to the old folder.
        return
    upserts = [
        (ident, mtime, (recipe.dict() if recipe is not None else None))
        for ident, (mtime, recipe) in dirty.items()
    ]
    try:
        await db.upsert_recipe_cache_entries(user_id, upserts)
        await db.delete_recipe_cache_entries(user_id, list(removed))
    except Exception:
        # Persistence is best-effort: a Mongo blip shouldn't fail the
        # request. The in-memory cache still has the data; we'll retry on
        # the next refresh that produces dirty entries.
        log.exception("Failed to flush recipe_cache for user %s", user_id)


async def _get_user_service(user_id: str) -> Optional[RecipeFileService]:
    with _user_services_lock:
        cached = _user_services.get(user_id)
    if cached is not None:
        return cached
    service = await _build_user_service(user_id)
    if service is None:
        return None
    with _user_services_lock:
        # Another request might have built one in parallel — keep
        # whichever is already there to avoid wasted work.
        existing = _user_services.get(user_id)
        if existing is not None:
            return existing
        _user_services[user_id] = service
    return service


def source_error_to_http(exc: RecipeSourceError) -> HTTPException:
    if isinstance(exc, RecipeFolderNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RecipeSourceAuthError):
        return HTTPException(
            status_code=409,
            detail=(
                "Dropbox access was revoked. Disconnect it on your Profile "
                "page and connect again."
            ),
        )
    log.warning("Recipe source error: %s", exc)
    return HTTPException(
        status_code=502, detail="Could not reach Dropbox. Try again shortly."
    )


# ---------------------------------------------------------------------------
# Per-user routes
# ---------------------------------------------------------------------------

@router.get("/user/{user_id}/recipes", status_code=200)
async def get_user_recipes(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
):
    service = await _get_user_service(user_id)
    if service is None:
        return []
    # The Dropbox SDK is synchronous; run it off the event loop so other
    # requests aren't starved while recipes load.
    try:
        recipes = await asyncio.to_thread(service.get_recipes)
    except RecipeSourceError as exc:
        raise source_error_to_http(exc)
    await _flush_pending(user_id, service)
    return recipes


@router.get("/user/{user_id}/recipe/{recipe_id}", status_code=200)
async def get_user_recipe(
    user_id: str,
    recipe_id: str,
    response: Response,
    user: CurrentUser = Depends(require_user_id),
):
    service = await _get_user_service(user_id)
    if service is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    try:
        recipe = await asyncio.to_thread(service.get_recipe, recipe_id)
    except RecipeSourceError as exc:
        raise source_error_to_http(exc)
    await _flush_pending(user_id, service)
    if recipe is None:
        response.status_code = status.HTTP_204_NO_CONTENT
    return recipe


# ---------------------------------------------------------------------------
# Single-tenant fallback routes (env-configured, login required)
# ---------------------------------------------------------------------------

# Module-level singleton — only constructed if the relevant env vars
# are set. Useful for local-folder dev and single-user self-hosted.
_fallback_service: Optional[RecipeFileService] = None


def _get_fallback_service() -> Optional[RecipeFileService]:
    global _fallback_service
    if _fallback_service is None:
        try:
            _fallback_service = build_default_service()
        except KeyError as exc:
            # Missing env var for the chosen RECIPE_SOURCE. Fine — we
            # just won't have a fallback.
            log.warning(
                "Single-tenant recipe fallback unavailable (missing %s)",
                exc.args[0] if exc.args else "env var",
            )
            _fallback_service = None
    return _fallback_service


# Login (and so ALLOWED_USERS) is required: with RECIPE_SOURCE=dropbox
# these would otherwise expose that Dropbox folder to anyone.
@router.get("/recipes", status_code=200)
async def get_recipes_fallback(user: CurrentUser = Depends(get_current_user)):
    service = _get_fallback_service()
    if service is None:
        return []
    try:
        return await asyncio.to_thread(service.get_recipes)
    except RecipeFolderNotFound:
        # Unconfigured dev setup (no RECIPES_DIR) — not an error here.
        return []
    except RecipeSourceError as exc:
        raise source_error_to_http(exc)


@router.get("/recipe/{recipe_id}", status_code=200)
async def get_recipe_fallback(
    recipe_id: str,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    service = _get_fallback_service()
    if service is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    try:
        recipe = await asyncio.to_thread(service.get_recipe, recipe_id)
    except RecipeSourceError as exc:
        raise source_error_to_http(exc)
    if recipe is None:
        response.status_code = status.HTTP_204_NO_CONTENT
    return recipe


# ---------------------------------------------------------------------------
# Mutation endpoints — read-only
# ---------------------------------------------------------------------------

_READ_ONLY_DETAIL = (
    "Recipes are read-only. Edit the markdown file in your Obsidian vault."
)


@router.post("/recipe", status_code=405)
async def add_recipe():
    raise HTTPException(status_code=405, detail=_READ_ONLY_DETAIL)


@router.put("/recipe/{recipe_id}", status_code=405)
async def update_recipe(recipe_id: str):
    raise HTTPException(status_code=405, detail=_READ_ONLY_DETAIL)


@router.delete("/recipe/{recipe_id}", status_code=405)
async def delete_recipe(recipe_id: str):
    raise HTTPException(status_code=405, detail=_READ_ONLY_DETAIL)

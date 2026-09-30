from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes import dropbox_routes, recipe_routes
from src.services import auth_service, dropbox_oauth_service


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("DROPBOX_TOKEN_ENC_KEY", "test-signing-key")
    monkeypatch.setenv("DROPBOX_APP_KEY", "app-key")
    monkeypatch.setenv("BACKEND_PUBLIC_URL", "https://example.test/api")
    monkeypatch.setenv("FRONTEND_PUBLIC_URL", "https://example.test")
    monkeypatch.delenv("ALLOWED_USERS", raising=False)
    # Any bearer token "is" the user named in it.
    monkeypatch.setattr(
        auth_service, "verify_token", lambda token: {"sub": token}
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dropbox_routes.router)
    app.include_router(recipe_routes.router)
    return TestClient(app, base_url="https://example.test")


@pytest.fixture
def stored(monkeypatch):
    """Stub out the token exchange + persistence; record what was stored."""
    saved = {}

    def exchange(code):
        saved["exchanged"] = code
        return dropbox_oauth_service.TokenExchangeResult("refresh", "access", 1)

    async def upsert(user_id, encrypted_refresh_token, recipes_path):
        saved["user_id"] = user_id
        saved["recipes_path"] = recipes_path

    async def reset(user_id):
        pass

    class Enc:
        def encrypt(self, value):
            return "enc:" + value

    monkeypatch.setattr(dropbox_routes, "exchange_code_for_tokens", exchange)
    monkeypatch.setattr(dropbox_routes.db, "upsert_user_dropbox_credentials", upsert)
    monkeypatch.setattr(dropbox_routes, "reset_user_recipe_cache", reset)
    monkeypatch.setattr(dropbox_routes, "get_token_encryption", lambda: Enc())
    return saved


def _start_flow(client, user="auth0|alice"):
    resp = client.get(
        f"/user/{user}/dropbox/auth-url",
        params={"recipes_path": "recipes/"},
        headers={"Authorization": f"Bearer {user}"},
    )
    assert resp.status_code == 200
    state = parse_qs(urlparse(resp.json()["url"]).query)["state"][0]
    return state


def _callback(client, state):
    return client.get(
        "/dropbox/callback",
        params={"code": "the-code", "state": state},
        follow_redirects=False,
    )


def test_state_roundtrip_and_tamper():
    state = dropbox_oauth_service.encode_state("u", "/p", "nonce")
    decoded = dropbox_oauth_service.decode_state(state)
    assert (decoded.user_id, decoded.recipes_path, decoded.nonce) == ("u", "/p", "nonce")

    body, sig = state.split(".")
    with pytest.raises(ValueError):
        dropbox_oauth_service.decode_state(body + "x." + sig)


def test_auth_url_sets_httponly_nonce_cookie(client):
    resp = client.get(
        "/user/auth0|alice/dropbox/auth-url",
        headers={"Authorization": "Bearer auth0|alice"},
    )
    cookie = resp.headers["set-cookie"]
    assert "wdwe_dropbox_oauth=" in cookie
    assert "HttpOnly" in cookie and "Secure" in cookie
    assert "samesite=lax" in cookie.lower()


def test_callback_in_same_browser_links_account(client, stored):
    state = _start_flow(client)
    resp = _callback(client, state)
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("dropbox_connected=1")
    assert stored["user_id"] == "auth0|alice"
    assert stored["recipes_path"] == "/recipes"


def test_callback_from_other_browser_is_rejected(client, stored):
    # Attacker starts the flow in their browser...
    state = _start_flow(client, user="auth0|attacker")
    # ...and the victim opens the Dropbox link in theirs (no cookie).
    victim = TestClient(client.app, base_url="https://example.test")
    resp = _callback(victim, state)
    assert resp.status_code == 302
    assert "dropbox_error=" in resp.headers["location"]
    assert stored == {}  # no code exchange, nothing stored


def test_callback_with_someone_elses_nonce_is_rejected(client, stored):
    _start_flow(client, user="auth0|victim")  # victim has their own cookie
    attacker_state = dropbox_oauth_service.encode_state(
        "auth0|attacker", "/x", "attacker-nonce"
    )
    resp = _callback(client, attacker_state)
    assert "dropbox_error=" in resp.headers["location"]
    assert stored == {}


def test_allowlist_rejects_other_accounts(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_USERS", "auth0|alice, google-oauth2|bob")
    ok = client.get(
        "/user/google-oauth2|bob/dropbox/auth-url",
        headers={"Authorization": "Bearer google-oauth2|bob"},
    )
    assert ok.status_code == 200
    denied = client.get(
        "/user/auth0|mallory/dropbox/auth-url",
        headers={"Authorization": "Bearer auth0|mallory"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == auth_service.ACCESS_DENIED_DETAIL


def test_fallback_recipe_routes_require_login(client, monkeypatch):
    monkeypatch.setattr(recipe_routes, "_get_fallback_service", lambda: None)
    assert client.get("/recipes").status_code == 401
    assert client.get("/recipe/abc").status_code == 401
    authed = {"Authorization": "Bearer auth0|alice"}
    assert client.get("/recipes", headers=authed).json() == []

    monkeypatch.setenv("ALLOWED_USERS", "auth0|alice")
    assert client.get("/recipes", headers={"Authorization": "Bearer auth0|eve"}).status_code == 403

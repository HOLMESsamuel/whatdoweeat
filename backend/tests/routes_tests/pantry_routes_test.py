import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.models.pantry import DEFAULT_PANTRY_STAPLES, PantryStaples
from src.routes import pantry_routes
from src.services.auth_service import require_user_id


class FakeDB:
    def __init__(self):
        self.docs = {}

    async def get_user_pantry_staples(self, user_id):
        if user_id not in self.docs:
            return PantryStaples()
        return PantryStaples(staples=self.docs[user_id])

    async def set_user_pantry_staples(self, user_id, staples):
        self.docs[user_id] = staples.staples


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def client(fake_db):
    app = FastAPI()
    app.include_router(pantry_routes.router)
    app.dependency_overrides[require_user_id] = lambda: None
    app.dependency_overrides[pantry_routes.get_db] = lambda: fake_db
    return TestClient(app)


def test_defaults_when_nothing_saved(client):
    resp = client.get("/user/auth0|alice/pantry-staples")
    assert resp.status_code == 200
    assert resp.json() == {"staples": DEFAULT_PANTRY_STAPLES}


def test_put_cleans_and_persists(client, fake_db):
    resp = client.put(
        "/user/auth0|alice/pantry-staples",
        json={"staples": ["  sel ", "Sel", "", "huile   d'olive", "beurre"]},
    )
    assert resp.json() == {"staples": ["sel", "huile d'olive", "beurre"]}
    assert fake_db.docs["auth0|alice"] == ["sel", "huile d'olive", "beurre"]
    assert client.get("/user/auth0|alice/pantry-staples").json()["staples"] == [
        "sel",
        "huile d'olive",
        "beurre",
    ]


def test_empty_list_is_kept_not_reset_to_defaults(client):
    client.put("/user/auth0|alice/pantry-staples", json={"staples": []})
    assert client.get("/user/auth0|alice/pantry-staples").json() == {"staples": []}


def test_routes_require_matching_user():
    app = FastAPI()
    app.include_router(pantry_routes.router)
    resp = TestClient(app).get("/user/auth0|alice/pantry-staples")
    assert resp.status_code == 401

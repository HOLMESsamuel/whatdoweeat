import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.models.meal_plan import MealPlan, MealRecipe, MealSlot
from src.routes import recipe_history_routes
from src.services.auth_service import require_user_id


class FakeDB:
    def __init__(self):
        self.plan = MealPlan(meals=[])
        self.uses = {}

    async def get_user_meal_plan(self, user_id):
        return self.plan

    async def get_user_recipe_uses(self, user_id):
        return dict(self.uses)

    async def record_user_recipe_use(self, user_id, recipe_id, day):
        self.uses[recipe_id] = max(day, self.uses.get(recipe_id, ""))


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def client(fake_db):
    app = FastAPI()
    app.include_router(recipe_history_routes.router)
    app.dependency_overrides[require_user_id] = lambda: None
    app.dependency_overrides[recipe_history_routes.get_db] = lambda: fake_db
    return TestClient(app)


def _slot(day, *ids):
    return MealSlot(day=day, label="Dinner", recipes=[MealRecipe(recipe_id=i) for i in ids])


def test_merges_plan_and_logged_uses_keeping_latest(client, fake_db):
    fake_db.plan = MealPlan(
        meals=[
            _slot("2026-09-01", "a", "b"),
            _slot("2026-10-20", "a"),  # planned in the future still counts
        ]
    )
    fake_db.uses = {"b": "2026-09-15", "c": "2026-08-01"}
    resp = client.get("/user/u/recipe-history")
    assert resp.json() == {
        "last_used": {"a": "2026-10-20", "b": "2026-09-15", "c": "2026-08-01"}
    }


def test_record_keeps_latest_day(client, fake_db):
    for day in ["2026-10-06", "2026-09-01"]:
        resp = client.post(
            "/user/u/recipe-history", json={"recipe_id": "abc123", "day": day}
        )
        assert resp.status_code == 204
    assert fake_db.uses == {"abc123": "2026-10-06"}


@pytest.mark.parametrize(
    "body",
    [
        {"recipe_id": "a.b", "day": "2026-10-06"},
        {"recipe_id": "$set", "day": "2026-10-06"},
        {"recipe_id": "abc", "day": "not-a-date"},
    ],
)
def test_rejects_unsafe_ids_and_bad_dates(client, body):
    assert client.post("/user/u/recipe-history", json=body).status_code == 422

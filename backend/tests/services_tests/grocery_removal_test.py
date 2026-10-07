import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from src.services import db_service
from src.services.db_service import DBService, REMOVED_TTL


@pytest.fixture
def db():
    service = DBService("mongodb://unused", "whatdoweeat")
    service.grocery_list_collection = AsyncMongoMockClient()["t"]["grocery_lists"]
    return service


async def _make_list(db, groceries, removed=None):
    list_id = ObjectId()
    await db.grocery_list_collection.insert_one(
        {"_id": list_id, "name": "Courses", "user_ids": ["u"],
         "groceries": groceries, **({"removed": removed} if removed is not None else {})}
    )
    return list_id


def _item(id, name):
    return {"id": id, "name": name, "quantity": "2", "description": "Ratatouille",
            "type": "vegetables", "color": "green"}


def test_delete_moves_item_to_recently_removed(db):
    async def scenario():
        list_id = await _make_list(db, [_item("a", "courgettes"), _item("b", "tomates")])
        assert await db.delete_grocery_from_list(list_id, "a") is True
        lst = await db.get_grocery_list(list_id)
        assert [g.id for g in lst.groceries] == ["b"]
        assert [r.name for r in lst.removed] == ["courgettes"]
        removed = lst.removed[0]
        assert removed.removed_at.tzinfo is not None
        assert removed.quantity == "2" and removed.description == "Ratatouille"
        # An explicit UTC offset, so browsers don't read it as local time.
        assert lst.model_dump(mode="json")["removed"][0]["removed_at"].endswith("Z")
    asyncio.run(scenario())


def test_restore_puts_item_back_once(db):
    async def scenario():
        list_id = await _make_list(db, [_item("a", "courgettes")])
        await db.delete_grocery_from_list(list_id, "a")
        assert await db.restore_grocery_in_list(list_id, "a") is True
        assert await db.restore_grocery_in_list(list_id, "a") is False  # double tap
        lst = await db.get_grocery_list(list_id)
        assert [(g.id, g.name, g.color) for g in lst.groceries] == [("a", "courgettes", "green")]
        assert lst.removed == []
        raw = await db.grocery_list_collection.find_one({"_id": list_id})
        assert "removed_at" not in raw["groceries"][0]
    asyncio.run(scenario())


def test_unknown_ids_are_noops(db):
    async def scenario():
        list_id = await _make_list(db, [_item("a", "courgettes")])
        assert await db.delete_grocery_from_list(list_id, "nope") is False
        assert await db.restore_grocery_in_list(list_id, "a") is False  # not removed
        assert await db.delete_grocery_from_list(ObjectId(), "a") is False
    asyncio.run(scenario())


def test_old_removals_are_hidden_then_pruned(db):
    async def scenario():
        old = datetime.now(timezone.utc) - REMOVED_TTL - timedelta(minutes=1)
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        list_id = await _make_list(
            db,
            [_item("c", "oignon")],
            removed=[{**_item("a", "old"), "removed_at": old},
                     {**_item("b", "recent"), "removed_at": recent}],
        )
        lst = await db.get_grocery_list(list_id)
        assert [r.name for r in lst.removed] == ["recent"]
        await db.delete_grocery_from_list(list_id, "c")
        raw = await db.grocery_list_collection.find_one({"_id": list_id})
        assert [r["name"] for r in raw["removed"]] == ["recent", "oignon"]
    asyncio.run(scenario())


def test_removed_list_is_capped(db, monkeypatch):
    monkeypatch.setattr(db_service, "REMOVED_MAX", 3)
    async def scenario():
        list_id = await _make_list(db, [_item(str(i), f"item{i}") for i in range(5)])
        for i in range(5):
            await db.delete_grocery_from_list(list_id, str(i))
        lst = await db.get_grocery_list(list_id)
        assert [r.name for r in lst.removed] == ["item2", "item3", "item4"]
    asyncio.run(scenario())


def test_lists_without_removed_field_still_load(db):
    async def scenario():
        list_id = await _make_list(db, [_item("a", "courgettes")], removed=None)
        lst = await db.get_grocery_list(list_id)
        assert lst.removed == [] and len(lst.groceries) == 1
    asyncio.run(scenario())

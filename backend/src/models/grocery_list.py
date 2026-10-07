from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
from .grocery import Grocery
from.pydantic_object_id import PydanticObjectId
from typing import List
from bson import ObjectId


class RemovedGrocery(Grocery):
    removed_at: datetime

    # Mongo hands back naive datetimes; they're UTC. Without a tzinfo the
    # JSON has no offset and browsers read it as local time.
    @field_validator("removed_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class GroceryList(BaseModel):
    id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id")
    user_ids: List[str] = Field(default_factory=list)
    name: str
    groceries: List[Grocery] = []
    # Items removed in the last REMOVED_TTL, newest last, so an accidental
    # tap can be undone. See DBService.delete_grocery_from_list.
    removed: List[RemovedGrocery] = []

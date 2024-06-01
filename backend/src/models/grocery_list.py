from pydantic import BaseModel, Field
from .grocery import Grocery
from.pydantic_object_id import PydanticObjectId
from typing import List
from bson import ObjectId

class GroceryList(BaseModel):
    id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id")
    user_ids: List[str] = Field(default_factory=list)
    name: str
    groceries: List[Grocery] = []
from pydantic import BaseModel, Field
from bson import ObjectId
from .pydantic_object_id import PydanticObjectId

class User(BaseModel):
    id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id")
    hashed_email: str
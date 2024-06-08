import os
from fastapi import APIRouter, Depends
from ..services.db_service import DBService
from ..models.grocery_list import GroceryList
from ..models.pydantic_object_id import PydanticObjectId
from pydantic import BaseModel

router = APIRouter()
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
db = DBService(mongo_uri, "whatdoweeat")

def get_db():
    return db

class CreateGroceryListRequest(BaseModel):
    name: str

class CreateUserRequest(BaseModel):
    hashed_email: str

@router.post("/user/{user_id}/grocery-list")
async def create_grocery_list(grocery_list: CreateGroceryListRequest, user_id: str, db: DBService = Depends(get_db)):
    new_grocery_list = GroceryList(name=grocery_list.name, user_ids=[user_id])
    await db.add_grocery_list(new_grocery_list)
    return {"message": "Grocery list added", "grocery_list_id": str(new_grocery_list.id)}

@router.get("/user/{user_id}/grocery-list")
async def get_user(user_id: str, db: DBService = Depends(get_db)):
    user = await db.get_user_grocery_lists(user_id)
    return user
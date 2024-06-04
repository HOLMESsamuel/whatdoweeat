from fastapi import APIRouter, Depends, Response, status
from ..services.db_service import DBService
from ..services.ws_service import ConnectionManager
from ..models.grocery_list import GroceryList
from ..models.grocery import Grocery
from ..models.pydantic_object_id import PydanticObjectId
from pydantic import BaseModel

router = APIRouter()
manager = ConnectionManager()
db = DBService("mongodb://localhost:27017", "whatdoweeat")

def get_db():
    return db

class AddGroceryRequest(BaseModel):
    grocery: Grocery

@router.patch("/grocery-list/{list_id}/user/{user_id}")
async def add_user_to_grocery_list(list_id: PydanticObjectId, user_id: str, db: DBService = Depends(get_db)):
    await db.add_user_to_grocery_list(list_id, user_id)
    return {"message": "user added to grocery list"}

@router.get("/grocery-list/{list_id}", status_code=200)
async def get_grocery_list(list_id: PydanticObjectId, response: Response, db: DBService = Depends(get_db)):
    grocery_list = await db.get_grocery_list(list_id)
    if grocery_list is None:
        response.status_code = status.HTTP_204_NO_CONTENT
    return grocery_list

@router.delete("/grocery-list/{list_id}")
async def delete_grocery_list(list_id: PydanticObjectId, db: DBService = Depends(get_db)):
    grocery_list = await db.delete_grocery_list(list_id)
    return grocery_list

@router.post("/grocery-list/{list_id}/grocery")
async def add_grocery(request: AddGroceryRequest, list_id: PydanticObjectId, db: DBService = Depends(get_db)):
    await db.add_grocery_to_list(list_id, request.grocery)
    await manager.broadcast(f"Grocery item added: {request.grocery.name}", str(list_id))
    return {"message": "Grocery item added"}

@router.delete("/grocery-list/{list_id}/grocery/{name}")
async def delete_grocery(list_id: PydanticObjectId, name: str, db: DBService = Depends(get_db)):
    await db.delete_grocery_from_list(list_id, name)
    await manager.broadcast(f"Grocery item deleted: {name}", str(list_id))
    return {"message": "Grocery item deleted"}

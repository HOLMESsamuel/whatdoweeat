import os
from fastapi import APIRouter, Depends, Response, status
from ..services.db_service import DBService
from ..services.ws_service import ConnectionManager
from ..models.pydantic_object_id import PydanticObjectId
from ..models.recipe import Recipe

router = APIRouter()
manager = ConnectionManager()
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
db = DBService(mongo_uri, "whatdoweeat")

def get_db():
    return db

@router.get("/recipe/{recipe_id}", status_code=200)
async def get_recipe(recipe_id: PydanticObjectId, response: Response, db: DBService = Depends(get_db)):
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        response.status_code = status.HTTP_204_NO_CONTENT
    return recipe

@router.delete("/recipe/{recipe_id}")
async def delete_recipe(recipe_id: PydanticObjectId, db: DBService = Depends(get_db)):
    recipe = await db.delete_recipe(recipe_id)
    return recipe

@router.post("/recipe")
async def add_recipe(request: Recipe, db: DBService = Depends(get_db)):
    await db.add_recipe(request)
    return {"message": "Recipe added"}

from motor.motor_asyncio import AsyncIOMotorClient
from typing import List
from src.models.grocery import Grocery
from src.models.user import User
from src.models.grocery_list import GroceryList
from src.models.recipe import Recipe
import logging
from src.models.pydantic_object_id import PydanticObjectId
from bson import ObjectId

class DBService:
    def __init__(self, uri: str, dbname: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[dbname]
        self.users_collection = self.db["users"]
        self.grocery_list_collection = self.db["grocery_lists"]
        self.recipe_collection = self.db["recipes"]

    async def get_user_grocery_lists(self, user_id: str) -> User:
        grocery_lists = await self.grocery_list_collection.find({"user_ids": user_id}).to_list(1000)
        return [GroceryList(**doc) for doc in grocery_lists]
    
    async def get_grocery_list(self, list_id: PydanticObjectId) -> GroceryList:
        logging.info(f"Querying for grocery list with _id: {list_id}")
        grocery_list = await self.grocery_list_collection.find_one({"_id": list_id})
        
        if grocery_list:
            logging.info(f"Grocery list found: {grocery_list}")
            return GroceryList(**grocery_list)
        
        logging.warning(f"No grocery list found with _id: {list_id}")
        return None
    
    async def get_recipe(self, recipe_id: PydanticObjectId) -> GroceryList:
        logging.info(f"Querying for recipe with _id: {recipe_id}")
        recipe = await self.recipe_collection.find_one({"_id": recipe_id})
        
        if recipe:
            logging.info(f"Grocery list found: {recipe}")
            return Recipe(**recipe)
        
        logging.warning(f"No recipe found with _id: {recipe_id}")
        return None

    async def add_grocery_list(self, grocery_list: GroceryList):
        grocery_list_dict = grocery_list.dict(by_alias=True)
        if '_id' in grocery_list_dict and isinstance(grocery_list_dict['_id'], str):
            grocery_list_dict['_id'] = ObjectId(grocery_list_dict['_id'])
        await self.grocery_list_collection.insert_one(grocery_list_dict)

    async def add_recipe(self, recipe: Recipe):
        recipe_dict = recipe.dict(by_alias=True)
        if '_id' in recipe_dict and isinstance(recipe_dict['_id'], str):
            recipe_dict['_id'] = ObjectId(recipe_dict['_id'])
        await self.recipe_collection.insert_one(recipe_dict)

    async def add_user_to_grocery_list(self, list_id: PydanticObjectId, user_id: str):
        await self.grocery_list_collection.find_one_and_update(
            {"_id": list_id},
            {"$addToSet": {"user_ids": user_id}}
        )

    async def delete_grocery_list(self, list_id: PydanticObjectId):
        await self.grocery_list_collection.delete_one({"_id": list_id})

    async def delete_recipe(self, recipe_id: PydanticObjectId):
        await self.recipe_collection.delete_one({"_id": recipe_id})

    async def add_grocery_to_list(self, list_id: PydanticObjectId, grocery: Grocery):
        grocery.clean_name()
        print(grocery)
        grocery_dict = grocery.dict()
        print(grocery_dict)
        await self.grocery_list_collection.update_one(
            {"_id": list_id},
            {"$push": {"groceries": grocery_dict}}
        )

    async def delete_grocery_from_list(self, list_id: PydanticObjectId, grocery_name: str):
        await self.grocery_list_collection.update_one(
            {"_id": list_id},
            {"$pull": {"groceries": {"name": grocery_name}}}
        )


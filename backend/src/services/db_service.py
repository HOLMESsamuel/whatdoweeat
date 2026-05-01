from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Optional
from src.models.grocery import Grocery
from src.models.user import User
from src.models.grocery_list import GroceryList
from src.models.dropbox_credential import DropboxCredential
import logging
from src.models.pydantic_object_id import PydanticObjectId
from bson import ObjectId
from src.services.item_sort_service import ItemSortService

class DBService:
    def __init__(self, uri: str, dbname: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[dbname]
        self.users_collection = self.db["users"]
        self.grocery_list_collection = self.db["grocery_lists"]
        self.dropbox_credentials_collection = self.db["dropbox_credentials"]
        # Recipes are no longer stored in Mongo — they're parsed from
        # markdown files by RecipeFileService.
        self.item_sorter = ItemSortService()

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
    
    async def add_grocery_list(self, grocery_list: GroceryList):
        grocery_list_dict = grocery_list.dict(by_alias=True)
        if '_id' in grocery_list_dict and isinstance(grocery_list_dict['_id'], str):
            grocery_list_dict['_id'] = ObjectId(grocery_list_dict['_id'])
        await self.grocery_list_collection.insert_one(grocery_list_dict)

    async def add_user_to_grocery_list(self, list_id: PydanticObjectId, user_id: str):
        await self.grocery_list_collection.find_one_and_update(
            {"_id": list_id},
            {"$addToSet": {"user_ids": user_id}}
        )

    async def delete_grocery_list(self, list_id: PydanticObjectId):
        await self.grocery_list_collection.delete_one({"_id": list_id})

    async def add_grocery_to_list(self, list_id: PydanticObjectId, grocery: Grocery):
        grocery.clean_name()
        grocery.generate_uuid()
        
        # If type is 'other', try to classify it
        # if grocery.type == 'other':
        #     grocery.type = self.item_sorter.classify_grocery_item(grocery.name)
            
        grocery_dict = grocery.dict()
        await self.grocery_list_collection.update_one(
            {"_id": list_id},
            {"$push": {"groceries": grocery_dict}}
        )

    async def delete_grocery_from_list(self, list_id: PydanticObjectId, grocery_id: str):
        await self.grocery_list_collection.update_one(
            {"_id": list_id},
            {"$pull": {"groceries": {"id": grocery_id}}}
        )

    async def update_grocery_in_list(self, list_id: PydanticObjectId, grocery_id: str, grocery: Grocery):
        await self.grocery_list_collection.update_one(
            {"_id": list_id, "groceries.id": grocery_id},
            {"$set": {
                "groceries.$.name": grocery.name,
                "groceries.$.quantity": grocery.quantity,
                "groceries.$.description": grocery.description,
                "groceries.$.type": grocery.type,
                "groceries.$.color": grocery.color
            }}
        )

    # -- Dropbox per-user credentials -----------------------------------

    async def get_user_dropbox_credentials(
        self, user_id: str
    ) -> Optional[DropboxCredential]:
        doc = await self.dropbox_credentials_collection.find_one(
            {"user_id": user_id}
        )
        if doc is None:
            return None
        # Strip Mongo's _id; the model doesn't carry it.
        doc.pop("_id", None)
        return DropboxCredential(**doc)

    async def upsert_user_dropbox_credentials(
        self,
        user_id: str,
        encrypted_refresh_token: str,
        recipes_path: str,
    ) -> None:
        now = datetime.utcnow()
        await self.dropbox_credentials_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "encrypted_refresh_token": encrypted_refresh_token,
                    "recipes_path": recipes_path,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def update_user_dropbox_recipes_path(
        self, user_id: str, recipes_path: str
    ) -> bool:
        result = await self.dropbox_credentials_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "recipes_path": recipes_path,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.matched_count > 0

    async def delete_user_dropbox_credentials(self, user_id: str) -> bool:
        result = await self.dropbox_credentials_collection.delete_one(
            {"user_id": user_id}
        )
        return result.deleted_count > 0


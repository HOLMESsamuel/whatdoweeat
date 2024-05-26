# src/db.py
from motor.motor_asyncio import AsyncIOMotorClient
from src.models.grocery import Grocery

class DBService:
    def __init__(self, uri: str, dbname: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[dbname]
        self.collection = self.db["groceries"]

    async def get_all_groceries(self):
        groceries = []
        async for doc in self.collection.find():
            groceries.append(Grocery(**doc))
        return groceries

    async def add_grocery(self, grocery: Grocery):
        await self.collection.insert_one(grocery.dict())

    async def delete_grocery(self, name: str):
        await self.collection.delete_one({"name": name})

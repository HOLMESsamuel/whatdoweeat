import os
from fastapi import APIRouter, Depends
from ..services.db_service import DBService
from ..services.auth_service import CurrentUser, require_user_id
from ..models.pantry import PantryStaples

router = APIRouter()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = DBService(mongo_uri, "whatdoweeat")


def get_db():
    return db


@router.get("/user/{user_id}/pantry-staples", response_model=PantryStaples)
async def get_pantry_staples(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    return await db.get_user_pantry_staples(user_id)


@router.put("/user/{user_id}/pantry-staples", response_model=PantryStaples)
async def put_pantry_staples(
    staples: PantryStaples,
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    await db.set_user_pantry_staples(user_id, staples)
    return staples

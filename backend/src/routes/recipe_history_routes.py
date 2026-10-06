import os
from fastapi import APIRouter, Depends
from ..services.db_service import DBService
from ..services.auth_service import CurrentUser, require_user_id
from ..models.recipe_history import RecipeHistory, RecipeUse, merge_last_used

router = APIRouter()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = DBService(mongo_uri, "whatdoweeat")


def get_db():
    return db


@router.get("/user/{user_id}/recipe-history", response_model=RecipeHistory)
async def get_recipe_history(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    plan = await db.get_user_meal_plan(user_id)
    logged = await db.get_user_recipe_uses(user_id)
    return RecipeHistory(last_used=merge_last_used(plan, logged))


@router.post("/user/{user_id}/recipe-history", status_code=204)
async def record_recipe_use(
    use: RecipeUse,
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    await db.record_user_recipe_use(user_id, use.recipe_id, use.day.isoformat())

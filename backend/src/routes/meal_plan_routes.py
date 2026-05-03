import os
from fastapi import APIRouter, Depends
from ..services.db_service import DBService
from ..services.auth_service import CurrentUser, require_user_id
from ..models.meal_plan import MealPlan

router = APIRouter()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db = DBService(mongo_uri, "whatdoweeat")


def get_db():
    return db


@router.get("/user/{user_id}/meal-plan")
async def get_meal_plan(
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    return await db.get_user_meal_plan(user_id)


@router.put("/user/{user_id}/meal-plan")
async def put_meal_plan(
    plan: MealPlan,
    user_id: str,
    user: CurrentUser = Depends(require_user_id),
    db: DBService = Depends(get_db),
):
    plan.user_id = user_id
    await db.upsert_user_meal_plan(user_id, plan)
    return {"message": "Meal plan saved"}

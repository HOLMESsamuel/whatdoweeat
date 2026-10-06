from datetime import date
from typing import Dict

from pydantic import BaseModel, Field

from .meal_plan import MealPlan


class RecipeUse(BaseModel):
    # Recipe ids are filename hashes; the pattern also keeps them safe to
    # use as Mongo field names (no `.` or `$`).
    recipe_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    day: date


class RecipeHistory(BaseModel):
    # recipe_id -> most recent day (YYYY-MM-DD) it was planned or sent to
    # the grocery list. Future days count: planned means "eaten soon".
    last_used: Dict[str, str] = Field(default_factory=dict)


def merge_last_used(plan: MealPlan, logged: Dict[str, str]) -> Dict[str, str]:
    out = dict(logged)
    for slot in plan.meals:
        for r in slot.recipes:
            if slot.day > out.get(r.recipe_id, ""):
                out[r.recipe_id] = slot.day
    return out

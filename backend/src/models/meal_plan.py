from pydantic import BaseModel, Field
from typing import List


class MealRecipe(BaseModel):
    recipe_id: str
    recipe_name: str = ""


class MealSlot(BaseModel):
    day: str  # ISO date YYYY-MM-DD
    label: str  # free-form, e.g. "Lunch", "Dinner", "Cake"
    recipes: List[MealRecipe] = Field(default_factory=list)


class MealPlan(BaseModel):
    user_id: str = ""
    meals: List[MealSlot] = Field(default_factory=list)

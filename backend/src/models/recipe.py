from pydantic import BaseModel, Field
from .grocery import Grocery
from typing import List, Optional


class Recipe(BaseModel):
    """A recipe parsed from a markdown file in the user's Obsidian vault.

    The id is a stable hash derived from the filename, computed by
    RecipeFileService. Recipes are read-only from the API's point of view —
    the source of truth is the .md file on disk.
    """

    id: str
    name: str
    tags: List[str] = Field(default_factory=list)
    groceries: List[Grocery] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    servings: int = 0
    time: str = ""
    # Optional metadata pulled from the markdown frontmatter; useful for
    # display but not required for the meal-plan / grocery flow.
    preparation: Optional[str] = None
    cuisson: Optional[str] = None
    link: Optional[str] = None
    remarque: Optional[str] = None
    source_path: Optional[str] = None

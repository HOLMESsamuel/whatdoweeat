from typing import List

from pydantic import BaseModel, Field, field_validator

# Ingredients most kitchens always have; never pushed to the grocery list
# unless the user removes them from their staples.
DEFAULT_PANTRY_STAPLES = ["sel", "poivre", "huile d'olive"]

_MAX_STAPLES = 200
_MAX_STAPLE_LENGTH = 80


class PantryStaples(BaseModel):
    staples: List[str] = Field(
        default_factory=lambda: list(DEFAULT_PANTRY_STAPLES)
    )

    @field_validator("staples")
    @classmethod
    def _clean(cls, value: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for raw in value:
            item = " ".join(str(raw).split())[:_MAX_STAPLE_LENGTH]
            key = item.casefold()
            if not item or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out[:_MAX_STAPLES]

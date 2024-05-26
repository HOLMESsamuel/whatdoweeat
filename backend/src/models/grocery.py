from pydantic import BaseModel

class Grocery(BaseModel):
    name : str = ""
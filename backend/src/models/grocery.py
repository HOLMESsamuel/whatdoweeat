from pydantic import BaseModel
import uuid

class Grocery(BaseModel):
    id : str = ""
    name : str = ""
    quantity : str = ""
    description : str = ""
    type : str = ""  # e.g., "vegetables", "carbs", "meat", etc.
    color : str = ""  # e.g., "red", "blue", "green", etc. for store sorting

    def clean_name(self):
        self.name = self.name.strip()
        self.name = self.name.replace("{","")
        self.name = self.name.replace("}","")

    def generate_uuid(self):
        self.id = str(uuid.uuid4())
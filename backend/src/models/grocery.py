from pydantic import BaseModel

class Grocery(BaseModel):
    name : str = ""
    quantity : str = ""
    description : str = ""

    def clean_name(self):
        self.name = self.name.strip()
        self.name = self.name.replace("{","")
        self.name = self.name.replace("}","")
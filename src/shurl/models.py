from pydantic import BaseModel

class GetOriginalURLResponse(BaseModel):
    original_url: str
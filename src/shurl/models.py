from pydantic import BaseModel, Field
from datetime import datetime

class GetOriginalURLResponse(BaseModel):
    original_url: str

class ShortenedItem(BaseModel):
    short_url: str
    original_url: str
    expires_at: datetime | None = Field(None)
    created_at: datetime = Field(default_factory=datetime.now)
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import UUID

class GetOriginalURLResponse(BaseModel):
    original_url: str

class ShortenedItem(BaseModel):
    short_url: str
    original_url: str
    created_by_uuid: UUID | None = Field(None)
    expires_at: datetime | None = Field(None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
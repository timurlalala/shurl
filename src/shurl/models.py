from sqlalchemy import Column, Integer, DateTime, MetaData, String, UUID
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Link(Base):
    __tablename__ = 'links'
    id = Column(Integer, primary_key=True)
    original_url = Column(String, nullable=False, index=True)
    short_url = Column(String, nullable=False, unique=True, index=True)
    created_by_uuid = Column(UUID, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=sqlalchemy.func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sqlalchemy.func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    clicks = Column(Integer, default=0, nullable=False)

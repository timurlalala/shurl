from sqlalchemy import Table, Column, Integer, DateTime, MetaData, String
import sqlalchemy

metadata = MetaData()

links = Table(
    "links",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("original_url", String, nullable=False, index=True),
    Column("short_url", String, nullable=False, unique=True, index=True),
    Column("created_at", DateTime, server_default=sqlalchemy.func.now(), nullable=False),
    Column("expires_at", DateTime, nullable=True, index=True),
    Column("clicks", Integer, default=0, nullable=False)
)
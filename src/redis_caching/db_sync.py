from database import get_async_session
from sqlalchemy import update
from shurl.models import Link
from logging import getLogger
from typing import Dict, Any

logger = getLogger('redis_caching')

async def write_stats_to_db(short_code: str, stats: Dict[str, Any]):
    async for session in get_async_session():
        try:
            statement = update(Link).where(Link.short_url == short_code).values(**stats) # type: ignore
            await session.execute(statement)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
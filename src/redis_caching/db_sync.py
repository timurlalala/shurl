from database import get_async_session
from sqlalchemy import update
from shurl.schemas import Link
from logging import getLogger

logger = getLogger('redis_caching')

async def write_clicks_to_db(short_code: str, clicks: int):
    async for session in get_async_session():
        try:
            statement = update(Link).where(Link.short_url == short_code).values(clicks=clicks) # type: ignore
            await session.execute(statement)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
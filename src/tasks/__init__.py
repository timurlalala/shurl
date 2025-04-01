import asyncio
from celery import Celery
from sqlalchemy import delete
from datetime import datetime, timedelta, timezone
from shurl.models import Link
from database import get_async_session
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from celery.schedules import crontab

app = Celery("tasks", broker=f"redis://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0")

async def adelete_expired_links():
    async for session in get_async_session():
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            statement = delete(Link.__table__).where(Link.__table__.c.expires_at < one_hour_ago)
            await session.execute(statement)
            await session.commit()
            print(f"Удалены устаревшие ссылки до {one_hour_ago}")
        except Exception as e:
            print(f"Ошибка при удалении устаревших ссылок: {e}")
            await session.rollback()
        finally:
            await session.close()

@app.task
def delete_expired_links():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(adelete_expired_links())

app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {
    "delete-expired-links-every-10-minutes": {
        "task": "tasks.delete_expired_links",
        "schedule": crontab(minute="*/10"),  # Каждые 10 минут
    },
}

app.conf.update(imports=['tasks'])
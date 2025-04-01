import redis.asyncio as redis
import json
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from logging import getLogger
from redis_caching.db_sync import write_clicks_to_db

logger = getLogger('redis_caching')

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

async def process_expired_keys():
    pubsub = r.pubsub()
    await pubsub.psubscribe("__keyevent@0__:expired")  # Подписываемся на события истечения срока жизни ключей

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            key = message["data"]

            logger.debug(key)

            if key.startswith("short_url:"):
                # logger.debug('got to point 1')
                # logger.debug(type(key))
                _, short_code = key.split(sep=':')
                clicks_key = f"clicks:{short_code}"
                try:
                    # Получаем данные из Redis
                    clicks = int(await r.get(clicks_key))

                    # Записываем данные в базу данных
                    await write_clicks_to_db(short_code, clicks)

                    logger.debug(f"Записаны клики для {short_code}: {clicks}")
                except Exception as e:
                    logger.warning(f"Ошибка при обработке ключа {key}: {e}")
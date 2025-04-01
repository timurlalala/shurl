import redis.asyncio as redis
import json
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from logging import getLogger
from redis_caching.db_sync import write_stats_to_db
from datetime import datetime

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
                stats_key = f"stats:{short_code}"
                try:
                    # Получаем данные из Redis
                    stats = json.loads(await r.get(stats_key))
                    stats['last_used'] = datetime.fromisoformat(stats['last_used'])

                    # Записываем данные в базу данных
                    await write_stats_to_db(short_code, stats)

                    logger.debug(f"Записаны статистики для {short_code}: {stats}")
                except Exception as e:
                    logger.warning(f"Ошибка при обработке ключа {key}: {e}")
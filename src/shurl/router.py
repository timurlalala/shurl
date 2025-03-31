from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select, delete, update, or_, and_
from sqlalchemy.exc import IntegrityError, NoResultFound

from typing_extensions import Annotated
from datetime import datetime, timezone
from logging import getLogger
import json

from database import get_async_session
from shurl.utils import generate_random_string, validate_and_fix_url
from shurl.schemas import Link
from shurl.models import ShortenedItem

from redis_caching import r, write_clicks_to_db


logger = getLogger('shurl_router')

router = APIRouter(
    prefix="/links",
    tags=["Links"],
)

@router.post("/shorten", status_code=status.HTTP_201_CREATED)
async def shorten_link(original_url: Annotated[str, Query()],
                       session: Annotated[AsyncSession, Depends(get_async_session)],
                       custom_alias: Annotated[str | None, Query()] = None,
                       expires_at: Annotated[datetime | None, Query()] = None):
    """Создает короткую ссылку."""
    try:

        original_url = validate_and_fix_url(original_url)

        if custom_alias is not None:
            short_code = custom_alias
        else:
            short_code = generate_random_string()

        while True:
            shurl = ShortenedItem(short_url=short_code, original_url=original_url, expires_at=expires_at)
            statement = insert(Link).values(**shurl.model_dump())
            try:
                await session.execute(statement)
                await session.commit()
                break
            except IntegrityError:
                await session.rollback()
                logger.debug("Collision occurred, retrying with new short code.")

                if custom_alias is None:
                    short_code = generate_random_string()
                else:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Custom alias already exists")

        return {"short_url": short_code}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.warning(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/search")
async def search_by_original_url(original_url: Annotated[str, Query()],
                                 session: Annotated[AsyncSession, Depends(get_async_session)]):
    try:
        original_url = validate_and_fix_url(original_url)

        query = select(Link.__table__).where(
            and_(Link.__table__.c.original_url == original_url),
            or_(Link.__table__.c.expires_at.is_(None), Link.__table__.c.expires_at > datetime.now(timezone.utc))
        ) # type: ignore

        logger.debug(query)

        result = await session.execute(query)
        await session.commit()
        links = result.all()
        return [{
            "short_url": l.short_url,
            "created_at": l.created_at,
            "expires_at": l.expires_at
        } for l in links]
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original URL not found")
    except Exception as e:
        logger.warning(e.args)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{short_code}")
async def redirect_to_original(short_code: Annotated[str, Path(max_length=16)],
                               session: Annotated[AsyncSession, Depends(get_async_session)]):
    """Перенаправляет на оригинальный URL."""
    try:
        cache_key = f"short_url:{short_code}"
        clicks_key = f"clicks:{short_code}"
        cached_data = await r.get(cache_key)

        if cached_data:
            link_data = json.loads(cached_data)
            clicks = int(await r.get(clicks_key))

            if link_data["expires_at"] and datetime.fromisoformat(link_data["expires_at"]) < datetime.now(timezone.utc):
                logger.debug('cached link is expired')
                await r.delete(cache_key)

                await write_clicks_to_db(short_code, clicks)
                await r.delete(clicks_key)
            else:
                logger.debug('using cached')
                await r.set(clicks_key, clicks+1)
                return RedirectResponse(url=link_data["original_url"], status_code=302)

        # Если кэш пустой
        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        link = result.one()

        if link.expires_at is not None and link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link has expired")

        # Сохраняем данные в кэш
        link_data = {
            "original_url": link.original_url,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None
        }

        await r.set(cache_key, json.dumps(link_data), ex=5)  # Кэшируем на 60 секунд
        await r.set(clicks_key, link.clicks + 1)

        return RedirectResponse(url=link.original_url, status_code=302)
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short code not found")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.warning(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{short_code}")
async def delete_link(short_code: Annotated[str, Path(max_length=16)],
                      session: Annotated[AsyncSession, Depends(get_async_session)]):
    """Удаляет связь."""
    try:
        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        result.one()
        delete_query = delete(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        await session.execute(delete_query)
        await session.commit()
        return {"message": "Link deleted successfully"}
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short code not found")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.warning(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{short_code}")
async def update_link(short_code: Annotated[str, Path(max_length=16)],
                      original_url: Annotated[str, Query()],
                      session: Annotated[AsyncSession, Depends(get_async_session)]):
    """Обновляет длинный адрес, на который ведет ссылка"""
    try:
        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        result.one()

        original_url = validate_and_fix_url(original_url)

        update_query = (
            update(Link.__table__)
            .where(Link.__table__.c.short_url == short_code)  # type: ignore
            .values(original_url=original_url)
        )
        await session.execute(update_query)
        await session.commit()
        return {"message": "Link updated successfully"}

    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short code not found")
    except Exception as e:
        logger.warning(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# GET /links/{short_code}/stats - Статистика по ссылке
@router.get("/{short_code}/stats")
async def get_link_stats(short_code: str):
    pass


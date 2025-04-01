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
from shurl.models import Link
from shurl.schemas import ShortenedItem

from redis_caching import r, write_stats_to_db
from auth.auth import User, current_active_user, current_user


logger = getLogger('shurl_router')

router = APIRouter(
    prefix="/links",
    tags=["Links"],
)

@router.post("/shorten", status_code=status.HTTP_201_CREATED)
async def shorten_link(original_url: Annotated[str, Query()],
                       session: Annotated[AsyncSession, Depends(get_async_session)],
                       user: Annotated[User, Depends(current_user)],
                       custom_alias: Annotated[str | None, Query()] = None,
                       expires_at: Annotated[datetime | None, Query()] = None):
    """Создает короткую ссылку."""
    try:

        if user is not None:
            user_id = user.id
        else:
            user_id = None

        original_url = validate_and_fix_url(original_url)

        if custom_alias is not None:
            short_code = custom_alias
        else:
            short_code = generate_random_string()

        while True:
            shurl = ShortenedItem(short_url=short_code, original_url=original_url, expires_at=expires_at, created_by_uuid=user_id)
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
            and_(Link.__table__.c.original_url == original_url,
            or_(Link.__table__.c.expires_at.is_(None), Link.__table__.c.expires_at > datetime.now(timezone.utc)))
        ) # type: ignore

        logger.debug(query)

        result = await session.execute(query)
        await session.commit()
        links = result.all()
        return [{
            "short_url": l.short_url,
            "created_at": l.created_at,
            "updated_at": l.updated_at,
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
        stats_key = f"stats:{short_code}"
        cached_data = await r.get(cache_key)

        if cached_data:
            link_data = json.loads(cached_data)
            stats = json.loads(await r.get(stats_key))

            if link_data["expires_at"] and datetime.fromisoformat(link_data["expires_at"]) < datetime.now(timezone.utc):
                logger.debug('cached link is expired')
                await r.delete(cache_key)

                stats['last_used'] = datetime.fromisoformat(stats['last_used'])

                await write_stats_to_db(short_code, stats)
                await r.delete(stats_key)
            else:
                logger.debug('using cached')

                stats['last_used'] = datetime.now(timezone.utc).isoformat()
                stats['clicks'] = int(stats['clicks']) + 1

                await r.set(stats_key, json.dumps(stats))
                return RedirectResponse(url=link_data["original_url"], status_code=302)

        # Если кэш пустой или ссылка просрочена, проверим бд (вдруг ссылку обновили?)
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
        await r.set(cache_key, json.dumps(link_data), ex=60)  # Кэшируем на 60 секунд

        stats = {
            "clicks": link.clicks + 1,
            "last_used": datetime.now(timezone.utc).isoformat()
        }
        await r.set(stats_key, json.dumps(stats))

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
                      session: Annotated[AsyncSession, Depends(get_async_session)],
                      user: Annotated[User, Depends(current_active_user)]):
    """Удаляет связь."""
    try:
        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        link = result.one()

        if (link.created_by_uuid is not None) and (link.created_by_uuid != user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an owner of this link")

        # удаляем кэш, если есть
        cache_key = f"short_url:{short_code}"
        stats_key = f"stats:{short_code}"
        await r.delete(cache_key)
        await r.delete(stats_key)

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
                      session: Annotated[AsyncSession, Depends(get_async_session)],
                      user: Annotated[User, Depends(current_active_user)]):
    """Обновляет длинный адрес, на который ведет ссылка"""
    try:
        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        link = result.one()

        if (link.created_by_uuid is not None) and (link.created_by_uuid != user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an owner of this link")

        original_url = validate_and_fix_url(original_url)

        # удаляем кэш, если есть
        cache_key = f"short_url:{short_code}"
        stats_key = f"stats:{short_code}"
        await r.delete(cache_key)
        await r.delete(stats_key)

        update_query = (
            update(Link.__table__)
            .where(Link.__table__.c.short_url == short_code)  # type: ignore
            .values(original_url=original_url, clicks=0, last_used=None, updated_at=datetime.now(timezone.utc))
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
async def get_link_stats(short_code: Annotated[str, Path(max_length=16)],
                         session: Annotated[AsyncSession, Depends(get_async_session)]):
    try:

        query = select(Link.__table__).where(Link.__table__.c.short_url == short_code) # type: ignore
        result = await session.execute(query)
        await session.commit()
        link = result.one()

        # Ищем клики в кэше
        stats_key = f"stats:{short_code}"

        stats = await r.get(stats_key)

        if stats is None:
            clicks = link.clicks
            last_used = link.last_used
        else:
            stats = json.loads(stats)
            clicks = int(stats['clicks'])
            last_used = datetime.fromisoformat(stats['last_used'])

        return {
            "short_code": link.short_url,
            "original_url": link.original_url,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
            "expires_at": link.expires_at,
            "clicks": clicks,
            "last_used": last_used
        }
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short code not found")
    except Exception as e:
        logger.warning(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


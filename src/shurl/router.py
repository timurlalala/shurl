from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from typing_extensions import Annotated
from datetime import datetime
from shurl.models import ShortenedItem
from database import get_async_session
from shurl.utils import generate_random_string
from shurl.schemas import Link
from logging import getLogger

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# GET /links/{short_code} – перенаправляет на оригинальный URL.
@router.get("/{short_code}")
async def redirect_to_original(short_code: str):
    pass


# DELETE /links/{short_code} – удаляет связь.
@router.delete("/{short_code}")
async def delete_link(short_code: str):
    pass


# PUT /links/{short_code} – обновляет короткий адрес ссылки
@router.put("/{short_code}")
async def update_link(short_code: str, original_url: str):
    pass


# GET /links/{short_code}/stats - Статистика по ссылке
@router.get("/{short_code}/stats")
async def get_link_stats(short_code: str):
    pass


# GET /links/search?original_url={url} - поиск по оригинальному URL
@router.get("/search")
async def search_by_original_url(original_url: str):
    pass

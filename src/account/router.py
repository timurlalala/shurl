from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select, delete, update, or_, and_
from sqlalchemy.exc import IntegrityError, NoResultFound

from typing_extensions import Annotated
from datetime import datetime, timezone, timedelta
from logging import getLogger
import json

from database import get_async_session
from shurl.utils import generate_random_string, validate_and_fix_url
from shurl.models import Link
from shurl.schemas import ShortenedItem

from redis_caching import r, write_stats_to_db
from auth.auth import User, current_active_user, current_user


logger = getLogger('account_router')

router = APIRouter(
    prefix="/account",
    tags=["Account"],
)

@router.get("/mylinks")
async def show_my_links(session: Annotated[AsyncSession, Depends(get_async_session)],
                        user: Annotated[User, Depends(current_active_user)]):
    try:

        query = select(Link.__table__).where(
            and_(Link.__table__.c.created_by_uuid == user.id,
            or_(Link.__table__.c.expires_at.is_(None), Link.__table__.c.expires_at > datetime.now(timezone.utc)))
        ) # type: ignore

        # logger.debug(query)

        result = await session.execute(query)
        await session.commit()
        links = result.all()

        report = {'links':[],
                  'total_clicks':0}

        # Ищем клики в кэше
        for l in links:
            short_code = l.short_url
            stats_key = f"stats:{short_code}"
            stats = await r.get(stats_key)

            if stats is None:
                report['links'].append({
                    "short_url": l.short_url,
                    "original_url": l.original_url,
                    "created_at": l.created_at,
                    "updated_at": l.updated_at,
                    "expires_at": l.expires_at,
                    "clicks": l.clicks,
                    "last_used": l.last_used
                })
                report['total_clicks']+=l.clicks
            else:
                stats = json.loads(stats)
                report['links'].append({
                    "short_url": l.short_url,
                    "original_url": l.original_url,
                    "created_at": l.created_at,
                    "updated_at": l.updated_at,
                    "expires_at": l.expires_at,
                    "clicks": int(stats['clicks']),
                    "last_used": datetime.fromisoformat(stats['last_used'])
                })
                report['total_clicks'] += int(stats['clicks'])

        return report
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original URL not found")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.warning(e.args)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/remove_unused_links")
async def remove_unused_links(session: Annotated[AsyncSession, Depends(get_async_session)],
                              user: Annotated[User, Depends(current_active_user)],
                              days: int = Query(default=0),
                              hours: int = Query(default=1, le=24)):
    try:
        delete_query = delete(Link.__table__).where(and_(
            and_(
                Link.__table__.c.created_by_uuid == user.id,
                Link.__table__.c.created_at < datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
            ),
            or_(
                Link.__table__.c.last_used.is_(None),
                Link.__table__.c.last_used < datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
            )
        ))  # type: ignore

        await session.execute(delete_query)
        await session.commit()
        return {"message": "Links deleted successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.warning(e.args)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



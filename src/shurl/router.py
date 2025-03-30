from fastapi import APIRouter, HTTPException, Depends, status


router = APIRouter(
    prefix="/links",
    tags=["Links"],
)

# POST /links/shorten – создает короткую ссылку.
@router.post("/shorten")
async def shorten_link(original_url: str, custom_alias: str = None, expires_at: str = None):
    pass

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
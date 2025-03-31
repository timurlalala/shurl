from fastapi import FastAPI
from shurl.router import router as shurl_router
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import logging
from redis_caching import process_expired_keys

logging.basicConfig(level=logging.DEBUG)

@asynccontextmanager
async def lifespan(application: FastAPI):
    task = asyncio.create_task(process_expired_keys())
    yield
    task.cancel()
    await task

app = FastAPI(lifespan=lifespan)

app.include_router(shurl_router)

@app.get("/")
async def root():
    return {"message": "App healthy"}

app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_expired_keys())

if __name__ == "__main__":
    uvicorn.run("main:app", reload=False, host="0.0.0.0", log_level="info")
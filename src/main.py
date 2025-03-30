from fastapi import FastAPI
from shurl.router import router as shurl_router
import uvicorn


app = FastAPI()

app.include_router(shurl_router)

@app.get("/")
async def root():
    return {"message": "App healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", reload=False, host="0.0.0.0", log_level="info")
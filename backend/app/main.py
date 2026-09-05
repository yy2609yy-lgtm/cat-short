import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import assets, auth, jobs, sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="猫咪短视频工作台", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(assets.router)
app.include_router(sync.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "drive_mode": settings.drive_mode,
        "youtube_mode": settings.youtube_mode,
    }

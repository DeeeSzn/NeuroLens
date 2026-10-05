"""FastAPI application — NeuroLens backend."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.local_access import LocalAccessMiddleware
from app.routers import analysis, comparison, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # Background reaper: fails processing jobs whose worker stopped heartbeating.
    from app.services.job_reaper import reaper_loop

    reaper_task = asyncio.create_task(reaper_loop())
    try:
        yield
    finally:
        reaper_task.cancel()
        with suppress(asyncio.CancelledError):
            await reaper_task


app = FastAPI(
    title=settings.app_name,
    description="Neuro-Optimized Content Design Platform — TRIBE v2-powered brain activation analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LocalAccessMiddleware)

# Routers
app.include_router(analysis.router)
app.include_router(comparison.router)
app.include_router(export.router)

# Static files — brain mesh GIFTIs served at /static/meshes/infl_left.gii etc.
_static_dir = settings.static_dir
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}

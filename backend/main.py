"""
İSO Pulse — FastAPI Ana Uygulama
Inpulse (/api/v1/hr/*) + Outpulse (/api/v1/radar/*) aynı platformda
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.database import init_db
from inpulse.router import inpulse_router
from outpulse.router import outpulse_router
from outpulse.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Başlangıç: DB tabloları (dev) + mevzuat scheduler
    if settings.environment == "development":
        await init_db()
    start_scheduler()
    yield
    # Kapanış: temizlik
    stop_scheduler()


app = FastAPI(
    title="İSO Pulse API",
    version="1.0.0",
    description="Inpulse (İç Kanal) + Outpulse (Mevzuat Radar) platformu",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router'lar ────────────────────────────────────────────────────────────────
app.include_router(inpulse_router)
app.include_router(outpulse_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.environment}

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import httpx
import os
from datetime import datetime, timezone
from typing import Optional
import logging

from routers import quotes, portfolio, watchlist, settings, futures, debug
from database import init_db
from services.shioaji_service import ShioajiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
shioaji_service = ShioajiService()
last_activity = datetime.now(timezone.utc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Portfolio API...")
    await init_db()
    app.state.shioaji = shioaji_service
    app.state.last_activity = last_activity
    yield
    # Shutdown
    logger.info("Shutting down...")
    await shioaji_service.logout()

app = FastAPI(
    title="Portfolio API",
    description="Personal Investment Portfolio Management API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set to your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(futures.router, prefix="/api/futures", tags=["futures"])
app.include_router(debug.router, tags=["debug"])

@app.get("/")
async def root():
    return {"status": "ok", "message": "Portfolio API is running"}

@app.get("/health")
async def health():
    """Health check endpoint - also used to keep Render awake"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "shioaji_connected": shioaji_service.is_connected
    }

@app.post("/api/keepalive")
async def keepalive():
    """Called by frontend 'I'm still here' button"""
    app.state.last_activity = datetime.now(timezone.utc)
    return {
        "status": "ok",
        "message": "Activity recorded",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/status")
async def get_status():
    """Returns server status including time since last activity"""
    now = datetime.now(timezone.utc)
    last = app.state.last_activity
    seconds_since_activity = (now - last).total_seconds()
    return {
        "server_time": now.isoformat(),
        "last_activity": last.isoformat(),
        "seconds_since_activity": int(seconds_since_activity),
        "shioaji_connected": shioaji_service.is_connected,
        "idle_timeout_seconds": 900  # 15 minutes
    }

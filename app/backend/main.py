import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.api import api_router
from app.backend.database import init_db, is_enabled

# Comma-separated list of allowed browser origins. Defaults to the two Vite dev
# servers; set this when serving the canvas from anywhere else.
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [origin.strip() for origin in os.environ.get("AI_HEDGE_FUND_CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # No-op unless AI_HEDGE_FUND_DATABASE_URL is configured.
    if is_enabled():
        init_db()
    yield


app = FastAPI(
    title="AI Hedge Fund API",
    description="Backend API for AI Hedge Fund",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets the browser read the run identifier off the streaming response.
    expose_headers=["X-Run-Id"],
)

# Include all routes
app.include_router(api_router)

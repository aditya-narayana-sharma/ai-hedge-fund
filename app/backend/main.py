import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.routes import api_router
from src.utils.progress import progress

# The agents share a progress tracker with the CLI, whose rich Live table
# would otherwise paint over the server's logs.
progress.disable_display()

# Defaults cover the two Vite dev origins; override for other deployments.
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)

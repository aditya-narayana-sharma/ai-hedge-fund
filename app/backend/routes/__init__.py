from fastapi import APIRouter

from app.backend.routes.backtest import router as backtest_router
from app.backend.routes.catalog import router as catalog_router
from app.backend.routes.hedge_fund import router as hedge_fund_router
from app.backend.routes.health import router as health_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(catalog_router, tags=["catalog"])
api_router.include_router(hedge_fund_router, tags=["hedge-fund"])
api_router.include_router(backtest_router, tags=["backtest"])

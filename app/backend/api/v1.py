"""Router assembly.

Health and catalog reads are cheap and unguarded. The two endpoints that spend
LLM tokens — ``/hedge-fund/run`` and ``/backtest`` — sit behind the API-key and
rate-limit dependencies, both of which are no-ops until configured.
"""

from fastapi import APIRouter, Depends

from app.backend.api.deps import enforce_rate_limit, require_api_key
from app.backend.routes.backtest import router as backtest_router
from app.backend.routes.catalog import router as catalog_router
from app.backend.routes.health import router as health_router
from app.backend.routes.hedge_fund import router as hedge_fund_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(catalog_router, tags=["catalog"])

_guarded = [Depends(require_api_key), Depends(enforce_rate_limit)]

api_router.include_router(hedge_fund_router, tags=["hedge-fund"], dependencies=_guarded)
api_router.include_router(backtest_router, tags=["backtest"], dependencies=_guarded)

"""Catalog endpoints.

``ANALYST_CONFIG`` calls itself the single source of truth, but with no
endpoint to read it the frontend re-declared all fourteen agents and every
model by hand. That mirror was already lossy: it omitted the Ollama provider
entirely, which made the whole local-LLM path unreachable from the web app.
Serving both catalogs removes the duplicate declaration.
"""

from fastapi import APIRouter

from app.backend.models.schemas import AgentInfo, ModelInfo
from src.llm.models import AVAILABLE_MODELS, OLLAMA_MODELS
from src.utils.analysts import ANALYST_CONFIG

router = APIRouter()


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """Every analyst the engine can run, in display order."""
    return [
        AgentInfo(
            key=key,
            display_name=config["display_name"],
            description=config.get("description", ""),
            order=config["order"],
        )
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda item: item[1]["order"])
    ]


@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    """Every model the engine can call, cloud and local alike."""
    return [
        ModelInfo(
            display_name=model.display_name,
            model_name=model.model_name,
            provider=model.provider.value,
            supports_json_mode=model.supports_json_mode,
        )
        for model in AVAILABLE_MODELS + OLLAMA_MODELS
    ]

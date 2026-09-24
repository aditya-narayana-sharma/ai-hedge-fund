"""Serve the analyst and model catalogs so the UI does not re-declare them.

src/utils/analysts.py calls itself the single source of truth, but the
frontend cannot import Python. Without these endpoints the catalogs were
copied into TypeScript by hand, and the copy had already gone lossy: it
omitted Ollama entirely, making the whole local-LLM path unreachable from the
web app.
"""

from fastapi import APIRouter

from app.backend.models.schemas import AgentSummary, ModelSummary
from src.llm.models import AVAILABLE_MODELS, OLLAMA_MODELS
from src.utils.analysts import ANALYST_CONFIG

router = APIRouter()


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents() -> list[AgentSummary]:
    """Every analyst the graph can run, in display order."""
    return [
        AgentSummary(
            key=key,
            display_name=config["display_name"],
            description=config.get("description"),
            order=config["order"],
        )
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda item: item[1]["order"])
    ]


@router.get("/models", response_model=list[ModelSummary])
async def list_models() -> list[ModelSummary]:
    """Every selectable model, cloud and local, excluding custom placeholders."""
    return [
        ModelSummary(
            display_name=model.display_name,
            model_name=model.model_name,
            provider=model.provider.value,
            supports_json_mode=model.supports_json_mode,
        )
        for model in [*AVAILABLE_MODELS, *OLLAMA_MODELS]
        if not model.is_custom()
    ]

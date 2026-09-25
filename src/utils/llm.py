"""Helper functions for LLM"""

import os
import time
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

from src.llm.models import get_model, get_model_info
from src.utils.json_parsing import extract_json_from_response
from src.utils.progress import progress

T = TypeVar("T", bound=BaseModel)

# How many analyst calls in this process fell back to a neutral default.
# Reset at the start of a run; printed on the summary line.
_degraded_analysts = 0


def reset_degraded_analysts() -> None:
    """Zero the degraded-analyst counter. Call once per run."""
    global _degraded_analysts
    _degraded_analysts = 0


def degraded_analyst_count() -> int:
    """Analyst calls that failed and were replaced with a neutral fallback."""
    return _degraded_analysts


def _note_degraded_analyst() -> None:
    global _degraded_analysts
    _degraded_analysts += 1


def _backoff_seconds(attempt: int) -> float:
    """Exponential delay before retry ``attempt`` (0-based).

    ``AI_HEDGE_FUND_LLM_BACKOFF_SECONDS=0`` disables the sleep, which tests use.
    """
    raw = os.environ.get("AI_HEDGE_FUND_LLM_BACKOFF_SECONDS", "0.5")
    try:
        base = max(0.0, float(raw))
    except ValueError:
        base = 0.5
    return base * (2**attempt)


def call_llm(
    prompt: Any,
    model_name: str,
    model_provider: str,
    pydantic_model: Type[T],
    agent_name: Optional[str] = None,
    max_retries: int = 3,
    default_factory=None,
) -> T:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.

    Args:
        prompt: The prompt to send to the LLM
        model_name: Name of the model to use
        model_provider: Provider of the model
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure

    Returns:
        An instance of the specified Pydantic model
    """

    model_info = get_model_info(model_name, model_provider)
    llm = get_model(model_name, model_provider)

    # For non-JSON support models, we can use structured output
    if not (model_info and not model_info.has_json_mode()):
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)

            # For non-JSON support models, we need to extract and parse the JSON manually
            if model_info and not model_info.has_json_mode():
                parsed_result = extract_json_from_response(result.content)
                if parsed_result:
                    return pydantic_model(**parsed_result)
            else:
                return result

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                break
            delay = _backoff_seconds(attempt)
            if delay:
                time.sleep(delay)

    # Every attempt either raised or produced unparseable output. Both paths
    # must honour the caller's fallback; previously only the exception path did,
    # so a parse failure silently discarded default_factory. The fallback is a
    # neutral signal, so it has to be counted or the summary reads "14 neutral
    # analysts" for a run where every call failed.
    _note_degraded_analyst()
    if agent_name:
        progress.update_status(agent_name, None, "Failed: LLM call failed")
    if default_factory:
        return default_factory()
    return create_default_response(pydantic_model)


def create_default_response(model_class: Type[T]) -> T:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)

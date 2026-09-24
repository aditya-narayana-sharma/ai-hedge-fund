"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any, cast
from langchain_core.runnables import Runnable
from pydantic import BaseModel
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress

T = TypeVar("T", bound=BaseModel)


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
    supports_json_mode = not (model_info and not model_info.has_json_mode())

    chat_model = get_model(model_name, model_provider)
    llm: Runnable = (
        chat_model.with_structured_output(
            pydantic_model,
            method="json_mode",
        )
        if supports_json_mode
        else chat_model
    )

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)

            if supports_json_mode:
                # with_structured_output already returned an instance.
                return cast(T, result)

            # Otherwise the model answered in prose and the JSON has to be dug out.
            content = result.content
            parsed_result = extract_json_from_response(content if isinstance(content, str) else json.dumps(content))
            if parsed_result:
                return pydantic_model(**parsed_result)

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                break

    # Every attempt either raised or produced unparseable output. Both paths owe
    # the caller its own fallback, not just the exception path.
    if default_factory:
        return default_factory()
    return create_default_response(pydantic_model)


def create_default_response(model_class: Type[T]) -> T:
    """Creates a safe default response based on the model's fields."""
    default_values: dict[str, Any] = {}
    for field_name, field in model_class.model_fields.items():
        annotation = field.annotation
        if annotation is str:
            default_values[field_name] = "Error in analysis, using default"
        elif annotation is float:
            default_values[field_name] = 0.0
        elif annotation is int:
            default_values[field_name] = 0
        elif getattr(annotation, "__origin__", None) is dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            args = getattr(annotation, "__args__", None)
            default_values[field_name] = args[0] if args else None

    return model_class(**default_values)


def extract_json_from_response(content: str) -> Optional[dict]:
    """Extract a JSON object from an LLM response.

    Accepts a bare object, a ```json fence, a plain ``` fence, and an object
    embedded in prose. Only fenced ```json output was accepted before, so a
    model that answered with bare JSON burned every retry and fell through to
    the default response.
    """
    if not content:
        return None

    for candidate in _json_candidates(content):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        # A model asked for one object sometimes wraps it in an array.
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return parsed[0]
    return None


def _json_candidates(content: str) -> list[str]:
    """Substrings of a response that might be a JSON object, best guess first."""
    candidates = [content.strip()]

    for fence in ("```json", "```"):
        start = content.find(fence)
        if start == -1:
            continue
        body = content[start + len(fence) :]
        end = body.find("```")
        candidates.append(body[:end].strip() if end != -1 else body.strip())

    # Last resort: the outermost brace pair, for JSON wrapped in prose.
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(content[first_brace : last_brace + 1])

    return candidates

"""JSON helpers shared by the engine and the web backend.

Kept free of LangChain and Pydantic imports so the parsing rules can be tested
without the whole model stack, and so ``parse_hedge_fund_response`` has one
definition instead of the two that had drifted between ``src/main.py`` and
``app/backend/services/graph.py``.
"""

import json
import re
from typing import Any, Optional

# ```json { ... } ```  or a bare ``` { ... } ``` fence.
_FENCE_PATTERN = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def parse_hedge_fund_response(response: Any) -> Optional[dict]:
    """Parse a JSON string into a dict, returning None on any malformed input."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        print(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None


def extract_json_from_response(content: str) -> Optional[dict]:
    """Extract a JSON object from an LLM reply.

    Accepts, in order: a bare JSON document, a ```json fenced block, a generic
    ``` fenced block, and finally the outermost brace-delimited span in the
    text. The original implementation handled only ```json fences, so models
    without JSON mode that answered with bare JSON — every Ollama model outside
    the llama3/neural-chat allow-list — burned all three retries and fell back
    to "Error in analysis, using default".
    """
    if not content:
        return None

    for candidate in _candidates(content):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _candidates(content: str) -> list[str]:
    """Yield progressively more forgiving slices of `content` to try as JSON."""
    text = content.strip()
    candidates = [text]
    candidates.extend(match.strip() for match in _FENCE_PATTERN.findall(text))

    # Last resort: the outermost {...} span, which survives leading prose.
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])

    return [c for c in candidates if c]

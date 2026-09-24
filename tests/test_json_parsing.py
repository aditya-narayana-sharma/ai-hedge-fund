"""JSON extraction rules for LLM replies and hedge-fund responses.

The bare-JSON cases are the regression: models outside the ``has_json_mode``
allow-list answer without a markdown fence, and a fence-only parser turned every
one of those replies into "Error in analysis, using default".
"""

from src.utils.json_parsing import extract_json_from_response, parse_hedge_fund_response


class TestExtractJsonFromResponse:
    def test_accepts_bare_json(self):
        assert extract_json_from_response('{"signal": "bullish", "confidence": 80}') == {
            "signal": "bullish",
            "confidence": 80,
        }

    def test_accepts_bare_json_with_surrounding_whitespace(self):
        assert extract_json_from_response('\n\n  {"signal": "bearish"}  \n') == {"signal": "bearish"}

    def test_accepts_a_json_tagged_fence(self):
        content = 'Here you go:\n```json\n{"signal": "neutral", "confidence": 50}\n```\nHope that helps.'
        assert extract_json_from_response(content) == {"signal": "neutral", "confidence": 50}

    def test_accepts_an_untagged_fence(self):
        content = '```\n{"signal": "bullish"}\n```'
        assert extract_json_from_response(content) == {"signal": "bullish"}

    def test_accepts_an_uppercase_fence_tag(self):
        content = '```JSON\n{"signal": "bullish"}\n```'
        assert extract_json_from_response(content) == {"signal": "bullish"}

    def test_recovers_an_object_embedded_in_prose(self):
        content = 'After reviewing the filings I conclude {"signal": "bearish", "confidence": 71} overall.'
        assert extract_json_from_response(content) == {"signal": "bearish", "confidence": 71}

    def test_handles_nested_objects(self):
        content = '{"signal": "bullish", "reasoning": {"moat": "wide", "value": {"pe": 12}}}'
        assert extract_json_from_response(content)["reasoning"]["value"]["pe"] == 12

    def test_returns_none_for_unparseable_text(self):
        assert extract_json_from_response("I am afraid I cannot answer that.") is None

    def test_returns_none_for_empty_input(self):
        assert extract_json_from_response("") is None

    def test_returns_none_for_a_bare_json_array(self):
        """Callers splat the result into a Pydantic model, so only objects qualify."""
        assert extract_json_from_response('["bullish", "bearish"]') is None


class TestParseHedgeFundResponse:
    def test_parses_valid_json(self):
        assert parse_hedge_fund_response('{"AAPL": {"action": "buy", "quantity": 10}}') == {"AAPL": {"action": "buy", "quantity": 10}}

    def test_returns_none_on_malformed_json(self):
        assert parse_hedge_fund_response('{"AAPL": ') is None

    def test_returns_none_on_non_string_input(self):
        assert parse_hedge_fund_response(None) is None

    def test_returns_none_on_empty_string(self):
        assert parse_hedge_fund_response("") is None

"""JSON extraction has to survive the shapes models actually emit."""

from pydantic import BaseModel

from app.backend.services.graph import parse_hedge_fund_response
from src.utils.llm import create_default_response, extract_json_from_response


class Signal(BaseModel):
    signal: str
    confidence: float
    reasoning: str


class TestExtractJsonFromResponse:
    def test_bare_json_object(self):
        assert extract_json_from_response('{"signal": "bullish", "confidence": 80}') == {"signal": "bullish", "confidence": 80}

    def test_json_fence(self):
        content = 'Here you go:\n```json\n{"signal": "bearish"}\n```'
        assert extract_json_from_response(content) == {"signal": "bearish"}

    def test_generic_fence(self):
        content = '```\n{"signal": "neutral"}\n```'
        assert extract_json_from_response(content) == {"signal": "neutral"}

    def test_object_embedded_in_prose(self):
        content = 'After reviewing the filings: {"signal": "bullish", "confidence": 55} — that is my call.'
        assert extract_json_from_response(content) == {"signal": "bullish", "confidence": 55}

    def test_unparseable_content_returns_none(self):
        assert extract_json_from_response("I could not decide.") is None

    def test_empty_content_returns_none(self):
        assert extract_json_from_response("") is None

    def test_a_single_element_array_is_unwrapped(self):
        assert extract_json_from_response('[{"signal": "bullish"}]') == {"signal": "bullish"}

    def test_an_ambiguous_multi_element_array_is_rejected(self):
        assert extract_json_from_response('[{"signal": "bullish"}, {"signal": "bearish"}]') is None


class TestCreateDefaultResponse:
    def test_fills_every_field_by_type(self):
        default = create_default_response(Signal)

        assert default.signal == "Error in analysis, using default"
        assert default.confidence == 0.0
        assert default.reasoning == "Error in analysis, using default"


class TestParseHedgeFundResponse:
    def test_valid_json(self):
        assert parse_hedge_fund_response('{"AAPL": {"action": "buy"}}') == {"AAPL": {"action": "buy"}}

    def test_malformed_json_returns_none(self):
        assert parse_hedge_fund_response("{not json") is None

    def test_non_string_returns_none(self):
        assert parse_hedge_fund_response(None) is None

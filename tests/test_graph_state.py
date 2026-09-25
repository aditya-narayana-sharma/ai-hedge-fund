"""The AgentState reducer.

A shallow ``{**a, **b}`` only worked because every analyst mutated one shared
``analyst_signals`` dict in place. These cases pin the deep merge that makes
disjoint parallel branches safe.
"""

from src.graph.state import merge_dicts


def test_disjoint_top_level_keys_are_both_kept():
    assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_scalars_are_overwritten_by_the_right_hand_side():
    assert merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}


def test_parallel_branches_do_not_drop_each_others_signals():
    left = {"analyst_signals": {"warren_buffett": {"AAPL": "bullish"}}}
    right = {"analyst_signals": {"michael_burry": {"AAPL": "bearish"}}}

    merged = merge_dicts(left, right)

    assert merged["analyst_signals"] == {
        "warren_buffett": {"AAPL": "bullish"},
        "michael_burry": {"AAPL": "bearish"},
    }


def test_same_agent_different_tickers_are_combined():
    left = {"analyst_signals": {"warren_buffett": {"AAPL": "bullish"}}}
    right = {"analyst_signals": {"warren_buffett": {"MSFT": "neutral"}}}

    assert merge_dicts(left, right)["analyst_signals"]["warren_buffett"] == {
        "AAPL": "bullish",
        "MSFT": "neutral",
    }


def test_inputs_are_not_mutated():
    left = {"analyst_signals": {"warren_buffett": {"AAPL": "bullish"}}}
    right = {"analyst_signals": {"michael_burry": {"AAPL": "bearish"}}}

    merge_dicts(left, right)

    assert left == {"analyst_signals": {"warren_buffett": {"AAPL": "bullish"}}}
    assert right == {"analyst_signals": {"michael_burry": {"AAPL": "bearish"}}}


def test_a_dict_replaces_a_scalar_of_the_same_key():
    assert merge_dicts({"a": 1}, {"a": {"b": 2}}) == {"a": {"b": 2}}

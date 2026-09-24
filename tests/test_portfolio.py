"""Invariants for the shared portfolio model.

The margin test is the regression that matters: before the model existed, two of
the three valuation sites omitted the margin posted against short positions, so
net liquidation value was understated by exactly ``margin_used``.
"""

import pytest

from src.data.portfolio import (
    create_portfolio,
    DEFAULT_POSITION_LIMIT,
    net_liquidation_value,
    Portfolio,
)


def test_create_portfolio_zeroes_every_ticker():
    portfolio = create_portfolio(100_000.0, 0.5, ["AAPL", "MSFT"])

    assert portfolio["cash"] == 100_000.0
    assert portfolio["margin_requirement"] == 0.5
    assert portfolio["margin_used"] == 0.0
    assert set(portfolio["positions"]) == {"AAPL", "MSFT"}
    assert portfolio["positions"]["AAPL"] == {
        "long": 0,
        "short": 0,
        "long_cost_basis": 0.0,
        "short_cost_basis": 0.0,
        "short_margin_used": 0.0,
    }
    assert portfolio["realized_gains"]["MSFT"] == {"long": 0.0, "short": 0.0}


def test_flat_portfolio_is_worth_its_cash():
    portfolio = Portfolio.create(50_000.0, 0.0, ["AAPL"])
    assert portfolio.net_liquidation_value({"AAPL": 190.0}) == 50_000.0


def test_long_position_is_marked_to_market():
    portfolio = Portfolio.create(1_000.0, 0.0, ["AAPL"])
    portfolio.positions["AAPL"].long = 10
    portfolio.cash -= 10 * 100.0  # bought 10 @ 100

    assert portfolio.net_liquidation_value({"AAPL": 100.0}) == 1_000.0
    assert portfolio.net_liquidation_value({"AAPL": 120.0}) == 1_200.0


def test_opening_a_short_on_margin_does_not_change_nlv():
    """Opening a short moves cash into collateral; it does not create or destroy value."""
    margin_requirement = 0.5
    price = 100.0
    shares = 10

    portfolio = Portfolio.create(10_000.0, margin_requirement, ["AAPL"])
    before = portfolio.net_liquidation_value({"AAPL": price})

    # Mirror src/backtester.py execute_trade: credit proceeds, debit margin.
    proceeds = price * shares
    margin_required = proceeds * margin_requirement
    portfolio.cash += proceeds
    portfolio.cash -= margin_required
    portfolio.margin_used += margin_required
    portfolio.positions["AAPL"].short = shares
    portfolio.positions["AAPL"].short_cost_basis = price
    portfolio.positions["AAPL"].short_margin_used = margin_required

    assert portfolio.net_liquidation_value({"AAPL": price}) == pytest.approx(before)


def test_short_round_trip_at_unchanged_price_is_flat():
    """Open a short and cover it immediately: NLV must be unchanged.

    This fails whenever ``margin_used`` is left out of the valuation.
    """
    margin_requirement = 0.5
    price = 100.0
    shares = 10

    portfolio = Portfolio.create(10_000.0, margin_requirement, ["AAPL"])
    start = portfolio.net_liquidation_value({"AAPL": price})

    proceeds = price * shares
    margin_required = proceeds * margin_requirement
    portfolio.cash += proceeds - margin_required
    portfolio.margin_used += margin_required
    portfolio.positions["AAPL"].short = shares
    portfolio.positions["AAPL"].short_cost_basis = price

    # Cover at the same price: pay to buy back, release the margin.
    portfolio.cash -= price * shares
    portfolio.cash += margin_required
    portfolio.margin_used -= margin_required
    portfolio.positions["AAPL"].short = 0

    assert portfolio.net_liquidation_value({"AAPL": price}) == pytest.approx(start)


def test_short_gains_value_when_price_falls():
    portfolio = Portfolio.create(10_000.0, 0.0, ["AAPL"])
    portfolio.positions["AAPL"].short = 10
    portfolio.cash += 10 * 100.0  # sold short 10 @ 100, no margin posted

    assert portfolio.net_liquidation_value({"AAPL": 100.0}) == 10_000.0
    assert portfolio.net_liquidation_value({"AAPL": 90.0}) == 10_100.0
    assert portfolio.net_liquidation_value({"AAPL": 110.0}) == 9_900.0


def test_unpriced_tickers_are_skipped_not_fatal():
    portfolio = Portfolio.create(1_000.0, 0.0, ["AAPL", "MSFT"])
    portfolio.positions["AAPL"].long = 5
    portfolio.positions["MSFT"].long = 5

    # The risk manager only prices what it managed to fetch.
    assert portfolio.net_liquidation_value({"AAPL": 10.0}) == 1_050.0


def test_net_liquidation_value_accepts_a_plain_dict():
    portfolio = create_portfolio(1_000.0, 0.0, ["AAPL"])
    portfolio["positions"]["AAPL"]["long"] = 2

    assert net_liquidation_value(portfolio, {"AAPL": 50.0}) == 1_100.0


def test_default_position_limit_is_twenty_percent():
    assert DEFAULT_POSITION_LIMIT == 0.20

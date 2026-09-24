"""Net liquidation value must not lose the margin posted against shorts."""

from src.data.portfolio import Portfolio, create_portfolio, net_liquidation_value

MARGIN_REQUIREMENT = 0.5
PRICE = 100.0
SHARES = 10


def _open_short(portfolio: Portfolio, ticker: str, shares: int, price: float) -> None:
    """Mirror the backtester's short-opening bookkeeping."""
    proceeds = shares * price
    margin = proceeds * portfolio.margin_requirement
    portfolio.cash += proceeds
    portfolio.cash -= margin
    portfolio.margin_used += margin
    position = portfolio.positions[ticker]
    position.short += shares
    position.short_cost_basis = price
    position.short_margin_used += margin


def _cover_short(portfolio: Portfolio, ticker: str, shares: int, price: float) -> None:
    """Mirror the backtester's short-covering bookkeeping."""
    position = portfolio.positions[ticker]
    margin_released = position.short_margin_used * (shares / position.short)
    portfolio.cash -= shares * price
    portfolio.cash += margin_released
    portfolio.margin_used -= margin_released
    position.short -= shares
    position.short_margin_used -= margin_released


def test_opening_a_short_leaves_net_liquidation_value_unchanged():
    portfolio = Portfolio.create(100_000.0, MARGIN_REQUIREMENT, ["AAPL"])
    before = portfolio.net_liquidation_value({"AAPL": PRICE})

    _open_short(portfolio, "AAPL", SHARES, PRICE)

    assert portfolio.margin_used > 0, "the test is pointless without posted margin"
    assert portfolio.net_liquidation_value({"AAPL": PRICE}) == before


def test_covering_a_short_at_an_unchanged_price_leaves_value_unchanged():
    portfolio = Portfolio.create(100_000.0, MARGIN_REQUIREMENT, ["AAPL"])
    before = portfolio.net_liquidation_value({"AAPL": PRICE})

    _open_short(portfolio, "AAPL", SHARES, PRICE)
    _cover_short(portfolio, "AAPL", SHARES, PRICE)

    assert portfolio.margin_used == 0
    assert portfolio.net_liquidation_value({"AAPL": PRICE}) == before


def test_short_gains_value_when_the_price_falls():
    portfolio = Portfolio.create(100_000.0, MARGIN_REQUIREMENT, ["AAPL"])
    _open_short(portfolio, "AAPL", SHARES, PRICE)

    assert portfolio.net_liquidation_value({"AAPL": PRICE / 2}) == 100_000.0 + SHARES * PRICE / 2


def test_long_position_is_marked_to_market():
    portfolio = Portfolio.create(1_000.0, 0.0, ["AAPL"])
    portfolio.cash -= 5 * PRICE
    portfolio.positions["AAPL"].long = 5

    assert portfolio.net_liquidation_value({"AAPL": PRICE}) == 1_000.0
    assert portfolio.net_liquidation_value({"AAPL": PRICE * 2}) == 1_500.0


def test_missing_prices_are_skipped_rather_than_guessed():
    portfolio = Portfolio.create(1_000.0, 0.0, ["AAPL", "MSFT"])
    portfolio.positions["AAPL"].long = 5

    assert portfolio.net_liquidation_value({}) == 1_000.0


def test_create_portfolio_matches_the_graph_dict_shape():
    portfolio = create_portfolio(50_000.0, 0.25, ["AAPL", "MSFT"])

    assert portfolio["cash"] == 50_000.0
    assert portfolio["margin_requirement"] == 0.25
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


def test_net_liquidation_value_accepts_the_plain_dict_form():
    portfolio = create_portfolio(1_000.0, 0.0, ["AAPL"])
    portfolio["positions"]["AAPL"]["long"] = 2

    assert net_liquidation_value(portfolio, {"AAPL": 10.0}) == 1_020.0

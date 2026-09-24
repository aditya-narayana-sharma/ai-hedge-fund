from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import init
from langgraph.graph.state import CompiledStateGraph

from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import DEFAULT_POSITION_LIMIT_PCT, risk_management_agent
from src.data.portfolio import create_portfolio
from src.graph.state import AgentState
from src.utils.display import print_trading_output
from src.utils.analysts import add_analyst_arguments, get_analyst_nodes, resolve_selected_analysts
from src.utils.model_selection import add_model_arguments, resolve_model
from src.utils.progress import progress

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from src.utils.visualize import save_graph_as_png
import json

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
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


##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] | None = None,
    model_name: str = "gpt-4o",
    model_provider: str = "OpenAI",
    graph: CompiledStateGraph | None = None,
    position_limit_pct: float = DEFAULT_POSITION_LIMIT_PCT,
):
    """Run one hedge fund pass and return its decisions and analyst signals.

    Pass ``graph`` to reuse an already-compiled workflow; otherwise one is
    compiled from ``selected_analysts`` (all analysts when omitted).
    """
    # Start progress tracking
    progress.start()

    try:
        agent = graph if graph is not None else create_workflow(selected_analysts).compile()

        final_state = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Make trading decisions based on the provided data.",
                    )
                ],
                "data": {
                    "tickers": tickers,
                    "portfolio": portfolio,
                    "start_date": start_date,
                    "end_date": end_date,
                    "analyst_signals": {},
                },
                "metadata": {
                    "show_reasoning": show_reasoning,
                    "model_name": model_name,
                    "model_provider": model_provider,
                    "position_limit_pct": position_limit_pct,
                },
            },
        )

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
        }
    finally:
        # Stop progress tracking
        progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always add risk and portfolio management
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_manager")
    workflow.add_edge("portfolio_manager", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
    parser.add_argument("--initial-cash", type=float, default=100000.0, help="Initial cash position. Defaults to 100000.0)")
    parser.add_argument("--margin-requirement", type=float, default=0.0, help="Initial margin requirement. Defaults to 0.0")
    parser.add_argument("--tickers", type=str, required=True, help="Comma-separated list of stock ticker symbols")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 3 months before end date",
    )
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD). Defaults to today")
    parser.add_argument("--show-reasoning", action="store_true", help="Show reasoning from each agent")
    parser.add_argument("--show-agent-graph", action="store_true", help="Show the agent graph")
    parser.add_argument("--graph-output", type=str, help="Where to write the agent graph PNG. Implies --show-agent-graph")
    parser.add_argument(
        "--position-limit",
        type=float,
        default=DEFAULT_POSITION_LIMIT_PCT,
        help=f"Maximum share of portfolio value in one ticker (default: {DEFAULT_POSITION_LIMIT_PCT})",
    )
    add_analyst_arguments(parser)
    add_model_arguments(parser)

    args = parser.parse_args()

    # Parse tickers from comma-separated string
    tickers = [ticker.strip() for ticker in args.tickers.split(",")]

    try:
        selected_analysts = resolve_selected_analysts(args.analysts, args.analysts_all)
        model_name, model_provider = resolve_model(args)
    except (ValueError, RuntimeError) as e:
        parser.error(str(e))

    # Create the workflow with selected analysts
    workflow = create_workflow(selected_analysts)
    app = workflow.compile()

    if args.show_agent_graph or args.graph_output:
        file_path = args.graph_output or "_".join(selected_analysts) + "_graph.png"
        save_graph_as_png(app, file_path)

    # Validate dates if provided
    if args.start_date:
        try:
            datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Start date must be in YYYY-MM-DD format")

    if args.end_date:
        try:
            datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("End date must be in YYYY-MM-DD format")

    # Set the start and end dates
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if not args.start_date:
        # Calculate 3 months before end_date
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # Initialize portfolio with cash amount and stock positions
    portfolio = create_portfolio(args.initial_cash, args.margin_requirement, tickers)

    # Run the hedge fund
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning,
        selected_analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
        graph=app,
        position_limit_pct=args.position_limit,
    )
    print_trading_output(result)

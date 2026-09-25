import asyncio

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.data.portfolio import DEFAULT_POSITION_LIMIT
from src.graph.state import AgentState
from src.main import start
from src.utils.analysts import ANALYST_CONFIG
from src.utils.json_parsing import parse_hedge_fund_response  # noqa: F401  (re-exported for routes)
from src.utils.llm import reset_degraded_analysts


class UnknownAgentsError(ValueError):
    """Raised when a request names agents that are not in ANALYST_CONFIG.

    Previously unknown keys were filtered out silently, so a typo produced a
    graph of risk-manager plus portfolio-manager only and a 200 with empty
    analyst_signals — indistinguishable from "every analyst was neutral".
    """

    def __init__(self, unknown: list[str]) -> None:
        self.unknown = unknown
        known = ", ".join(sorted(ANALYST_CONFIG))
        super().__init__(f"Unknown agent(s): {', '.join(unknown)}. Available agents: {known}.")


def validate_agents(selected_agents: list[str]) -> list[str]:
    """Return the requested agents, raising on an empty or unknown selection."""
    if not selected_agents:
        raise ValueError("selected_agents must contain at least one agent.")

    unknown = [agent for agent in selected_agents if agent not in ANALYST_CONFIG]
    if unknown:
        raise UnknownAgentsError(unknown)

    # De-duplicate while preserving the caller's order.
    return list(dict.fromkeys(selected_agents))


# Helper function to create the agent graph
def create_graph(
    selected_agents: list[str],
    include_risk_management: bool = True,
    include_portfolio_management: bool = True,
) -> StateGraph:
    """Create the workflow with selected agents.

    The risk and portfolio stages are optional rather than unconditional, which
    is what the old "(for now)" comment was standing in for. They remain on by
    default because the portfolio manager is what produces the orders.
    """
    selected_agents = validate_agents(selected_agents)

    graph = StateGraph(AgentState)
    graph.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}

    # Add selected analyst nodes
    for agent_name in selected_agents:
        node_name, node_func = analyst_nodes[agent_name]
        graph.add_node(node_name, node_func)
        graph.add_edge("start_node", node_name)

    analyst_node_names = [analyst_nodes[agent_name][0] for agent_name in selected_agents]

    if include_risk_management:
        graph.add_node("risk_management_agent", risk_management_agent)
        for node_name in analyst_node_names:
            graph.add_edge(node_name, "risk_management_agent")

    if include_portfolio_management:
        graph.add_node("portfolio_manager", portfolio_management_agent)
        if include_risk_management:
            graph.add_edge("risk_management_agent", "portfolio_manager")
        else:
            for node_name in analyst_node_names:
                graph.add_edge(node_name, "portfolio_manager")
        graph.add_edge("portfolio_manager", END)
    elif include_risk_management:
        graph.add_edge("risk_management_agent", END)
    else:
        for node_name in analyst_node_names:
            graph.add_edge(node_name, END)

    # Set the entry point to the start node
    graph.set_entry_point("start_node")
    return graph


DEFAULT_PROMPT = "Make trading decisions based on the provided data."


async def run_graph_async(graph, portfolio, tickers, start_date, end_date, model_name, model_provider, position_limit=DEFAULT_POSITION_LIMIT, prompt=None):
    """Run the synchronous graph off the event loop, preserving the run context.

    ``asyncio.to_thread`` copies the active contextvars, which is what lets the
    agents resolve the per-run cache and progress handlers. ``run_in_executor``
    does not, so switching back would silently reinstate the shared globals.
    """
    return await asyncio.to_thread(
        run_graph,
        graph,
        portfolio,
        tickers,
        start_date,
        end_date,
        model_name,
        model_provider,
        position_limit,
        prompt,
    )


def run_graph(
    graph: StateGraph,
    portfolio: dict,
    tickers: list[str],
    start_date: str,
    end_date: str,
    model_name: str,
    model_provider: str,
    position_limit: float = DEFAULT_POSITION_LIMIT,
    prompt: str | None = None,
) -> dict:
    """
    Run the graph with the given portfolio, tickers,
    start date, end date, show reasoning, model name,
    and model provider.
    """
    reset_degraded_analysts()
    return graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=prompt or DEFAULT_PROMPT,
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
                "show_reasoning": False,
                "model_name": model_name,
                "model_provider": model_provider,
                "position_limit": position_limit,
            },
        },
    )

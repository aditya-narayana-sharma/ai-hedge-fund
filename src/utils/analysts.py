"""Constants and utilities related to analysts configuration."""

import sys

import questionary
from colorama import Fore, Style

from src.agents.aswath_damodaran import aswath_damodaran_agent
from src.agents.ben_graham import ben_graham_agent
from src.agents.bill_ackman import bill_ackman_agent
from src.agents.cathie_wood import cathie_wood_agent
from src.agents.charlie_munger import charlie_munger_agent
from src.agents.fundamentals import fundamentals_agent
from src.agents.michael_burry import michael_burry_agent
from src.agents.phil_fisher import phil_fisher_agent
from src.agents.peter_lynch import peter_lynch_agent
from src.agents.sentiment import sentiment_agent
from src.agents.stanley_druckenmiller import stanley_druckenmiller_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_agent
from src.agents.warren_buffett import warren_buffett_agent

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    "aswath_damodaran": {
        "display_name": "Aswath Damodaran",
        "description": "The Dean of Valuation",
        "agent_func": aswath_damodaran_agent,
        "order": 0,
    },
    "ben_graham": {
        "display_name": "Ben Graham",
        "description": "The Father of Value Investing",
        "agent_func": ben_graham_agent,
        "order": 1,
    },
    "bill_ackman": {
        "display_name": "Bill Ackman",
        "description": "The Activist Investor",
        "agent_func": bill_ackman_agent,
        "order": 2,
    },
    "cathie_wood": {
        "display_name": "Cathie Wood",
        "description": "The Queen of Growth Investing",
        "agent_func": cathie_wood_agent,
        "order": 3,
    },
    "charlie_munger": {
        "display_name": "Charlie Munger",
        "description": "The Rational Thinker",
        "agent_func": charlie_munger_agent,
        "order": 4,
    },
    "michael_burry": {
        "display_name": "Michael Burry",
        "description": "The Big Short Contrarian",
        "agent_func": michael_burry_agent,
        "order": 5,
    },
    "peter_lynch": {
        "display_name": "Peter Lynch",
        "description": "The 10-Bagger Investor",
        "agent_func": peter_lynch_agent,
        "order": 6,
    },
    "phil_fisher": {
        "display_name": "Phil Fisher",
        "description": "The Scuttlebutt Investor",
        "agent_func": phil_fisher_agent,
        "order": 7,
    },
    "stanley_druckenmiller": {
        "display_name": "Stanley Druckenmiller",
        "description": "The Macro Investor",
        "agent_func": stanley_druckenmiller_agent,
        "order": 8,
    },
    "warren_buffett": {
        "display_name": "Warren Buffett",
        "description": "The Oracle of Omaha",
        "agent_func": warren_buffett_agent,
        "order": 9,
    },
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "description": "Chart Pattern Specialist",
        "agent_func": technical_analyst_agent,
        "order": 10,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "description": "Financial Statement Specialist",
        "agent_func": fundamentals_agent,
        "order": 11,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "description": "Market Sentiment Specialist",
        "agent_func": sentiment_agent,
        "order": 12,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "description": "Company Valuation Specialist",
        "agent_func": valuation_agent,
        "order": 13,
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}


def all_analyst_keys() -> list[str]:
    """Every analyst key, in display order."""
    return [key for _, key in ANALYST_ORDER]


def parse_analyst_keys(value: str) -> list[str]:
    """Parse a comma-separated --analysts value, rejecting unknown keys."""
    keys = [key.strip() for key in value.split(",") if key.strip()]
    unknown = [key for key in keys if key not in ANALYST_CONFIG]
    if unknown:
        raise ValueError(f"Unknown analyst(s): {', '.join(unknown)}. Available: {', '.join(all_analyst_keys())}")
    if not keys:
        raise ValueError("No analysts given. Pass --analysts-all or a comma-separated list of analyst keys.")
    return keys


def select_analysts_interactively() -> list[str]:
    """Prompt for analysts, exiting the process if the prompt is cancelled."""
    choices = questionary.checkbox(
        "Use the Space bar to select/unselect analysts.",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
        instruction="\n\nPress 'a' to toggle all.\n\nPress Enter when done.",
        validate=lambda selection: len(selection) > 0 or "You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        print("\n\nInterrupt received. Exiting...")
        sys.exit(0)

    print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}")
    return choices


def resolve_selected_analysts(analysts: str | None, analysts_all: bool) -> list[str]:
    """Resolve --analysts / --analysts-all, falling back to the interactive picker.

    The CLI and the backtester share this so the two entry points cannot drift
    into different selection contracts again.
    """
    if analysts_all:
        return all_analyst_keys()
    if analysts:
        return parse_analyst_keys(analysts)
    return select_analysts_interactively()


def add_analyst_arguments(parser) -> None:
    """Add the shared --analysts / --analysts-all flags to an argument parser."""
    parser.add_argument(
        "--analysts",
        type=str,
        required=False,
        help="Comma-separated list of analysts to use (e.g., michael_burry,warren_buffett)",
    )
    parser.add_argument(
        "--analysts-all",
        action="store_true",
        help="Use all available analysts (overrides --analysts)",
    )

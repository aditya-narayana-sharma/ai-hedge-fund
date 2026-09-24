"""Shared LLM selection for the CLI entry points.

The hedge fund and the backtester used to carry identical copies of this
prompt sequence, and neither offered a non-interactive path — which is why the
Docker services all need a TTY.
"""

import sys

import questionary
from colorama import Fore, Style

from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, ModelProvider, get_model_info
from src.utils.ollama import ensure_ollama_and_model

_PROMPT_STYLE = questionary.Style(
    [
        ("selected", "fg:green bold"),
        ("pointer", "fg:green bold"),
        ("highlighted", "fg:green"),
        ("answer", "fg:green bold"),
    ]
)


def add_model_arguments(parser) -> None:
    """Add the shared model-selection flags to an argument parser."""
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local LLM inference")
    parser.add_argument("--model-name", type=str, help="Model name to use, e.g. gpt-4o. Skips the interactive picker")
    parser.add_argument(
        "--model-provider",
        type=str,
        choices=[provider.value for provider in ModelProvider],
        help="Provider for --model-name. Defaults to Ollama with --ollama, otherwise inferred from the catalog",
    )


def resolve_model(args) -> tuple[str, str]:
    """Resolve the model to run with, prompting only when flags are absent.

    Returns ``(model_name, model_provider)``.
    """
    if args.model_name:
        return _resolve_from_flags(args)
    if args.ollama:
        return _prompt_for_ollama_model()
    return _prompt_for_cloud_model()


def _resolve_from_flags(args) -> tuple[str, str]:
    model_name = args.model_name
    provider = args.model_provider or (ModelProvider.OLLAMA.value if args.ollama else None)

    if provider is None:
        model_info = next((model for model in LLM_ORDER if model[1] == model_name), None)
        if model_info is None:
            raise ValueError(f"Unknown model {model_name!r}. Pass --model-provider to use a model outside the catalog.")
        provider = model_info[2]

    if provider == ModelProvider.OLLAMA.value and not ensure_ollama_and_model(model_name):
        raise RuntimeError(f"Ollama is not available for model {model_name!r}.")

    return model_name, provider


def _prompt_for_ollama_model() -> tuple[str, str]:
    print(f"{Fore.CYAN}Using Ollama for local LLM inference.{Style.RESET_ALL}")

    model_name = questionary.select(
        "Select your Ollama model:",
        choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER],
        style=_PROMPT_STYLE,
    ).ask()
    model_name = _require(model_name)

    if model_name == "-":
        model_name = _require(questionary.text("Enter the custom model name:").ask())

    if not ensure_ollama_and_model(model_name):
        print(f"{Fore.RED}Cannot proceed without Ollama and the selected model.{Style.RESET_ALL}")
        sys.exit(1)

    print(f"\nSelected {Fore.CYAN}Ollama{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
    return model_name, ModelProvider.OLLAMA.value


def _prompt_for_cloud_model() -> tuple[str, str]:
    model_choice = questionary.select(
        "Select your LLM model:",
        choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER],
        style=_PROMPT_STYLE,
    ).ask()
    model_name, model_provider = _require(model_choice)

    model_info = get_model_info(model_name, model_provider)
    if model_info is None:
        print(f"\nSelected model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
        return model_name, "Unknown"

    if model_info.is_custom():
        model_name = _require(questionary.text("Enter the custom model name:").ask())

    print(f"\nSelected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
    return model_name, model_provider


def _require(answer):
    """Exit cleanly when a questionary prompt is cancelled."""
    if not answer:
        print("\n\nInterrupt received. Exiting...")
        sys.exit(0)
    return answer

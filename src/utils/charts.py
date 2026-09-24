"""Matplotlib setup that works with or without a display.

``plt.show()`` blocks on an interactive event loop and writes no file, so under
Docker, CI or any headless shell the equity-curve chart produced nothing at all.
Importing this module before ``matplotlib.pyplot`` selects the non-interactive
``Agg`` backend whenever no display is available, and :func:`render_figure`
gives callers one path that saves, shows, or both.
"""

import os
import sys

import matplotlib


def _display_available() -> bool:
    """True when matplotlib can realistically open a window."""
    if os.environ.get("MPLBACKEND"):
        # Respect an explicit operator choice.
        return True
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


if not _display_available():
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)


def is_headless() -> bool:
    """True when the selected backend cannot open a window."""
    return matplotlib.get_backend().lower() in {"agg", "pdf", "ps", "svg", "template"}


def render_figure(output_path: str | None = None) -> str | None:
    """Save the current figure and/or display it.

    Returns the path written, or ``None`` when the figure was only displayed.
    Headless runs always write a file so a container produces an artifact
    rather than silently nothing.
    """
    if output_path is None and is_headless():
        output_path = "backtest_equity_curve.png"

    written = None
    if output_path:
        directory = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(directory, exist_ok=True)
        plt.savefig(output_path, dpi=120, bbox_inches="tight")
        written = output_path
        print(f"Saved chart to {output_path}")

    if not is_headless():
        plt.show()
    else:
        plt.close()

    return written

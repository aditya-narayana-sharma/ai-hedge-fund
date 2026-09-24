"""Agent-graph rendering that does not require a network round-trip.

``MermaidDrawMethod.API`` posts the diagram to mermaid.ink, so ``--show-agent-graph``
failed offline, inside restricted networks, and in CI. Rendering is now attempted
locally first (pyppeteer), then falls back to the hosted renderer, and finally to
writing the Mermaid source next to the requested output so the user still gets
something usable.
"""

from langchain_core.runnables.graph import MermaidDrawMethod
from langgraph.graph.state import CompiledGraph


def save_graph_as_png(app: CompiledGraph, output_file_path: str) -> str:
    """Write the compiled graph to ``output_file_path`` and return the path written."""
    file_path = output_file_path if output_file_path else "graph.png"
    graph = app.get_graph()

    for draw_method in (MermaidDrawMethod.PYPPETEER, MermaidDrawMethod.API):
        try:
            png_image = graph.draw_mermaid_png(draw_method=draw_method)
        except Exception as exc:  # renderer missing, or no network
            print(f"Graph render via {draw_method.value} failed: {exc}")
            continue

        with open(file_path, "wb") as f:
            f.write(png_image)
        return file_path

    # Both renderers are unavailable. The Mermaid source needs neither, and can
    # be pasted into any Mermaid viewer.
    fallback_path = f"{file_path.rsplit('.', 1)[0]}.mmd"
    with open(fallback_path, "w", encoding="utf-8") as f:
        f.write(graph.draw_mermaid())
    print(f"Could not render a PNG. Wrote Mermaid source to {fallback_path} instead.")
    return fallback_path

from langgraph.graph.state import CompiledGraph
from langchain_core.runnables.graph import MermaidDrawMethod


def save_graph_as_png(app: CompiledGraph, output_file_path) -> None:
    """Render the agent graph to PNG, preferring a local renderer.

    ``MermaidDrawMethod.API`` posts the diagram to mermaid.ink, so it fails
    offline and pins a build-time feature to a third-party service. Pyppeteer
    renders locally; the hosted API stays as the fallback.
    """
    file_path = output_file_path if len(output_file_path) > 0 else "graph.png"
    graph = app.get_graph()

    try:
        png_image = graph.draw_mermaid_png(draw_method=MermaidDrawMethod.PYPPETEER)
    except Exception as local_render_error:
        print(f"Local graph rendering unavailable ({local_render_error}); falling back to mermaid.ink.")
        png_image = graph.draw_mermaid_png(draw_method=MermaidDrawMethod.API)

    with open(file_path, "wb") as f:
        f.write(png_image)
    print(f"Agent graph written to {file_path}")

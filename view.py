from __future__ import annotations

from pathlib import Path
import html
import webbrowser

from agents.supervisor import SupervisorAgent
from app_config import settings
from db_layer import SessionLocal


def create_graph_view():
    # Create SupervisorAgent using the SAME project configuration
    # used by main.py / web_app.py.
    supervisor = SupervisorAgent(
        settings=settings,
        session_factory=SessionLocal,
    )

    # Get the actual compiled LangGraph
    mermaid_code = supervisor.graph.get_graph().draw_mermaid()

    # Save Mermaid source
    mmd_file = Path("agent_graph.mmd")
    mmd_file.write_text(
        mermaid_code,
        encoding="utf-8",
    )

    # Create standalone HTML viewer
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Agentic Bill Analyzer - Agent Graph</title>

    <script type="module">
        import mermaid from
        "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

        mermaid.initialize({{
            startOnLoad: true,
            theme: "default",

            flowchart: {{
                curve: "linear",
                useMaxWidth: true,
                htmlLabels: true
            }}
        }});
    </script>

    <style>
        body {{
            margin: 0;
            padding: 30px;

            font-family: Arial, sans-serif;

            background: #f5f5f5;
        }}

        h1 {{
            margin-bottom: 25px;
        }}

        .graph-container {{
            background: white;

            padding: 30px;

            border-radius: 12px;

            box-shadow:
                0 2px 10px rgba(0, 0, 0, 0.1);

            overflow: auto;
        }}
    </style>
</head>

<body>

<h1>Agentic Bill Analyzer - LangGraph Workflow</h1>

<div class="graph-container">

<div class="mermaid">
{html.escape(mermaid_code)}
</div>

</div>

</body>
</html>
"""

    html_file = Path("agent_graph.html")

    html_file.write_text(
        html_content,
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("AGENT GRAPH CREATED")
    print("=" * 60)

    print(
        f"Mermaid : {mmd_file.resolve()}"
    )

    print(
        f"HTML    : {html_file.resolve()}"
    )

    print("=" * 60)

    # Automatically open the graph
    webbrowser.open(
        html_file.resolve().as_uri()
    )


if __name__ == "__main__":
    create_graph_view()
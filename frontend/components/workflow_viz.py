"""Workflow visualization showing agent execution flow as a pipeline/DAG."""

from __future__ import annotations

from typing import Any

import streamlit as st


# Ordered list of agents in the pipeline
AGENT_PIPELINE: list[dict[str, str]] = [
    {"id": "requirement_analyst", "name": "Requirement Analyst", "short": "Req"},
    {"id": "data_discovery", "name": "Data Discovery", "short": "Disc"},
    {"id": "data_architect", "name": "Data Architect", "short": "Arch"},
    {"id": "business_logic", "name": "Business Logic", "short": "Logic"},
    {"id": "sql_developer", "name": "SQL Developer", "short": "SQL"},
    {"id": "yaml_developer", "name": "YAML Developer", "short": "YAML"},
    {"id": "data_quality", "name": "Data Quality", "short": "DQ"},
    {"id": "documentation", "name": "Documentation", "short": "Docs"},
    {"id": "qa_validation", "name": "QA Validation", "short": "QA"},
    {"id": "error_correction", "name": "Error Correction", "short": "Fix"},
    {"id": "packaging", "name": "Packaging", "short": "Pkg"},
]

_STATUS_COLORS: dict[str, str] = {
    "waiting": "#64748b",
    "running": "#3b82f6",
    "completed": "#22c55e",
    "failed": "#ef4444",
    "error": "#ef4444",
    "requires_approval": "#eab308",
}


def _build_graphviz_source(agent_statuses: dict[str, str]) -> str:
    """Build a Graphviz DOT source string for the agent pipeline.

    Args:
        agent_statuses: Dict mapping agent_id → status string.

    Returns:
        DOT format string.
    """
    lines: list[str] = [
        "digraph agent_pipeline {",
        '    rankdir=LR;',
        '    bgcolor="transparent";',
        '    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.3,0.15"];',
        '    edge [color="#475569", arrowsize=0.7];',
        "",
    ]

    for agent in AGENT_PIPELINE:
        agent_id = agent["id"]
        status = agent_statuses.get(agent_id, "waiting")
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["waiting"])
        font_color = "#ffffff" if status != "waiting" else "#e2e8f0"
        label = agent["name"]

        lines.append(
            f'    {agent_id} [label="{label}", fillcolor="{color}", '
            f'fontcolor="{font_color}"];'
        )

    lines.append("")

    # Edges — linear pipeline with branch for error correction
    for i in range(len(AGENT_PIPELINE) - 3):  # Up to QA
        lines.append(f"    {AGENT_PIPELINE[i]['id']} -> {AGENT_PIPELINE[i+1]['id']};")

    # QA → error_correction (on failure) or packaging (on success)
    lines.append('    qa_validation -> error_correction [label="fail", fontsize=9, fontcolor="#ef4444"];')
    lines.append('    qa_validation -> packaging [label="pass", fontsize=9, fontcolor="#22c55e"];')
    lines.append('    error_correction -> qa_validation [label="retry", fontsize=9, fontcolor="#eab308", style=dashed];')

    lines.append("}")
    return "\n".join(lines)


def render_workflow_viz(
    agent_statuses: dict[str, str] | None = None,
    title: str = "Agent Execution Pipeline",
) -> None:
    """Render the workflow visualization.

    Args:
        agent_statuses: Dict mapping agent_id → status string.
            Keys should match AGENT_PIPELINE ids.
        title: Section title.
    """
    st.markdown(f'<div class="section-header">🔄 {title}</div>', unsafe_allow_html=True)

    if agent_statuses is None:
        agent_statuses = {}

    dot_source = _build_graphviz_source(agent_statuses)

    try:
        st.graphviz_chart(dot_source, use_container_width=True)
    except Exception:
        # Fallback to text-based representation
        st.markdown("**Pipeline Flow:**")
        _render_text_pipeline(agent_statuses)

    # Status legend
    st.markdown("---")
    cols = st.columns(5)
    legends = [
        ("⏳ Waiting", "#64748b"),
        ("🔄 Running", "#3b82f6"),
        ("✅ Completed", "#22c55e"),
        ("❌ Failed", "#ef4444"),
        ("⚠️ Approval", "#eab308"),
    ]
    for col, (label, color) in zip(cols, legends):
        col.markdown(
            f'<span style="color:{color};font-size:0.8rem;font-weight:500;">{label}</span>',
            unsafe_allow_html=True,
        )


def _render_text_pipeline(agent_statuses: dict[str, str]) -> None:
    """Fallback text-based pipeline rendering."""
    status_icons = {
        "waiting": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "error": "❌",
        "requires_approval": "⚠️",
    }

    parts: list[str] = []
    for agent in AGENT_PIPELINE:
        status = agent_statuses.get(agent["id"], "waiting")
        icon = status_icons.get(status, "⏳")
        parts.append(f"{icon} {agent['short']}")

    st.markdown(" → ".join(parts))


def render_progress_bar(agent_statuses: dict[str, str]) -> None:
    """Render an overall progress bar based on agent statuses.

    Args:
        agent_statuses: Dict mapping agent_id → status string.
    """
    total = len(AGENT_PIPELINE)
    completed = sum(
        1
        for a in AGENT_PIPELINE
        if agent_statuses.get(a["id"]) == "completed"
    )
    running = sum(
        1
        for a in AGENT_PIPELINE
        if agent_statuses.get(a["id"]) == "running"
    )
    failed = sum(
        1
        for a in AGENT_PIPELINE
        if agent_statuses.get(a["id"]) in ("failed", "error")
    )

    progress = completed / total if total > 0 else 0.0
    st.progress(progress, text=f"Progress: {completed}/{total} agents completed"
                f"{f' | {running} running' if running else ''}"
                f"{f' | {failed} failed' if failed else ''}")

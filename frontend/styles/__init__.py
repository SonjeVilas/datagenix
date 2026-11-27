"""Style loader for the Datagenix dashboard."""

import os
import streamlit as st


def load_custom_css() -> None:
    """Load and inject custom CSS into the Streamlit app."""
    css_path = os.path.join(os.path.dirname(__file__), "custom.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("Custom CSS file not found. Using default styles.")


def inject_metric_card(label: str, value: str | int, delta: str = "", color: str = "blue") -> None:
    """Render a styled metric card using custom HTML."""
    color_map = {
        "blue": "#3b82f6",
        "green": "#22c55e",
        "red": "#ef4444",
        "yellow": "#eab308",
        "purple": "#8b5cf6",
    }
    accent = color_map.get(color, color_map["blue"])
    delta_html = f'<div style="font-size:0.75rem;color:{accent};margin-top:0.25rem;">{delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="metric-card" style="border-left: 3px solid {accent};">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

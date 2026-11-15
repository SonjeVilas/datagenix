"""SQL and YAML code viewer with syntax highlighting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st


_LANG_MAP: dict[str, str] = {
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".py": "python",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".csv": "text",
    ".toml": "toml",
    ".cfg": "ini",
    ".ini": "ini",
}


def _detect_language(filename: str) -> str:
    """Detect the code language from file extension."""
    suffix = Path(filename).suffix.lower()
    return _LANG_MAP.get(suffix, "text")


def render_code_viewer(
    files: dict[str, str],
    title: str = "Code Viewer",
    editable: bool = False,
    key_prefix: str = "code_viewer",
) -> dict[str, str] | None:
    """Render a code viewer with file selector sidebar.

    Args:
        files: Mapping of filename/path → file content.
        title: Section title.
        editable: Whether to show an edit text area below the code.
        key_prefix: Unique key prefix for Streamlit widgets.

    Returns:
        Updated files dict if editable and changes were saved, else None.
    """
    if not files:
        st.info("No files to display.", icon="📂")
        return None

    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

    file_list = sorted(files.keys())

    # File selector
    selected_file = st.selectbox(
        "Select file",
        options=file_list,
        format_func=lambda x: f"📄 {x}",
        key=f"{key_prefix}_selector",
    )

    if selected_file is None:
        return None

    content = files[selected_file]
    language = _detect_language(selected_file)

    # Header bar
    st.markdown(
        f"""
        <div class="code-container">
            <div class="code-header">
                <span class="file-name">{selected_file}</span>
                <span class="file-type">{language.upper()} · {len(content.splitlines())} lines</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Code display
    st.code(content, language=language, line_numbers=True)

    # Editable mode
    if editable:
        updated_files = dict(files)
        st.markdown("---")
        st.markdown("**✏️ Edit Mode**")
        edited_content = st.text_area(
            "Edit content",
            value=content,
            height=400,
            key=f"{key_prefix}_editor_{selected_file}",
            label_visibility="collapsed",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Changes", key=f"{key_prefix}_save_{selected_file}"):
                updated_files[selected_file] = edited_content
                st.success(f"Saved changes to {selected_file}")
                return updated_files
        with col2:
            if st.button("↩️ Revert", key=f"{key_prefix}_revert_{selected_file}"):
                st.info("Reverted to original content.")

    return None


def render_single_file(
    filename: str,
    content: str,
    editable: bool = False,
    key_prefix: str = "single_file",
) -> str | None:
    """Render a single file with optional editing.

    Args:
        filename: The file name/path.
        content: File content string.
        editable: Whether to allow editing.
        key_prefix: Unique key prefix.

    Returns:
        Updated content string if saved, else None.
    """
    language = _detect_language(filename)

    st.markdown(
        f"""
        <div class="code-container">
            <div class="code-header">
                <span class="file-name">{filename}</span>
                <span class="file-type">{language.upper()} · {len(content.splitlines())} lines</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.code(content, language=language, line_numbers=True)

    if editable:
        edited = st.text_area(
            f"Edit {filename}",
            value=content,
            height=350,
            key=f"{key_prefix}_edit_{filename}",
            label_visibility="collapsed",
        )
        if st.button("💾 Save", key=f"{key_prefix}_save_{filename}"):
            st.success(f"Saved {filename}")
            return edited

    return None

"""Directory tree viewer component for browsing generated dbt projects."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import streamlit as st


_ICON_MAP: dict[str, str] = {
    ".sql": "📊",
    ".yml": "📋",
    ".yaml": "📋",
    ".py": "🐍",
    ".md": "📝",
    ".txt": "📄",
    ".json": "📦",
    ".csv": "📈",
    ".toml": "⚙️",
    ".gitkeep": "📌",
}


def _get_file_icon(filename: str) -> str:
    """Get an icon for a file based on extension."""
    suffix = Path(filename).suffix.lower()
    return _ICON_MAP.get(suffix, "📄")


def _build_tree(root_path: str) -> dict[str, Any]:
    """Build a nested directory tree structure from a filesystem path.

    Returns a dict like:
    {
        "name": "project",
        "type": "dir",
        "path": "/abs/path",
        "children": [...]
    }
    """
    root = Path(root_path)
    if not root.exists():
        return {"name": root.name, "type": "dir", "path": str(root), "children": []}

    def _walk(p: Path) -> dict[str, Any]:
        if p.is_file():
            return {
                "name": p.name,
                "type": "file",
                "path": str(p),
                "size": p.stat().st_size,
            }
        children = []
        try:
            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith(".") or entry.name == "__pycache__":
                    continue
                children.append(_walk(entry))
        except PermissionError:
            pass
        return {
            "name": p.name,
            "type": "dir",
            "path": str(p),
            "children": children,
        }

    return _walk(root)


def _build_tree_from_dict(files: dict[str, str], root_name: str = "project") -> dict[str, Any]:
    """Build a tree structure from a dict of {relative_path: content}."""
    tree: dict[str, Any] = {"name": root_name, "type": "dir", "path": "", "children": []}
    dirs: dict[str, dict[str, Any]] = {"": tree}

    for filepath in sorted(files.keys()):
        parts = Path(filepath).parts
        current_path = ""
        parent_node = tree

        for i, part in enumerate(parts[:-1]):
            current_path = str(Path(current_path) / part) if current_path else part
            if current_path not in dirs:
                new_dir: dict[str, Any] = {
                    "name": part,
                    "type": "dir",
                    "path": current_path,
                    "children": [],
                }
                parent_node["children"].append(new_dir)
                dirs[current_path] = new_dir
            parent_node = dirs[current_path]

        # Add file node
        file_node: dict[str, Any] = {
            "name": parts[-1],
            "type": "file",
            "path": filepath,
            "size": len(files[filepath].encode("utf-8")),
        }
        parent_node["children"].append(file_node)

    return tree


def render_project_tree(
    root_path: str | None = None,
    files: dict[str, str] | None = None,
    project_name: str = "project",
    key_prefix: str = "tree",
) -> str | None:
    """Render a project directory tree and return the selected file path.

    Provide either root_path (for filesystem) or files dict (for in-memory).

    Args:
        root_path: Filesystem path to the project root.
        files: Dict of {relative_path: content} for in-memory tree.
        project_name: Display name for the root.
        key_prefix: Unique key prefix for widgets.

    Returns:
        The selected file's path, or None if nothing selected.
    """
    if root_path:
        tree = _build_tree(root_path)
    elif files:
        tree = _build_tree_from_dict(files, root_name=project_name)
    else:
        st.info("No project to display.", icon="📂")
        return None

    st.markdown(f'<div class="section-header">📁 {project_name}</div>', unsafe_allow_html=True)

    selected = _render_node(tree, key_prefix=key_prefix, depth=0)

    return selected


def _render_node(
    node: dict[str, Any],
    key_prefix: str,
    depth: int = 0,
) -> str | None:
    """Recursively render a tree node. Returns selected file path or None."""
    selected: str | None = None
    indent = "&nbsp;" * (depth * 4)

    if node["type"] == "dir":
        children = node.get("children", [])
        if not children and depth > 0:
            return None

        label = f"📁 {node['name']}/" if depth > 0 else f"📁 {node['name']}"
        with st.expander(label, expanded=(depth < 2)):
            for child in children:
                result = _render_node(child, key_prefix=key_prefix, depth=depth + 1)
                if result is not None:
                    selected = result
    else:
        icon = _get_file_icon(node["name"])
        size_kb = node.get("size", 0) / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{node.get('size', 0)} B"
        btn_key = f"{key_prefix}_{node['path'].replace('/', '_').replace(os.sep, '_')}"

        if st.button(
            f"{icon} {node['name']} ({size_str})",
            key=btn_key,
            use_container_width=True,
        ):
            selected = node["path"]
            st.session_state[f"{key_prefix}_selected_file"] = node["path"]

    # Check if there was a selection stored in session state
    if selected is None:
        selected = st.session_state.get(f"{key_prefix}_selected_file")

    return selected

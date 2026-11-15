"""Packaging Agent — assembles and archives the final dbt project."""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent
from backend.file_manager import FileManager

logger = logging.getLogger(__name__)

# Default requirements for a generated dbt project
_DEFAULT_DBT_REQUIREMENTS = [
    "dbt-core>=1.7,<2.0",
    "dbt-snowflake>=1.7,<2.0",
    "dbt-utils>=1.1,<2.0",
]


class PackagingAgent(BaseAgent):
    """Creates the final deliverable dbt project package.

    Responsibilities:
    * Verify that all expected artefact categories are present in state.
    * Lay out the canonical dbt directory structure.
    * Generate a top-level ``README.md`` with setup instructions.
    * Generate a ``requirements.txt`` for Python / dbt dependencies.
    * Write every file to disk via :class:`FileManager`.
    * Create a ``.zip`` archive of the project for easy download.
    """

    def __init__(self) -> None:
        super().__init__(
            name="packaging",
            description=(
                "Assembles all generated artefacts into a final dbt project "
                "directory, writes files to disk, and creates a ZIP archive."
            ),
            system_prompt=(
                "You are a DevOps-oriented dbt project packager.  You receive "
                "a fully validated set of SQL models, YAML configs, tests, "
                "and documentation for a dbt project.  Your job is to combine "
                "them into a clean, ready-to-run dbt project that a data team "
                "can unzip and immediately start using.\n\n"
                "You must:\n"
                "1. Verify every expected artefact category (models, YAML, "
                "tests, docs) has content.\n"
                "2. Generate a professional README.md with: project overview, "
                "directory structure, prerequisites, setup instructions, how "
                "to run, testing guide, and contribution notes.\n"
                "3. Generate a requirements.txt listing dbt-core, the "
                "warehouse adapter, and any dbt packages used.\n"
                "4. Organise files into the standard dbt layout.\n\n"
                "Return a JSON object with:\n"
                "- ``readme``: the full README.md content string.\n"
                "- ``requirements``: the full requirements.txt content string.\n"
                "- ``directory_structure``: a list of all relative paths.\n"
                "- ``manifest``: a summary object with file counts by category."
            ),
        )
        self.file_manager: FileManager | None = None

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Package the dbt project and write it to disk."""
        self._update_agent_status(state, "running", "Packaging dbt project")
        logger.info("PackagingAgent starting")

        try:
            project_name: str = state.get("project_name", "dbt_project")
            existing_path: str = state.get("project_output_path", "")
            if existing_path and os.path.basename(os.path.normpath(existing_path)) == project_name:
                project_dir = existing_path
            else:
                output_base: str = "generated_projects"
                project_dir = os.path.join(output_base, project_name)

            # Initialise FileManager
            self.file_manager = FileManager(base_dir=project_dir)

            # ---- Collect artefacts ----
            artefacts: dict[str, dict[str, str]] = {
                "generated_models": state.get("generated_models", {}),
                "generated_yaml": state.get("generated_yaml", {}),
                "generated_tests": state.get("generated_tests", {}),
                "generated_docs": state.get("generated_docs", {}),
            }

            # ---- Verify completeness ----
            missing = self._verify_artefacts(artefacts)
            if missing:
                logger.warning("Missing artefact categories: %s", missing)
                state.setdefault("warnings", []).append(
                    {
                        "agent": self.name,
                        "message": f"Missing artefact categories: {missing}",
                    }
                )

            # ---- Generate supplementary files via Gemini ----
            supplement = self._generate_supplements(state, artefacts)
            readme_content: str = supplement.get("readme", self._fallback_readme(project_name))
            requirements_content: str = supplement.get(
                "requirements", "\n".join(_DEFAULT_DBT_REQUIREMENTS) + "\n"
            )

            # ---- Write files to disk ----
            written_files: list[str] = []

            # Write README.md
            self.file_manager.write_file("README.md", readme_content)
            written_files.append("README.md")

            # Write requirements.txt
            self.file_manager.write_file("requirements.txt", requirements_content)
            written_files.append("requirements.txt")

            # Write all artefact files
            for _category, files in artefacts.items():
                for rel_path, content in files.items():
                    self.file_manager.write_file(rel_path, content)
                    written_files.append(rel_path)

            # Ensure profiles.yml is written for immediate dbt CLI execution
            if "profiles.yml" not in written_files:
                try:
                    from config.settings import get_settings
                    s = get_settings()
                    pwd = s.snowflake_password.get_secret_value() if hasattr(s.snowflake_password, 'get_secret_value') else str(s.snowflake_password)
                    prof_content = (
                        f"{project_name}:\n"
                        f"  target: dev\n"
                        f"  outputs:\n"
                        f"    dev:\n"
                        f"      type: snowflake\n"
                        f"      account: {s.snowflake_account}\n"
                        f"      user: {s.snowflake_user}\n"
                        f"      password: '{pwd}'\n"
                        f"      role: {s.snowflake_role or 'ACCOUNTADMIN'}\n"
                        f"      database: {s.snowflake_database or 'ECOM_DB'}\n"
                        f"      warehouse: {s.snowflake_warehouse or 'COMPUTE_WH'}\n"
                        f"      schema: {s.snowflake_schema or 'RAW'}\n"
                        f"      threads: 4\n"
                        f"      client_session_keep_alive: false\n"
                    )
                    self.file_manager.write_file("profiles.yml", prof_content)
                    written_files.append("profiles.yml")
                except Exception as e:
                    logger.warning("Could not write profiles.yml: %s", e)

            # ---- Create ZIP archive ----
            zip_dir = os.path.dirname(os.path.normpath(project_dir)) or "generated_projects"
            zip_path = os.path.join(zip_dir, f"{project_name}.zip")
            self._create_zip(project_dir, zip_path, written_files, artefacts, readme_content, requirements_content)

            # ---- Build manifest ----
            manifest: dict[str, Any] = {
                "project_name": project_name,
                "output_directory": project_dir,
                "zip_archive": zip_path,
                "total_files": len(written_files),
                "categories": {
                    cat: len(files) for cat, files in artefacts.items()
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            state["packaging_result"] = manifest
            state["project_output_path"] = project_dir

            status_msg = (
                f"Packaged {len(written_files)} file(s) into {project_dir} "
                f"and created {zip_path}"
            )
            logger.info(status_msg)
            self._update_agent_status(state, "completed", status_msg)

        except Exception as exc:
            logger.exception("PackagingAgent failed: %s", exc)
            self._update_agent_status(state, "error", str(exc))
            state.setdefault("errors", []).append(
                {
                    "agent": self.name,
                    "error": str(exc),
                    "phase": "packaging",
                }
            )

        return state

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _verify_artefacts(
        artefacts: dict[str, dict[str, str]],
    ) -> list[str]:
        """Return names of artefact categories that are empty."""
        return [cat for cat, files in artefacts.items() if not files]

    def _generate_supplements(
        self,
        state: dict[str, Any],
        artefacts: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """Ask Gemini for README and requirements.txt content."""
        project_name = state.get("project_name", "dbt_project")
        project_description = state.get("project_description", "")

        file_list = []
        for _cat, files in artefacts.items():
            file_list.extend(files.keys())

        prompt_parts: list[str] = [
            f"Generate a README.md and requirements.txt for the dbt project "
            f"**{project_name}**.\n",
            f"Description: {project_description}\n",
            "## Files in the project\n"
            f"```json\n{json.dumps(sorted(file_list), indent=2)}\n```\n",
        ]

        architecture = state.get("architecture", {})
        if architecture:
            prompt_parts.append(
                "## Architecture\n"
                f"```json\n{json.dumps(architecture, indent=2, default=str)}\n```\n"
            )

        prompt_parts.append(
            "Return JSON with `readme` (full markdown string) and "
            "`requirements` (full requirements.txt string) and "
            "`directory_structure` (list of paths) and "
            "`manifest` (summary object with file counts)."
        )

        try:
            return self._call_gemini_json("\n".join(prompt_parts))
        except Exception as exc:
            logger.warning("Gemini supplement generation failed: %s", exc)
            return {}

    def _create_zip(
        self,
        project_dir: str,
        zip_path: str,
        written_files: list[str],
        artefacts: dict[str, dict[str, str]],
        readme_content: str,
        requirements_content: str,
    ) -> None:
        """Create a ZIP archive of the project."""
        project_name = os.path.basename(project_dir)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(zip_path) or ".", exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            seen_entries: set[str] = set()

            def _add_to_zip(arc_path: str, data: str) -> None:
                clean_arc = arc_path.replace("\\", "/").strip("/")
                if clean_arc not in seen_entries:
                    zf.writestr(clean_arc, data)
                    seen_entries.add(clean_arc)

            # Add README and requirements
            _add_to_zip(f"{project_name}/README.md", readme_content)
            _add_to_zip(f"{project_name}/requirements.txt", requirements_content)

            # Add all artefact files
            for _category, files in artefacts.items():
                for rel_path, content in files.items():
                    _add_to_zip(f"{project_name}/{rel_path}", content)

        logger.info("Created ZIP archive: %s", zip_path)

    @staticmethod
    def _fallback_readme(project_name: str) -> str:
        """Return a minimal README when Gemini is unavailable."""
        return (
            f"# {project_name}\n\n"
            "A dbt project generated by the AI-Powered Multi-Agent dbt "
            "Project Factory.\n\n"
            "## Setup\n\n"
            "1. Install dependencies: `pip install -r requirements.txt`\n"
            "2. Configure your `profiles.yml` for your Snowflake connection.\n"
            "3. Run `dbt deps` to install dbt packages.\n"
            "4. Run `dbt build` to build and test all models.\n\n"
            "## Directory Structure\n\n"
            "```\n"
            "models/\n"
            "  staging/       — Source-aligned 1:1 transformations\n"
            "  intermediate/  — Business logic joins and aggregations\n"
            "  marts/         — Final consumption-layer models\n"
            "tests/           — Custom data tests\n"
            "macros/          — Reusable Jinja macros\n"
            "```\n"
        )

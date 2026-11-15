"""Documentation Agent — generates model docs, column docs, README, and lineage."""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DocumentationAgent(BaseAgent):
    """Produces comprehensive dbt documentation artefacts.

    Generates:
    * Per-model description blocks and column-level documentation.
    * A project-level ``README.md`` with setup instructions, model
      overview, and DAG description.
    * Lineage explanations that describe how data flows from sources
      through staging, intermediate, and mart layers.

    All outputs are stored in ``state["generated_docs"]`` as a dict
    mapping relative file paths to their string content.
    """

    def __init__(self) -> None:
        super().__init__(
            name="documentation",
            description=(
                "Generates model documentation, column descriptions, README, "
                "and data-lineage explanations for the dbt project."
            ),
            system_prompt=(
                "You are a senior analytics-engineering technical writer.  "
                "Your mission is to produce clear, thorough, and accurate "
                "documentation for a dbt project.\n\n"
                "For every model you receive, generate:\n"
                "1. A concise but informative model-level description that "
                "explains the business purpose, grain, and key relationships.\n"
                "2. Column-level descriptions for every column — include data "
                "type, business meaning, allowed values, and any caveats.\n"
                "3. A project README.md that includes: project overview, "
                "prerequisites, setup instructions, model layer descriptions "
                "(staging / intermediate / mart), a high-level DAG summary, "
                "and contribution guidelines.\n"
                "4. A lineage narrative (lineage.md) that traces the data flow "
                "from raw sources to final mart models, explaining what each "
                "transformation layer does and why.\n\n"
                "Return a JSON object whose keys are relative file paths and "
                "whose values are the full file-content strings.  For model "
                "and column descriptions, merge them into the appropriate "
                "schema YAML files (e.g. models/staging/schema.yml).  For "
                "README and lineage, use markdown files at the project root.\n\n"
                "Guidelines:\n"
                "• Write for an audience of data analysts and analytics "
                "engineers who are new to the project.\n"
                "• Use consistent formatting — headings, bullet points, code "
                "blocks for column references.\n"
                "• Never fabricate column names or models; use only what is "
                "provided in the context.\n"
                "• If information is ambiguous, note the assumption you made."
            ),
        )

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Generate documentation artefacts and store them in state."""
        self._update_agent_status(state, "running", "Generating documentation")
        logger.info("DocumentationAgent starting")

        try:
            # ---- Collect context ----
            source_catalog: dict[str, Any] = state.get("source_catalog", {})
            generated_models: dict[str, str] = state.get("generated_models", {})
            generated_yaml: dict[str, str] = state.get("generated_yaml", {})
            generated_tests: dict[str, str] = state.get("generated_tests", {})
            architecture: dict[str, Any] = state.get("architecture", {})
            business_logic: dict[str, Any] = state.get("business_logic", {})
            project_spec: dict[str, Any] = state.get("project_specification", {})
            project_name: str = state.get("project_name", "dbt_project")
            project_description: str = state.get(
                "project_description", "A dbt project."
            )

            # ---- Build prompt ----
            prompt = self._build_prompt(
                project_name=project_name,
                project_description=project_description,
                source_catalog=source_catalog,
                generated_models=generated_models,
                generated_yaml=generated_yaml,
                generated_tests=generated_tests,
                architecture=architecture,
                business_logic=business_logic,
                project_spec=project_spec,
            )

            # ---- Call Gemini ----
            logger.info("Calling Gemini for documentation generation")
            response: dict[str, Any] = self._call_gemini_json(prompt)

            # ---- Validate & normalise ----
            generated_docs = self._validate_and_normalise(response)

            # ---- Merge into state ----
            if "generated_docs" not in state:
                state["generated_docs"] = {}
            state["generated_docs"].update(generated_docs)

            logger.info(
                "DocumentationAgent produced %d doc file(s)",
                len(generated_docs),
            )
            self._update_agent_status(
                state,
                "completed",
                f"Generated {len(generated_docs)} documentation file(s)",
            )

        except Exception as exc:
            logger.exception("DocumentationAgent failed: %s", exc)
            self._update_agent_status(state, "error", str(exc))
            state.setdefault("errors", []).append(
                {
                    "agent": self.name,
                    "error": str(exc),
                    "phase": "documentation_generation",
                }
            )

        return state

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        *,
        project_name: str,
        project_description: str,
        source_catalog: dict[str, Any],
        generated_models: dict[str, str],
        generated_yaml: dict[str, str],
        generated_tests: dict[str, str],
        architecture: dict[str, Any],
        business_logic: dict[str, Any],
        project_spec: dict[str, Any],
    ) -> str:
        parts: list[str] = [
            f"Generate documentation for the dbt project **{project_name}**.\n",
            f"Project description: {project_description}\n",
        ]

        if project_spec:
            parts.append(
                "## Project Specification\n"
                f"```json\n{json.dumps(project_spec, indent=2, default=str)}\n```\n"
            )

        if source_catalog:
            parts.append(
                "## Source Catalog\n"
                f"```json\n{json.dumps(source_catalog, indent=2, default=str)}\n```\n"
            )

        if architecture:
            parts.append(
                "## Architecture\n"
                f"```json\n{json.dumps(architecture, indent=2, default=str)}\n```\n"
            )

        if business_logic:
            parts.append(
                "## Business Logic\n"
                f"```json\n{json.dumps(business_logic, indent=2, default=str)}\n```\n"
            )

        if generated_models:
            parts.append("## Generated SQL Models\n")
            for path, sql in generated_models.items():
                parts.append(f"### `{path}`\n```sql\n{sql}\n```\n")

        if generated_yaml:
            parts.append("## Existing YAML Configs\n")
            for path, content in generated_yaml.items():
                parts.append(f"### `{path}`\n```yaml\n{content}\n```\n")

        if generated_tests:
            parts.append("## Generated Tests\n")
            for path, content in generated_tests.items():
                parts.append(f"### `{path}`\n```yaml\n{content}\n```\n")

        parts.append(
            "Return a JSON object: keys = relative file paths, values = full "
            "file content strings.\n"
            "Required outputs:\n"
            "1. Schema YAML files with model & column descriptions added.\n"
            "2. `README.md` (project root) — overview, setup, model layers, DAG.\n"
            "3. `docs/lineage.md` — data lineage narrative.\n"
        )

        return "\n".join(parts)

    @staticmethod
    def _validate_and_normalise(response: dict[str, Any]) -> dict[str, str]:
        """Ensure response is ``{path: content_str, …}``."""
        if not isinstance(response, dict):
            raise ValueError(
                f"Expected dict from Gemini, got {type(response).__name__}"
            )

        normalised: dict[str, str] = {}
        for path, content in response.items():
            if not isinstance(path, str):
                logger.warning("Skipping non-string key: %r", path)
                continue
            if isinstance(content, dict):
                import yaml

                content = yaml.dump(content, default_flow_style=False, sort_keys=False)
            if not isinstance(content, str):
                content = str(content)
            normalised[path] = content

        return normalised

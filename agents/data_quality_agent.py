"""Data Quality Agent — generates dbt tests (generic + dbt_utils) from metadata."""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DataQualityAgent(BaseAgent):
    """Generates comprehensive dbt test definitions for every model layer.

    The agent inspects the project's source catalog, generated models, and
    architecture metadata to decide which generic tests (unique, not_null,
    relationships, accepted_values) and which ``dbt_utils`` tests
    (e.g. expression_is_true, recency, unique_combination_of_columns) are
    appropriate for each column.  It produces YAML test definitions stored
    in ``state["generated_tests"]`` keyed by relative path.
    """

    def __init__(self) -> None:
        super().__init__(
            name="data_quality",
            description=(
                "Generates dbt generic tests and dbt_utils tests for every "
                "model based on source metadata, column types, and business rules."
            ),
            system_prompt=(
                "You are an expert dbt data-quality engineer.  Your sole job is "
                "to generate comprehensive, production-grade dbt test definitions "
                "for a dbt project.\n\n"
                "For every model you are given, analyse its columns, data types, "
                "relationships, and business context to decide which tests are "
                "appropriate.  Apply the following rules:\n"
                "• Every primary-key column MUST have `unique` and `not_null` tests.\n"
                "• Every foreign-key column MUST have a `relationships` test pointing "
                "to the referenced model and column.\n"
                "• Columns whose name or description implies a fixed domain (e.g. "
                "status, type, category) SHOULD receive an `accepted_values` test "
                "with realistic sample values.\n"
                "• Timestamp columns SHOULD receive `not_null` tests; fact-table "
                "date columns SHOULD receive `dbt_utils.recency` tests.\n"
                "• Composite keys SHOULD receive `dbt_utils.unique_combination_of_columns`.\n"
                "• Numeric columns that have known business constraints (e.g. "
                "quantity > 0, discount between 0 and 1) SHOULD receive "
                "`dbt_utils.expression_is_true` tests.\n"
                "• Do NOT generate tests that are irrelevant to the column type or "
                "business context.\n\n"
                "Return your output as a JSON object whose keys are relative file "
                "paths (e.g. `models/staging/schema.yml`) and whose values are the "
                "full YAML content string for that file's test section.  Each YAML "
                "value must be valid dbt schema YAML with a top-level `models` key "
                "containing the model name, columns, and their tests."
            ),
        )

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Generate dbt test definitions and store them in state."""
        self._update_agent_status(state, "running", "Generating data-quality tests")
        logger.info("DataQualityAgent starting test generation")

        try:
            # ----- Gather context from state -----
            source_catalog: dict[str, Any] = state.get("source_catalog", {})
            generated_models: dict[str, str] = state.get("generated_models", {})
            generated_yaml: dict[str, str] = state.get("generated_yaml", {})
            architecture: dict[str, Any] = state.get("architecture", {})
            business_logic: dict[str, Any] = state.get("business_logic", {})

            # ----- Build the prompt -----
            prompt = self._build_prompt(
                source_catalog, generated_models, generated_yaml,
                architecture, business_logic,
            )

            # ----- Call Gemini for test generation -----
            logger.info("Calling Gemini to generate test definitions")
            response: dict[str, Any] = self._call_gemini_json(prompt)

            # ----- Validate response structure -----
            generated_tests = self._validate_and_normalise(response)

            # ----- Merge into state -----
            if "generated_tests" not in state:
                state["generated_tests"] = {}
            state["generated_tests"].update(generated_tests)

            logger.info(
                "DataQualityAgent generated tests for %d file(s)",
                len(generated_tests),
            )
            self._update_agent_status(
                state,
                "completed",
                f"Generated tests for {len(generated_tests)} file(s)",
            )

        except Exception as exc:
            logger.exception("DataQualityAgent failed: %s", exc)
            self._update_agent_status(state, "error", str(exc))
            state.setdefault("errors", []).append(
                {
                    "agent": self.name,
                    "error": str(exc),
                    "phase": "test_generation",
                }
            )

        return state

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        source_catalog: dict[str, Any],
        generated_models: dict[str, str],
        generated_yaml: dict[str, str],
        architecture: dict[str, Any],
        business_logic: dict[str, Any],
    ) -> str:
        """Compose the Gemini prompt from state data."""
        sections: list[str] = [
            "Generate comprehensive dbt test definitions for the following "
            "dbt project.  Return a single JSON object mapping relative file "
            "paths to their full YAML content string.\n",
        ]

        if source_catalog:
            sections.append(
                "## Source Catalog (tables, columns, types, keys)\n"
                f"```json\n{json.dumps(source_catalog, indent=2, default=str)}\n```\n"
            )

        if architecture:
            sections.append(
                "## Architecture (layers, model graph)\n"
                f"```json\n{json.dumps(architecture, indent=2, default=str)}\n```\n"
            )

        if business_logic:
            sections.append(
                "## Business Logic & Rules\n"
                f"```json\n{json.dumps(business_logic, indent=2, default=str)}\n```\n"
            )

        if generated_models:
            model_summary: dict[str, str] = {}
            for path, sql in generated_models.items():
                # Only send first 120 chars of each SQL to keep prompt small
                model_summary[path] = sql[:120] + ("…" if len(sql) > 120 else "")
            sections.append(
                "## Generated SQL Models (path → first 120 chars)\n"
                f"```json\n{json.dumps(model_summary, indent=2)}\n```\n"
            )

        if generated_yaml:
            sections.append(
                "## Existing YAML Configs (path → content)\n"
                f"```json\n{json.dumps(generated_yaml, indent=2, default=str)}\n```\n"
            )

        sections.append(
            "Rules for generating tests:\n"
            "1. Every PK column → unique + not_null (standard dbt tests).\n"
            "2. Every FK column → relationships test (standard dbt test).\n"
            "3. Status/type/category → accepted_values (standard dbt test).\n"
            "4. Timestamp/date columns → not_null.\n"
            "5. Prefer standard native dbt tests (unique, not_null, accepted_values, relationships) so the project compiles cleanly out-of-the-box.\n"
            "6. Do NOT add irrelevant tests.\n"
            "7. Output JSON: keys are relative paths, values are full YAML strings.\n"
        )

        return "\n".join(sections)

    @staticmethod
    def _validate_and_normalise(response: dict[str, Any]) -> dict[str, str]:
        """Ensure the Gemini response is ``{path: yaml_str, …}``."""
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
                # Gemini sometimes returns parsed YAML as dict; dump back
                import yaml  # local import to keep module lightweight

                content = yaml.dump(content, default_flow_style=False, sort_keys=False)
            if not isinstance(content, str):
                content = str(content)
            normalised[path] = content

        return normalised

"""
YAML Developer Agent for dbt Project Factory.

Generates all YAML configuration files required by a dbt project:
dbt_project.yml, sources.yml, schema.yml per layer, packages.yml, and
profiles.yml.example. Outputs a dict mapping relative file paths to YAML
content strings.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class GeneratedYAMLFile(BaseModel):
    file_path: str = Field(..., description="Relative path, e.g. dbt_project.yml or models/staging/sources.yml")
    file_type: str = Field(
        ...,
        description="dbt_project | sources | schema | packages | profiles | properties",
    )
    content: str = Field(..., description="Full YAML content of the file")
    description: Optional[str] = Field(default="")

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class GeneratedYAMLResponse(BaseModel):
    files: list[GeneratedYAMLFile] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class YAMLDeveloperAgent(BaseAgent):
    """Generates all YAML configuration files for a dbt project."""

    def __init__(self) -> None:
        super().__init__(
            name="yaml_developer",
            description=(
                "Generates all dbt YAML configuration files including dbt_project.yml, "
                "sources, schema definitions, packages, and profiles."
            ),
            system_prompt=(
                "You are a dbt YAML configuration specialist. You produce complete, "
                "production-ready YAML files for dbt projects following the latest dbt "
                "conventions (dbt Core 1.7+ / dbt Cloud).\n\n"
                "You must generate the following files:\n\n"
                "1. **dbt_project.yml** — Project configuration with:\n"
                "   - name, version, config-version: 2, profile\n"
                "   - model-paths, analysis-paths, test-paths, seed-paths, macro-paths, "
                "snapshot-paths, clean-targets\n"
                "   - models: section with per-folder materialization and schema settings\n"
                "   - vars: section for project-wide variables\n\n"
                "2. **models/staging/sources.yml** (or one per source) — Source definitions:\n"
                "   - version: 2, sources: list with name, database, schema, description, "
                "loader, loaded_at_field, freshness (warn/error), tables with columns, "
                "descriptions, and basic tests (not_null, unique on keys)\n\n"
                "3. **models/<layer>/schema.yml** — One per layer (staging, intermediate, "
                "marts) with model-level and column-level documentation and tests:\n"
                "   - version: 2, models: list with name, description, columns with "
                "descriptions, data_type, tests (not_null, unique, accepted_values, "
                "relationships)\n\n"
                "4. **packages.yml** — Package dependencies:\n"
                "   - packages: list including dbt-labs/dbt_utils, dbt-labs/codegen, and "
                "any others needed (dbt_date, dbt_expectations, etc.)\n\n"
                "5. **profiles.yml.example** — Example connection profile for Snowflake:\n"
                "   - target: dev, outputs: dev and prod with account, user, password "
                "(env_var), role, database, warehouse, schema, threads\n\n"
                "YAML guidelines:\n"
                "- Use proper YAML indentation (2 spaces)\n"
                "- Include descriptive comments where helpful\n"
                "- Every column in a schema.yml should have a description\n"
                "- Apply tests: not_null and unique on primary keys, relationships on "
                "foreign keys, accepted_values on status/type columns\n"
                "- Use dbt's {{ env_var('VAR_NAME') }} for sensitive values in profiles\n\n"
                "Return a JSON object (no markdown fences) with key:\n"
                "  files (list of {file_path, file_type, content, description}).\n"
                "Each 'content' value must be the complete YAML as a plain string."
            ),
        )

    def execute(self, state: dict) -> dict:
        """Generate YAML files and populate state.generated_yaml."""
        logger.info("YAMLDeveloperAgent: starting execution")
        self._update_agent_status(state, "running", "Generating dbt YAML configuration files")

        try:
            architecture: dict = state.get("architecture", {})
            source_catalog: dict = state.get("source_catalog", {})
            project_spec: dict = state.get("project_specification", {})
            generated_models: dict = state.get("generated_models", {})
            business_logic: dict = state.get("business_logic", {})
            project_name: str = state.get("project_name", "my_dbt_project")

            if not architecture:
                raise ValueError("No architecture found in state — run ArchitectAgent first")

            # ----------------------------------------------------------
            # Step 1: Generate dbt_project.yml + packages.yml + profiles
            # ----------------------------------------------------------
            project_prompt = (
                "Generate the following dbt YAML configuration files:\n\n"
                "1. **dbt_project.yml** for a project named "
                f"'{project_name}' with these layers and models:\n"
                f"{json.dumps(architecture.get('layers', []), indent=2)}\n\n"
                "Materialization strategy:\n"
                f"{json.dumps(architecture.get('materialization_strategy', {}), indent=2)}\n\n"
                "2. **packages.yml** with dbt_utils and any other packages needed.\n\n"
                "3. **profiles.yml.example** for Snowflake with dev and prod targets "
                "using env_var() for credentials.\n\n"
                "Return a JSON object with key: files (list of "
                "{file_path, file_type, content, description}).\n"
                "Return ONLY the JSON object, no markdown fences."
            )

            logger.info("YAMLDeveloperAgent: generating project-level YAML files")
            project_response = self._call_gemini_json(project_prompt)

            # ----------------------------------------------------------
            # Step 2: Generate sources.yml
            # ----------------------------------------------------------
            # Extract any source('source_name', 'table_name') calls already used by sql_developer
            used_sources = set()
            for sql in state.get("generated_models", {}).values():
                for m in re.finditer(r"source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", sql):
                    used_sources.add(f"source('{m.group(1)}', '{m.group(2)}')")

            used_sources_str = ""
            if used_sources:
                used_sources_str = (
                    "\n\nCRITICAL: The generated SQL staging models use these exact source calls:\n"
                    + "\n".join(f"- {s}" for s in sorted(used_sources))
                    + "\nYou MUST declare source definitions with these exact source names and table names in sources.yml so every reference resolves!"
                )

            sources_prompt = (
                "Generate a dbt sources.yml file based on this source catalog:\n\n"
                f"## Source Catalog\n{json.dumps(source_catalog, indent=2)}\n"
                f"{used_sources_str}\n\n"
                "Include:\n"
                "- All source tables with their columns\n"
                "- Column descriptions and data types\n"
                "- Freshness checks (loaded_at_field if identifiable)\n"
                "- Tests: not_null and unique on primary key columns\n\n"
                "Return a JSON object with key: files (list of "
                "{file_path, file_type, content, description}).\n"
                "Put the file at models/staging/sources.yml.\n"
                "Return ONLY the JSON object, no markdown fences."
            )

            logger.info("YAMLDeveloperAgent: generating sources.yml")
            sources_response = self._call_gemini_json(sources_prompt)

            # ----------------------------------------------------------
            # Step 3: Generate schema.yml for each layer
            # ----------------------------------------------------------
            all_models_list: list[dict] = architecture.get("models", [])
            layers_with_models: dict[str, list[dict]] = {}
            for model in all_models_list:
                layer = model.get("layer", "staging")
                layers_with_models.setdefault(layer, []).append(model)

            # Get data quality requirements and transformation rules for tests
            dq_requirements = project_spec.get("data_quality_requirements", [])
            transformation_rules = business_logic.get("transformation_rules", [])

            schema_files_responses: list[dict] = []

            for layer_name, models_in_layer in layers_with_models.items():
                # Find relevant transformation rules for column info
                layer_rules = [
                    r for r in transformation_rules
                    if r.get("layer") == layer_name
                    or r.get("model_name") in [m.get("name", "") for m in models_in_layer]
                ]

                schema_prompt = (
                    f"Generate a schema.yml file for the **{layer_name}** layer of a dbt project.\n\n"
                    f"## Models in This Layer\n{json.dumps(models_in_layer, indent=2)}\n\n"
                    f"## Transformation Rules (for column details)\n{json.dumps(layer_rules, indent=2)}\n\n"
                    f"## Data Quality Requirements\n{json.dumps(dq_requirements, indent=2)}\n\n"
                    f"## Source Catalog (for column reference)\n{json.dumps(source_catalog, indent=2)}\n\n"
                    "Include:\n"
                    "- Every model with a description\n"
                    "- Every output column with a description and data_type\n"
                    "- Tests: not_null on required columns, unique on keys, "
                    "relationships on FK columns (using ref()), accepted_values where applicable\n\n"
                    f"Put the file at models/{layer_name}/schema.yml.\n"
                    "Return a JSON object with key: files (list of "
                    "{file_path, file_type, content, description}).\n"
                    "Return ONLY the JSON object, no markdown fences."
                )

                logger.info("YAMLDeveloperAgent: generating schema.yml for %s layer", layer_name)
                layer_response = self._call_gemini_json(schema_prompt)
                schema_files_responses.append(layer_response)

            # ----------------------------------------------------------
            # Merge all responses and validate
            # ----------------------------------------------------------
            all_files: list[dict] = []

            for response in [project_response, sources_response] + schema_files_responses:
                validated = GeneratedYAMLResponse.model_validate(response)
                all_files.extend(f.model_dump() for f in validated.files)

            # Build the generated_yaml dict: path → content
            generated_yaml: dict[str, str] = {}
            for file_info in all_files:
                path = file_info["file_path"]
                content = file_info["content"]
                generated_yaml[path] = content
                logger.debug("YAMLDeveloperAgent: generated %s", path)

            logger.info(
                "YAMLDeveloperAgent: generated %d YAML files",
                len(generated_yaml),
            )

            # ----------------------------------------------------------
            # Update state
            # ----------------------------------------------------------
            state["generated_yaml"] = generated_yaml

            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "yaml_generation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Generated {len(generated_yaml)} YAML files: "
                    + ", ".join(sorted(generated_yaml.keys()))
                ),
            })

            self._update_agent_status(
                state,
                "completed",
                f"Generated {len(generated_yaml)} YAML configuration files",
            )
            logger.info("YAMLDeveloperAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"YAMLDeveloperAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except ValueError as exc:
            error_msg = f"YAMLDeveloperAgent: {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"YAMLDeveloperAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state

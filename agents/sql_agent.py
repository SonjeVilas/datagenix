"""
SQL Developer Agent for dbt Project Factory.

Generates production-ready dbt SQL model files using CTE structure, source()
and ref() macros, Snowflake dialect, and proper materializations. Outputs a
dict mapping relative file paths to SQL content.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class GeneratedModel(BaseModel):
    file_path: str = Field(..., description="Relative path, e.g. models/staging/stg_orders.sql")
    model_name: str = Field(..., description="Model name without extension")
    sql_content: str = Field(..., description="Full SQL content of the model file")
    layer: Optional[str] = Field(default="", description="staging | intermediate | marts")
    materialization: Optional[str] = Field(default="view")
    description: Optional[str] = Field(default="")

    @field_validator("layer", "materialization", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class GeneratedModelsResponse(BaseModel):
    models: list[GeneratedModel] = Field(default_factory=list)
    macros: list[dict[str, str]] = Field(
        default_factory=list,
        description="Optional reusable macros [{name, file_path, sql_content}]",
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class SQLDeveloperAgent(BaseAgent):
    """Generates dbt SQL model files from architecture and business logic."""

    def __init__(self) -> None:
        super().__init__(
            name="sql_developer",
            description=(
                "Generates production-quality dbt SQL model files with proper CTE "
                "structure, source()/ref() references, and Snowflake-compatible SQL."
            ),
            system_prompt=(
                "You are an expert dbt SQL developer who writes clean, well-documented, "
                "production-grade SQL models targeting Snowflake. You follow the dbt style "
                "guide and community best practices rigorously.\n\n"
                "When generating SQL models you MUST:\n\n"
                "1. **CTE structure**: Every model starts with an import CTE section that "
                "pulls in dependencies using `{{ source('schema', 'table') }}` (for staging "
                "models) or `{{ ref('model_name') }}` (for intermediate/marts). Follow with "
                "transformation CTEs, then a final CTE that is selected at the end.\n\n"
                "2. **Config block**: Begin each model with a Jinja config block:\n"
                "   ```\n"
                "   {{ config(\n"
                "       materialized='<strategy>',\n"
                "       schema='<schema>',\n"
                "       tags=['<layer>'],\n"
                "       unique_key='<key>'  -- for incremental only\n"
                "   ) }}\n"
                "   ```\n\n"
                "3. **Staging models**: 1:1 with source tables. Rename columns to snake_case, "
                "cast data types explicitly, add surrogate keys if needed, filter soft-deleted "
                "rows.\n\n"
                "4. **Intermediate models**: Implement joins, aggregations, window functions, "
                "filters, and deduplication logic as specified in the business rules.\n\n"
                "5. **Marts models (dims)**: Build dimension tables with proper surrogate keys "
                "(using `{{ dbt_utils.generate_surrogate_key(['col1','col2']) }}`), SCD "
                "handling when needed, and descriptive column names.\n\n"
                "6. **Marts models (facts)**: Build fact tables with foreign keys to dimensions, "
                "measures, and incremental logic using `{% if is_incremental() %}` blocks.\n\n"
                "7. **Snowflake dialect**: Use Snowflake-specific functions (TRY_CAST, "
                "DATEADD, DATEDIFF, NVL, IFF, QUALIFY, FLATTEN). Prefer QUALIFY over "
                "subqueries for deduplication.\n\n"
                "8. **Documentation**: Add a brief comment block at the top of each model "
                "describing its purpose, grain, and key assumptions.\n\n"
                "9. **Macros**: If you identify reusable SQL patterns (currency conversion, "
                "date spine, status mapping), generate them as separate macro files.\n\n"
                "Return a JSON object (no markdown fences) with keys:\n"
                "  models (list of {file_path, model_name, sql_content, layer, "
                "materialization, description}),\n"
                "  macros (list of {name, file_path, sql_content}).\n"
                "All SQL must be complete and ready to run — no stubs, no placeholders, "
                "no TODOs."
            ),
        )

    def _generate_models_for_layer(
        self,
        layer: str,
        models_in_layer: list[dict[str, Any]],
        state: dict,
    ) -> dict:
        """Generate SQL for a single layer to keep prompts manageable."""
        project_spec: dict = state.get("project_specification", {})
        source_catalog: dict = state.get("source_catalog", {})
        architecture: dict = state.get("architecture", {})
        business_logic: dict = state.get("business_logic", {})

        # Extract transformation rules relevant to this layer
        layer_rules = [
            r for r in business_logic.get("transformation_rules", [])
            if r.get("layer", "") == layer
            or r.get("model_name", "") in [m.get("name", "") for m in models_in_layer]
        ]

        prompt = (
            f"Generate complete dbt SQL model files for the **{layer}** layer.\n\n"
            f"## Models to Generate\n{json.dumps(models_in_layer, indent=2)}\n\n"
            f"## Transformation Rules for These Models\n{json.dumps(layer_rules, indent=2)}\n\n"
            f"## Source Catalog\n{json.dumps(source_catalog, indent=2)}\n\n"
            f"## Full Architecture (for ref() context)\n{json.dumps(architecture.get('models', []), indent=2)}\n\n"
            f"## Global Rules\n"
            f"Global Filters: {json.dumps(business_logic.get('global_filters', []), indent=2)}\n"
            f"Global Calculations: {json.dumps(business_logic.get('global_calculations', []), indent=2)}\n"
            f"SCD Definitions: {json.dumps(business_logic.get('scd_definitions', []), indent=2)}\n\n"
            "Generate each model with:\n"
            "- A {{ config(...) }} block at the top\n"
            "- Import CTEs using source() for staging or ref() for int/marts\n"
            "- Transformation CTEs implementing the business logic\n"
            "- A final SELECT\n"
            "- Comments explaining the model\n\n"
            "Return a JSON object with keys: models (list of {file_path, model_name, "
            "sql_content, layer, materialization, description}), macros (list, may be empty).\n"
            "Return ONLY the JSON object, no markdown fences."
        )
        return self._call_gemini_json(prompt)

    def execute(self, state: dict) -> dict:
        """Generate SQL model files and populate state.generated_models."""
        logger.info("SQLDeveloperAgent: starting execution")
        self._update_agent_status(state, "running", "Generating dbt SQL model files")

        try:
            architecture: dict = state.get("architecture", {})
            business_logic: dict = state.get("business_logic", {})

            if not architecture:
                raise ValueError("No architecture found in state — run ArchitectAgent first")
            if not business_logic:
                raise ValueError("No business_logic found in state — run BusinessLogicAgent first")

            all_models: list[dict] = architecture.get("models", [])
            if not all_models:
                raise ValueError("Architecture contains no models")

            # Group models by layer
            layers: dict[str, list[dict]] = {}
            for model in all_models:
                layer = model.get("layer", "staging")
                layers.setdefault(layer, []).append(model)

            generated_models: dict[str, str] = {}
            all_macros: list[dict[str, str]] = []

            # Generate SQL for each layer
            for layer_name in ["staging", "intermediate", "marts"]:
                models_in_layer = layers.get(layer_name, [])
                if not models_in_layer:
                    continue

                logger.info(
                    "SQLDeveloperAgent: generating %d models for %s layer",
                    len(models_in_layer),
                    layer_name,
                )

                raw_response = self._generate_models_for_layer(
                    layer_name, models_in_layer, state,
                )

                # Validate
                layer_result = GeneratedModelsResponse.model_validate(raw_response)

                for model in layer_result.models:
                    generated_models[model.file_path] = model.sql_content
                    logger.debug("SQLDeveloperAgent: generated %s", model.file_path)

                all_macros.extend(
                    m if isinstance(m, dict) else m.model_dump()
                    for m in layer_result.macros
                )

            # Add macros to generated_models dict
            for macro in all_macros:
                path = macro.get("file_path", "")
                content = macro.get("sql_content", "")
                if path and content:
                    generated_models[path] = content

            logger.info(
                "SQLDeveloperAgent: generated %d total SQL files (%d macros)",
                len(generated_models),
                len(all_macros),
            )

            # ----------------------------------------------------------
            # Update state
            # ----------------------------------------------------------
            state["generated_models"] = generated_models

            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "sql_generation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Generated {len(generated_models)} SQL files "
                    f"({len(all_macros)} macros)"
                ),
            })

            self._update_agent_status(
                state,
                "completed",
                f"Generated {len(generated_models)} SQL model files",
            )
            logger.info("SQLDeveloperAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"SQLDeveloperAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except ValueError as exc:
            error_msg = f"SQLDeveloperAgent: {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"SQLDeveloperAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state

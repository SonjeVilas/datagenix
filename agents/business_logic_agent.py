"""
Business Logic Agent for dbt Project Factory.

Converts high-level business requirements into concrete SQL transformation
rules: joins, aggregations, filters, calculations, deduplication, NULL
handling, and slowly-changing-dimension identification.
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

class JoinRule(BaseModel):
    name: str = Field(..., description="Descriptive name of the join")
    left_model: str = Field(...)
    right_model: str = Field(...)
    join_type: str = Field(default="inner", description="inner | left | right | full | cross")
    join_condition: str = Field(..., description="SQL ON clause")
    description: Optional[str] = Field(default="")

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class AggregationRule(BaseModel):
    name: str = Field(...)
    source_model: str = Field(...)
    group_by_columns: list[str] = Field(default_factory=list)
    aggregations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {column, function, alias} dicts",
    )
    filters: Optional[str] = Field(default="", description="WHERE clause if any")
    description: Optional[str] = Field(default="")

    @field_validator("filters", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class FilterRule(BaseModel):
    name: str = Field(...)
    source_model: str = Field(...)
    condition: str = Field(..., description="SQL WHERE/QUALIFY condition")
    reason: Optional[str] = Field(default="", description="Why this filter exists")

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class CalculationRule(BaseModel):
    name: str = Field(...)
    expression: str = Field(..., description="SQL expression for the calculation")
    output_column: str = Field(...)
    source_columns: list[str] = Field(default_factory=list)
    description: Optional[str] = Field(default="")

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class DeduplicationRule(BaseModel):
    name: str = Field(...)
    source_model: str = Field(...)
    partition_by: list[str] = Field(default_factory=list, description="Columns for ROW_NUMBER partition")
    order_by: Optional[str] = Field(default="", description="ORDER BY clause for picking the winner")
    keep: str = Field(default="first", description="first or last")
    description: Optional[str] = Field(default="")

    @field_validator("order_by", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class NullHandlingRule(BaseModel):
    column: str = Field(...)
    source_model: str = Field(...)
    strategy: str = Field(
        default="coalesce",
        description="coalesce | default_value | filter_out | flag",
    )
    default_value: Optional[str] = Field(default="", description="Default value for coalesce / default_value strategy")
    description: Optional[str] = Field(default="")

    @field_validator("default_value", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class SCDDefinition(BaseModel):
    entity: str = Field(..., description="Entity requiring SCD handling")
    scd_type: str = Field(default="type_2", description="type_1 | type_2 | type_3")
    tracked_columns: list[str] = Field(default_factory=list, description="Columns tracked for changes")
    unique_key: str = Field(..., description="Natural key of the entity")
    valid_from_column: Optional[str] = Field(default="valid_from")
    valid_to_column: Optional[str] = Field(default="valid_to")
    current_flag_column: Optional[str] = Field(default="is_current")
    description: Optional[str] = Field(default="")

    @field_validator("valid_from_column", "valid_to_column", "current_flag_column", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class TransformationRuleSet(BaseModel):
    model_name: str = Field(..., description="Target model these rules apply to")
    layer: Optional[str] = Field(default="", description="staging | intermediate | marts")
    joins: list[JoinRule] = Field(default_factory=list)
    aggregations: list[AggregationRule] = Field(default_factory=list)
    filters: list[FilterRule] = Field(default_factory=list)
    calculations: list[CalculationRule] = Field(default_factory=list)
    dedup_rules: list[DeduplicationRule] = Field(default_factory=list)
    null_handling: list[NullHandlingRule] = Field(default_factory=list)
    column_mappings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {source_column, target_column, transformation} dicts",
    )
    notes: Optional[str] = Field(default="")

    @field_validator("layer", "notes", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class BusinessLogic(BaseModel):
    transformation_rules: list[TransformationRuleSet] = Field(default_factory=list)
    scd_definitions: list[SCDDefinition] = Field(default_factory=list)
    global_filters: list[FilterRule] = Field(default_factory=list, description="Filters applied across all models")
    global_calculations: list[CalculationRule] = Field(default_factory=list, description="Reusable calculated fields")
    assumptions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class BusinessLogicAgent(BaseAgent):
    """Converts business requirements into concrete SQL transformation rules."""

    def __init__(self) -> None:
        super().__init__(
            name="business_logic",
            description=(
                "Translates high-level business requirements and architecture into "
                "concrete SQL transformation rules for each dbt model."
            ),
            system_prompt=(
                "You are a senior SQL developer and data transformation expert. Your "
                "speciality is converting vague business requirements into precise, "
                "executable SQL logic targeting Snowflake.\n\n"
                "Given a project specification (objectives, entities, rules), an "
                "architecture (models, layers, DAG), and a source catalog (tables, columns), "
                "you must produce detailed transformation rules for every model in the "
                "architecture.\n\n"
                "For each model you must specify:\n"
                "1. **Joins**: Which tables/models are joined, the join type (inner/left/"
                "right/full), and the exact ON condition using column names from the catalog.\n"
                "2. **Aggregations**: GROUP BY columns, aggregate functions (SUM, COUNT, "
                "AVG, MIN, MAX, LISTAGG), and any HAVING filters.\n"
                "3. **Filters**: WHERE conditions to exclude invalid, deleted, or out-of-scope "
                "records. Explain the business reason for each filter.\n"
                "4. **Calculations**: Derived columns — revenue, margin, duration, status "
                "mappings, CASE expressions, window functions (ROW_NUMBER, RANK, LAG/LEAD, "
                "running totals).\n"
                "5. **Deduplication**: When source data can contain duplicates, specify the "
                "partition columns, ordering, and which record to keep.\n"
                "6. **NULL handling**: For every column that may be NULL, specify the strategy: "
                "COALESCE with a default, filter out, or flag with a boolean indicator.\n"
                "7. **SCD identification**: If an entity changes over time, identify the SCD "
                "type (1, 2, or 3), the tracked columns, natural key, and validity columns.\n\n"
                "Also identify any global filters or calculations that apply across models "
                "(e.g., 'exclude test accounts everywhere').\n\n"
                "Return a single JSON object (no markdown fences) with keys: "
                "transformation_rules, scd_definitions, global_filters, "
                "global_calculations, assumptions."
            ),
        )

    def execute(self, state: dict) -> dict:
        """Generate transformation rules and populate state.business_logic."""
        logger.info("BusinessLogicAgent: starting execution")
        self._update_agent_status(state, "running", "Converting requirements to transformation rules")

        try:
            project_spec: dict = state.get("project_specification", {})
            source_catalog: dict = state.get("source_catalog", {})
            architecture: dict = state.get("architecture", {})

            if not architecture:
                raise ValueError("No architecture found in state — run ArchitectAgent first")

            # ----------------------------------------------------------
            # Build prompt
            # ----------------------------------------------------------
            prompt = (
                "Generate detailed SQL transformation rules for every model in the "
                "architecture below.\n\n"
                f"## Project Specification\n{json.dumps(project_spec, indent=2)}\n\n"
                f"## Source Catalog\n{json.dumps(source_catalog, indent=2)}\n\n"
                f"## Architecture\n{json.dumps(architecture, indent=2)}\n\n"
                "For each model, provide:\n"
                "- joins (name, left_model, right_model, join_type, join_condition, description)\n"
                "- aggregations (name, source_model, group_by_columns, aggregations [{column, function, alias}], filters, description)\n"
                "- filters (name, source_model, condition, reason)\n"
                "- calculations (name, expression, output_column, source_columns, description)\n"
                "- dedup_rules (name, source_model, partition_by, order_by, keep, description)\n"
                "- null_handling (column, source_model, strategy, default_value, description)\n"
                "- column_mappings ([{source_column, target_column, transformation}])\n\n"
                "Also provide:\n"
                "- scd_definitions for entities needing SCD handling\n"
                "- global_filters applied everywhere\n"
                "- global_calculations reusable across models\n"
                "- assumptions you are making\n\n"
                "Return a JSON object with keys: transformation_rules (list of objects each "
                "with model_name, layer, joins, aggregations, filters, calculations, "
                "dedup_rules, null_handling, column_mappings, notes), scd_definitions, "
                "global_filters, global_calculations, assumptions.\n"
                "Return ONLY the JSON object, no markdown fences."
            )

            # ----------------------------------------------------------
            # Call Gemini
            # ----------------------------------------------------------
            logger.info("BusinessLogicAgent: calling Gemini for transformation rules")
            raw_response: dict = self._call_gemini_json(prompt)

            # ----------------------------------------------------------
            # Validate
            # ----------------------------------------------------------
            logic = BusinessLogic.model_validate(raw_response)
            logic_dict: dict = logic.model_dump()

            total_rules = len(logic.transformation_rules)
            total_joins = sum(len(r.joins) for r in logic.transformation_rules)
            total_calcs = sum(len(r.calculations) for r in logic.transformation_rules)

            logger.info(
                "BusinessLogicAgent: generated rules for %d models — "
                "%d joins, %d calculations, %d SCDs",
                total_rules,
                total_joins,
                total_calcs,
                len(logic.scd_definitions),
            )

            # ----------------------------------------------------------
            # Update state
            # ----------------------------------------------------------
            state["business_logic"] = logic_dict

            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "business_logic_generation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Generated transformation rules for {total_rules} models "
                    f"({total_joins} joins, {total_calcs} calculations, "
                    f"{len(logic.scd_definitions)} SCDs)"
                ),
            })

            self._update_agent_status(
                state,
                "completed",
                f"Rules for {total_rules} models generated",
            )
            logger.info("BusinessLogicAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"BusinessLogicAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except ValueError as exc:
            error_msg = f"BusinessLogicAgent: {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"BusinessLogicAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state

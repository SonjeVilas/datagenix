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

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class JoinRule(BaseModel):
    name: str = Field(default="join", description="Descriptive name of the join")
    left_model: str = Field(default="")
    right_model: str = Field(default="")
    join_type: str = Field(default="inner", description="inner | left | right | full | cross")
    join_condition: str = Field(default="", description="SQL ON clause")
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["name"] = str(data.get("name") or data.get("join_name") or "join")
            data["left_model"] = str(data.get("left_model") or data.get("left_table") or data.get("left") or "")
            data["right_model"] = str(data.get("right_model") or data.get("right_table") or data.get("right") or "")
            data["join_condition"] = str(data.get("join_condition") or data.get("on") or data.get("condition") or "")
        return data


class AggregationRule(BaseModel):
    name: str = Field(default="agg")
    source_model: str = Field(default="")
    group_by_columns: list[str] = Field(default_factory=list)
    aggregations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {column, function, alias} dicts",
    )
    filters: Optional[str] = Field(default="", description="WHERE clause if any")
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["name"] = str(data.get("name") or data.get("agg_name") or "agg")
            data["source_model"] = str(data.get("source_model") or data.get("model") or data.get("table") or "")
        return data


class FilterRule(BaseModel):
    name: str = Field(default="filter")
    source_model: str = Field(default="")
    condition: str = Field(default="", description="SQL WHERE/QUALIFY condition")
    reason: Optional[str] = Field(default="", description="Why this filter exists")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["name"] = str(data.get("name") or data.get("filter_name") or data.get("rule_name") or "filter")
            data["source_model"] = str(data.get("source_model") or data.get("model") or data.get("table") or data.get("target_model") or "")
            data["condition"] = str(data.get("condition") or data.get("filter_condition") or data.get("sql") or data.get("where") or "")
        return data


class CalculationRule(BaseModel):
    name: str = Field(default="calc")
    expression: str = Field(default="", description="SQL expression for the calculation")
    output_column: str = Field(default="")
    source_columns: list[str] = Field(default_factory=list)
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["name"] = str(data.get("name") or data.get("calculation_name") or data.get("calc_name") or "calc")
            data["output_column"] = str(data.get("output_column") or data.get("column") or data.get("alias") or data.get("target_column") or data["name"])
            data["expression"] = str(data.get("expression") or data.get("sql") or data.get("formula") or "")
        return data


class DeduplicationRule(BaseModel):
    name: str = Field(default="dedup")
    source_model: str = Field(default="")
    partition_by: list[str] = Field(default_factory=list, description="Columns for ROW_NUMBER partition")
    order_by: Optional[str] = Field(default="", description="ORDER BY clause for picking the winner")
    keep: str = Field(default="first", description="first or last")
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["name"] = str(data.get("name") or data.get("dedup_name") or "dedup")
            data["source_model"] = str(data.get("source_model") or data.get("model") or data.get("table") or "")
        return data


class NullHandlingRule(BaseModel):
    column: str = Field(default="")
    source_model: str = Field(default="")
    strategy: str = Field(
        default="coalesce",
        description="coalesce | default_value | filter_out | flag",
    )
    default_value: Optional[str] = Field(default="", description="Default value for coalesce / default_value strategy")
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["column"] = str(data.get("column") or data.get("name") or "")
            data["source_model"] = str(data.get("source_model") or data.get("model") or "")
        return data


class SCDDefinition(BaseModel):
    entity: str = Field(default="entity", description="Entity requiring SCD handling")
    scd_type: str = Field(default="type_2", description="type_1 | type_2 | type_3")
    tracked_columns: list[str] = Field(default_factory=list, description="Columns tracked for changes")
    unique_key: str = Field(default="id", description="Natural key of the entity")
    valid_from_column: Optional[str] = Field(default="valid_from")
    valid_to_column: Optional[str] = Field(default="valid_to")
    current_flag_column: Optional[str] = Field(default="is_current")
    description: Optional[str] = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["entity"] = str(data.get("entity") or data.get("name") or "entity")
            data["unique_key"] = str(data.get("unique_key") or data.get("key") or "id")
        return data


class TransformationRuleSet(BaseModel):
    model_name: str = Field(default="model", description="Target model these rules apply to")
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

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["model_name"] = str(data.get("model_name") or data.get("name") or data.get("target_model") or "model")
        return data

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

            all_models = architecture.get("models", [])

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
            # Call Gemini with resilient fallback
            # ----------------------------------------------------------
            logger.info("BusinessLogicAgent: calling Gemini for transformation rules")
            try:
                raw_response: dict = self._call_gemini_json(prompt)
                logic = BusinessLogic.model_validate(raw_response)
            except Exception as exc:
                logger.warning(
                    "BusinessLogicAgent: model validation/parsing error (%s) — synthesizing rules from architecture",
                    exc,
                )
                fallback_rules = []
                for m in all_models:
                    m_name = m.get("name", "model") if isinstance(m, dict) else getattr(m, "name", "model")
                    m_layer = m.get("layer", "staging") if isinstance(m, dict) else getattr(m, "layer", "staging")
                    fallback_rules.append(
                        TransformationRuleSet(
                            model_name=m_name,
                            layer=m_layer,
                            notes=f"Synthesized baseline transformation rules for {m_name}",
                        )
                    )
                logic = BusinessLogic(
                    transformation_rules=fallback_rules,
                    assumptions=["Synthesized baseline transformation rules from architecture models."],
                )
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

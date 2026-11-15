"""Unit tests for Validator static checks, YAML parsing, and SQL checking."""

from backend.validator import Validator


def test_validator_clean_artifacts():
    models = {
        "models/staging/stg_users.sql": (
            "with src as (\n"
            "    select * from {{ source('raw_data', 'users') }}\n"
            ")\n"
            "select * from src"
        ),
        "models/marts/dim_users.sql": (
            "with stg as (\n"
            "    select * from {{ ref('stg_users') }}\n"
            ")\n"
            "select user_id, name from stg"
        ),
    }
    yaml_files = {
        "models/staging/sources.yml": (
            "version: 2\n"
            "sources:\n"
            "  - name: raw_data\n"
            "    tables:\n"
            "      - name: users\n"
        ),
    }

    validator = Validator()
    result = validator.validate_artifacts(models, yaml_files)
    assert result["passed"]
    assert result["error_count"] == 0


def test_validator_broken_ref():
    models = {
        "models/marts/fct_orders.sql": "select * from {{ ref('non_existent_stg') }}",
    }
    yaml_files = {}

    validator = Validator()
    result = validator.validate_artifacts(models, yaml_files)
    assert not result["passed"]
    assert any(i["rule"] == "broken_ref" for i in result["issues"])


def test_validator_circular_dependency():
    models = {
        "models/marts/a.sql": "select * from {{ ref('b') }}",
        "models/marts/b.sql": "select * from {{ ref('a') }}",
    }
    yaml_files = {}

    validator = Validator()
    result = validator.validate_artifacts(models, yaml_files)
    assert not result["passed"]
    assert any(i["rule"] == "circular_dependency" for i in result["issues"])


def test_validator_validate_all():
    state = {
        "generated_models": {
            "models/staging/stg_test.sql": "select 1 as id",
        },
        "generated_yaml": {
            "models/staging/schema.yml": "version: 2\nmodels:\n  - name: stg_test\n",
        },
    }
    validator = Validator()
    res = validator.validate_all(state)
    assert "QA Agent" in res
    assert "dbt_parse" in res
    assert "dbt_compile" in res
    assert "sqlfluff" in res
    assert res["QA Agent"]["passed"] is True
    assert "qa_report" in state
    assert state["qa_report"]["passed"] is True


def test_validator_validate_all_with_dbt_runner(tmp_path):
    # Create sample models on disk
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "test.sql").write_text("select 1", encoding="utf-8")
    (models_dir / "schema.yml").write_text("version: 2\n", encoding="utf-8")

    state = {
        "project_output_path": str(tmp_path),
        "generated_models": {},
        "generated_yaml": {},
    }
    validator = Validator()
    res = validator.validate_all(state)
    assert "QA Agent" in res
    assert "dbt_parse" in res
    assert isinstance(res["dbt_parse"], dict)
    assert "passed" in res["dbt_parse"]


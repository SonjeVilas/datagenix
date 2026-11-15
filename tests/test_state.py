"""Unit tests for ProjectState model and serialization."""

from backend.state import ProjectState


def test_project_state_creation():
    state = ProjectState(
        project_name="my_dbt_project",
        project_description="Test project description",
        business_requirements="Transform orders into sales mart",
    )
    assert state.project_name == "my_dbt_project"
    assert state.retry_count == 0
    assert state.max_retries == 3
    assert not state.human_approval_required
    assert isinstance(state.generated_models, dict)
    assert isinstance(state.generated_yaml, dict)


def test_project_state_dump_and_load():
    state = ProjectState(
        project_name="analytics",
        generated_models={"models/staging/stg_users.sql": "select * from raw_users"},
        retry_count=1,
    )
    data = state.model_dump()
    assert isinstance(data, dict)
    assert data["project_name"] == "analytics"
    assert data["retry_count"] == 1

    loaded = ProjectState.model_validate(data)
    assert loaded.project_name == "analytics"
    assert "models/staging/stg_users.sql" in loaded.generated_models


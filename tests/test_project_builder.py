"""Unit tests for ProjectBuilder filesystem layout."""

from backend.project_builder import ProjectBuilder


def test_project_builder_creates_structure(tmp_path, populated_state):
    builder = ProjectBuilder(base_output_dir=tmp_path)
    output_path = builder.build_project(populated_state)
    
    assert output_path
    proj_dir = tmp_path / "banking_analytics"
    assert proj_dir.is_dir()
    assert (proj_dir / "models").is_dir()
    assert (proj_dir / "models" / "staging").is_dir()
    assert (proj_dir / "models" / "marts").is_dir()
    assert (proj_dir / "models" / "marts" / "dim_customer.sql").is_file()
    assert (proj_dir / "README.md").is_file()
    assert (proj_dir / "requirements.txt").is_file()


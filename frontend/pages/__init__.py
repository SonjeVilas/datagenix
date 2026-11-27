"""Frontend pages for Datagenix."""

from frontend.pages.ai_agents import render_agents_page
from frontend.pages.data_sources import render_data_sources_page
from frontend.pages.execution_history import render_execution_history_page
from frontend.pages.new_project import render_new_project_page
from frontend.pages.project_explorer import render_project_explorer_page
from frontend.pages.settings import render_settings_page
from frontend.pages.sql_editor import render_sql_editor_page
from frontend.pages.validation_center import render_validation_center_page
from frontend.pages.yaml_editor import render_yaml_editor_page

__all__ = [
    "render_agents_page",
    "render_data_sources_page",
    "render_execution_history_page",
    "render_new_project_page",
    "render_project_explorer_page",
    "render_settings_page",
    "render_sql_editor_page",
    "render_validation_center_page",
    "render_yaml_editor_page",
]


"""SQLite database layer for project metadata, execution history, and metrics."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("storage/project_history.db")


class Database:
    """SQLite database manager for dbt Project Factory."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    output_path TEXT,
                    specification_json TEXT,
                    architecture_json TEXT,
                    state_json TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    summary TEXT,
                    error_details TEXT
                );

                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    validation_type TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    issues_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS error_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    issue_summary TEXT,
                    changes_json TEXT,
                    retry_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def save_project(
        self,
        project_name: str,
        description: str = "",
        status: str = "created",
        output_path: str = "",
        specification: Optional[Dict[str, Any]] = None,
        architecture: Optional[Dict[str, Any]] = None,
        state_dict: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert or update a project record."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM projects WHERE project_name = ? ORDER BY id DESC LIMIT 1",
                (project_name,),
            )
            row = cursor.fetchone()
            if row:
                proj_id = row["id"]
                cursor.execute(
                    """
                    UPDATE projects
                    SET description = ?, updated_at = ?, status = ?, output_path = ?,
                        specification_json = ?, architecture_json = ?, state_json = ?
                    WHERE id = ?
                    """,
                    (
                        description,
                        now,
                        status,
                        output_path,
                        json.dumps(specification or {}),
                        json.dumps(architecture or {}),
                        json.dumps(state_dict or {}),
                        proj_id,
                    ),
                )
                return proj_id
            else:
                cursor.execute(
                    """
                    INSERT INTO projects
                    (project_name, description, created_at, updated_at, status, output_path, specification_json, architecture_json, state_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_name,
                        description,
                        now,
                        now,
                        status,
                        output_path,
                        json.dumps(specification or {}),
                        json.dumps(architecture or {}),
                        json.dumps(state_dict or {}),
                    ),
                )
                return cursor.lastrowid or 0

    def list_projects(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all projects ordered by creation time descending."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM projects ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_project(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve project record by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM projects WHERE project_name = ? ORDER BY id DESC LIMIT 1",
                (project_name,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def record_agent_execution(
        self,
        project_name: str,
        agent_name: str,
        status: str,
        started_at: str = "",
        completed_at: str = "",
        duration_seconds: float = 0.0,
        summary: str = "",
        error_details: str = "",
    ) -> None:
        """Record an agent execution cycle."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_executions
                (project_name, agent_name, status, started_at, completed_at, duration_seconds, summary, error_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    agent_name,
                    status,
                    started_at,
                    completed_at,
                    duration_seconds,
                    summary,
                    error_details,
                ),
            )

    def get_agent_executions(self, project_name: str) -> List[Dict[str, Any]]:
        """Retrieve agent executions for a specific project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_executions WHERE project_name = ? ORDER BY id ASC",
                (project_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def record_validation(
        self,
        project_name: str,
        validation_type: str,
        passed: bool,
        issues: List[Dict[str, Any]],
    ) -> None:
        """Record validation results."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO validation_results
                (project_name, validation_type, passed, issues_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    validation_type,
                    1 if passed else 0,
                    json.dumps(issues),
                    now,
                ),
            )

    def record_error_correction(
        self,
        project_name: str,
        file_path: str,
        issue_summary: str,
        changes: List[Dict[str, Any]],
        retry_number: int,
    ) -> None:
        """Record an error correction applied by the fixer agent."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO error_corrections
                (project_name, file_path, issue_summary, changes_json, retry_number, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    file_path,
                    issue_summary,
                    json.dumps(changes),
                    retry_number,
                    now,
                ),
            )

    def get_metrics(self) -> Dict[str, int]:
        """Aggregate system metrics for the dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM projects")
            total_projects = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM validation_results WHERE passed = 1")
            successful_validations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM validation_results WHERE passed = 0")
            failed_validations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM agent_executions")
            total_agent_executions = cursor.fetchone()[0]

            return {
                "total_projects": total_projects,
                "successful_validations": successful_validations,
                "failed_validations": failed_validations,
                "total_agent_executions": total_agent_executions,
            }

    def get_all_runs(self) -> List[Dict[str, Any]]:
        """Retrieve all project runs with their summary metrics and state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY id DESC")
            rows = cursor.fetchall()
            runs: List[Dict[str, Any]] = []
            for row in rows:
                p = dict(row)
                p_name = p.get("project_name", "Untitled")

                # Count completed agents
                cursor.execute(
                    "SELECT COUNT(*) FROM agent_executions WHERE project_name = ? AND status = 'completed'",
                    (p_name,),
                )
                agents_completed = cursor.fetchone()[0]

                # Check validation results
                cursor.execute(
                    "SELECT passed FROM validation_results WHERE project_name = ? ORDER BY id DESC LIMIT 1",
                    (p_name,),
                )
                val_row = cursor.fetchone()
                val_passed = bool(val_row[0]) if val_row else False

                # Parse state_json
                state: Dict[str, Any] = {}
                try:
                    state = json.loads(p.get("state_json") or "{}")
                except Exception:
                    pass

                # Calculate models count & errors
                models_count = len(state.get("generated_models", {}))
                errors = state.get("errors", [])
                if not val_passed and len(errors) == 0 and models_count > 0:
                    val_passed = True

                # Extract timestamp
                created_at = p.get("created_at", "")
                display_date = created_at[:19].replace("T", " ") if created_at else "Unknown"

                runs.append({
                    "project_name": p_name,
                    "project_description": p.get("description", "") or state.get("project_description", "—"),
                    "timestamp": display_date,
                    "duration": "—",
                    "status": p.get("status", "unknown"),
                    "agents_completed": agents_completed,
                    "models_count": models_count,
                    "validation_passed": val_passed,
                    "error_count": len(errors),
                    "output_path": p.get("output_path", ""),
                    "state": state,
                })
            return runs


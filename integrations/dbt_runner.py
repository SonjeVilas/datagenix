"""Subprocess wrapper for dbt CLI and sqlfluff commands."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # seconds


@dataclass
class CommandResult:
    """Result of a subprocess execution."""

    command: str
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    success: bool = field(init=False)

    def __post_init__(self) -> None:
        self.success = self.return_code == 0 and not self.timed_out

    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like accessor for compatibility."""
        if key in ("passed", "valid"):
            return self.success
        if key in ("output", "stdout"):
            return self.stdout
        if key in ("error", "stderr"):
            return self.stderr
        if key == "errors":
            if not self.success:
                msg = (self.stderr.strip() or self.stdout.strip())
                return [{"file": "project", "line": 1, "message": msg}] if msg else []
            return []
        if key == "warnings":
            return []
        if key == "raw_output":
            return f"{self.stdout}\n{self.stderr}".strip()
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and not hasattr(self, key):
            raise KeyError(key)
        return val

    def to_dict(self) -> dict[str, Any]:
        """Convert result into standard dictionary."""
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "success": self.success,
            "passed": self.success,
            "errors": [
                {"file": "project", "line": 1, "message": self.stderr.strip() or self.stdout.strip()}
            ] if not self.success else [],
            "warnings": [],
            "output": self.stdout,
            "error": self.stderr,
            "raw_output": f"{self.stdout}\n{self.stderr}".strip(),
        }


class DbtRunner:
    """Safe subprocess wrapper for dbt and sqlfluff commands.

    All commands are executed via argument lists (never ``shell=True``)
    with configurable timeouts and full stdout/stderr capture.
    """

    def __init__(
        self,
        project_dir: str | Path,
        profiles_dir: Optional[str | Path] = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.profiles_dir = Path(profiles_dir).resolve() if profiles_dir else None
        logger.info("DbtRunner initialised (project_dir=%s)", self.project_dir)

    # ── private helpers ─────────────────────────────────────────────────

    def _run(
        self,
        args: List[str],
        timeout: int = DEFAULT_TIMEOUT,
        cwd: Optional[Path] = None,
    ) -> CommandResult:
        """Execute *args* as a subprocess and return a ``CommandResult``."""
        cmd_str = " ".join(args)
        work_dir = cwd or self.project_dir
        logger.info("Running: %s (cwd=%s, timeout=%ds)", cmd_str, work_dir, timeout)

        try:
            proc = subprocess.run(
                args,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result = CommandResult(
                command=cmd_str,
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after %ds: %s", timeout, cmd_str)
            result = CommandResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                timed_out=True,
            )
        except FileNotFoundError:
            logger.error("Executable not found: %s", args[0])
            result = CommandResult(
                command=cmd_str,
                return_code=-1,
                stdout="",
                stderr=f"Executable not found: {args[0]}",
            )

        if result.success:
            logger.info("Command succeeded: %s", cmd_str)
        else:
            logger.warning(
                "Command failed (rc=%d): %s\nstderr: %s",
                result.return_code,
                cmd_str,
                result.stderr[:500],
            )
        return result

    def _dbt_cmd(self, subcommand: str, extra_args: Optional[List[str]] = None) -> List[str]:
        """Return dbt CLI arguments with subcommand placed first."""
        args = ["dbt", subcommand, "--project-dir", str(self.project_dir)]
        if self.profiles_dir:
            args.extend(["--profiles-dir", str(self.profiles_dir)])
        if extra_args:
            args.extend(extra_args)
        return args

    # ── dbt commands ────────────────────────────────────────────────────

    def debug(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt debug``."""
        return self._run(self._dbt_cmd("debug"), timeout=timeout)

    def deps(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt deps``."""
        return self._run(self._dbt_cmd("deps"), timeout=timeout)

    def parse(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt parse``."""
        return self._run(self._dbt_cmd("parse"), timeout=timeout)

    def compile(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt compile``."""
        return self._run(self._dbt_cmd("compile"), timeout=timeout)

    def test(
        self,
        select: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt test``."""
        extra = ["--select", select] if select else []
        return self._run(self._dbt_cmd("test", extra), timeout=timeout)

    def build(
        self,
        select: Optional[str] = None,
        full_refresh: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt build``."""
        extra = []
        if select:
            extra.extend(["--select", select])
        if full_refresh:
            extra.append("--full-refresh")
        return self._run(self._dbt_cmd("build", extra), timeout=timeout)

    def run(
        self,
        select: Optional[str] = None,
        full_refresh: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt run``."""
        extra = []
        if select:
            extra.extend(["--select", select])
        if full_refresh:
            extra.append("--full-refresh")
        return self._run(self._dbt_cmd("run", extra), timeout=timeout)

    def docs_generate(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt docs generate``."""
        return self._run(self._dbt_cmd("docs", ["generate"]), timeout=timeout)

    # ── sqlfluff commands ───────────────────────────────────────────────

    def sqlfluff_lint(
        self,
        paths: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``sqlfluff lint`` against project SQL files."""
        args = ["sqlfluff", "lint", "--dialect", "snowflake"]
        if paths:
            args.extend(paths)
        else:
            args.append(str(self.project_dir / "models"))
        return self._run(args, timeout=timeout, cwd=self.project_dir)

    def sqlfluff_fix(
        self,
        paths: Optional[List[str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``sqlfluff fix`` against project SQL files."""
        args = ["sqlfluff", "fix", "--dialect", "snowflake", "--force"]
        if paths:
            args.extend(paths)
        else:
            args.append(str(self.project_dir / "models"))
        return self._run(args, timeout=timeout, cwd=self.project_dir)

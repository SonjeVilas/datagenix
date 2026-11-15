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

    def _dbt_base_args(self) -> List[str]:
        """Return common dbt CLI flags."""
        args = ["dbt", "--project-dir", str(self.project_dir)]
        if self.profiles_dir:
            args.extend(["--profiles-dir", str(self.profiles_dir)])
        return args

    # ── dbt commands ────────────────────────────────────────────────────

    def debug(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt debug``."""
        return self._run(self._dbt_base_args() + ["debug"], timeout=timeout)

    def deps(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt deps``."""
        return self._run(self._dbt_base_args() + ["deps"], timeout=timeout)

    def parse(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt parse``."""
        return self._run(self._dbt_base_args() + ["parse"], timeout=timeout)

    def compile(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt compile``."""
        return self._run(self._dbt_base_args() + ["compile"], timeout=timeout)

    def test(
        self,
        select: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt test``."""
        args = self._dbt_base_args() + ["test"]
        if select:
            args.extend(["--select", select])
        return self._run(args, timeout=timeout)

    def build(
        self,
        select: Optional[str] = None,
        full_refresh: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt build``."""
        args = self._dbt_base_args() + ["build"]
        if select:
            args.extend(["--select", select])
        if full_refresh:
            args.append("--full-refresh")
        return self._run(args, timeout=timeout)

    def run(
        self,
        select: Optional[str] = None,
        full_refresh: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``dbt run``."""
        args = self._dbt_base_args() + ["run"]
        if select:
            args.extend(["--select", select])
        if full_refresh:
            args.append("--full-refresh")
        return self._run(args, timeout=timeout)

    def docs_generate(self, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
        """Run ``dbt docs generate``."""
        return self._run(self._dbt_base_args() + ["docs", "generate"], timeout=timeout)

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

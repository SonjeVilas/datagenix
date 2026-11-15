"""Unit tests for security protections (path traversal, credentials masking, command safety)."""

from pathlib import Path
from pydantic import SecretStr
import pytest

from backend.executor import ExecutionSecurityError, SafeExecutor
from backend.file_manager import FileManager, SecurityError
from config.settings import Settings


def test_path_traversal_attempts(tmp_path):
    fm = FileManager(tmp_path)
    malicious_paths = [
        "../secret.txt",
        "../../boot.ini",
        "foo/../../etc/passwd",
    ]
    for p in malicious_paths:
        with pytest.raises(SecurityError):
            fm.write_file(p, "bad")


def test_executor_blocks_prod_target(tmp_path):
    executor = SafeExecutor(tmp_path)
    with pytest.raises(ExecutionSecurityError, match="strictly disallowed"):
        executor.execute_with_approval("run", target="prod", user_approved=True)

    with pytest.raises(ExecutionSecurityError, match="strictly disallowed"):
        executor.execute_with_approval("build", target="production", user_approved=True)


def test_executor_requires_approval(tmp_path):
    executor = SafeExecutor(tmp_path)
    res = executor.execute_with_approval("run", target="dev", user_approved=False)
    assert not res["passed"]
    assert res.get("requires_approval")


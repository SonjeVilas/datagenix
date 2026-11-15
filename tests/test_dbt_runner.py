"""Unit tests for DbtRunner subprocess wrapper."""

from unittest.mock import patch, MagicMock
from integrations.dbt_runner import DbtRunner


def test_dbt_runner_parse_invokes_subprocess(tmp_path):
    runner = DbtRunner(project_dir=tmp_path)
    with patch("subprocess.run") as mock_sub:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Parsed 3 models."
        mock_proc.stderr = ""
        mock_sub.return_value = mock_proc

        result = runner.parse()
        assert result.success
        assert result.return_code == 0
        assert "Parsed 3 models." in result.stdout
        # Ensure shell=False (list of args passed)
        args, kwargs = mock_sub.call_args
        assert isinstance(args[0], list)
        assert args[0][0] == "dbt"
        assert "parse" in args[0]


def test_dbt_runner_timeout_handling(tmp_path):
    runner = DbtRunner(project_dir=tmp_path)
    import subprocess
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="dbt compile", timeout=5)):
        result = runner.compile(timeout=5)
        assert not result.success
        assert result.timed_out
        assert "timed out" in result.stderr


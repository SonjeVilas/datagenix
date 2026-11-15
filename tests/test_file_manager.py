"""Unit tests for FileManager and path-traversal security."""

from pathlib import Path
import pytest

from backend.file_manager import FileManager, SecurityError


def test_file_manager_write_and_read(tmp_path):
    fm = FileManager(tmp_path)
    file_path = fm.write_file("sub/test.txt", "hello world")
    assert file_path.exists()
    assert fm.read_file("sub/test.txt") == "hello world"


def test_file_manager_path_traversal_prevention(tmp_path):
    fm = FileManager(tmp_path)
    with pytest.raises(SecurityError):
        fm.write_file("../../../evil.txt", "malicious payload")

    with pytest.raises(SecurityError):
        fm.read_file("../../../secret.env")


def test_file_manager_create_zip(tmp_path):
    fm = FileManager(tmp_path)
    fm.write_file("proj/model.sql", "select 1;")
    fm.write_file("proj/schema.yml", "version: 2")

    zip_file = fm.create_zip("proj", "export")
    assert zip_file.exists()
    assert zip_file.suffix == ".zip"
    assert zip_file.stat().st_size > 0


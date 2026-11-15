"""Safe filesystem operations with path traversal protection and zip archive creation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
from typing import List, Optional
import zipfile

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when an illegal file operation or path traversal is detected."""
    pass


class FileManager:
    """Provides path-traversal protected filesystem operations."""

    def __init__(
        self,
        base_dir: Optional[Path | str] = None,
        base_path: Optional[Path | str] = None,
    ) -> None:
        target = base_dir or base_path
        if target:
            self.base_dir = Path(target).resolve()
        else:
            self.base_dir = Path.cwd().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe(self, target_path: Path | str) -> Path:
        """Resolve target_path and ensure it remains strictly within base_dir."""
        p = Path(target_path)
        if p.is_absolute():
            target = p.resolve()
        else:
            target = (self.base_dir / p).resolve()

        try:
            target.relative_to(self.base_dir)
        except ValueError:
            raise SecurityError(
                f"Path traversal detected! Target path '{target_path}' resolves "
                f"to '{target}', which is outside base directory '{self.base_dir}'."
            )
        return target

    def write_file(self, rel_path: str, content: str, encoding: str = "utf-8") -> Path:
        """Safely write text content to a relative path inside base_dir."""
        safe_path = self._resolve_safe(rel_path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding=encoding)
        logger.debug("Wrote %d bytes to %s", len(content), safe_path)
        return safe_path

    def read_file(self, rel_path: str, encoding: str = "utf-8") -> str:
        """Safely read text content from a relative path inside base_dir."""
        safe_path = self._resolve_safe(rel_path)
        if not safe_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")
        return safe_path.read_text(encoding=encoding)

    def file_exists(self, rel_path: str) -> bool:
        """Check if a file exists safely."""
        safe_path = self._resolve_safe(rel_path)
        return safe_path.is_file()

    def directory_exists(self, rel_path: str) -> bool:
        """Check if a directory exists safely."""
        safe_path = self._resolve_safe(rel_path)
        return safe_path.is_dir()

    def create_directory(self, rel_path: str) -> Path:
        """Safely create a directory inside base_dir."""
        safe_path = self._resolve_safe(rel_path)
        safe_path.mkdir(parents=True, exist_ok=True)
        return safe_path

    def list_files(self, rel_dir: str = "", pattern: str = "*") -> List[str]:
        """List files matching pattern relative to base_dir."""
        safe_dir = self._resolve_safe(rel_dir)
        if not safe_dir.exists():
            return []
        
        file_list: List[str] = []
        for p in safe_dir.rglob(pattern):
            if p.is_file():
                file_list.append(str(p.relative_to(self.base_dir)).replace("\\", "/"))
        return sorted(file_list)

    def create_zip(self, source_rel_dir: str, output_zip_name: str) -> Path:
        """Create a zip archive of source_rel_dir into output_zip_name."""
        source_path = self._resolve_safe(source_rel_dir)
        if not source_path.exists():
            raise FileNotFoundError(f"Directory to zip does not exist: {source_rel_dir}")

        if not output_zip_name.endswith(".zip"):
            output_zip_name += ".zip"
        
        zip_path = self._resolve_safe(output_zip_name)
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_path):
                for file in files:
                    full_file = Path(root) / file
                    # Store relative to source_path parent so zip contains the project folder
                    arcname = full_file.relative_to(source_path.parent)
                    zipf.write(full_file, arcname=str(arcname).replace("\\", "/"))

        logger.info("Created ZIP archive at %s (%d bytes)", zip_path, zip_path.stat().st_size)
        return zip_path

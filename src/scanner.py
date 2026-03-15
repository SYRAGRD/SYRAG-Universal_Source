from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable, List, Optional, Set


logger = logging.getLogger(__name__)


@dataclass
class ScanFile:
    path: Path
    extension: str
    size: int


def discover_files(
    root: Path,
    extensions: Iterable[str],
    *,
    include_hidden: bool = False,
    max_depth: Optional[int] = None,
    max_files: Optional[int] = None,
    exclude_dirs: Optional[Set[str]] = None,
) -> List[ScanFile]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid scan root: {root}")

    norm_exts = {e.lower().strip() for e in extensions if e.strip()}
    if not norm_exts:
        return []

    effective_excludes = exclude_dirs or {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
    }

    root_parts_len = len(root.parts)

    files: List[ScanFile] = []
    for path in root.rglob("*"):
        rel_parts = path.parts[root_parts_len:]

        if any(part in effective_excludes for part in rel_parts):
            continue

        if not include_hidden and any(part.startswith(".") for part in rel_parts):
            continue

        if max_depth is not None and len(rel_parts) > max_depth:
            continue

        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in norm_exts:
            try:
                size = path.stat().st_size
            except OSError as exc:
                logger.warning("Failed to stat file %s: %s", path, exc)
                size = 0
            files.append(ScanFile(path=path, extension=suffix, size=size))
            if max_files is not None and len(files) >= max_files:
                logger.info("Scan capped at max_files=%s", max_files)
                break

    return sorted(files, key=lambda item: str(item.path))

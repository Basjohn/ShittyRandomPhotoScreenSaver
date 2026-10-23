"""D6: writers under the shared data root replace files atomically.

The normal saver and MC share one data root and may run at once; per-path
locks are in-process only, so every shared writer writes a temp file and
replaces it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from core.utils.atomic_files import atomic_write_text

_DATA_ROOT_USE = re.compile(
    r"get_(app_data|cache|rss_cache|feed_cache|state|steam|steam_cache)_dir|"
    r"get_\w+_(file)\(|resolve_app_data_dir|_REDDIT_CACHE_DIR"
)
_RAW_WRITE = re.compile(r"(\w+)\.write_(text|bytes)\(")
_RAW_OPEN = re.compile(r"\bopen\(\s*(\w+)[^)]*['\"][wax]b?['\"]")
# Per-profile settings files are owned by one profile, not the shared root.
_OUT_OF_SCOPE = {"core/settings/settings_manager.py", "core/settings/storage_paths.py"}


def _product_modules() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True, check=True)
    return [
        name for name in listed.stdout.splitlines()
        if name.split("/", 1)[0] in {"core", "ui", "widgets", "sources", "engine", "rendering"}
    ]


def test_data_root_writers_only_write_temp_files_directly() -> None:
    offenders = []
    for module in _product_modules():
        if module in _OUT_OF_SCOPE:
            continue
        source = Path(module).read_text(encoding="utf-8")
        if not _DATA_ROOT_USE.search(source):
            continue
        for number, line in enumerate(source.splitlines(), 1):
            for pattern in (_RAW_WRITE, _RAW_OPEN):
                match = pattern.search(line)
                if match and not re.search(r"tmp|temp", match.group(1), re.IGNORECASE):
                    offenders.append(f"{module}:{number}: {line.strip()}")
    assert offenders == []


def test_atomic_write_replaces_whole_file_and_cleans_up_on_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "nested" / "cache.json"
    atomic_write_text(target, "old")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert sorted(p.name for p in target.parent.iterdir()) == ["cache.json"]

    import core.utils.atomic_files as atomic_files

    def failing_replace(_src, _dst):
        raise PermissionError("locked")

    monkeypatch.setattr(atomic_files.os, "replace", failing_replace)
    with pytest.raises(PermissionError):
        atomic_write_text(target, "lost")
    assert target.read_text(encoding="utf-8") == "new"
    assert sorted(p.name for p in target.parent.iterdir()) == ["cache.json"]

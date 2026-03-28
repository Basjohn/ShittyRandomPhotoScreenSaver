"""Shipped curated visualizer preset manifest and extraction-tree sync."""

from __future__ import annotations

import builtins
import json
import re
import sys
from pathlib import Path
from typing import Collection

from core.logging.logger import get_logger

logger = get_logger(__name__)

_MANAGED_PRESET_NAME_RE = re.compile(r"^preset[_-]*\d+(?:[_-].+)?\.json$", re.IGNORECASE)


def _is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False)) or bool(getattr(builtins, "__compiled__", False))


def get_visualizer_preset_manifest_path(root: Path | None = None) -> Path:
    presets_root = root or (Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes")
    return presets_root.parent / "visualizer_modes_manifest.json"


def load_curated_visualizer_preset_manifest(root: Path | None = None) -> set[str]:
    manifest_path = get_visualizer_preset_manifest_path(root)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("[VIS_PRESET_MANIFEST] Failed to load %s: %s", manifest_path, exc)
        return set()

    entries = payload.get("managed_curated_files") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return set()
    return {
        Path(str(entry)).as_posix()
        for entry in entries
        if isinstance(entry, str) and entry.strip()
    }


def is_managed_curated_preset_path(relative_path: Path) -> bool:
    if len(relative_path.parts) != 2:
        return False
    if relative_path.suffix.lower() != ".json":
        return False
    stem = relative_path.stem.lower()
    if "custom" in stem:
        return False
    return bool(_MANAGED_PRESET_NAME_RE.match(relative_path.name))


def sync_curated_preset_tree(
    root: Path,
    *,
    manifest_entries: Collection[str] | None = None,
    allow_non_frozen: bool = False,
) -> list[Path]:
    """Remove stale shipped curated preset files from a stable extraction tree."""
    if not allow_non_frozen and not _is_frozen_build():
        return []
    if not root.exists() or not root.is_dir():
        return []

    managed_entries = {
        Path(str(entry)).as_posix()
        for entry in (
            manifest_entries if manifest_entries is not None else load_curated_visualizer_preset_manifest(root)
        )
        if str(entry).strip()
    }
    if not managed_entries:
        return []

    removed: list[Path] = []
    for json_path in root.rglob("*.json"):
        try:
            relative_path = json_path.relative_to(root)
        except Exception:
            continue
        normalized = relative_path.as_posix()
        if normalized in managed_entries:
            continue
        if not is_managed_curated_preset_path(relative_path):
            continue
        try:
            json_path.unlink()
            removed.append(json_path)
        except Exception as exc:
            logger.warning("[VIS_PRESET_MANIFEST] Failed to remove stale preset %s: %s", json_path, exc)

    if removed:
        logger.info("[VIS_PRESET_MANIFEST] Removed %d stale shipped curated preset file(s)", len(removed))
    return removed

"""Shipped curated visualizer preset manifest and extraction-tree sync."""

from __future__ import annotations

import builtins
import json
import re
import shutil
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


def _normalize_manifest_entries(entries: object) -> set[str]:
    if not isinstance(entries, list):
        return set()
    return {
        Path(str(entry)).as_posix()
        for entry in entries
        if isinstance(entry, str) and entry.strip()
    }


def build_curated_visualizer_manifest_payload(entries: Collection[str]) -> dict[str, list[str]]:
    """Build the canonical manifest payload for a curated preset tree."""
    normalized = {
        Path(str(entry)).as_posix()
        for entry in entries
        if str(entry).strip()
    }
    return {
        "managed_curated_files": sorted(normalized),
    }


def scan_curated_visualizer_preset_tree(root: Path) -> set[str]:
    """Return managed curated preset paths that currently exist under *root*."""
    if not root.exists() or not root.is_dir():
        return set()
    discovered: set[str] = set()
    for json_path in root.rglob("*.json"):
        try:
            relative_path = json_path.relative_to(root)
        except Exception:
            continue
        if not is_managed_curated_preset_path(relative_path):
            continue
        discovered.add(relative_path.as_posix())
    return discovered


def load_curated_visualizer_preset_manifest(root: Path | None = None) -> set[str]:
    manifest_path = get_visualizer_preset_manifest_path(root)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("[VIS_PRESET_MANIFEST] Failed to load %s: %s", manifest_path, exc)
        return set()

    entries = payload.get("managed_curated_files") if isinstance(payload, dict) else payload
    return _normalize_manifest_entries(entries)


def write_curated_visualizer_preset_manifest(
    root: Path,
    entries: Collection[str] | None = None,
) -> set[str]:
    """Write a canonical manifest for the curated preset tree under *root*."""
    resolved_entries = {
        Path(str(entry)).as_posix()
        for entry in (entries if entries is not None else scan_curated_visualizer_preset_tree(root))
        if str(entry).strip()
    }
    manifest_path = get_visualizer_preset_manifest_path(root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_curated_visualizer_manifest_payload(resolved_entries)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return resolved_entries


def resolve_curated_visualizer_manifest_entries(root: Path) -> set[str]:
    """Return manifest entries reconciled with the live curated source tree.

    This is intended for source-tree aware operations such as replacement from
    shipped assets. Missing manifest updates should not make freshly-authored
    curated presets invisible, and stale manifest paths should not make those
    operations fail.
    """
    manifest_entries = load_curated_visualizer_preset_manifest(root)
    live_entries = scan_curated_visualizer_preset_tree(root)
    if not manifest_entries:
        return live_entries
    if not live_entries:
        return manifest_entries

    stale_manifest = manifest_entries - live_entries
    missing_manifest = live_entries - manifest_entries
    if stale_manifest:
        logger.info(
            "[VIS_PRESET_MANIFEST] Ignoring %d stale manifest entrie(s) missing from %s",
            len(stale_manifest),
            root,
        )
    if missing_manifest:
        logger.info(
            "[VIS_PRESET_MANIFEST] Auto-accepting %d live curated preset file(s) missing from manifest under %s",
            len(missing_manifest),
            root,
        )
    return (manifest_entries & live_entries) | missing_manifest


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


def mirror_curated_visualizer_preset_tree(
    source_root: Path,
    target_root: Path,
    *,
    manifest_entries: Collection[str] | None = None,
) -> set[str]:
    """Mirror the authoritative curated preset tree into another managed tree.

    The source tree is treated as authoritative. The target tree is pruned of
    stale managed preset files, then rewritten from source, and finally gets a
    canonical manifest generated from the mirrored result.
    """
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"Curated preset source root does not exist: {source_root}")

    resolved_entries = {
        Path(str(entry)).as_posix()
        for entry in (
            manifest_entries if manifest_entries is not None else resolve_curated_visualizer_manifest_entries(source_root)
        )
        if str(entry).strip()
    }
    if not resolved_entries:
        raise RuntimeError(f"No curated preset entries were discovered under {source_root}")

    target_root.mkdir(parents=True, exist_ok=True)
    sync_curated_preset_tree(
        target_root,
        manifest_entries=resolved_entries,
        allow_non_frozen=True,
    )

    missing_sources: list[str] = []
    for entry in sorted(resolved_entries):
        rel_path = Path(entry)
        source_path = source_root / rel_path
        if not source_path.exists():
            missing_sources.append(rel_path.as_posix())
            continue
        target_path = target_root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    if missing_sources:
        raise FileNotFoundError(
            "Missing curated preset source files during mirror: " + ", ".join(missing_sources[:5])
        )

    write_curated_visualizer_preset_manifest(target_root, resolved_entries)
    logger.info(
        "[VIS_PRESET_MANIFEST] Mirrored %d curated preset file(s) from %s into %s",
        len(resolved_entries),
        source_root,
        target_root,
    )
    return resolved_entries


def regenerate_repo_shipped_visualizer_preset_artifacts(repo_root: Path | None = None) -> dict[str, object]:
    """Regenerate repo-local visualizer preset artifacts from the source tree.

    Source-of-truth:
    - ``<repo>/presets/visualizer_modes``

    Generated artifacts:
    - ``<repo>/presets/visualizer_modes_manifest.json``
    - ``<repo>/release/main_mc.dist/presets/visualizer_modes``
    - ``<repo>/release/main_mc.dist/presets/visualizer_modes_manifest.json``
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    source_root = root / "presets" / "visualizer_modes"
    release_root = root / "release" / "main_mc.dist" / "presets" / "visualizer_modes"

    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"Authoritative visualizer preset source tree not found: {source_root}")

    source_entries = write_curated_visualizer_preset_manifest(source_root)
    mirrored_entries = mirror_curated_visualizer_preset_tree(
        source_root,
        release_root,
        manifest_entries=source_entries,
    )
    return {
        "source_root": source_root,
        "release_root": release_root,
        "entry_count": len(source_entries),
        "entries": mirrored_entries,
    }

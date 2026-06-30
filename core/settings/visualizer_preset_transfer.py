"""Import/export helpers for visualizer curated preset trees."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from core.logging.logger import get_logger
from core.visualizer_preset_manifest import (
    mirror_curated_visualizer_preset_tree,
    resolve_curated_visualizer_manifest_entries,
    write_curated_visualizer_preset_manifest,
)
from core.settings import visualizer_presets as vp

logger = get_logger(__name__)


@dataclass(frozen=True)
class VisualizerPresetTransferResult:
    """Summary of a visualizer preset import/export operation."""

    files: int
    root: Path


def export_visualizer_presets_zip(
    zip_path: str | Path,
    *,
    source_root: Path | None = None,
) -> VisualizerPresetTransferResult:
    """Export the active curated visualizer preset tree to a zip archive."""

    root = Path(source_root) if source_root is not None else vp.get_visualizer_presets_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"Visualizer presets root does not exist: {root}")

    entries = write_curated_visualizer_preset_manifest(
        root,
        resolve_curated_visualizer_manifest_entries(root),
    )
    target = Path(zip_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for entry in sorted(entries):
            source = root / Path(entry)
            if source.is_file():
                archive.write(source, Path("visualizer_modes") / Path(entry))
        manifest = root.parent / "visualizer_modes_manifest.json"
        if manifest.is_file():
            archive.write(manifest, "visualizer_modes_manifest.json")

    logger.info("[VIS_PRESET_TRANSFER] Exported %d preset file(s) to %s", len(entries), target)
    return VisualizerPresetTransferResult(files=len(entries), root=root)


def import_visualizer_presets_archive(
    archive_path: str | Path,
    *,
    target_root: Path | None = None,
) -> VisualizerPresetTransferResult:
    """Replace the active curated preset tree from a zip archive."""

    source_archive = Path(archive_path)
    if not source_archive.is_file():
        raise FileNotFoundError(f"Visualizer preset archive does not exist: {source_archive}")

    with tempfile.TemporaryDirectory(prefix="srpss_viz_presets_") as tmp:
        tmp_root = Path(tmp)
        with ZipFile(source_archive, "r") as archive:
            _extract_archive_safely(archive, tmp_root)
        source_root = _resolve_import_tree_root(tmp_root)
        return _replace_curated_tree(source_root, target_root=target_root)


def import_visualizer_presets_folder(
    folder_path: str | Path,
    *,
    target_root: Path | None = None,
) -> VisualizerPresetTransferResult:
    """Replace the active curated preset tree from a folder."""

    source_root = _resolve_import_tree_root(Path(folder_path))
    return _replace_curated_tree(source_root, target_root=target_root)


def import_visualizer_preset_json_files(
    json_paths: Iterable[str | Path],
    *,
    target_root: Path | None = None,
) -> VisualizerPresetTransferResult:
    """Import loose JSON preset files into their inferred mode/slot folders."""

    root = Path(target_root) if target_root is not None else vp.get_visualizer_presets_dir()
    root.mkdir(parents=True, exist_ok=True)

    written = 0
    for raw_path in json_paths:
        path = Path(raw_path)
        mode, index, payload = _canonicalize_loose_preset(path)
        mode_dir = root / mode
        mode_dir.mkdir(parents=True, exist_ok=True)
        _remove_existing_slot_file(mode_dir, index)
        target_path = mode_dir / _target_filename(path, payload, index)
        target_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written += 1

    write_curated_visualizer_preset_manifest(root)
    vp.reload_presets()
    logger.info("[VIS_PRESET_TRANSFER] Imported %d loose preset file(s) into %s", written, root)
    return VisualizerPresetTransferResult(files=written, root=root)


def import_visualizer_presets_path(
    path: str | Path,
    *,
    target_root: Path | None = None,
) -> VisualizerPresetTransferResult:
    """Import a zip archive, folder, or single loose JSON preset file."""

    source = Path(path)
    if source.is_dir():
        return import_visualizer_presets_folder(source, target_root=target_root)
    if source.suffix.lower() == ".zip":
        return import_visualizer_presets_archive(source, target_root=target_root)
    if source.suffix.lower() == ".json":
        return import_visualizer_preset_json_files([source], target_root=target_root)
    raise ValueError(f"Unsupported visualizer preset import type: {source}")


def _replace_curated_tree(source_root: Path, *, target_root: Path | None = None) -> VisualizerPresetTransferResult:
    root = Path(target_root) if target_root is not None else vp.get_visualizer_presets_dir()
    entries = mirror_curated_visualizer_preset_tree(source_root, root)
    vp.reload_presets()
    logger.info("[VIS_PRESET_TRANSFER] Replaced curated preset tree at %s from %s", root, source_root)
    return VisualizerPresetTransferResult(files=len(entries), root=root)


def _extract_archive_safely(archive: ZipFile, target_dir: Path) -> None:
    resolved_target = target_dir.resolve()
    for member in archive.infolist():
        destination = (target_dir / member.filename).resolve()
        if resolved_target != destination and resolved_target not in destination.parents:
            raise ValueError(f"Unsafe visualizer preset archive path: {member.filename}")
    archive.extractall(target_dir)


def _resolve_import_tree_root(path: Path) -> Path:
    if not path.is_dir():
        raise FileNotFoundError(f"Visualizer preset folder does not exist: {path}")
    if (path / "visualizer_modes").is_dir():
        return path / "visualizer_modes"
    if _contains_mode_dirs(path):
        return path
    raise FileNotFoundError(f"No visualizer_modes tree found under {path}")


def _contains_mode_dirs(path: Path) -> bool:
    return any((path / mode).is_dir() for mode in vp.MODES)


def _canonicalize_loose_preset(path: Path) -> tuple[str, int, dict[str, Any]]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to parse visualizer preset JSON {path}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ValueError(f"Visualizer preset JSON root must be an object: {path}")

    mode = _infer_mode(path, loaded)
    parsed = vp._parse_preset_payload(  # type: ignore[attr-defined]
        path,
        loaded,
        mode,
        prefer_filename_index=True,
        prefer_filename_name=True,
    )
    if parsed is None:
        raise ValueError(f"Could not read a {mode} preset payload from {path}")

    index, preset = parsed
    payload = {
        "mode": mode,
        "name": preset.name,
        "description": preset.description,
        "preset_index": index,
        "snapshot": {
            "widgets": {
                "spotify_visualizer": dict(preset.settings),
            },
        },
    }
    return mode, index, payload


def _infer_mode(path: Path, payload: Mapping[str, Any]) -> str:
    candidates = [
        payload.get("visualizer_preset_mode"),
        payload.get("mode"),
        _nested_mode(payload.get("settings")),
        _nested_mode(payload.get("snapshot")),
        path.parent.name,
    ]
    for candidate in candidates:
        mode = str(candidate).strip().lower() if candidate is not None else ""
        if mode in vp.MODES:
            return mode
    raise ValueError(f"Could not infer visualizer mode for {path}")


def _nested_mode(section: Any) -> Any:
    if not isinstance(section, Mapping):
        return None
    mode = section.get("mode")
    if mode is not None:
        return mode
    widgets = section.get("widgets")
    if isinstance(widgets, Mapping):
        spotify = widgets.get("spotify_visualizer")
        if isinstance(spotify, Mapping):
            return spotify.get("mode")
    return None


_SAFE_FILENAME_RE = re.compile(r"[^a-z0-9_]+")


def _target_filename(source_path: Path, payload: Mapping[str, Any], index: int) -> str:
    suffix = vp._infer_suffix_from_name(source_path.stem)  # type: ignore[attr-defined]
    if not suffix:
        name = str(payload.get("name") or "").strip()
        match = re.search(r"\(([^)]+)\)", name)
        suffix = match.group(1) if match else ""
    safe_suffix = _SAFE_FILENAME_RE.sub("_", str(suffix).strip().lower()).strip("_")
    if safe_suffix:
        return f"preset_{index + 1}_{safe_suffix}.json"
    return f"preset_{index + 1}.json"


def _remove_existing_slot_file(mode_dir: Path, index: int) -> None:
    for existing in mode_dir.glob("preset_*.json"):
        existing_index = vp._infer_preset_index_from_name(existing.stem)  # type: ignore[attr-defined]
        if existing_index != index:
            continue
        try:
            existing.unlink()
        except Exception as exc:
            logger.warning("[VIS_PRESET_TRANSFER] Failed to remove stale preset %s: %s", existing, exc)

"""Shape-preserving edits of an authored visualizer preset file (one owner for every writer).

Curated preset files are operator-authored. Anything that rewrites one (the preset repair tool's
repair, the Studio's Save To <Preset>) patches the file's own visualizer sections in place and
serialises it the way the file was written: existing keys keep their order and their values unless
changed, metadata and inert keys survive, and the file keeps its indentation, escaping, line endings
and final newline. Paths come only from the canonical preset owner
(:func:`core.settings.visualizer_presets.get_preset_file_path`), which is reloaded after a write.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Tuple

from core.settings import visualizer_presets as vp
from core.settings.visualizer_settings_contract import LEGACY_GLOBAL_SHARED_VISUAL_KEYS
from core.settings.visualizer_settings_snapshot import _TECHNICAL_GLOBAL_KEYS, normalize_visualizer_mode_payload

MANDATORY_TECH_SUFFIXES: Tuple[str, ...] = tuple(sorted(_TECHNICAL_GLOBAL_KEYS))
DEPRECATED_AUTHORED_GLOBAL_KEYS: Tuple[str, ...] = (
    "bar_fill_color",
    "bar_border_color",
    "bar_border_opacity",
    "ghosting_enabled",
    "ghost_alpha",
    "ghost_decay",
)
DEPRECATED_MODE_ALIAS_KEYS: Dict[str, Tuple[str, ...]] = {
    "oscilloscope": ("osc_sensitivity",),
}
_DOTTED_PREFIX = "widgets.spotify_visualizer."

_DEFAULTS_CACHE: Dict[str, Any] | None = None


def load_visualizer_defaults() -> Dict[str, Any]:
    """The canonical ``widgets.spotify_visualizer`` defaults (a copy)."""
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        from core.settings.defaults import get_default_settings

        _DEFAULTS_CACHE = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
    return deepcopy(_DEFAULTS_CACHE)


def canonical_mode_defaults(mode: str) -> Dict[str, Any]:
    defaults = load_visualizer_defaults()
    defaults["mode"] = mode
    return normalize_visualizer_mode_payload(mode, defaults)


def is_visualizer_setting_key(key: Any) -> bool:
    """A key the preset writers own: any mode's setting family, a shared/legacy visualizer key or a retired alias."""
    if not isinstance(key, str):
        return False
    if key in vp.GLOBAL_ALLOWED_KEYS or key in LEGACY_GLOBAL_SHARED_VISUAL_KEYS:
        return True
    if key in DEPRECATED_AUTHORED_GLOBAL_KEYS or key in MANDATORY_TECH_SUFFIXES:
        return True
    if any(key in aliases for aliases in DEPRECATED_MODE_ALIAS_KEYS.values()):
        return True
    return any(
        prefix and key.startswith(prefix)
        for prefixes in vp.MODE_KEY_PREFIXES.values()  # type: ignore[attr-defined]
        for prefix in prefixes
    )


def merge_section(mode: str, original: Mapping[str, Any], cleaned: Mapping[str, Any]) -> Dict[str, Any]:
    """Return ``original`` patched with ``cleaned``, keeping the authored file's own shape.

    Existing keys keep their position (a value changes only where ``cleaned`` changes it); a key is
    removed only when it is a visualizer setting ``cleaned`` lacks, while inert authored entries (the view
    pose inside the artwork, ``preset_<mode>`` slot metadata, notes) stay verbatim. New controls go into a
    key-sorted section at their sorted place, otherwise right after their nearest registry predecessor that
    the section already has (before the nearest successor, else at the end).
    """
    from core.settings.visualizer_view_orbit import get_visualizer_view_pose_keys

    pose = set(get_visualizer_view_pose_keys(mode))
    merged: Dict[str, Any] = {}
    for key, value in original.items():
        if key in cleaned:
            merged[key] = deepcopy(cleaned[key])
        elif key in pose or not is_visualizer_setting_key(key):
            merged[key] = deepcopy(value)
    missing = [key for key in cleaned if key not in merged]
    if not missing:
        return merged
    string_keys = [key for key in merged if isinstance(key, str)]
    if len(string_keys) == len(merged) and string_keys == sorted(string_keys):
        for key in missing:
            merged[key] = deepcopy(cleaned[key])
        return {key: merged[key] for key in sorted(merged)}
    registry = list(dict.fromkeys([*vp.preset_artwork_keys(mode), *canonical_mode_defaults(mode), *cleaned]))
    rank = {key: index for index, key in enumerate(registry)}
    order = list(merged)
    for key in sorted(missing, key=lambda item: rank.get(item, len(rank))):
        position = rank.get(key, len(rank))
        before = [i for i, existing in enumerate(order) if existing in rank and rank[existing] < position]
        after = [i for i, existing in enumerate(order) if existing in rank and rank[existing] > position]
        if before:
            order.insert(max(before, key=lambda i: rank[order[i]]) + 1, key)
        elif after:
            order.insert(min(after, key=lambda i: rank[order[i]]), key)
        else:
            order.append(key)
        merged[key] = deepcopy(cleaned[key])
    return {key: merged[key] for key in order}


def _patch_dotted(section: Dict[str, Any], merged: Callable[[Mapping[str, Any]], Dict[str, Any]]) -> bool:
    """Patch a section's ``widgets.spotify_visualizer.<key>`` entries in place, where the first of them stood."""
    dotted_keys = [key for key in list(section) if isinstance(key, str) and key.startswith(_DOTTED_PREFIX)]
    if not dotted_keys:
        return False
    block = merged({key[len(_DOTTED_PREFIX):]: section[key] for key in dotted_keys})
    rebuilt: Dict[str, Any] = {}
    for key, value in section.items():
        if key == dotted_keys[0]:
            rebuilt.update({f"{_DOTTED_PREFIX}{name}": item for name, item in block.items()})
        elif key not in dotted_keys:
            rebuilt[key] = value
    section.clear()
    section.update(rebuilt)
    return True


def _patch_live_sections(payload: Dict[str, Any], merged: Callable[[Mapping[str, Any]], Dict[str, Any]]) -> list[str]:
    """Patch the live visualizer sections (snapshot widgets, direct, settings) in place; returns their paths."""
    updated: list[str] = []
    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        widgets_section = snapshot.get("widgets")
        if isinstance(widgets_section, dict) and isinstance(widgets_section.get("spotify_visualizer"), Mapping):
            widgets_section["spotify_visualizer"] = merged(widgets_section["spotify_visualizer"])
            updated.append("snapshot.widgets.spotify_visualizer")
    if isinstance(payload.get("spotify_visualizer"), Mapping):
        payload["spotify_visualizer"] = merged(payload["spotify_visualizer"])
        updated.append("spotify_visualizer")
    settings_section = payload.get("settings")
    if isinstance(settings_section, dict):
        if not _patch_dotted(settings_section, merged):
            payload["settings"] = merged(settings_section)
        updated.append("settings")
    return updated


def apply_cleaned_payload_in_place(payload: Dict[str, Any], cleaned: Mapping[str, Any]) -> list[str]:
    """The repair's patch: every live block becomes ``cleaned`` (its full sanitised settings) in the block's
    own shape; a legacy Custom backup is dropped (a backup-only payload migrates to one live section)."""
    cleaned_block = deepcopy(dict(cleaned))
    mode = str(cleaned_block.get("mode") or "")

    def merged(original: Any) -> Dict[str, Any]:
        if not mode or not isinstance(original, Mapping):
            return deepcopy(cleaned_block)
        return merge_section(mode, original, cleaned_block)

    updated_paths = _patch_live_sections(payload, merged)
    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("custom_preset_backup"), dict):
        snapshot.pop("custom_preset_backup", None)
        updated_paths.insert(1 if "snapshot.widgets.spotify_visualizer" in updated_paths else 0,
                             "snapshot.custom_preset_backup")

    if any(path != "snapshot.custom_preset_backup" for path in updated_paths):
        return list(dict.fromkeys(updated_paths))

    # Forward-migrate a legacy backup-only payload into its one live section.
    snapshot_map = payload.get("snapshot")
    if not isinstance(snapshot_map, dict):
        snapshot_map = {}
        payload["snapshot"] = snapshot_map
    widgets_map = snapshot_map.get("widgets")
    if not isinstance(widgets_map, dict):
        widgets_map = {}
        snapshot_map["widgets"] = widgets_map
    widgets_map["spotify_visualizer"] = deepcopy(cleaned_block)
    return [*updated_paths, "snapshot.widgets.spotify_visualizer"]


def apply_setting_changes_in_place(payload: Dict[str, Any], mode: str, changes: Mapping[str, Any]) -> list[str]:
    """Write ``changes`` into every visualizer section the preset loader reads, touching nothing else.

    Existing keys keep their place, a key the section lacks goes in by the merge's ordering rule; no key
    is removed and no section is added or dropped."""
    changes = deepcopy(dict(changes))

    def merged(original: Mapping[str, Any]) -> Dict[str, Any]:
        return merge_section(mode, original, {**original, **changes})

    updated = _patch_live_sections(payload, merged)
    snapshot = payload.get("snapshot")
    backup = snapshot.get("custom_preset_backup") if isinstance(snapshot, dict) else None
    if isinstance(backup, dict) and _patch_dotted(backup, merged):
        updated.append("snapshot.custom_preset_backup")
    return updated


def key_order(value: Any) -> Any:
    """Nested key order of a JSON value (dict equality ignores order)."""
    if isinstance(value, Mapping):
        return [(key, key_order(item)) for key, item in value.items()]
    if isinstance(value, list):
        return [key_order(item) for item in value]
    return None


def format_like_source(payload: Mapping[str, Any], source_text: str) -> str:
    """Serialize ``payload`` with the source file's indentation, escaping, line endings and final newline."""
    indent: int | str = 2
    for line in source_text.splitlines()[1:]:
        stripped = line.lstrip(" \t")
        if stripped and len(stripped) < len(line):
            leading = line[: len(line) - len(stripped)]
            indent = leading if "\t" in leading else len(leading)
            break
    ensure_ascii = all(ord(ch) < 128 for ch in source_text)
    text = json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii)
    if source_text.endswith("\n") or not source_text:
        text += "\n"
    if "\r\n" in source_text:
        text = text.replace("\n", "\r\n")
    return text


# ------------------------------------------------------------------------------ save into a curated preset
class PresetFileReadOnly(OSError):
    """The curated preset's file cannot be written here (for example an installed, read-only copy)."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"{path} is read-only")
        self.path = Path(path)


@dataclass(frozen=True)
class PresetSaveResult:
    path: Path
    changed: Tuple[str, ...]          # setting keys written (plus "starting_view" when the view was)
    written: bool                     # False: the file already held these values; nothing was written


def preset_file_writable(path: Path) -> bool:
    path = Path(path)
    return os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)


_MISSING = object()


def preset_setting_changes(mode: str, index: int, payload: Mapping[str, Any], edited) -> Dict[str, Any]:
    """The settings of ``payload`` (a Save-As shaped payload of the current values) to write into curated
    preset ``index``: only ``edited`` keys whose value differs from what selecting that preset resolves
    (its own settings over the canonical mode defaults). The view pose is never one of them."""
    from core.settings.visualizer_view_orbit import get_visualizer_view_pose_keys

    current = vp.resolve_preset_payload_settings(mode, payload)
    baseline = canonical_mode_defaults(mode)
    baseline.update(vp.get_preset_settings(mode, index))
    pose = set(get_visualizer_view_pose_keys(mode))
    return {key: deepcopy(current[key]) for key in sorted(set(edited))
            if key in current and key != "mode" and key not in pose
            and baseline.get(key, _MISSING) != current[key]}


def save_changes_to_preset(mode: str, index: int, changes: Mapping[str, Any], *,
                           starting_view: Mapping[str, Any] | None = None) -> PresetSaveResult:
    """Write ``changes`` (and the starting view, when given) into curated preset ``index``'s own file,
    preserving its authored shape, then reload the mode's presets. Raises :class:`PresetFileReadOnly`
    when the location cannot be written and ``FileNotFoundError`` when the slot has no file."""
    from core.utils.atomic_files import atomic_write_bytes

    path = vp.get_preset_file_path(mode, index)
    if path is None:
        raise FileNotFoundError(f"{mode} preset {index + 1} has no file on disk")
    original_bytes = path.read_bytes()
    source_text = original_bytes.decode("utf-8")
    payload = json.loads(source_text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    patched = deepcopy(payload)
    written_keys = list(changes)
    if changes:
        apply_setting_changes_in_place(patched, mode, changes)
    if starting_view is not None:
        patched["starting_view"] = deepcopy(dict(starting_view))
        written_keys.append("starting_view")
    if patched == payload and key_order(patched) == key_order(payload):
        return PresetSaveResult(path, (), False)
    resolved = vp.resolve_preset_payload_settings(mode, patched)
    unresolved = [key for key, value in changes.items() if resolved.get(key, _MISSING) != value]
    if unresolved:
        raise ValueError(f"{path.name} would not load these values: {', '.join(unresolved)}")
    if not preset_file_writable(path):
        raise PresetFileReadOnly(path)
    if path.read_bytes() != original_bytes:
        raise RuntimeError(f"{path.name} changed on disk while saving; nothing was written")
    try:
        atomic_write_bytes(path, format_like_source(patched, source_text).encode("utf-8"))
    except PermissionError as exc:
        raise PresetFileReadOnly(path) from exc
    vp.reload_presets(mode)
    return PresetSaveResult(path, tuple(written_keys), True)


__all__ = [
    "DEPRECATED_AUTHORED_GLOBAL_KEYS", "DEPRECATED_MODE_ALIAS_KEYS", "MANDATORY_TECH_SUFFIXES",
    "PresetFileReadOnly", "PresetSaveResult", "apply_cleaned_payload_in_place", "apply_setting_changes_in_place",
    "canonical_mode_defaults", "format_like_source", "is_visualizer_setting_key", "key_order",
    "load_visualizer_defaults", "merge_section", "preset_file_writable", "preset_setting_changes",
    "save_changes_to_preset",
]

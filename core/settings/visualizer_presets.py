"""Per-visualizer-mode preset system.

Each visualizer mode has a curated slot list loaded from disk plus a trailing
Custom slot that reflects the user's live settings. Curated slot counts are
mode-authored and may grow over time; callers must not assume a fixed count.

Presets are orthogonal to the global widget presets in core/settings/presets.py.
Global presets control *which widgets are visible*; visualizer presets control
*how a visualizer mode looks/behaves*.

Usage:
    from core.settings.visualizer_presets import get_presets, apply_preset, MODES
    presets = get_presets("spectrum")   # list of 4 VisualizerPreset
    apply_preset(settings_manager, "spectrum", 0)  # apply Preset 1
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import builtins
import json
import os
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, TYPE_CHECKING

from core.logging.logger import get_logger
from core.visualizer_preset_manifest import mirror_curated_visualizer_preset_tree, sync_curated_preset_tree
from core.settings.visualizer_preset_indices import (
    get_missing_preset_fallback_index,          # noqa: F401  intentional re-export
    resolve_all_preset_indices_from_getter,     # noqa: F401  intentional re-export
    resolve_all_preset_indices_from_mapping,    # noqa: F401  intentional re-export
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_preset_key,
    get_setting_prefixes,
)
from core.settings.visualizer_settings_contract import (
    normalize_spectrum_render_mode,
)
from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)

DEFAULT_CURATED_SLOTS = 3
VISUALIZER_CUSTOM_STORAGE_KEY = "visualizer_custom_presets"

_PLACEHOLDER_NAME_RE = re.compile(
    r"^preset\s*(?:\d+)?\s*$",
    flags=re.IGNORECASE,
)

GLOBAL_ALLOWED_KEYS = {
    "bar_border_color",
    "bar_border_opacity",
    "bar_fill_color",
    "ghost_alpha",
    "ghost_decay",
    "ghosting_enabled",
    "monitor",
    "mode",
}
# rainbow_enabled / rainbow_speed are now per-mode keys (e.g. spectrum_rainbow_enabled)
# and match MODE_KEY_PREFIXES automatically. Kept out of GLOBAL_ALLOWED_KEYS so presets
# only carry each mode's own rainbow state.

MODE_KEY_PREFIXES: Dict[str, List[str]] = {
    mode_id: list(get_setting_prefixes(mode_id))
    for mode_id in VISUALIZER_MODE_IDS
}

# All visualizer modes that support presets
MODES: List[str] = list(VISUALIZER_MODE_IDS)


def _is_key_for_mode(key: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return False
    candidate = key
    dotted_prefix = "widgets.spotify_visualizer."
    if candidate.startswith(dotted_prefix):
        candidate = candidate[len(dotted_prefix):]
    return any(candidate.startswith(prefix) for prefix in prefixes)


def _is_global_visualizer_key(key: str) -> bool:
    if key in GLOBAL_ALLOWED_KEYS:
        return True
    return key in {
        "mode",
        "enabled",
        "visualizers_enabled",
        "monitor",
        "ghosting_enabled",
        "ghost_alpha",
        "ghost_decay",
        "rainbow_enabled",
        "rainbow_speed",
    }


def extract_visualizer_snapshot(mode_key: str, spotify_vis_config: Mapping[str, Any]) -> Dict[str, Any]:
    prefixes = MODE_KEY_PREFIXES.get(mode_key, [])
    snapshot: Dict[str, Any] = {}
    for key, value in spotify_vis_config.items():
        if key == VISUALIZER_CUSTOM_STORAGE_KEY:
            continue
        if key.startswith("preset_") and key != f"preset_{mode_key}":
            continue
        if _is_key_for_mode(key, prefixes) or _is_global_visualizer_key(key):
            snapshot[key] = deepcopy(value)
    return snapshot


def build_normalized_custom_snapshot(mode_key: str, spotify_vis_config: Mapping[str, Any]) -> Dict[str, Any]:
    normalized_live = normalize_visualizer_section_mapping(
        dict(spotify_vis_config),
        apply_preset_overlay=False,
    )
    snapshot = extract_visualizer_snapshot(mode_key, normalized_live)
    return normalize_visualizer_mode_payload(mode_key, snapshot)


@dataclass(frozen=True)
class VisualizerActivationPayload:
    mode: str
    preset_index: int
    is_custom: bool
    preset_name: str
    preset_path: str | None
    resolved_config: Dict[str, Any]


def resolve_visualizer_activation_payload(
    config: Mapping[str, Any] | None,
    *,
    mode: str | None = None,
    prefix: str = "widgets.spotify_visualizer",
) -> VisualizerActivationPayload:
    """Resolve one canonical runtime/settings activation payload."""
    source = dict(config) if isinstance(config, Mapping) else {}
    normalized_live = normalize_visualizer_section_mapping(
        source,
        prefix=prefix,
        apply_preset_overlay=False,
    )
    mode_key = str(mode or normalized_live.get("mode") or source.get("mode") or "bubble")
    mode_key = builtins.str(mode_key).strip().lower()
    if mode_key not in MODES:
        mode_key = "bubble"

    normalized_live["mode"] = mode_key
    preset_index = resolve_preset_index_from_mapping(mode_key, normalized_live, prefix=prefix)
    resolved_config = apply_preset_to_config(mode_key, preset_index, dict(normalized_live))
    resolved_config["mode"] = mode_key
    resolved_config = normalize_visualizer_section_mapping(
        resolved_config,
        prefix=prefix,
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    resolved_config["mode"] = mode_key

    preset_key = get_preset_key(mode_key)
    resolved_config[preset_key] = preset_index

    custom_index = get_custom_preset_index(mode_key)
    is_custom = preset_index == custom_index
    preset_name = "Custom"
    preset_path: str | None = None
    presets = get_presets(mode_key)
    if 0 <= preset_index < len(presets):
        preset_name = presets[preset_index].name
    if not is_custom:
        path = get_preset_file_path(mode_key, preset_index)
        preset_path = str(path) if path is not None else None

    return VisualizerActivationPayload(
        mode=mode_key,
        preset_index=preset_index,
        is_custom=is_custom,
        preset_name=preset_name,
        preset_path=preset_path,
        resolved_config=resolved_config,
    )


def restore_visualizer_snapshot(
    mode_key: str,
    spotify_vis_config: Dict[str, Any],
    payload: Mapping[str, Any],
) -> bool:
    if not isinstance(payload, Mapping):
        return False
    changed = False
    prefixes = MODE_KEY_PREFIXES.get(mode_key, [])
    for key in list(spotify_vis_config.keys()):
        if key in payload:
            continue
        if _is_key_for_mode(key, prefixes):
            spotify_vis_config.pop(key, None)
            changed = True
    for key, value in payload.items():
        stored = spotify_vis_config.get(key)
        if stored != value:
            spotify_vis_config[key] = deepcopy(value)
            changed = True
    return changed


@dataclass
class VisualizerPreset:
    """A named preset for a specific visualizer mode."""
    name: str
    description: str
    settings: Dict[str, Any] = field(default_factory=dict)
    is_custom: bool = False


def _default_presets(curated_slots: int = DEFAULT_CURATED_SLOTS) -> List[VisualizerPreset]:
    """Return placeholder presets plus a trailing Custom slot."""
    curated_slots = max(0, curated_slots)
    presets: List[VisualizerPreset] = []
    for idx in range(curated_slots):
        presets.append(
            VisualizerPreset(
                name=f"Preset {idx + 1}",
                description="Default settings",
                settings={},
            )
        )

    presets.append(
        VisualizerPreset(
            name="Custom",
            description="Your own settings (Advanced)",
            settings={},
            is_custom=True,
        )
    )
    return presets


# Registry: mode -> list of curated presets plus trailing Custom.
# Modes start with placeholder slots and then load the authored curated tree.
_PRESETS: Dict[str, List[VisualizerPreset]] = {
    mode: _default_presets() for mode in MODES
}
_CURATED_TREE_SYNCED = False


def _looks_like_onefile_extraction_path(path: Path) -> bool:
    """True when *path* appears to be a onefile extraction tree."""
    normalized = str(path).replace("/", "\\").lower()
    if "\\srpss\\onefile" in normalized:
        return True
    return any("onefile" in str(part).lower() for part in path.parts)


def _presets_root() -> Path:
    """Return the active curated preset root for the current runtime.

    Script mode uses the repository source tree directly.

    Frozen SCR/MC builds converge on a shared ProgramData curated tree so both
    installs see the same shipped preset state. If that shared tree is missing
    but the packaged/bundled preset tree exists, we bootstrap ProgramData from
    the bundled copy once and then keep using the shared location.
    """
    bundled_root = _bundled_presets_root()
    shared_root = _shared_presets_root()
    frozen_like_runtime = _is_frozen_build() or _looks_like_onefile_extraction_path(bundled_root)
    if not frozen_like_runtime:
        return bundled_root

    # Frozen SCR/MC builds must always resolve curated presets from the shared
    # machine-wide tree so both binaries consume the exact same authored files.
    # Never fall back to onefile extraction paths for curated preset reads.
    if shared_root.is_dir():
        return shared_root

    if bundled_root.is_dir():
        try:
            mirror_curated_visualizer_preset_tree(bundled_root, shared_root)
        except Exception:
            logger.debug("[VIS_PRESETS] Failed to bootstrap shared preset tree", exc_info=True)

    if not shared_root.is_dir():
        try:
            shared_root.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.warning(
                "[VIS_PRESETS] Failed to ensure shared preset tree exists at %s",
                shared_root,
                exc_info=True,
            )
    return shared_root


def get_visualizer_presets_dir(mode: str | None = None) -> Path:
    """Return the on-disk directory that stores curated presets for *mode*."""
    root = _presets_root()
    if mode is None:
        return root
    return root / mode


def get_packaged_visualizer_presets_dir(mode: str | None = None) -> Path:
    """Return the packaged/bundled curated preset tree for replacement flows."""
    root = _bundled_presets_root()
    if mode is None:
        return root
    return root / mode


def _snapshot_presets_root() -> Path:
    """Return the directory containing explicit visualizer preset overrides.

    Script mode uses the repository tree. Frozen SCR/MC builds share a
    ProgramData override folder so repair/import flows are not split by build.
    """
    bundled_overrides_root = _bundled_snapshot_overrides_root()
    if _is_frozen_build() or _looks_like_onefile_extraction_path(bundled_overrides_root):
        return _shared_presets_base_dir() / "visualizer_mode_overrides"
    return bundled_overrides_root


def _is_frozen_build() -> bool:
    if bool(getattr(sys, "frozen", False)):
        return True
    if globals().get("__compiled__", False):
        return True
    if bool(getattr(builtins, "__compiled__", False)):
        return True
    main_mod = sys.modules.get("__main__")
    if main_mod is not None and bool(getattr(main_mod, "__compiled__", False)):
        return True
    argv0 = Path(str(sys.argv[0]) if sys.argv else "").suffix.lower()
    if argv0 in (".exe", ".scr"):
        return True
    exe_path = Path(getattr(sys, "executable", "") or "")
    exe_name = exe_path.name.lower()
    if exe_name and exe_name not in ("python.exe", "pythonw.exe"):
        if exe_name.startswith("srpss") or exe_name.endswith(".scr"):
            return True
    return False


def _bundled_presets_root() -> Path:
    return Path(__file__).resolve().parents[2] / "presets" / "visualizer_modes"


def _bundled_snapshot_overrides_root() -> Path:
    return Path(__file__).resolve().parents[2] / "presets" / "visualizer_mode_overrides"


def _shared_presets_base_dir() -> Path:
    return Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "SRPSS" / "presets"


def _shared_presets_root() -> Path:
    return _shared_presets_base_dir() / "visualizer_modes"


def _is_explicit_snapshot_override(payload: Mapping[str, Any], mode: str) -> bool:
    """True when a payload is an explicit visualizer preset override.

    We require an explicit marker + mode match + integer preset_index to avoid
    accidental ingestion of full settings snapshots.
    """
    marker = payload.get("visualizer_preset_override")
    payload_mode = payload.get("visualizer_preset_mode")
    payload_index = payload.get("preset_index")
    if marker is True and payload_mode == mode and isinstance(payload_index, int):
        return True

    # Fallback: accept legacy snapshot exports that include a spotify_visualizer
    # section with an explicit mode match plus a preset_index. This lets full
    # SST dumps (and older repair-tool outputs) act as overrides once copied
    # into the overrides folder without requiring a manual marker edit.
    if not isinstance(payload_index, int):
        return False
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return False
    widgets = snapshot.get("widgets")
    if not isinstance(widgets, Mapping):
        return False
    sv_settings = widgets.get("spotify_visualizer")
    if not isinstance(sv_settings, Mapping):
        return False
    snapshot_mode = sv_settings.get("mode")
    return snapshot_mode == mode


def _infer_preset_index_from_name(name: str) -> int | None:
    match = re.search(r"preset[\s_-]*(\d+)", name, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        idx = int(match.group(1)) - 1
    except ValueError:
        return None
    return idx if idx >= 0 else None


def _infer_suffix_from_name(name: str) -> str | None:
    match = re.search(r"preset[\s_-]*\d+(?:[\s_-]+(.+))?", name, flags=re.IGNORECASE)
    if not match:
        return None
    suffix = match.group(1)
    if not suffix:
        return None
    cleaned = re.sub(r"[_-]+", " ", suffix).strip()
    return cleaned if cleaned else None


def _friendly_name_from_suffix(index: int, suffix: str | None) -> str:
    base = f"Preset {index + 1}"
    if suffix:
        titled = suffix.title().strip()
        if titled:
            return f"{base} ({titled})"
    return base


def _resolve_index_and_name(
    json_path: Path,
    payload_name: str | None,
    payload_index: Any,
    *,
    prefer_filename_index: bool = False,
    prefer_filename_name: bool = False,
) -> tuple[int | None, str]:
    filename_index = _infer_preset_index_from_name(json_path.stem)
    if prefer_filename_index and filename_index is not None:
        index: int | None = filename_index
        if isinstance(payload_index, int) and payload_index != filename_index:
            logger.warning(
                "[VIS_PRESETS] Ignoring payload preset_index=%s for %s; using filename slot=%s",
                payload_index,
                json_path.name,
                filename_index,
            )
    else:
        index = payload_index if isinstance(payload_index, int) else None
        if index is None:
            index = filename_index
    suffix: str | None = None

    if index is not None and index < 0:
        index = None

    normalized_name: str | None = None
    if payload_name and not (prefer_filename_name and filename_index is not None):
        candidate = str(payload_name).strip()
        if candidate and not _PLACEHOLDER_NAME_RE.match(candidate):
            normalized_name = candidate

    if normalized_name is None:
        suffix = _infer_suffix_from_name(json_path.stem)
        name = _friendly_name_from_suffix(index if index is not None else 0, suffix)
    else:
        name = normalized_name

    if index is None:
        return None, ""
    if not name:
        name = f"Preset {index + 1}"
    return index, name


def _collect_visualizer_sections(payload: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    """Return all mapping sections that may contain spotify_visualizer keys."""
    sections: List[Mapping[str, Any]] = []

    settings = payload.get("settings")
    if isinstance(settings, Mapping):
        sections.append(settings)

    snapshot = payload.get("snapshot")
    if isinstance(snapshot, Mapping):
        custom_backup = snapshot.get("custom_preset_backup")
        if isinstance(custom_backup, Mapping):
            prefix = "widgets.spotify_visualizer."
            backup_section: Dict[str, Any] = {}
            for key, value in custom_backup.items():
                if isinstance(key, str) and key.startswith(prefix):
                    backup_section[key[len(prefix):]] = value
            if backup_section:
                sections.append(backup_section)

        widgets = snapshot.get("widgets")
        if isinstance(widgets, Mapping):
            sv_settings = widgets.get("spotify_visualizer")
            if isinstance(sv_settings, Mapping):
                sections.append(sv_settings)

    return sections


def _parse_preset_payload(
    json_path: Path,
    payload: Mapping[str, Any],
    mode: str,
    *,
    prefer_filename_index: bool = False,
    prefer_filename_name: bool = False,
) -> tuple[int, VisualizerPreset] | None:
    """Parse either curated JSON or SST snapshot payloads into presets."""
    sections = _collect_visualizer_sections(payload)
    if not sections:
        return None

    combined: Dict[str, Any] = {}
    for section in sections:
        # Migrate first so legacy keys (e.g. rainbow_enabled) are converted
        # to per-mode keys before the filter drops them.
        migrated = _migrate_preset_settings(mode, dict(section))
        filtered = _filter_settings_for_mode(mode, migrated)
        if filtered:
            combined.update(filtered)

    if not combined:
        return None

    combined["mode"] = mode
    combined = normalize_visualizer_mode_payload(mode, combined)
    if not combined:
        return None

    index, name = _resolve_index_and_name(
        json_path,
        payload.get("name"),
        payload.get("preset_index"),
        prefer_filename_index=prefer_filename_index,
        prefer_filename_name=prefer_filename_name,
    )
    if index is None:
        return None

    description = payload.get("description") or "Imported preset"
    preset = VisualizerPreset(name=name, description=description, settings=combined)
    return index, preset


def _filter_settings_for_mode(mode: str, sv_settings: Mapping[str, Any]) -> Dict[str, Any]:
    prefixes = MODE_KEY_PREFIXES.get(mode, [])
    filtered: Dict[str, Any] = {}

    for key, value in sv_settings.items():
        if key == "mode":
            # Force the active mode later, regardless of the payload value.
            continue
        if any(key.startswith(prefix) for prefix in prefixes):
            filtered[key] = value
        elif key in GLOBAL_ALLOWED_KEYS:
            filtered[key] = value
    # Ensure presets never flip the visualizer mode when applied.
    filtered["mode"] = mode
    return filtered


def _migrate_preset_settings(mode: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Apply forward-migrations for removed/renamed settings keys."""
    # Collapse accidental double-prefixed keys such as blob_blob_* or
    # oscilloscope_oscilloscope_* that older repair/tooling flows allowed through.
    for _prefix in MODE_KEY_PREFIXES.get(mode, [""]):
        if not _prefix:
            continue
        _double_prefix = f"{_prefix}{_prefix}"
        for key in list(settings.keys()):
            if not key.startswith(_double_prefix):
                continue
            normalized = f"{_prefix}{key[len(_double_prefix):]}"
            if normalized not in settings:
                settings[normalized] = settings[key]
            settings.pop(key, None)

    # Removed: sine_min_height/max_height/height_tendency are dead keys.
    # If old presets have them but no card_adaptation, derive it.
    if mode == "sine_wave":
        if "sine_card_adaptation" not in settings and "sine_min_height" in settings:
            minh = float(settings.get("sine_min_height", 0.10))
            settings["sine_card_adaptation"] = round(min(1.0, max(0.05, minh / 0.24)), 2)
        settings.pop("sine_min_height", None)
        settings.pop("sine_max_height", None)
        settings.pop("sine_height_tendency", None)

    # Blob legacy authored/runtime keys are retired. Do not forward-migrate
    # them into modern presets; source-authoritative preset payloads should
    # carry only the current Blob contract.
    if mode == "blob":
        for retired_key in (
            "blob_pulse_cap",
            "blob_stage2_release_ms",
            "blob_stage3_release_ms",
            "blob_stretch_x_bias",
            "blob_stretch_y_bias",
        ):
            settings.pop(retired_key, None)

    # spectrum_bar_profile → removed (curved is now always-on, shaping is parameterized)
    if mode == "spectrum":
        settings.pop("spectrum_bar_profile", None)
        settings.pop("spectrum_curved_profile", None)
        if "spectrum_render_mode" not in settings:
            if "spectrum_single_piece" in settings:
                settings["spectrum_render_mode"] = (
                    "bars" if bool(settings.get("spectrum_single_piece")) else "segment"
                )
            else:
                settings["spectrum_render_mode"] = "bars"
        else:
            settings["spectrum_render_mode"] = normalize_spectrum_render_mode(
                settings.get("spectrum_render_mode"),
                "bars",
            )

        if "spectrum_unique_colors" not in settings:
            if "spectrum_rainbow_per_bar" in settings:
                settings["spectrum_unique_colors"] = bool(settings.get("spectrum_rainbow_per_bar"))
            elif "rainbow_per_bar" in settings:
                settings["spectrum_unique_colors"] = bool(settings.get("rainbow_per_bar"))
            else:
                settings["spectrum_unique_colors"] = True

        settings.pop("spectrum_single_piece", None)
        settings.pop("spectrum_rainbow_per_bar", None)
        settings.pop("rainbow_per_bar", None)
        settings.pop("spectrum_vocal_position", None)
        _shape_defaults = {
            "spectrum_lane_strengths_mirrored": {
                "Mid": 0.60,
                "Vocal": 0.64,
                "Low-Mid": 0.70,
                "Bass": 0.80,
            },
            "spectrum_lane_strengths_linear": {
                "Bass": 0.80,
                "Low-Mid": 0.70,
                "Vocal": 0.64,
                "Hi-Mid": 0.80,
                "Treble": 1.0,
            },
            "spectrum_wave_amplitude": 0.5,
            "spectrum_profile_floor": 0.12,
            "spectrum_glow_enabled": False,
            "spectrum_glow_intensity": 0.55,
            "spectrum_glow_color": [110, 220, 255, 235],
            "spectrum_mirrored": True,
            "spectrum_shape_nodes": [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]],
        }
        for _sk, _sv in _shape_defaults.items():
            if _sk not in settings:
                settings[_sk] = _sv
        settings.pop("spectrum_bass_emphasis", None)
        settings.pop("spectrum_mid_suppression", None)
    if mode == "oscilloscope":
        if "osc_line_amplitude" not in settings and "osc_sensitivity" in settings:
            settings["osc_line_amplitude"] = settings["osc_sensitivity"]
        settings.pop("osc_sensitivity", None)
        for _key, _val in (
            ("osc_ghost_line2_enabled", True),
            ("osc_ghost_line3_enabled", True),
        ):
            if _key not in settings:
                settings[_key] = _val
    if mode == "sine_wave":
        for _key, _val in (
            ("sine_ghost_line2_enabled", True),
            ("sine_ghost_line3_enabled", True),
        ):
            if _key not in settings:
                settings[_key] = _val

    # rainbow_enabled / rainbow_speed → per-mode keys
    # Old presets stored these as global keys; convert to {mode}_rainbow_enabled.
    _prefix = MODE_KEY_PREFIXES.get(mode, [""])[0]
    _pm_re_key = f"{_prefix}rainbow_enabled"
    _pm_rs_key = f"{_prefix}rainbow_speed"
    if "rainbow_enabled" in settings and _pm_re_key not in settings:
        settings[_pm_re_key] = settings["rainbow_enabled"]
    if "rainbow_speed" in settings and _pm_rs_key not in settings:
        settings[_pm_rs_key] = settings["rainbow_speed"]
    settings.pop("rainbow_enabled", None)
    settings.pop("rainbow_speed", None)

    return settings


def _load_snapshot_presets(mode: str) -> Dict[int, VisualizerPreset]:
    folder = _snapshot_presets_root()
    if not folder.exists() or not folder.is_dir():
        return {}

    overrides: Dict[int, VisualizerPreset] = {}
    for json_path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - logged for debugging only
            logger.warning("[VIS_PRESETS] Failed to parse snapshot %s: %s", json_path.name, exc)
            continue

        if not isinstance(payload, Mapping):
            continue
        if not _is_explicit_snapshot_override(payload, mode):
            continue

        try:
            parsed = _parse_preset_payload(json_path, payload, mode)
        except Exception as exc:
            logger.warning(
                "[VIS_PRESETS] Failed to load snapshot override %s for %s: %s",
                json_path.name,
                mode,
                exc,
            )
            logger.debug("[VIS_PRESETS] Snapshot override load failure details", exc_info=True)
            continue
        if not parsed:
            continue
        index, preset = parsed
        overrides[index] = preset

    return overrides


def _load_mode_presets_from_disk(mode: str) -> Dict[int, VisualizerPreset]:
    """Load curated presets for *mode* from presets/visualizer_modes/<mode>."""
    folder = _presets_root() / mode
    if not folder.exists() or not folder.is_dir():
        return {}

    overrides: Dict[int, VisualizerPreset] = {}
    source_paths: Dict[int, Path] = {}
    for json_path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - logged for debugging only
            logger.warning("[VIS_PRESETS] Failed to parse %s: %s", json_path, exc)
            continue

        try:
            parsed = _parse_preset_payload(
                json_path,
                payload,
                mode,
                prefer_filename_index=True,
                prefer_filename_name=True,
            )
        except Exception as exc:
            logger.warning(
                "[VIS_PRESETS] Failed to load curated preset %s for %s: %s",
                json_path.name,
                mode,
                exc,
            )
            logger.debug("[VIS_PRESETS] Curated preset load failure details", exc_info=True)
            continue
        if parsed:
            index, preset = parsed
            previous = source_paths.get(index)
            if previous is not None:
                logger.warning(
                    "[VIS_PRESETS] Duplicate curated slot for %s preset %d: %s overrides %s",
                    mode,
                    index + 1,
                    json_path.name,
                    previous.name,
                )
            overrides[index] = preset
            source_paths[index] = json_path
            continue

        logger.warning("[VIS_PRESETS] %s has no usable settings", json_path.name)

    return overrides


def _build_presets_for_mode(mode: str) -> List[VisualizerPreset]:
    global _CURATED_TREE_SYNCED
    if not _CURATED_TREE_SYNCED:
        try:
            sync_curated_preset_tree(_presets_root())
        except Exception:
            logger.debug("[VIS_PRESETS] Failed to sync curated preset tree", exc_info=True)
        _CURATED_TREE_SYNCED = True

    try:
        curated = _load_mode_presets_from_disk(mode)
        snapshot_overrides = _load_snapshot_presets(mode)
        logger.info(
            "[VIS_PRESETS] Build mode=%s curated_root=%s snapshot_root=%s curated_slots=%d snapshot_overrides=%d",
            mode,
            _presets_root(),
            _snapshot_presets_root(),
            len(curated),
            len(snapshot_overrides),
        )
    except Exception as exc:
        logger.warning(
            "[VIS_PRESETS] Failed to build presets for mode=%s; using safe defaults: %s",
            mode,
            exc,
        )
        logger.debug("[VIS_PRESETS] Preset build failure details", exc_info=True)
        return _default_presets()

    combined: Dict[int, VisualizerPreset] = dict(curated)
    for index, override in snapshot_overrides.items():
        curated_base = combined.get(index)
        if curated_base is None:
            combined[index] = override
            continue
        # Snapshot overrides should replace settings, not rename curated slots.
        combined[index] = VisualizerPreset(
            name=curated_base.name,
            description=curated_base.description,
            settings=dict(override.settings),
        )

    if combined:
        max_index = max(combined.keys())
        curated_slots = max(max_index + 1, 1)
    else:
        curated_slots = DEFAULT_CURATED_SLOTS

    presets = _default_presets(curated_slots)
    for index, preset in combined.items():
        if index < 0:
            continue
        while index >= len(presets) - 1:
            presets.insert(
                len(presets) - 1,
                VisualizerPreset(
                    name=f"Preset {len(presets)}",
                    description="Default settings",
                    settings={},
                ),
            )
        presets[index] = preset
    return presets


for _mode in MODES:
    _PRESETS[_mode] = _build_presets_for_mode(_mode)


def get_presets(mode: str) -> List[VisualizerPreset]:
    """Return the preset list for *mode* (curated slots plus trailing Custom)."""
    return _PRESETS.get(mode, _default_presets())


def get_preset_file_path(mode: str, preset_index: int) -> Path | None:
    """Return the JSON file path for a curated preset, or None for Custom/missing."""
    custom_idx = get_custom_preset_index(mode)
    if preset_index >= custom_idx or preset_index < 0:
        return None
    root = _presets_root() / mode
    if not root.is_dir():
        return None
    selected_path: Path | None = None
    for json_path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        parsed = _parse_preset_payload(
            json_path,
            payload,
            mode,
            prefer_filename_index=True,
            prefer_filename_name=True,
        )
        if not parsed:
            continue
        index, _preset = parsed
        if index == preset_index:
            selected_path = json_path
    if selected_path is not None:
        return selected_path
    pattern = f"preset_{preset_index + 1}_*"
    matches = sorted(root.glob(pattern + ".json"))
    if matches:
        return matches[-1]
    # Fallback: try exact name without suffix
    exact = root / f"preset_{preset_index + 1}.json"
    return exact if exact.is_file() else None


def get_preset_names(mode: str) -> List[str]:
    """Return display names for the mode's presets."""
    return [p.name for p in get_presets(mode)]


def get_preset_count(mode: str) -> int:
    """Return the number of presets (including Custom) for *mode*."""
    return len(get_presets(mode))


def get_custom_preset_index(mode: str) -> int:
    """Return the trailing Custom index for *mode*."""
    return max(0, len(get_presets(mode)) - 1)


def reload_presets(mode: str | None = None) -> None:
    """Reload curated preset metadata from disk.

    Args:
        mode: When provided, only rebuild presets for that visualizer mode.
            When ``None`` (default) every mode is refreshed.
    """
    global _CURATED_TREE_SYNCED
    _CURATED_TREE_SYNCED = False
    if mode is not None:
        if mode not in MODES:
            return
        _PRESETS[mode] = _build_presets_for_mode(mode)
        return

    for _mode in MODES:
        _PRESETS[_mode] = _build_presets_for_mode(_mode)


def get_active_preset_index(settings: "SettingsManager", mode: str) -> int:
    """Read the active preset index for *mode* from settings (0-based)."""
    key = f"widgets.spotify_visualizer.{get_preset_key(mode)}"
    return resolve_preset_index_from_mapping(
        mode,
        {key: settings.get(key, None)},
        prefix="widgets.spotify_visualizer",
    )


def set_active_preset_index(settings: "SettingsManager", mode: str, index: int) -> None:
    """Persist the active preset index for *mode*."""
    key = f"widgets.spotify_visualizer.{get_preset_key(mode)}"
    custom_idx = get_custom_preset_index(mode)
    settings.set(key, max(0, min(custom_idx, index)))


def is_custom_preset(settings: "SettingsManager", mode: str) -> bool:
    """True if the active preset for *mode* is Custom (last index)."""
    return get_active_preset_index(settings, mode) == get_custom_preset_index(mode)


def get_preset_settings(mode: str, index: int) -> Dict[str, Any]:
    """Return the settings dict for a specific preset.

    For non-custom presets, this is the curated override dict (empty = defaults).
    For Custom, this returns empty — the actual custom values live in the
    normal settings keys and are loaded by the existing 8-layer pipeline.
    """
    presets = get_presets(mode)
    if 0 <= index < len(presets):
        return dict(presets[index].settings)
    return {}


def apply_preset_to_config(mode: str, index: int, config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply preset settings to a config dict using authoritative REPLACE semantics.

    For non-custom presets, all mode-specific keys are cleared first, then the
    preset's settings are applied. This ensures custom settings cannot persist
    when loading a curated preset.

    For Custom (last index), *config* is returned unchanged (user's saved values
    are already in it).

    Returns the config dict with preset applied.
    """
    if index == get_custom_preset_index(mode):
        # Custom — don't override anything
        return config

    preset_settings = get_preset_settings(mode, index)
    if not preset_settings:
        # Empty preset settings = use defaults (no override needed)
        return config

    # Use the same CLEAR-then-APPLY pattern as restore_visualizer_snapshot()
    # to ensure mode-specific keys are fully replaced, not merged
    prefixes = MODE_KEY_PREFIXES.get(mode, [])
    cleaned = dict(config)

    # First: CLEAR all mode-specific keys not in preset
    for key in list(cleaned.keys()):
        if key in preset_settings:
            continue
        if _is_key_for_mode(key, prefixes):
            cleaned.pop(key, None)
    
    # Then: APPLY preset settings
    for key, value in preset_settings.items():
        cleaned[key] = deepcopy(value)
    
    return cleaned


def switch_to_custom_if_needed(settings: "SettingsManager", mode: str) -> bool:
    """If the active preset is NOT Custom, switch to Custom.

    Called when the user modifies a setting while Advanced is shown.
    Returns True if a switch occurred.
    """
    if is_custom_preset(settings, mode):
        return False
    set_active_preset_index(settings, mode, get_custom_preset_index(mode))
    logger.debug("[VIS_PRESETS] Auto-switched %s to Custom preset", mode)
    return True

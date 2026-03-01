"""Regenerate curated visualizer preset JSON payloads.

The legacy preset exports bundled the *entire* Screensaver_MC snapshot which
made them brittle (stale defaults, eco mode remnants, corrupt JSON). This
utility rebuilds the curated presets so that each file only contains the data
the visualizer preset loader actually consumes: the
`widgets.spotify_visualizer` section.

For every curated preset listed in `TARGETS`, we:

1. Load the canonical Spotify visualizer defaults from
   `core/settings/default_settings.py`.
2. Overlay the historical preset values from the last committed JSON snapshot
   (falling back to the working tree if needed).
3. Filter the merged mapping down to only the keys allowed for the preset's mode
   (matching the parser logic in `core.settings.visualizer_presets`).
4. Emit a compact JSON payload with `application`, `preset_index`, `name`, and a
   minimal `snapshot.widgets.spotify_visualizer` block.

Usage:

    python tools/rebuild_visualizer_presets.py

"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = ROOT / "core" / "settings" / "default_settings.py"


# Keep these in sync with core/settings/visualizer_presets.py to mirror parser
# behaviour without importing the module (importing requires valid presets).
GLOBAL_ALLOWED_KEYS = {
    "adaptive_sensitivity",
    "audio_block_size",
    "bar_border_color",
    "bar_border_opacity",
    "bar_count",
    "bar_fill_color",
    "dynamic_floor",
    "dynamic_range_enabled",
    "ghost_alpha",
    "ghost_decay",
    "ghosting_enabled",
    "manual_floor",
    "mode",
    "monitor",
    "rainbow_enabled",
    "rainbow_per_bar",
    "rainbow_speed",
    "sensitivity",
    "software_visualizer_enabled",
}

MODE_KEY_PREFIXES: Dict[str, List[str]] = {
    "spectrum": ["spectrum_"],
    "oscilloscope": ["osc_"],
    "sine_wave": ["sine_", "sinewave_"],
    "blob": ["blob_"],
    "helix": ["helix_"],
    "starfield": ["star_", "nebula_"],
    "bubble": ["bubble_"],
}


@dataclass(frozen=True)
class PresetTarget:
    mode: str
    filename: str

    @property
    def path(self) -> Path:
        return ROOT / "presets" / "visualizer_modes" / self.mode / self.filename

    @property
    def relpath(self) -> str:
        return str(Path("presets") / "visualizer_modes" / self.mode / self.filename).replace("\\", "/")

    @property
    def preset_index(self) -> int:
        match = re.search(r"preset[ _-]*(\d+)", self.filename, re.IGNORECASE)
        if match:
            return max(int(match.group(1)) - 1, 0)
        raise ValueError(f"Unable to determine preset index from {self.filename}")

    @property
    def friendly_name(self) -> str:
        suffix_match = re.search(
            r"preset[ _-]*\d+(?:[ _-]+(.+?))?(?:\.json)?$",
            self.filename,
            re.IGNORECASE,
        )
        suffix = suffix_match.group(1) if suffix_match else None
        label = f"Preset {self.preset_index + 1}"
        if suffix:
            titled = re.sub(r"[_-]+", " ", suffix).strip().title()
            if titled:
                return f"{label} ({titled})"
        return label


TARGETS: List[PresetTarget] = [
    PresetTarget("bubble", "preset_3_sideway_swish.json"),
    PresetTarget("oscilloscope", "preset_1_classic.json"),
    PresetTarget("spectrum", "preset_1_rainbow.json"),
    PresetTarget("sine_wave", "preset_1_wave.json"),
    PresetTarget("sine_wave", "preset_3_drunken_serenity.json"),
]


def load_default_visualizer_settings() -> dict:
    spec = importlib.util.spec_from_file_location("default_settings", DEFAULTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[misc]
    defaults = getattr(module, "DEFAULT_SETTINGS")
    return deepcopy(defaults["widgets"]["spotify_visualizer"])


def load_legacy_override(target: PresetTarget) -> dict:
    relpath = target.relpath
    try:
        blob = subprocess.check_output([
            "git",
            "show",
            f"HEAD:{relpath}",
        ], cwd=ROOT)
        payload = json.loads(blob)
    except subprocess.CalledProcessError:
        if not target.path.exists():
            return {}
        payload = json.loads(target.path.read_text(encoding="utf-8"))
    snapshot = payload.get("snapshot", {}) if isinstance(payload, dict) else {}
    widgets = snapshot.get("widgets", {}) if isinstance(snapshot, dict) else {}
    sv = widgets.get("spotify_visualizer") if isinstance(widgets, dict) else None
    return dict(sv) if isinstance(sv, dict) else {}


def filter_for_mode(settings: dict, mode: str) -> dict:
    prefixes = MODE_KEY_PREFIXES.get(mode, [])
    filtered = {}
    for key, value in settings.items():
        if key in GLOBAL_ALLOWED_KEYS or any(key.startswith(prefix) for prefix in prefixes):
            filtered[key] = value
    filtered["mode"] = mode
    return filtered


def build_payload(target: PresetTarget, defaults: dict) -> dict:
    merged = deepcopy(defaults)
    merged["mode"] = target.mode
    legacy = load_legacy_override(target)
    merged.update(legacy)
    filtered = filter_for_mode(merged, target.mode)
    return {
        "application": "Screensaver_MC",
        "preset_index": target.preset_index,
        "name": target.friendly_name,
        "description": f"Curated {target.mode.replace('_', ' ')} preset derived from MC snapshot.",
        "snapshot": {
            "widgets": {
                "spotify_visualizer": filtered,
            }
        },
    }


def main() -> None:
    defaults = load_default_visualizer_settings()
    for target in TARGETS:
        payload = build_payload(target, defaults)
        target.path.parent.mkdir(parents=True, exist_ok=True)
        target.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Rebuilt {target.relpath}")


if __name__ == "__main__":
    main()

"""Write a curated Visualizer preset from Settings values alone, as Save Preset As writes one (no Settings writes).

    .venv/Scripts/python tools/visualizer_preset_author.py --mode extruded_bubble --values scenes.json --scene Abyss \
        --index 5 --title "Abyss" --description "..."

``--values`` is a JSON object of scenes, each a mapping of the mode's Settings values (keys with or without the
``<mode>_`` prefix). Every value must come back unchanged from its Settings control's ``admit`` (so the Settings UI can
reach it: no hidden keys, nothing out of range); the view pose keys (turn, tilt, scale, pan) become the preset's
``starting_view``, as Save Preset As stores it with **Include current camera view when saving**. The rest start from
the canonical defaults, pass the same normalisers the Settings save uses, and are written to
``presets/visualizer_modes/<mode>/preset_<index>_<slug>.json``. The written preset is then read back through
``get_presets`` and must resolve to the values given.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# What the Settings save drops from a preset (``ui/tabs/visualizer_settings_context.py``).
_DEPRECATED_EXPORT_SUFFIXES = ("energy_boost", "use_raw_energy")


def _admitted(mode: str, values: dict) -> dict:
    from core.settings.defaults import get_default_settings
    from core.settings.visualizer_mode_settings import spec_control

    defaults = get_default_settings()["widgets"]["spotify_visualizer"]
    admitted = {}
    for key, value in values.items():
        key = key if key.startswith(f"{mode}_") else f"{mode}_{key}"
        control = spec_control(key)
        if control is None:
            raise ValueError(f"{key} has no Settings control")
        back = control.admit(value, defaults[key])
        if json.loads(json.dumps(back)) != json.loads(json.dumps(value)):
            raise ValueError(f"{key}: the Settings control admits {value!r} as {back!r}")
        admitted[key] = back
    return admitted


def author(mode: str, values: dict, *, index: int, title: str, description: str, root: Path | None = None) -> Path:
    from core.settings.defaults import get_default_settings
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor, get_visualizer_view_pose_keys
    from core.settings.visualizer_presets import (
        MODE_KEY_PREFIXES,
        apply_preset_starting_view,
        apply_preset_to_config,
        extract_visualizer_snapshot,
        get_preset_file_path,
        get_visualizer_presets_dir,
        reload_presets,
    )
    from core.settings.visualizer_settings_snapshot import (
        normalize_visualizer_mode_payload,
        normalize_visualizer_section_mapping,
    )
    from core.settings.visualizer_view_orbit import validate_visualizer_starting_view

    admitted = _admitted(mode, values)
    config = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
    config.update(admitted, mode=mode)
    live = normalize_visualizer_section_mapping(config, apply_preset_overlay=False)
    snapshot = normalize_visualizer_mode_payload(mode, extract_visualizer_snapshot(mode, live))
    for prefix in MODE_KEY_PREFIXES.get(mode, []):
        for suffix in _DEPRECATED_EXPORT_SUFFIXES:
            snapshot.pop(f"{prefix}{suffix}", None)
    payload = {"description": description, "mode": mode, "name": f"Preset {index} ({title})", "preset_index": index - 1,
               "visualizer_preset_override": True, "visualizer_preset_mode": mode,
               "snapshot": {"widgets": {"spotify_visualizer": snapshot}}}
    if get_visualizer_mode_descriptor(mode).scene_transform_settings:
        payload["starting_view"] = validate_visualizer_starting_view(
            mode, {key: live[key] for key in get_visualizer_view_pose_keys(mode)})
    directory = root or get_visualizer_presets_dir(mode)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    path = directory / f"preset_{index}_{slug}.json"
    for stale in directory.glob(f"preset_{index}_*.json"):
        if stale != path:
            stale.unlink()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    # Read back through the activation path (the preset applied, then its starting view): exactly the values given.
    reload_presets(mode)
    if (get_preset_file_path(mode, index - 1) or Path()).resolve() != path.resolve():
        raise RuntimeError(f"{path.name} is not preset {index} of {mode}")
    base = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
    resolved = apply_preset_starting_view(mode, index - 1, apply_preset_to_config(mode, index - 1, base))
    wrong = {key: (value, resolved.get(key)) for key, value in admitted.items()
             if json.loads(json.dumps(resolved.get(key))) != json.loads(json.dumps(value))}
    if wrong:
        raise RuntimeError(f"{path.name} reads back differently: {wrong}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--values", type=Path, required=True, help="JSON object of scenes (Settings values each)")
    parser.add_argument("--scene", required=True, help="the scene's name in --values")
    parser.add_argument("--index", type=int, required=True, help="the preset's number (1-based)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="Saved from current Settings state.")
    args = parser.parse_args()
    scenes = json.loads(args.values.read_text(encoding="utf-8"))
    print(author(args.mode, scenes[args.scene], index=args.index, title=args.title, description=args.description))


if __name__ == "__main__":
    main()

"""Generate ``Docs/Reference/Naming.md``: what every product name is called in code.

The reference is derived from the registries (Visualizer mode descriptors, retired modes, the Studio registry, the
transition registry, retired transitions, the widget family catalog and the card surface materials). The few
hand-written columns ("other spellings in code", "grep hazards", the senses of "Glass") are claims, and each carries
proofs this tool checks against the current source: a claim the source no longer supports stops generation
(``StaleClaim``) instead of silently publishing a stale map. A registered mode, transition or widget id without a
hand-written entry stops it too, so a new member is mapped when it lands.

Usage::

    python tools/naming_reference.py --write    # regenerate the file
    python tools/naming_reference.py --check    # exit 1 when the file differs from a fresh generation

``tests/test_naming_reference.py`` runs the check. Read-only apart from ``--write``; never imported by production.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "Docs" / "Reference" / "Naming.md"


class StaleClaim(ValueError):
    """A hand-written naming claim that the current source no longer supports."""


@dataclass(frozen=True)
class Proof:
    """``path`` (repo-relative, may be a glob) must exist; with ``pattern``, the regex must match (``absent``: must
    not match) in at least one (``absent``: any) of its files."""

    path: str
    pattern: str = ""
    absent: bool = False


@dataclass(frozen=True)
class Claim:
    text: str                      # Markdown shown in the reference
    proofs: tuple[Proof, ...]


def _files(path: str) -> list[Path]:
    if any(char in path for char in "*?["):
        return sorted(p for p in ROOT.glob(path) if p.is_file())
    candidate = ROOT / path
    return [candidate] if candidate.is_file() else []


def verify(claim: Claim) -> Claim:
    if not claim.proofs:
        raise StaleClaim(f"claim has no proof: {claim.text!r}")
    for proof in claim.proofs:
        files = _files(proof.path)
        if not files:
            raise StaleClaim(f"{proof.path} does not exist (claim: {claim.text!r})")
        if not proof.pattern:
            continue
        hits = [f for f in files if re.search(proof.pattern, f.read_text(encoding="utf-8", errors="replace"), re.M)]
        if proof.absent and hits:
            raise StaleClaim(f"{proof.pattern!r} now appears in {hits[0].relative_to(ROOT).as_posix()} "
                             f"(claim: {claim.text!r})")
        if not proof.absent and not hits:
            raise StaleClaim(f"{proof.pattern!r} not found in {proof.path} (claim: {claim.text!r})")
    return claim


def _p(path: str, pattern: str = "", absent: bool = False) -> Proof:
    return Proof(path, pattern, absent)


# ---- Hand-written claims (each proven against the source) ------------------------------------------------------

MODE_SPELLINGS: dict[str, tuple[Claim, ...]] = {
    "spectrum": (),
    "oscilloscope": (
        Claim("`osc_` (look keys; the Studio adapter's `PREFIX`) beside `oscilloscope_` (analysis keys)",
              (_p("ui/studio/oscilloscope_adapter.py", r'^PREFIX = "osc_"'),)),
    ),
    "bubble": (
        Claim('"original Bubble", "2D Bubble" in docs (never Extruded Bubble)',
              (_p("Docs/**/*.md", r"original Bubble"), _p("Docs/**/*.md", r"2D Bubble"))),
    ),
    "devcurve": (
        Claim("DevCurve / Dev Curve, the code name: `DevCurveFrameRuntime`, `QuickDevCurveRenderer`, "
              "`DevCurveStudioAdapter`",
              (_p("widgets/spotify_visualizer/devcurve_frame_runtime.py", r"^class DevCurveFrameRuntime\b"),
               _p("rendering/quick/visualizer/implementations/devcurve.py", r"^class QuickDevCurveRenderer\b"),
               _p("ui/studio/devcurve_adapter.py", r"^class DevCurveStudioAdapter\b"))),
        Claim("solver `widgets/spotify_visualizer/devcurve_runtime.py` (`solve_devcurve_frame`)",
              (_p("widgets/spotify_visualizer/devcurve_runtime.py", r"^def solve_devcurve_frame\b"),)),
        Claim("GLSL `widgets/spotify_visualizer/shaders/devcurve.frag` (under `widgets/`, unlike newer modes)",
              (_p("widgets/spotify_visualizer/shaders/devcurve.frag"),)),
    ),
    "sphere": (
        Claim('"Sphere" (short name); renderer `sphere_voxel.py` (`QuickSphereVoxelRenderer`)',
              (_p("rendering/quick/visualizer/implementations/sphere_voxel.py", r"^class QuickSphereVoxelRenderer\b"),)),
    ),
    "extruded_spectrum": (),
    "shockwave_grid": (
        Claim('"Shockwave Grid", its name until the 13 Oct 2026 rebuild (the id kept it); '
              "`shockwave_grid_*` modules, keys and builder",
              (_p("rendering/gl_programs/shockwave_grid_program.py"),
               _p("ui/tabs/media/shockwave_grid_builder.py"))),
        Claim("`shockwave_frame_runtime.py` (no `_grid`) holding `ShockwaveGridFrameRuntime`",
              (_p("widgets/spotify_visualizer/shockwave_frame_runtime.py", r"^class ShockwaveGridFrameRuntime\b"),)),
        Claim("`neon_*`: camera `core/settings/neon_lake_camera.py`, world `core/constants/neon_lake_world.py`, "
              "GL `rendering/gl_programs/neon_*.py`",
              (_p("core/settings/neon_lake_camera.py"), _p("core/constants/neon_lake_world.py"),
               _p("rendering/gl_programs/neon_lake_basin_program.py"), _p("rendering/gl_programs/neon_*.py"))),
        Claim("Studio adapter class `NeonLakeStudioAdapter`",
              (_p("ui/studio/shockwave_grid_adapter.py", r"^class NeonLakeStudioAdapter\b"),)),
        Claim("tests `tests/test_neon_*.py` and `tests/test_qtquick_shockwave_grid.py`; music trace "
              "`tools/visualizer_replay/neon_lake_music_response.py`",
              (_p("tests/test_neon_*.py"), _p("tests/test_qtquick_shockwave_grid.py"),
               _p("tools/visualizer_replay/neon_lake_music_response.py"))),
    ),
    "extruded_bubble": (
        Claim('"EB" in docs',
              (_p("Docs/Reference/Extruded_Bubble/*.md", r"\bEB\b"),)),
    ),
    "waveform_ribbon": (
        Claim('"Waveform" (short name); Studio adapter `ui/studio/waveform_adapter.py` (no `_ribbon`)',
              (_p("ui/studio/waveform_adapter.py", r"^class WaveformStudioAdapter\b"),)),
        Claim("shared ribbon primitives `core/ribbon_*.py` and `rendering/gl_programs/ribbon*.py`",
              (_p("core/ribbon_*.py"), _p("rendering/gl_programs/ribbon*.py"))),
        Claim("music trace `tools/visualizer_replay/waveform_music_response.py` (this mode's only)",
              (_p("tools/visualizer_replay/waveform_music_response.py", r"Reaction"),)),
    ),
}

RETIRED_MODE_NAMES: dict[str, Claim] = {
    "blob": Claim("Blob", (_p("core/settings/visualizer_retired_modes.py", r'"blob"'),)),
    "sine_wave": Claim("Sine Waves", (_p("core/settings/visualizer_retired_modes.py", r"Sine Waves retired"),)),
}

TRANSITION_SPELLINGS: dict[str, tuple[Claim, ...]] = {
    "ripple": (
        Claim("`raindrops` (shader `rendering/gl_programs/raindrops_program.py`)",
              (_p("rendering/gl_programs/raindrops_program.py"),)),
    ),
    "block_spins": (
        Claim("`blockspin` (section, `rendering/gl_programs/blockspin_program.py`, `blockspin_options.py`), "
              "`BlockSpin`",
              (_p("rendering/gl_programs/blockspin_program.py"), _p("rendering/gl_programs/blockspin_options.py"),
               _p("rendering/gl_programs/blockspin_*.py", r"BlockSpin"))),
    ),
    "warp_dissolve": (
        Claim("`warp` (`rendering/quick/transitions/implementations/warp.py`, `rendering/gl_programs/warp_program.py`)",
              (_p("rendering/quick/transitions/implementations/warp.py"), _p("rendering/gl_programs/warp_program.py"))),
    ),
    "melt_drip": (
        Claim('"Melt" in docs', (_p("Docs/Reference/Transitions.md", r"\bMelt\b(?! Drip)"),)),
    ),
    "burn": (
        Claim("persisted field `smoke_density` (see its Settings label in `rendering/transition_settings.py`)",
              (_p("rendering/transition_settings.py", r'"smoke_density"'),)),
    ),
}

WIDGET_SPELLINGS: dict[str, tuple[Claim, ...]] = {
    "spotify_visualizer": (
        Claim("package `widgets/spotify_visualizer/` (every audio source, not Spotify only), "
              "`core/settings/models/_spotify_visualizer.py`, `rendering/quick/qml/VisualizerPresentation.qml`",
              (_p("widgets/spotify_visualizer/__init__.py"), _p("core/settings/models/_spotify_visualizer.py"),
               _p("rendering/quick/qml/VisualizerPresentation.qml"))),
    ),
    "steam_progress": (
        Claim("`games_you_follow` (`rendering/quick/widgets/games_you_follow.py`, `GamesYouFollowPresentation.qml`), "
              "`steam_followed` (`widgets/steam_followed_runtime.py`, `widgets/steam_followed_layout.py`), "
              "`games_followed` (`rendering/games_followed_child_roles.py`)",
              (_p("rendering/quick/widgets/games_you_follow.py"),
               _p("rendering/quick/qml/GamesYouFollowPresentation.qml"),
               _p("widgets/steam_followed_runtime.py"), _p("widgets/steam_followed_layout.py"),
               _p("rendering/games_followed_child_roles.py"))),
    ),
    "spotify_volume": (
        Claim("`widgets/media_volume_runtime.py`", (_p("widgets/media_volume_runtime.py"),)),
    ),
    "mute_button": (
        Claim("`widgets/system_mute_runtime.py`", (_p("widgets/system_mute_runtime.py"),)),
    ),
}

# (meaning, owner, persisted as)
GLASS_SENSES: tuple[tuple[str, str, Claim], ...] = (
    ("Settings / Studio **window backdrop** (DWM AccentPolicy)", "`.srtheme` `backdrop.mode`",
     Claim("`core/windows/dwm_blur.py`; `ui/settings_theme_io.py`",
           (_p("core/windows/dwm_blur.py", r'mode == "glass"'), _p("ui/settings_theme_io.py", r'"backdrop"')))),
    ("**Card surface material** (shader-drawn)", "`widgets.global.surface_material`, per-widget `surface_material`",
     Claim("`rendering/quick/widgets/surface_material.py`; `rendering/quick/qml/MaterialSurface.qml`",
           (_p("rendering/quick/widgets/surface_material.py", r'"glass"'),
            _p("rendering/quick/qml/MaterialSurface.qml", r'"glass"')))),
    ("Glass Shatter **transition**", "its label and section",
     Claim("`rendering/transition_registry.py`", (_p("rendering/transition_registry.py", r'stable_id="glass_shatter"'),))),
    ("3D Block Spins **edge glass**", "`transitions.blockspin.edge_glass`",
     Claim("`rendering/quick/transitions/parameter_resolution.py`",
           (_p("rendering/quick/transitions/parameter_resolution.py", r'"edge_glass"'),))),
    ("Neon Lake Basin **surface style** glass", "a `shockwave_grid_*` value",
     Claim("`core/settings/visualizer_mode_settings.py` (`_BASIN_GLASS`)",
           (_p("core/settings/visualizer_mode_settings.py", r"^_BASIN_GLASS = "),))),
    ("Extruded Bubble **Glass bucket** and Lit Glass", "`extruded_bubble_*` keys",
     Claim("`core/settings/visualizer_mode_settings.py`",
           (_p("core/settings/visualizer_mode_settings.py", r'Bucket\("glass"'),
            _p("core/settings/visualizer_mode_settings.py", r'"extruded_bubble_lit_glass"')))),
)

ACRYLIC = Claim(
    '"Acrylic" is both a window backdrop (`enable_acrylic_blur`) and a card material; cards never borrow the '
    "Settings AccentPolicy stack (R-61, `Docs/Architecture/Card_Surface_Materials.md`)",
    (_p("core/windows/dwm_blur.py", r"^def enable_acrylic_blur\b"),
     _p("rendering/quick/widgets/surface_material.py", r'"acrylic"'),
     _p("Docs/Architecture/Card_Surface_Materials.md", r"R-61")))

HAZARDS: tuple[Claim, ...] = (
    Claim('"shockwave" is also Neon Lake Basin\'s **onset-wave concept** (`ShockwaveEvent`, `SHOCKWAVE_WAVE_GLSL`, '
          "`SHOCKWAVE_DEPTH`), not only its old name: never rewrite `shockwave` to `neon_lake` mechanically",
          (_p("rendering/gl_programs/neon_lake_basin_program.py", r"\bSHOCKWAVE_WAVE_GLSL\b"),
           _p("rendering/gl_programs/neon_lake_basin_program.py", r"\bSHOCKWAVE_DEPTH\b"),
           _p("rendering/gl_programs/neon_terrain_reaction.py", r"\bShockwaveEvent\b"))),
    Claim('"spline" is generic curve maths (Waveform Ribbon\'s `core/ribbon_geometry.py`, '
          "`core/ribbon_continuation.py`, `rendering/gl_programs/ribbon*.py`, and others); Spline Curve's own code "
          "is `devcurve*`",
          (_p("core/ribbon_geometry.py", r"(?i)spline"), _p("core/ribbon_continuation.py", r"(?i)spline"),
           _p("rendering/gl_programs/ribbon*.py", r"(?i)spline"))),
    Claim('"waveform" is also the captured PCM waveform that Oscilloscope draws; Waveform Ribbon\'s code is '
          "`waveform_ribbon*` plus `ui/studio/waveform_adapter.py`",
          (_p("widgets/spotify_visualizer/oscilloscope_frame_runtime.py", r"\bwaveform\b"),)),
    Claim("Waveform Ribbon's framed camera `SPEC` lives in `core/waveform_ribbon_scene.py`; "
          "`core/settings/waveform_ribbon_camera.py` holds only its floor and clipping contract",
          (_p("core/waveform_ribbon_scene.py", r"^SPEC = "),
           _p("core/settings/waveform_ribbon_camera.py", r"^SPEC\b", absent=True))),
    Claim('"Glass" and "Acrylic" each name several systems (see Materials above): a card-material defect is never '
          "in `core/windows/dwm_blur.py`",
          (_p("core/windows/dwm_blur.py", r"AccentPolicy|ACCENT"),)),
)


# ---- Generation -------------------------------------------------------------------------------------------------

def _module_path(module: str) -> str:
    path = module.replace(".", "/") + ".py"
    if not (ROOT / path).is_file():
        raise StaleClaim(f"registry names a module that does not exist: {module}")
    return path


def _code(text: str) -> str:
    return f"`{text}`"


def _cell(claims: tuple[Claim, ...]) -> str:
    return "; ".join(verify(claim).text for claim in claims) or "none"


def _require_keys(name: str, hand: dict, registered: list[str]) -> None:
    missing, extra = sorted(set(registered) - set(hand)), sorted(set(hand) - set(registered))
    if missing or extra:
        raise StaleClaim(f"{name}: hand-written entries out of step with the registry "
                         f"(missing {missing}, not registered {extra})")


def _prefix_hazards(descriptors) -> list[str]:
    owner = {prefix: d.mode_id for d in descriptors for prefix in d.setting_prefixes}
    lines = []
    for short in sorted(owner):
        for longer in sorted(owner):
            if short != longer and short in longer and owner[short] != owner[longer]:
                lines.append(f"`{short}` (`{owner[short]}`) also matches `{longer}` (`{owner[longer]}`) keys: "
                             f"search `\\b{short}` or `'{short}`, never a bare substring")
    return lines


def _visualizers(lines: list[str]) -> None:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    from ui.studio.registry import has_studio, studio_modes, studio_title

    descriptors = iter_all_visualizer_mode_descriptors()
    _require_keys("MODE_SPELLINGS", MODE_SPELLINGS, [d.mode_id for d in descriptors])
    factories = {entry.mode_id: entry.factory for entry in studio_modes()}

    lines += ["## Visualizer modes", "",
              "`display_name` is what Settings, Guided Setup and the Studio show (the Studio's title is "
              "\"`display_name` Studio\"); it is not persisted. The mode id and its key prefixes are persisted "
              "(settings, `preset_<id>`, preset folders, goldens, evidence folders) and are the code's name. Each "
              "mode's Settings declarations live in `core/settings/visualizer_mode_settings.py` under a "
              "\"# ---- Product name (`id`)\" section header.", "",
              "| Product name (`display_name`) | Mode id (persisted) | Key prefixes (persisted) | Other spellings in code |",
              "|---|---|---|---|"]
    spec_source = (ROOT / "core" / "settings" / "visualizer_mode_settings.py").read_text(encoding="utf-8")
    for d in descriptors:
        if not re.search(rf"^# ---- .+ \(`{re.escape(d.mode_id)}`\) -", spec_source, re.M):
            raise StaleClaim(f"core/settings/visualizer_mode_settings.py has no '# ---- <product> (`{d.mode_id}`)' "
                             "section header")
        prefixes = ", ".join(_code(prefix) for prefix in d.setting_prefixes)
        lines.append(f"| {d.display_name} | `{d.mode_id}` | {prefixes} | {_cell(MODE_SPELLINGS[d.mode_id])} |")

    lines += ["", "### Owners per mode", "",
              "| Mode id | Frame runtime | Renderer | Settings builder | Studio | Framed camera |",
              "|---|---|---|---|---|---|"]
    for d in descriptors:
        runtime = f"`{_module_path(d.frame_runtime_module)}` `{d.frame_runtime_class}`"
        renderer = _code(_module_path(d.renderer_module))
        builder = _code(_module_path(d.settings_builder_module)) if d.settings_builder_module else "none"
        if has_studio(d.mode_id):
            module, _, cls = factories[d.mode_id].partition(":")
            studio = f"`{_module_path(module)}` `{cls}` (\"{studio_title(d.mode_id)}\")"
        else:
            studio = "none"
        camera = _code(_module_path(d.framed_camera.partition(":")[0])) if d.framed_camera else "none"
        lines.append(f"| `{d.mode_id}` | {runtime} | {renderer} | {builder} | {studio} | {camera} |")

    from core.settings.visualizer_retired_modes import (
        _RETIRED_VISUALIZER_PREFIXES,
        RETIRED_VISUALIZER_MODE_IDS,
    )
    _require_keys("RETIRED_MODE_NAMES", RETIRED_MODE_NAMES, list(RETIRED_VISUALIZER_MODE_IDS))
    lines += ["", "### Retired modes", "",
              "Not live: no descriptor, runtime, renderer or Settings. Saved state is stripped on input by "
              "`core/settings/visualizer_retired_modes.py` (`Docs/Architecture/Persisted_Input_Compatibility.md`); "
              "never re-register one to read old state.", "",
              "| Former name | Mode id | Stripped prefixes |", "|---|---|---|"]
    for mode_id in sorted(RETIRED_VISUALIZER_MODE_IDS):
        squashed = mode_id.replace("_", "")
        prefixes = [p for p in _RETIRED_VISUALIZER_PREFIXES if squashed.startswith(p.rstrip("_").replace("_", ""))]
        lines.append(f"| {verify(RETIRED_MODE_NAMES[mode_id]).text} | `{mode_id}` | "
                     f"{', '.join(_code(p) for p in prefixes) + ', ' if prefixes else ''}`preset_{mode_id}` |")


def _transitions(lines: list[str]) -> None:
    from core.settings.transition_retired import RETIRED_TRANSITIONS
    from rendering.transition_registry import _LEGACY_TO_SETTING, iter_transition_descriptors

    descriptors = iter_transition_descriptors()
    unknown = sorted(set(TRANSITION_SPELLINGS) - {d.stable_id for d in descriptors})
    if unknown:
        raise StaleClaim(f"TRANSITION_SPELLINGS names unregistered transitions: {unknown}")
    legacy: dict[str, list[str]] = {}
    for alias, label in _LEGACY_TO_SETTING.items():
        legacy.setdefault(label, []).append(alias)
    lines += ["", "## Transitions", "",
              "**Persistence is the inverse of Visualizers:** the label is persisted (`transitions.type` and the "
              "`activation`, `pool` and `durations` maps); the section holds the transition's own settings. A label "
              "rename needs its old label in the descriptor's `legacy_names`.", "",
              "| Label (persisted) | Stable id | Settings section | Legacy labels accepted on input | "
              "Other spellings in code |", "|---|---|---|---|---|"]
    for d in descriptors:
        section = f"**`{d.settings_section}`**" if d.settings_section != d.stable_id else _code(d.settings_section)
        aliases = ", ".join(f'"{alias}"' for alias in sorted(legacy.get(d.setting_name, ()))) or "none"
        lines.append(f"| {d.setting_name} | `{d.stable_id}` | {section} | {aliases} | "
                     f"{_cell(TRANSITION_SPELLINGS.get(d.stable_id, ()))} |")
    lines += ["", "Retired (stripped on input by `core/settings/transition_retired.py`): "
              + ", ".join(f"{label} (`{section}`)" for label, section in RETIRED_TRANSITIONS.items()) + "."]


def _widgets(lines: list[str]) -> None:
    from core.settings.widget_family_catalog import get_widget_family_catalog, get_widget_member_label

    families = get_widget_family_catalog()
    members = [widget_id for family in families for widget_id in family.member_widget_ids]
    unknown = sorted(set(WIDGET_SPELLINGS) - set(members))
    if unknown:
        raise StaleClaim(f"WIDGET_SPELLINGS names widgets outside the catalog: {unknown}")
    lines += ["", "## Widgets", "",
              "The widget id is the persisted settings section (`widgets.<id>`); the label is Settings wording.", "",
              "| Family | Widget label | Widget id (persisted) | Other spellings in code |", "|---|---|---|---|"]
    for family in families:
        for widget_id in family.member_widget_ids:
            lines.append(f"| {family.label} (`{family.family_id}`) | {get_widget_member_label(widget_id)} | "
                         f"`{widget_id}` | {_cell(WIDGET_SPELLINGS.get(widget_id, ()))} |")


def _materials(lines: list[str]) -> None:
    from rendering.quick.widgets.surface_material import SURFACE_MATERIAL_LABELS

    lines += ["", "## Materials", "",
              "Card surface materials (`widgets.global.surface_material` and per-widget overrides): "
              + ", ".join(f"{label} (`{key}`)" for key, label in SURFACE_MATERIAL_LABELS.items()) + ".", "",
              '"Glass" means all of these:', "",
              "| Meaning | Owner | Persisted as |", "|---|---|---|"]
    for meaning, persisted, claim in GLASS_SENSES:
        lines.append(f"| {meaning} | {verify(claim).text} | {persisted} |")
    lines += ["", verify(ACRYLIC).text + "."]


def generate() -> str:
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors

    lines = [
        "# Naming Reference",
        "",
        "> Generated by `tools/naming_reference.py --write` from the registries; do not edit by hand. "
        "`tests/test_naming_reference.py` fails when this file differs from a fresh generation, and generation "
        "fails when a hand-written spelling or hazard no longer holds in the source.",
        "",
        "- **Product names** (a mode's `display_name`, a transition label, a widget label) are what users and the "
        "operator say. Docs write the product name first with the id in backticks on first use in a section: "
        "Neon Lake Basin (`shockwave_grid`), Spline Curve (`devcurve`).",
        "- **Ids are persisted** (settings keys, preset folders, goldens, evidence folders) and are the code's "
        "name. Never rename one to match a product name; that needs a compatibility bridge "
        "(`Docs/Architecture/Persisted_Input_Compatibility.md`).",
        "- To find every owner, search the id **and** every other spelling in its row; then check the grep hazards.",
        "",
    ]
    _visualizers(lines)
    _transitions(lines)
    _widgets(lines)
    _materials(lines)
    lines += ["", "## Grep hazards", ""]
    lines += [f"- {line}" for line in _prefix_hazards(iter_all_visualizer_mode_descriptors())]
    lines += [f"- {verify(claim).text}" for claim in HAZARDS]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="regenerate Docs/Reference/Naming.md")
    group.add_argument("--check", action="store_true", help="exit 1 when the file is stale (default)")
    args = parser.parse_args(argv)
    text = generate()
    if args.write:
        OUTPUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
        return 0
    current = OUTPUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUTPUT.is_file() else None
    if current != text:
        print(f"{OUTPUT.relative_to(ROOT).as_posix()} is stale: run tools/naming_reference.py --write")
        return 1
    print(f"{OUTPUT.relative_to(ROOT).as_posix()} is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

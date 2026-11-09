"""Theme legibility: every text role of a theme pair against what it is composed over, on its material.

The Settings window composes its semantic surfaces over a native material, and the material over the desktop. The
model here is analytic and conservative: compositing is affine in the desktop colour and luminance is monotone in
every channel, so over any desktop (busy or flat) the composed surface's luminance lies between its value over a
black and over a white desktop. The worst contrast of a text role over every wallpaper is therefore the worse of
those two (or 1:1 when the text's own luminance lies between them). A heavy blur only narrows that range.

* Settings: ``settings_theme_legibility`` -- each text role over the stack of surfaces it sits on
  (``SETTINGS_TEXT_STACKS``), over ``window.dialog_glass``, over the theme's material
  (``SettingsThemeSpec.native_tint``: Glass and Off show the desktop itself; the tinted materials lay their
  derived tint over it), over a black and a white desktop.
* Widget cards: ``widget_theme_legibility`` -- each card text role over the card's own surfaces. On a material the
  wallpaper side is carried by the card's legibility panel, whose floor holds ``card.text`` at 7:1 against the
  blurred backdrop (Docs/Architecture/Card_Surface_Materials.md 3.3); it is measured in pixels by
  ``tools/surface_material_capture.py --legibility``.

Bars: 4.5:1 for small text, 3:1 for large text (WCAG AA). Disabled roles are exempt (inactive controls).
The contrast function is the canonical ``ui.theme_semantics.contrast_ratio``.

Usage:
  python tools/theme_legibility.py [--themes NAME ...] [--light] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if "ui" not in sys.modules:
    # The production ``ui`` package registers compiled Qt resources on import; the theme modules need none.
    _ui = types.ModuleType("ui")
    _ui.__path__ = [str(_PROJECT_ROOT / "ui")]
    sys.modules["ui"] = _ui

from ui.settings_theme_spec import Rgba  # noqa: E402
from ui.theme_semantics import composite_over, contrast_ratio  # noqa: E402
from tools import artifact_paths  # noqa: E402

SMALL_TEXT = 4.5
LARGE_TEXT = 3.0
DESKTOPS = {"black": Rgba(0, 0, 0, 255), "white": Rgba(255, 255, 255, 255)}

from ui.settings_surface_composition import SETTINGS_TEXT_STACKS, CONTROL_STATE_TEXT_STACKS

# Widget card text roles and the opaque card surfaces they sit on (a mirror projects them from Settings roles).
WIDGET_TEXT_SURFACES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("card.text", ("card.background", "widget.panel")),
    ("widget.muted", ("card.background", "widget.panel")),
    ("widget.accent", ("card.background", "widget.panel")),
    ("gmail.sender", ("card.background", "widget.panel")),
    ("header.text", ("card.background", "widget.panel")),
)


@dataclass(frozen=True)
class RoleResult:
    role: str
    worst: float
    bar: float
    where: str

    @property
    def passes(self) -> bool:
        return self.worst >= self.bar


def _opaque(color: Rgba) -> Rgba:
    return Rgba(color.r, color.g, color.b, 255)


def settings_material_base(theme, desktop: Rgba) -> Rgba:
    """What the Settings window's semantic surfaces are composed over on ``desktop``."""
    tint = theme.material_tint()
    return desktop if tint is None else composite_over(tint, desktop)


def _role_text(theme, role: str) -> Rgba:
    return theme.color(role)


def settings_theme_legibility(theme) -> dict[str, RoleResult]:
    """Worst contrast per Settings text role over every desktop, on the theme's own material."""
    results: dict[str, RoleResult] = {}
    stacks = [(role, stack, large, theme.color(role)) for role, stack, large in SETTINGS_TEXT_STACKS]
    stacks.extend((f"control.mode.{state}_text", stack, False, theme.mode_state_ink(state))
                  for state, stack in CONTROL_STATE_TEXT_STACKS)
    for role, stack, large, ink in stacks:
        bar = LARGE_TEXT if large else SMALL_TEXT
        for desktop_name, desktop in DESKTOPS.items():
            surface = settings_material_base(theme, desktop)
            for layer in stack:
                surface = composite_over(theme.color(layer), surface)
            text = composite_over(ink, surface)
            ratio = contrast_ratio(text, surface)
            previous = results.get(role)
            if previous is None or ratio < previous.worst:
                results[role] = RoleResult(role, round(ratio, 2), bar, f"{stack[-1]} / {desktop_name} desktop")
    return results


def widget_theme_legibility(theme) -> dict[str, RoleResult]:
    """Worst contrast per card text role over the card's own surfaces (and the header label on its fill)."""
    results: dict[str, RoleResult] = {}

    def record(role: str, ratio: float, where: str) -> None:
        previous = results.get(role)
        if previous is None or ratio < previous.worst:
            results[role] = RoleResult(role, round(ratio, 2), SMALL_TEXT, where)

    for role, surfaces in WIDGET_TEXT_SURFACES:
        for surface_role in surfaces:
            surface = _opaque(theme.color(surface_role))
            record(role, contrast_ratio(composite_over(theme.color(role), surface), surface), surface_role)
    header = composite_over(theme.color("header.fill"), _opaque(theme.color("widget.panel")))
    record("header.text", contrast_ratio(composite_over(theme.color("header.text"), header), header), "header.fill")
    return results


def worst(results: dict[str, RoleResult]) -> RoleResult:
    return min(results.values(), key=lambda result: result.worst / result.bar)


def _pairs(themes_root: Path):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.widget_theme_io import load_widget_theme_file

    mirrors = {}
    for path in sorted((themes_root / "widgets").glob("*.srwtheme")):
        theme = load_widget_theme_file(path)
        if theme.linked_settings_theme_id:
            mirrors[theme.linked_settings_theme_id] = theme
    for path in sorted(themes_root.glob("*.srtheme"), key=lambda value: value.name.casefold()):
        yield path, load_settings_theme_file(path), mirrors.get(f"file:{path.name}")


def report(themes_root: Path, *, names=None, light_only=False) -> list[dict]:
    from ui.theme_semantics import settings_theme_is_light

    rows = []
    for path, settings, mirror in _pairs(themes_root):
        if names and path.stem not in names and settings.name not in names:
            continue
        if light_only and not settings_theme_is_light(settings):
            continue
        s = settings_theme_legibility(settings)
        w = widget_theme_legibility(mirror) if mirror is not None else {}
        rows.append({
            "theme": settings.name,
            "light": settings_theme_is_light(settings),
            "settings_material": settings.backdrop.mode,
            "card_material": mirror.surface_material if mirror is not None else None,
            "settings": {role: [r.worst, r.bar, r.where] for role, r in s.items()},
            "cards": {role: [r.worst, r.bar, r.where] for role, r in w.items()},
            "settings_failures": sorted(role for role, r in s.items() if not r.passes),
            "card_failures": sorted(role for role, r in w.items() if not r.passes),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--themes-root", type=Path, default=_PROJECT_ROOT / "themes")
    parser.add_argument("--themes", nargs="+", metavar="NAME")
    parser.add_argument("--light", action="store_true", help="only light Settings themes (settings_theme_is_light)")
    parser.add_argument("--json", type=artifact_paths.evidence_arg,
                        help="write the full per-role report here (inside the evidence layout, tools/artifact_paths.py)")
    args = parser.parse_args(argv)
    rows = report(args.themes_root, names=args.themes, light_only=args.light)
    for row in rows:
        s_worst = min(row["settings"].items(), key=lambda item: item[1][0] / item[1][1])
        c_worst = min(row["cards"].items(), key=lambda item: item[1][0] / item[1][1]) if row["cards"] else None
        print(f"{row['theme']:48s} {row['settings_material']:8s}/{str(row['card_material']):8s} "
              f"settings worst {s_worst[0]} {s_worst[1][0]} ({s_worst[1][2]}) "
              f"cards worst {c_worst[0] if c_worst else '-'} {c_worst[1][0] if c_worst else ''} "
              f"fails S{len(row['settings_failures'])} C{len(row['card_failures'])}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate mirrored ``.srwtheme`` files from the curated Settings theme pack.

This is pack-authoring tooling, not runtime authority.  Runtime pairing uses the
explicit stable ``linked_settings_theme_id`` written into each generated file;
there is no display-name matching after generation.

The mapping deliberately projects *semantic language*, not QWidget/QSS structure:
common card/header/panel/accent roles are copied from the closest Settings-theme
semantics, while family-specific Widget roles remain sparse and inherit through
``ui.widget_visual_roles``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import types

# Pack tooling is intentionally Qt-free.  The production ``ui`` package imports
# compiled Qt resources in ``ui.__init__``; install only a namespace package here
# so the pure theme schema/IO modules can be imported on build machines without
# PySide6.  This does not affect application runtime imports.
if "ui" not in sys.modules:
    ui_package = types.ModuleType("ui")
    ui_package.__path__ = [str(Path(__file__).resolve().parent.parent / "ui")]
    sys.modules["ui"] = ui_package

from ui.settings_theme_io import load_settings_theme_file
from ui.settings_theme_spec import Rgba, SettingsThemeSpec
from ui.widget_theme_io import widget_theme_to_json
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME, WidgetThemeSpec


CANONICAL_SETTINGS_DEFAULT = "Default Dark.srtheme"
CANONICAL_WIDGET_DEFAULT = "Default Dark.srwtheme"
BUILTIN_SETTINGS_THEME_ID = "builtin:default-dark"


def _rgba(theme: SettingsThemeSpec, token: str) -> Rgba:
    return theme.color(token)


def _gradient_triplet(theme: SettingsThemeSpec) -> tuple[Rgba, Rgba, Rgba]:
    """Return a neutral theme-surface gradient for Widget decorative roles."""

    try:
        stops = tuple(theme.gradient("slider.groove.surface").stops)
    except KeyError:
        base = _rgba(theme, "panel.group.surface")
        alt = _rgba(theme, "panel.subsection.surface")
        return base, alt, base
    if not stops:
        base = _rgba(theme, "panel.group.surface")
        return base, base, base
    first = stops[0].color
    middle = stops[len(stops) // 2].color
    last = stops[-1].color
    return first, middle, last




def _scaled_alpha(color: Rgba, scale: float) -> Rgba:
    return Rgba(
        color.r, color.g, color.b,
        max(0, min(255, int(round(color.a * max(0.0, min(1.0, scale)))))),
    )

def _recommended_material(theme: SettingsThemeSpec) -> str:
    mode = str(theme.backdrop.mode or "off").strip().lower()
    return mode if mode in {"glass", "acrylic"} else "normal"


def mirrored_widget_theme(
    settings_theme: SettingsThemeSpec,
    *,
    settings_theme_id: str,
    widget_theme_id: str,
) -> WidgetThemeSpec:
    """Project one Settings theme into the mature shared Widget visual vocabulary."""

    gradient_start, gradient_middle, gradient_end = _gradient_triplet(settings_theme)
    colors = {
        # Core shared card language.
        "card.background": _rgba(settings_theme, "panel.group.surface"),
        "card.border": _rgba(settings_theme, "panel.border"),
        "card.text": _rgba(settings_theme, "text.primary"),
        # Runtime Context Menu already has direct Settings semantic equivalents.
        "context.menu.surface": _rgba(settings_theme, "context.menu.surface"),
        "context.menu.border": _rgba(settings_theme, "context.menu.border"),
        "context.menu.text": _rgba(settings_theme, "context.menu.text"),
        "context.menu.selected_surface": _rgba(settings_theme, "context.menu.selected_surface"),
        "context.menu.disabled_text": _rgba(settings_theme, "context.menu.disabled_text"),
        "context.menu.separator": _rgba(settings_theme, "context.menu.separator"),
        "context.submenu.surface": _rgba(settings_theme, "context.submenu.surface"),
        "context.submenu.border": _rgba(settings_theme, "context.submenu.border"),
        "context.submenu.text": _rgba(settings_theme, "context.submenu.text"),
        "context.submenu.selected_surface": _rgba(settings_theme, "context.submenu.selected_surface"),
        "context.submenu.checked_text": _rgba(settings_theme, "context.submenu.checked_text"),
        "context.submenu.checked_surface": _rgba(settings_theme, "context.submenu.checked_surface"),
        # Sparse optional shared vocabulary. Family-specialized roles inherit from
        # these parents instead of bloating every generated file.
        "header.fill": _rgba(settings_theme, "navigation.subtab.selected_surface"),
        "header.border": _rgba(settings_theme, "navigation.subtab.border"),
        "header.text": _rgba(settings_theme, "navigation.subtab.text"),
        "widget.panel": _rgba(settings_theme, "control.input.surface"),
        "widget.panel.alt": _rgba(settings_theme, "panel.subsection.surface"),
        "widget.outline": _rgba(settings_theme, "panel.border"),
        "widget.separator": _rgba(settings_theme, "bucket.closed.border"),
        "widget.icon": _rgba(settings_theme, "text.primary"),
        "widget.muted": _rgba(settings_theme, "text.secondary"),
        "widget.accent": _rgba(settings_theme, "control.list.selected_accent"),
        "widget.gradient.start": gradient_start,
        "widget.gradient.middle": gradient_middle,
        "widget.gradient.end": gradient_end,
        # Family metadata roles keep their existing hierarchy while following the
        # Settings theme's secondary-text language. These are semantic consumers,
        # not new per-family Settings controls.
        "gmail.sender": _rgba(settings_theme, "text.secondary"),
        "gmail.read_sender": _scaled_alpha(_rgba(settings_theme, "text.secondary"), 0.86),
        "gmail.read_subject": _scaled_alpha(_rgba(settings_theme, "text.primary"), 0.90),
        "gmail.timestamp": _scaled_alpha(_rgba(settings_theme, "text.secondary"), 0.76),
        "reddit.age": _scaled_alpha(_rgba(settings_theme, "text.secondary"), 0.86),
        "reddit2.age": _scaled_alpha(_rgba(settings_theme, "text.secondary"), 0.86),
        # Optional menu details inherit naturally, but materializing the obvious
        # Settings equivalents makes mirrored packs feel deliberately matched.
        "context.menu.indicator.border": _rgba(settings_theme, "context.submenu.checked_text"),
        "context.menu.indicator.fill": _rgba(settings_theme, "control.list.selected_accent"),
        "context.menu.arrow": _rgba(settings_theme, "context.menu.border"),
        "context.submenu.indicator.border": _rgba(settings_theme, "context.submenu.checked_text"),
        "context.submenu.indicator.fill": _rgba(settings_theme, "control.list.selected_accent"),
    }
    return WidgetThemeSpec(
        theme_id=widget_theme_id,
        name=settings_theme.name,
        default_card_material_mode=_recommended_material(settings_theme),
        linked_settings_theme_id=settings_theme_id,
        colors=colors,
    )


def generate_widget_theme_mirrors(
    themes_root: Path,
    *,
    output_directory: Path | None = None,
) -> tuple[Path, ...]:
    """Regenerate the curated Widget mirror pack deterministically."""

    root = Path(themes_root)
    output = Path(output_directory) if output_directory is not None else root / "widgets"
    output.mkdir(parents=True, exist_ok=True)

    # Compiled Default Dark is the canonical mirror and intentionally recommends
    # Normal even though the Settings GUI's native backdrop happens to be Acrylic.
    canonical_default = replace(
        DEFAULT_DARK_WIDGET_THEME,
        linked_settings_theme_id=BUILTIN_SETTINGS_THEME_ID,
    )
    written: list[Path] = []
    default_path = output / CANONICAL_WIDGET_DEFAULT
    default_path.write_text(widget_theme_to_json(canonical_default), encoding="utf-8")
    written.append(default_path)

    for path in sorted(root.glob("*.srtheme"), key=lambda value: value.name.casefold()):
        if path.name.casefold() == CANONICAL_SETTINGS_DEFAULT.casefold():
            continue
        settings_theme = load_settings_theme_file(path)
        settings_theme_id = f"file:{path.name}"
        widget_theme_id = f"mirror:{settings_theme_id}"
        widget_theme = mirrored_widget_theme(
            settings_theme,
            settings_theme_id=settings_theme_id,
            widget_theme_id=widget_theme_id,
        )
        target = output / f"{path.stem}.srwtheme"
        target.write_text(widget_theme_to_json(widget_theme), encoding="utf-8")
        written.append(target)

    expected = {path.name for path in written}
    for stale in output.glob("*.srwtheme"):
        if stale.name not in expected:
            stale.unlink()
    return tuple(written)


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    written = generate_widget_theme_mirrors(project_root / "themes")
    print(f"Generated {len(written)} Widget theme mirrors in themes/widgets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

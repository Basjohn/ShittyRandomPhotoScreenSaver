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
import re
import sys
import types

# The production ``ui`` package imports compiled Qt resources in ``ui.__init__``;
# install only a namespace package here so the theme schema/IO modules import
# without them.  This does not affect application runtime imports.  A theme that
# names a ``surface_material`` (every Glass/Acrylic mirror) validates it through
# ``rendering.quick.widgets.surface_material``, so the generator needs the
# project root on the path and PySide6 installed.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if "ui" not in sys.modules:
    ui_package = types.ModuleType("ui")
    ui_package.__path__ = [str(Path(__file__).resolve().parent.parent / "ui")]
    sys.modules["ui"] = ui_package

from ui.settings_theme_io import load_settings_theme_file
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba, SettingsThemeSpec
from ui.theme_semantics import settings_theme_is_light
from ui.widget_theme_io import load_widget_theme_file, widget_theme_to_json
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


def _uses_dark_text_on_light_surface(theme: SettingsThemeSpec) -> bool:
    """Detect the light-value hierarchy that needs an opaque runtime floor.

    Settings can rely on its native HWND backdrop plus semantic dialog surface.
    Runtime Widget cards sit directly over arbitrary wallpaper, so a pale RGB card
    at the pack's historic dark-theme alpha can turn into a mid/dark surface while
    its typography remains dark.  Detect the hierarchy from values rather than
    theme names so future light themes inherit the same safety rule.
    """

    return settings_theme_is_light(theme)


def _runtime_card_surface(theme: SettingsThemeSpec) -> Rgba:
    surface = _rgba(theme, "panel.group.surface")
    if not _uses_dark_text_on_light_surface(theme):
        return surface
    # A light runtime card has no native light backdrop underneath it.  Keep a
    # small amount of wallpaper translucency while establishing a real luminance
    # floor for dark primary/secondary text even over black artwork.
    return Rgba(surface.r, surface.g, surface.b, max(surface.a, 232))


def _runtime_secondary_text(
    theme: SettingsThemeSpec,
    token: str,
    *,
    dark_theme_alpha_scale: float,
) -> Rgba:
    color = _rgba(theme, token)
    if _uses_dark_text_on_light_surface(theme):
        # Alpha-fading dark metadata over a translucent light card destroys
        # contrast because the wallpaper participates twice.  The secondary RGB
        # itself already supplies hierarchy; keep it opaque on light runtime cards.
        return Rgba(color.r, color.g, color.b, 255)
    return _scaled_alpha(color, dark_theme_alpha_scale)

_MATERIAL_SUFFIX_RE = re.compile(r"\s+\[(?:Glass|Acrylic)\]\s*$", re.IGNORECASE)

# A pair's card material is its Settings theme's backdrop material (operator, 7 Nov
# 2026: "[Glass]" and "[Acrylic]" themes give Glass and Acrylic cards). ``off`` names
# none, so the cards stay Normal under Style Overrides' "Theme".
_SURFACE_MATERIAL_FOR_BACKDROP_MODE: dict[str, str | None] = {
    "glass": "glass",
    "acrylic": "acrylic",
    "off": None,
}


def surface_material_for_settings_theme(settings_theme: SettingsThemeSpec) -> str | None:
    """The card ``surface_material`` a Settings theme's linked Widget mirror carries.

    The one projection of ``backdrop.mode`` into the Widget side of a pair
    (Docs/Architecture/Card_Surface_Materials.md section 4). The runtime never
    reads the Settings theme: the mirror carries the value.
    """

    return _SURFACE_MATERIAL_FOR_BACKDROP_MODE[settings_theme.backdrop.mode]


def _widget_display_name(settings_name: str) -> str:
    """Drop the Settings name's backdrop tag from the Widget theme's file name.

    Stable IDs remain unchanged. The material itself travels in the mirror's
    ``surface_material`` (see :func:`surface_material_for_settings_theme`); the
    Themes tab shows it as a tag on the Widget list label.
    """

    return _MATERIAL_SUFFIX_RE.sub("", str(settings_name or "").strip()).strip()


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
        "card.background": _runtime_card_surface(settings_theme),
        "card.border": _rgba(settings_theme, "panel.border"),
        "card.text": _rgba(settings_theme, "text.primary"),
        # Runtime Context Menu already has direct Settings semantic equivalents.
        "context.menu.surface": _rgba(settings_theme, "context.menu.surface"),
        "context.menu.border": _rgba(settings_theme, "context.menu.border"),
        "context.menu.text": _rgba(settings_theme, "context.menu.text"),
        "context.menu.selected_surface": _rgba(settings_theme, "context.menu.selected_surface"),
        "context.menu.disabled_text": (
            _rgba(settings_theme, "text.secondary")
            if _uses_dark_text_on_light_surface(settings_theme)
            else _rgba(settings_theme, "context.menu.disabled_text")
        ),
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

        # Materialize the mature Media vocabulary instead of relying only on
        # optional-role inheritance.  This makes exported/mirrored themes
        # self-describing for every Media surface (transport, mute, volume, seek)
        # while preserving the same semantic parents used by runtime resolution.
        "media.transport.surface": _rgba(settings_theme, "control.button.surface"),
        "media.transport.border": _rgba(settings_theme, "control.button.border"),
        "media.transport.separator": _rgba(settings_theme, "bucket.closed.border"),
        "media.transport.icon": _rgba(settings_theme, "control.button.text"),
        "media.mute.surface": _rgba(settings_theme, "control.mode.surface"),
        "media.mute.border": _rgba(settings_theme, "control.mode.border"),
        "media.mute.inner_border": _rgba(settings_theme, "slider.groove.border"),
        "media.mute.icon": _rgba(settings_theme, "control.mode.text"),
        "media.mute.muted_icon": _rgba(settings_theme, "text.secondary"),
        "media.volume.track": _rgba(settings_theme, "control.input.surface"),
        "media.volume.fill": _rgba(settings_theme, "control.list.selected_accent"),
        "media.volume.outline": _rgba(settings_theme, "slider.groove.border"),
        "media.progress.track": _rgba(settings_theme, "panel.subsection.surface"),
        "media.progress.fill": _rgba(settings_theme, "control.list.selected_accent"),
        "media.progress.glow": _scaled_alpha(
            _rgba(settings_theme, "control.list.selected_accent"), 0.72
        ),
        "media.progress.shadow": _scaled_alpha(
            _rgba(settings_theme, "text.secondary"), 0.56
        ),

        # Abandonment's archive/Backlog accent is a real Widget semantic, not a
        # separate Settings swatch.  Materializing it makes exported counterparts
        # explicit while the runtime parent chain remains widget.accent.
        "abandonment_issues.accent": _rgba(
            settings_theme, "control.list.selected_accent"
        ),

        # Family metadata roles keep their existing hierarchy while following the
        # Settings theme's secondary-text language. These are semantic consumers,
        # not new per-family Settings controls.
        "gmail.sender": _rgba(settings_theme, "text.secondary"),
        "gmail.read_sender": _runtime_secondary_text(
            settings_theme, "text.secondary", dark_theme_alpha_scale=0.86
        ),
        "gmail.read_subject": _runtime_secondary_text(
            settings_theme, "text.primary", dark_theme_alpha_scale=0.90
        ),
        "gmail.timestamp": _runtime_secondary_text(
            settings_theme, "text.secondary", dark_theme_alpha_scale=0.76
        ),
        "reddit.age": _runtime_secondary_text(
            settings_theme, "text.secondary", dark_theme_alpha_scale=0.86
        ),
        "reddit2.age": _runtime_secondary_text(
            settings_theme, "text.secondary", dark_theme_alpha_scale=0.86
        ),
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
        name=_widget_display_name(settings_theme.name),
        linked_settings_theme_id=settings_theme_id,
        colors=colors,
        surface_material=surface_material_for_settings_theme(settings_theme),
    )


def widget_counterpart_for_settings_theme(
    settings_theme: SettingsThemeSpec,
    *,
    settings_theme_id: str,
) -> WidgetThemeSpec:
    """Return the deterministic stable-ID-linked Widget counterpart.

    Pack generation, the Theme Foundry and the Theme Sorter call this authority.
    The Widget counterpart mirrors semantic colours, link identity and the pair's
    card material (:func:`surface_material_for_settings_theme`), so a "[Glass]"
    pair under Keep Synced gives Glass cards through its mirror alone.

    The built-in pair is the exception: its Widget half is the compiled
    ``DEFAULT_DARK_WIDGET_THEME``, the unconditional runtime fallback and the
    process's initial active theme, which names no material so that the error
    path and every un-themed start stay Normal (dormant).
    """

    stable_id = str(settings_theme_id or "").strip()
    if not stable_id:
        raise ValueError("settings_theme_id must be a stable non-empty identity")
    if (
        stable_id == BUILTIN_SETTINGS_THEME_ID
        and settings_theme == DEFAULT_DARK_SETTINGS_THEME
    ):
        return replace(
            DEFAULT_DARK_WIDGET_THEME,
            linked_settings_theme_id=BUILTIN_SETTINGS_THEME_ID,
        )
    return mirrored_widget_theme(
        settings_theme,
        settings_theme_id=stable_id,
        widget_theme_id=f"mirror:{stable_id}",
    )


def generate_widget_theme_mirrors(
    themes_root: Path,
    *,
    output_directory: Path | None = None,
) -> tuple[Path, ...]:
    """Regenerate the curated Widget mirror pack deterministically.

    Wholesale: it rewrites every mirror from its Settings theme, which erases
    hand-authored colour roles in shipped mirrors, and deletes every other
    ``.srwtheme`` in the output folder (the unlinked ``widget:material:*`` themes
    included). To add one projected field to the shipped pack use
    :func:`fill_widget_theme_mirror_materials` instead.
    """

    root = Path(themes_root)
    output = Path(output_directory) if output_directory is not None else root / "widgets"
    output.mkdir(parents=True, exist_ok=True)

    # Compiled Default Dark is the canonical Widget mirror.
    canonical_default = widget_counterpart_for_settings_theme(
        DEFAULT_DARK_SETTINGS_THEME,
        settings_theme_id=BUILTIN_SETTINGS_THEME_ID,
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
        widget_theme = widget_counterpart_for_settings_theme(
            settings_theme,
            settings_theme_id=settings_theme_id,
        )
        target = output / f"{_widget_display_name(path.stem)}.srwtheme"
        target.write_text(widget_theme_to_json(widget_theme), encoding="utf-8")
        written.append(target)

    expected = {path.name for path in written}
    for stale in output.glob("*.srwtheme"):
        if stale.name not in expected:
            stale.unlink()
    return tuple(written)


def _linked_settings_theme(themes_root: Path, settings_theme_id: str) -> SettingsThemeSpec | None:
    if settings_theme_id == BUILTIN_SETTINGS_THEME_ID:
        return DEFAULT_DARK_SETTINGS_THEME
    if not settings_theme_id.startswith("file:"):
        return None
    path = themes_root / settings_theme_id.removeprefix("file:")
    return load_settings_theme_file(path) if path.is_file() else None


def fill_widget_theme_mirror_materials(themes_root: Path) -> tuple[Path, ...]:
    """Fill ``surface_material`` into existing linked mirrors, changing nothing else.

    The repair fill for the pair material (AC-17): each linked ``.srwtheme`` gets
    the value :func:`widget_counterpart_for_settings_theme` projects for its own
    Settings theme. Authored colour roles, names and ids are kept, unlinked themes
    are skipped, and a file whose bytes the canonical writer would not reproduce is
    refused rather than rewritten. Returns the files it changed.
    """

    root = Path(themes_root)
    changed: list[Path] = []
    for path in sorted((root / "widgets").glob("*.srwtheme"), key=lambda value: value.name.casefold()):
        current = load_widget_theme_file(path)
        link = current.linked_settings_theme_id
        if link is None:
            continue
        settings_theme = _linked_settings_theme(root, link)
        if settings_theme is None:
            continue
        material = widget_counterpart_for_settings_theme(
            settings_theme, settings_theme_id=link
        ).surface_material
        if material == current.surface_material:
            continue
        raw = path.read_bytes()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        if raw.decode("utf-8").replace("\r\n", "\n") != widget_theme_to_json(current):
            raise ValueError(f"{path.name} is not in canonical form; refusing to rewrite it")
        with path.open("w", encoding="utf-8", newline=newline) as handle:
            handle.write(widget_theme_to_json(replace(current, surface_material=material)))
        changed.append(path)
    return tuple(changed)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    project_root = Path(__file__).resolve().parent.parent
    if args == ["--fill-materials"]:
        changed = fill_widget_theme_mirror_materials(project_root / "themes")
        print(f"Filled surface_material into {len(changed)} Widget theme mirrors in themes/widgets")
        return 0
    written = generate_widget_theme_mirrors(project_root / "themes")
    print(f"Generated {len(written)} Widget theme mirrors in themes/widgets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
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
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba, SettingsThemeSpec, strip_material_tag
from ui.theme_semantics import settings_theme_is_light
from ui.widget_theme_io import load_widget_theme_file, widget_theme_to_json
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME, WidgetThemeSpec


CANONICAL_SETTINGS_DEFAULT = "Default Dark.srtheme"
CANONICAL_WIDGET_DEFAULT = "Default Dark.srwtheme"
BUILTIN_SETTINGS_THEME_ID = "builtin:default-dark"


def _rgba(theme: SettingsThemeSpec, token: str) -> Rgba:
    # Pack authoring projects authored palette data, never process-local surface
    # calibration or the operator's current Settings opacity override.
    return theme.colors[token]


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

# A pair's card material is its Settings theme's backdrop material (operator, 7 Nov
# 2026: "[Glass]" and "[Acrylic]" themes give Glass and Acrylic cards; 8 Nov: the
# Settings window takes Frosted, Mica and Smoked too, one material per pair). ``off``
# names none, so the cards stay Normal under Style Overrides' "Theme".
_SURFACE_MATERIAL_FOR_BACKDROP_MODE: dict[str, str | None] = {
    "glass": "glass",
    "acrylic": "acrylic",
    "frosted": "frosted",
    "mica": "mica",
    "smoked": "smoked",
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

    return strip_material_tag(settings_name)


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


class MirrorRegenerationRefused(RuntimeError):
    """Wholesale regeneration would erase authored content it was not told to erase."""


@dataclass(frozen=True)
class MirrorRegenerationPlan:
    """What a wholesale regeneration would do to one Widget theme folder."""

    writes: Mapping[Path, str]
    # Existing files whose text the regeneration would change: hand-authored mirrors.
    overwrites_authored: tuple[Path, ...]
    # Existing ``.srwtheme`` files the regeneration would delete (unlinked themes, the
    # ``widget:material:*`` themes among them, and orphans).
    deletes: tuple[Path, ...]

    def describe(self) -> str:
        lines = [f"Would write {len(self.writes)} Widget theme mirrors."]
        lines.append(f"Would overwrite {len(self.overwrites_authored)} hand-authored mirrors"
                     + (":" if self.overwrites_authored else "."))
        lines.extend(f"  {path.name}" for path in self.overwrites_authored)
        lines.append(f"Would delete {len(self.deletes)} other Widget themes"
                     + (":" if self.deletes else "."))
        lines.extend(f"  {path.name}" for path in self.deletes)
        return "\n".join(lines)


def _normalised_text(path: Path) -> str | None:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n") if path.is_file() else None


def plan_widget_theme_mirror_regeneration(
    themes_root: Path,
    *,
    output_directory: Path | None = None,
) -> MirrorRegenerationPlan:
    """Compute a wholesale regeneration without touching the disk."""

    root = Path(themes_root)
    output = Path(output_directory) if output_directory is not None else root / "widgets"
    writes: dict[Path, str] = {}
    # Compiled Default Dark is the canonical Widget mirror.
    writes[output / CANONICAL_WIDGET_DEFAULT] = widget_theme_to_json(
        widget_counterpart_for_settings_theme(
            DEFAULT_DARK_SETTINGS_THEME,
            settings_theme_id=BUILTIN_SETTINGS_THEME_ID,
        )
    )
    for path in sorted(root.glob("*.srtheme"), key=lambda value: value.name.casefold()):
        if path.name.casefold() == CANONICAL_SETTINGS_DEFAULT.casefold():
            continue
        widget_theme = widget_counterpart_for_settings_theme(
            load_settings_theme_file(path),
            settings_theme_id=f"file:{path.name}",
        )
        writes[output / f"{_widget_display_name(path.stem)}.srwtheme"] = widget_theme_to_json(widget_theme)

    authored = tuple(
        target for target, text in writes.items()
        if (current := _normalised_text(target)) is not None and current != text
    )
    expected = {target.name for target in writes}
    deletes = tuple(
        sorted((stale for stale in output.glob("*.srwtheme") if stale.name not in expected),
               key=lambda value: value.name.casefold())
    ) if output.is_dir() else ()
    return MirrorRegenerationPlan(writes=writes, overwrites_authored=authored, deletes=deletes)


def generate_widget_theme_mirrors(
    themes_root: Path,
    *,
    output_directory: Path | None = None,
    overwrite_authored: bool = False,
    delete_unlinked: bool = False,
) -> tuple[Path, ...]:
    """Regenerate the curated Widget mirror pack wholesale, deterministically.

    Every mirror is rewritten from its Settings theme and every other ``.srwtheme``
    in the folder is deleted. Both destroy authored content, so each needs its own
    explicit permission: without ``overwrite_authored`` it refuses when any existing
    mirror is not byte for byte what it would write (hand-authored colour roles);
    without ``delete_unlinked`` it refuses when it would delete any file (the
    unlinked ``widget:material:*`` themes). A refusal writes nothing. To add one
    projected field to the shipped pack use :func:`fill_widget_theme_mirror_materials`.
    """

    plan = plan_widget_theme_mirror_regeneration(themes_root, output_directory=output_directory)
    refused = []
    if plan.overwrites_authored and not overwrite_authored:
        refused.append(f"{len(plan.overwrites_authored)} hand-authored mirrors would be overwritten "
                       "(pass overwrite_authored / --overwrite-authored)")
    if plan.deletes and not delete_unlinked:
        refused.append(f"{len(plan.deletes)} other Widget themes would be deleted "
                       "(pass delete_unlinked / --delete-unlinked)")
    if refused:
        raise MirrorRegenerationRefused("Refusing to regenerate: " + "; ".join(refused) + "\n" + plan.describe())

    written: list[Path] = []
    for target, text in plan.writes.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = target.read_bytes() if target.is_file() else b""
        newline = "\r\n" if b"\r\n" in raw else "\n"
        with target.open("w", encoding="utf-8", newline=newline) as handle:
            handle.write(text)
        written.append(target)
    for stale in plan.deletes:
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


_USAGE = """usage: generate_widget_theme_mirrors.py MODE
  --fill-materials     fill each linked mirror's surface_material, changing nothing else
  --regenerate-all     rewrite every mirror from its Settings theme; refuses to
                       overwrite hand-authored mirrors or delete other Widget themes
                       unless these name that intent too:
      --overwrite-authored   allow overwriting mirrors the generator would change
      --delete-unlinked      allow deleting every other .srwtheme (material themes)
With no mode it changes nothing and prints what --regenerate-all would do."""


def main(argv: list[str] | None = None, *, themes_root: Path | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(themes_root) if themes_root is not None else (
        Path(__file__).resolve().parent.parent / "themes"
    )
    flags = set(args)
    known = {"--fill-materials", "--regenerate-all", "--overwrite-authored", "--delete-unlinked"}
    if flags - known or len(flags) != len(args):
        print(_USAGE, file=sys.stderr)
        return 2
    if flags == {"--fill-materials"}:
        changed = fill_widget_theme_mirror_materials(root)
        print(f"Filled surface_material into {len(changed)} Widget theme mirrors in {root / 'widgets'}")
        return 0
    if "--regenerate-all" in flags and "--fill-materials" not in flags:
        try:
            written = generate_widget_theme_mirrors(
                root,
                overwrite_authored="--overwrite-authored" in flags,
                delete_unlinked="--delete-unlinked" in flags,
            )
        except MirrorRegenerationRefused as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"Generated {len(written)} Widget theme mirrors in {root / 'widgets'}")
        return 0
    # No mode (or a meaningless combination): refuse, and show what regeneration would do.
    print(_USAGE, file=sys.stderr)
    print("\nNothing was changed. --regenerate-all would do this:", file=sys.stderr)
    print(plan_widget_theme_mirror_regeneration(root).describe(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

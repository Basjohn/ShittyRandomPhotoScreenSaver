"""Permanent source contracts for the 2026-09-02 light/metal theme expansion."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
WIDGETS = THEMES / "widgets"

# The curated light batch was simplified (Porcelain Sky / Alabaster Citrus were
# retired in the swatch simplification); these two remain the only themes whose
# panel.group.surface actually inverts to a light value (luminance >= 0.75).
LIGHT = (
    "Linen Sage [Two-Tone] [Acrylic]",
    "Pearl Blush [Three-Tone] [Glass]",
)
METAL = (
    "Polished Chrome [Single] [Glass]",
    "Brushed Nickel [Two-Tone] [Acrylic]",
    "Titanium Cobalt [Two-Tone] [Glass]",
    "Tungsten Brass [Three-Tone] [Acrylic]",
)

# These use dark typography over intentionally light/translucent Settings
# surfaces. They need a backdrop-aware contrast gate rather than the old
# opaque-RGB-only check.
LIGHT_SURFACE = LIGHT + (
    "Polished Chrome [Single] [Glass]",
    "Brushed Nickel [Two-Tone] [Acrylic]",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))



def _widget_name(settings_name: str) -> str:
    return settings_name.removesuffix(" [Glass]").removesuffix(" [Acrylic]")


def _luminance(rgb: list[int]) -> float:
    channels = []
    for value in rgb[:3]:
        channel = value / 255.0
        channels.append(
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(left: list[int], right: list[int]) -> float:
    l1 = _luminance(left)
    l2 = _luminance(right)
    high, low = max(l1, l2), min(l1, l2)
    return (high + 0.05) / (low + 0.05)


def _composite(foreground: list[int], background: list[int]) -> list[int]:
    alpha = foreground[3] / 255.0
    return [
        round(foreground[index] * alpha + background[index] * (1.0 - alpha))
        for index in range(3)
    ] + [255]


def _light_theme_backdrop_floor(theme: dict) -> list[int]:
    # Glass is untinted natively, so black is the conservative dark-desktop case.
    # Acrylic contributes its explicit tint before the semantic dialog surface.
    backdrop = [0, 0, 0, 255]
    if theme["backdrop"]["mode"] == "acrylic":
        backdrop = _composite(theme["backdrop"]["tint"], backdrop)
    return _composite(theme["colors"]["window.dialog_glass"], backdrop)




def _widget_runtime_card_floor(widget: dict) -> list[int]:
    # Runtime cards sit directly over arbitrary wallpaper; use black as the
    # conservative floor for light-card/dark-text readability.
    return _composite(widget["colors"]["card.background"], [0, 0, 0, 255])


def _composite_text_on_surface(text: list[int], surface: list[int]) -> list[int]:
    return _composite(text, surface)

def test_curated_light_metal_themes_and_widget_mirrors_exist() -> None:
    for name in LIGHT + METAL:
        assert (THEMES / f"{name}.srtheme").is_file(), name
        assert (WIDGETS / f"{_widget_name(name)}.srwtheme").is_file(), name


def test_light_batch_is_actually_light_and_readable() -> None:
    for name in LIGHT:
        theme = _load(THEMES / f"{name}.srtheme")
        colors = theme["colors"]
        # This batch must invert the pack's historic dark value hierarchy rather
        # than merely attaching pastel accents to another dark surface.
        assert _luminance(colors["panel.group.surface"]) >= 0.75, name
        assert _contrast(colors["text.primary"], colors["panel.group.surface"]) >= 4.5, name
        assert _contrast(colors["control.input.text"], colors["control.input.surface"]) >= 4.5, name


def test_all_dark_text_light_surfaces_survive_a_dark_native_backdrop() -> None:
    for name in LIGHT_SURFACE:
        theme = _load(THEMES / f"{name}.srtheme")
        colors = theme["colors"]
        floor = _light_theme_backdrop_floor(theme)
        assert _contrast(colors["text.primary"], floor) >= 7.0, name
        assert _contrast(colors["text.secondary"], floor) >= 4.5, name
        # Helper copy is ordinary explanatory text in Settings, so alpha must
        # not collapse it below normal-text contrast on a dark desktop.
        helper = _composite(colors["text.helper"], floor)
        assert _contrast(helper, floor) >= 4.5, name




def test_light_widget_mirrors_establish_a_readable_wallpaper_independent_floor() -> None:
    for name in LIGHT_SURFACE:
        widget = _load(WIDGETS / f"{_widget_name(name)}.srwtheme")
        colors = widget["colors"]
        floor = _widget_runtime_card_floor(widget)
        assert colors["card.background"][3] >= 232, name
        assert _contrast(colors["card.text"], floor) >= 7.0, name
        assert _contrast(colors["widget.muted"], floor) >= 4.5, name

        # Metadata roles are rendered directly over the card.  On a light card,
        # alpha-fading dark text lets wallpaper bleed through twice and destroys
        # contrast; hierarchy must come from RGB semantics instead.
        for token in (
            "reddit.age",
            "reddit2.age",
            "gmail.read_sender",
            "gmail.read_subject",
            "gmail.timestamp",
        ):
            rendered = _composite_text_on_surface(colors[token], floor)
            assert _contrast(rendered, floor) >= 4.5, (name, token)

        # Context Menu has no card behind it, so its disabled text also needs a
        # real dark-on-light semantic instead of a very low-alpha platform-like
        # fade over arbitrary wallpaper.
        menu_floor = _composite(colors["context.menu.surface"], [0, 0, 0, 255])
        disabled = _composite_text_on_surface(colors["context.menu.disabled_text"], menu_floor)
        assert _contrast(disabled, menu_floor) >= 4.5, name


def test_light_theme_heading_shadows_do_not_render_as_duplicate_dark_glyphs() -> None:
    for name in LIGHT_SURFACE:
        theme = _load(THEMES / f"{name}.srtheme")
        for token in ("text.section", "text.page", "text.title"):
            shadow = theme["shadows"][token]
            assert shadow["color"][3] <= 48, (name, token)
            assert abs(shadow["offset_x"]) <= 2.0, (name, token)
            assert abs(shadow["offset_y"]) <= 2.0, (name, token)




def test_list_selection_explicitly_keeps_theme_text_colour() -> None:
    source = (ROOT / "ui" / "settings_theme.py").read_text(encoding="utf-8")
    selected = source.split("QListWidget::item:selected {", 1)[1].split("}", 1)[0]
    assert "color: %(list_text)s;" in selected

def test_metal_batch_has_readable_primary_hierarchy() -> None:
    for name in METAL:
        theme = _load(THEMES / f"{name}.srtheme")
        colors = theme["colors"]
        assert _contrast(colors["text.primary"], colors["panel.group.surface"]) >= 4.5, name
        assert _contrast(colors["navigation.tab.selected_text"], colors["navigation.tab.selected_surface"]) >= 4.5, name


def test_generated_widget_counterparts_keep_stable_pair_identity_without_material() -> None:
    for name in LIGHT + METAL:
        widget = _load(WIDGETS / f"{_widget_name(name)}.srwtheme")
        stable_settings_id = f"file:{name}.srtheme"
        assert widget["linked_settings_theme_id"] == stable_settings_id, name
        assert widget["theme_id"] == f"mirror:{stable_settings_id}", name
        assert widget["schema_version"] == 3, name
        assert "default_card_material_mode" not in widget, name
        assert not widget["name"].endswith(" [Glass]"), name
        assert not widget["name"].endswith(" [Acrylic]"), name


def test_curated_widget_mirrors_include_mature_media_and_backlog_semantics() -> None:
    required = {
        "abandonment_issues.accent",
        "media.transport.surface",
        "media.transport.border",
        "media.transport.separator",
        "media.transport.icon",
        "media.mute.surface",
        "media.mute.border",
        "media.mute.inner_border",
        "media.mute.icon",
        "media.mute.muted_icon",
        "media.volume.track",
        "media.volume.fill",
        "media.volume.outline",
        "media.progress.track",
        "media.progress.fill",
        "media.progress.glow",
        "media.progress.shadow",
    }
    for name in LIGHT + METAL:
        raw = _load(WIDGETS / f"{_widget_name(name)}.srwtheme")
        colors = set(raw["colors"])
        assert raw.get("schema_version") == 3, name
        assert required <= colors, name

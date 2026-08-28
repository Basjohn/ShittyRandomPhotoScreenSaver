"""Pure semantic model for SRPSS Theme Foundry.

Theme Foundry edits the same immutable schema-v5 :class:`SettingsThemeSpec`
consumed by Settings and serializes only through ``ui.settings_theme_io``.
There is no source/QSS scanner and no second theme schema hidden in the tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ui.settings_theme_spec import (
    NativeBackdropStyle,
    DEFAULT_DARK_SETTINGS_THEME,
    GradientStop,
    GradientStyle,
    Rgba,
    SettingsThemeSpec,
    ShadowStyle,
)


@dataclass(frozen=True, slots=True)
class AcrylicTintPreset:
    name: str
    tint: Rgba
    description: str


# These are explicitly Acrylic-only. Glass has no native tint in the accepted
# Settings architecture; its colour/opacity belongs to semantic Qt surfaces.
ACRYLIC_TINT_PRESETS: tuple[AcrylicTintPreset, ...] = (
    AcrylicTintPreset(
        "Charcoal (Default)",
        Rgba(24, 24, 24, 80),
        "Default Dark native Acrylic tint.",
    ),
    AcrylicTintPreset(
        "Neutral Smoke",
        Rgba(42, 44, 50, 68),
        "Lighter neutral native Acrylic tint.",
    ),
    AcrylicTintPreset(
        "Cool Acrylic",
        Rgba(62, 82, 112, 58),
        "Cool native Acrylic tint; this does not change the material to Glass.",
    ),
    AcrylicTintPreset(
        "Warm Acrylic",
        Rgba(110, 79, 58, 62),
        "Warm native Acrylic tint; this does not change the material to Glass.",
    ),
    AcrylicTintPreset(
        "Weak Tint Acrylic",
        Rgba(24, 24, 24, 18),
        "Very weak but still non-zero native Acrylic tint.",
    ),
)

BACKDROP_MODE_LABELS: dict[str, str] = {
    "off": "Off",
    "acrylic": "Acrylic",
    "glass": "Glass",
}

BACKDROP_MODE_DESCRIPTIONS: dict[str, str] = {
    "off": "No native Settings backdrop.",
    "acrylic": (
        "AccentPolicy state 4. The backdrop tint below is a real native tint/strength "
        "and must have non-zero alpha."
    ),
    "glass": (
        "AccentPolicy state 3 with no native tint. Visible Glass colour and opacity "
        "come from the semantic Qt RGBA surface roles; backdrop.tint is retained in "
        "the file schema but ignored by the native Glass adapter."
    ),
}


@dataclass(frozen=True, slots=True)
class LayerRelation:
    lower: str
    upper: str
    kind: str
    explanation: str
    reverse_solve: bool = False


# Presentation guidance for Foundry only; runtime renderers remain authoritative.
LAYER_RELATIONS: tuple[LayerRelation, ...] = (
    LayerRelation(
        "window.dialog_glass",
        "window.titlebar.surface",
        "composite",
        "The title bar is painted above the outer dialog glass.",
        True,
    ),
    LayerRelation(
        "window.dialog_glass",
        "navigation.sidebar.surface",
        "composite",
        "The navigation sidebar is painted above the outer dialog glass.",
        True,
    ),
    LayerRelation(
        "window.dialog_glass",
        "content.surface",
        "composite",
        "The main content host is painted above the outer dialog glass.",
        True,
    ),
    LayerRelation(
        "content.surface",
        "panel.group.surface",
        "composite",
        "Group panels are painted above the content host.",
        True,
    ),
    LayerRelation(
        "content.surface",
        "panel.subsection.surface",
        "composite",
        "Subsection panels are painted above the content host.",
        True,
    ),
    LayerRelation(
        "navigation.sidebar.surface",
        "navigation.tab.surface",
        "composite",
        "Ordinary navigation-tab surfaces are painted above the sidebar block.",
        True,
    ),
    LayerRelation(
        "context.menu.surface",
        "context.menu.selected_surface",
        "composite",
        "The selected context-menu item surface is translucent over the menu base.",
        True,
    ),
    LayerRelation(
        "context.submenu.surface",
        "context.submenu.selected_surface",
        "composite",
        "The selected submenu item surface is translucent over the submenu base.",
        True,
    ),
    LayerRelation(
        "popup.container.surface",
        "popup.button.surface",
        "composite",
        "Popup buttons are drawn above the popup container surface.",
        True,
    ),
    LayerRelation(
        "control.list.surface",
        "control.list.selected_surface",
        "composite",
        "The selected-list surface is translucent above the list base.",
        True,
    ),
    LayerRelation(
        "navigation.tab.surface",
        "navigation.tab.hover_surface",
        "state",
        "Hover replaces the ordinary navigation-tab state while active.",
    ),
    LayerRelation(
        "navigation.tab.surface",
        "navigation.tab.selected_surface",
        "state",
        "Selected state replaces the ordinary navigation-tab state.",
    ),
    LayerRelation(
        "control.button.surface",
        "control.button.hover_surface",
        "state",
        "Hover state replaces the ordinary button surface.",
    ),
    LayerRelation(
        "control.button.surface",
        "control.button.pressed_surface",
        "state",
        "Pressed state replaces the ordinary button surface.",
    ),
    LayerRelation(
        "bucket.closed.surface",
        "bucket.open.surface",
        "state",
        "Open and closed bucket surfaces are mutually exclusive states.",
    ),
)


_COLOR_CATEGORY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("window.", "Window & Chrome"),
    ("chrome.", "Window & Chrome"),
    ("navigation.", "Navigation"),
    ("bucket.", "Buckets"),
    ("content.", "Panels & Content"),
    ("panel.", "Panels & Content"),
    ("text.", "Text"),
    ("control.input.", "Inputs & Combos"),
    ("control.stepper.", "Inputs & Combos"),
    ("combo.", "Inputs & Combos"),
    ("tooltip.", "Tooltips"),
    ("control.list.", "Lists"),
    ("control.button.", "Buttons & Actions"),
    ("control.setup_action.", "Buttons & Actions"),
    ("control.ghost_action.", "Buttons & Actions"),
    ("control.mode.", "Buttons & Actions"),
    ("control.checkbox.", "Checkboxes"),
    ("sources.", "Sources"),
    ("shadow.direction.", "Shadow Controls"),
    ("slider.", "Sliders"),
    ("about.", "About"),
    ("popup.", "Popups"),
    ("swatch.", "Swatches"),
    ("color_picker.", "Colour Picker"),
    ("context.", "Context Menu"),
)

_SPECIAL_WORDS = {
    "rss": "RSS",
    "api": "API",
    "html": "HTML",
    "rgb": "RGB",
    "rgba": "RGBA",
    "qss": "QSS",
}


def _human_piece(piece: str) -> str:
    piece = piece.replace("_", " ")
    return " ".join(
        _SPECIAL_WORDS.get(word.lower(), word.capitalize()) for word in piece.split()
    )


def friendly_token_label(token: str) -> str:
    return " · ".join(_human_piece(piece) for piece in token.split("."))


def color_category(token: str) -> str:
    for prefix, category in _COLOR_CATEGORY_PREFIXES:
        if token.startswith(prefix):
            return category
    return "Other Colours"


def semantic_description(kind: str, token: str) -> str:
    if kind == "color":
        return (
            f"Semantic Settings colour role `{token}`. Runtime renderers consume "
            "this role directly; Theme Foundry does not rewrite Python/QSS source literals."
        )
    if kind == "shadow":
        return (
            f"Semantic Settings shadow role `{token}`. Blur, offset, colour and disabled-alpha "
            "scale are serialized into the .srtheme file."
        )
    if kind == "gradient":
        return (
            f"Semantic Settings gradient role `{token}`. The renderer owns geometry; the theme "
            "owns this ordered stop list."
        )
    return token


@dataclass(slots=True)
class ThemeDraft:
    name: str
    backdrop_mode: str
    backdrop_tint: Rgba
    colors: dict[str, Rgba]
    shadows: dict[str, ShadowStyle]
    gradients: dict[str, GradientStyle]

    @classmethod
    def from_spec(cls, spec: SettingsThemeSpec) -> "ThemeDraft":
        return cls(
            name=spec.name,
            backdrop_mode=spec.backdrop.mode,
            backdrop_tint=spec.backdrop.tint,
            colors=dict(spec.colors),
            shadows=dict(spec.shadows),
            gradients=dict(spec.gradients),
        )

    def to_spec(self) -> SettingsThemeSpec:
        return SettingsThemeSpec(
            name=self.name,
            backdrop=NativeBackdropStyle(
                mode=self.backdrop_mode,
                tint=self.backdrop_tint,
            ),
            colors=dict(self.colors),
            shadows=dict(self.shadows),
            gradients=dict(self.gradients),
        )


def alpha_over(top: Rgba, bottom: Rgba) -> Rgba:
    """Straight-alpha composite used for Foundry's predicted visible preview."""

    ta = top.a / 255.0
    ba = bottom.a / 255.0
    out_a = ta + ba * (1.0 - ta)
    if out_a <= 1e-9:
        return Rgba(0, 0, 0, 0)

    def channel(tc: int, bc: int) -> int:
        value = (tc * ta + bc * ba * (1.0 - ta)) / out_a
        return max(0, min(255, round(value)))

    return Rgba(
        channel(top.r, bottom.r),
        channel(top.g, bottom.g),
        channel(top.b, bottom.b),
        max(0, min(255, round(out_a * 255.0))),
    )


def nearest_composite_relation(token: str) -> LayerRelation | None:
    for relation in LAYER_RELATIONS:
        if relation.kind == "composite" and token in {relation.lower, relation.upper}:
            return relation
    return None


def relations_for(token: str) -> tuple[LayerRelation, ...]:
    return tuple(
        relation for relation in LAYER_RELATIONS if token in {relation.lower, relation.upper}
    )


def matching_color_tokens(
    colors: dict[str, Rgba],
    value: Rgba,
) -> tuple[str, ...]:
    """Return semantic colour roles whose full 8-bit RGBA exactly matches ``value``."""

    return tuple(token for token, candidate in colors.items() if candidate == value)


def replace_matching_color_roles(
    colors: dict[str, Rgba],
    match: Rgba,
    replacement: Rgba,
) -> tuple[str, ...]:
    """Replace exact-matching semantic colour roles and return the changed tokens."""

    tokens = matching_color_tokens(colors, match)
    for token in tokens:
        colors[token] = replacement
    return tokens


def most_used_colors(
    colors: dict[str, Rgba],
    *,
    limit: int = 6,
    include_fully_transparent: bool = False,
) -> tuple[tuple[Rgba, tuple[str, ...]], ...]:
    """Rank exact semantic RGBA values by how many colour roles use them.

    Equal-frequency colours keep first-appearance order from ``colors`` so the
    Foundry display is deterministic. Fully transparent values are omitted by
    default because they contribute no visible colour and would otherwise crowd
    the useful palette summary.
    """

    if limit <= 0:
        return ()

    groups: dict[Rgba, list[str]] = {}
    first_seen: dict[Rgba, int] = {}
    for index, (token, value) in enumerate(colors.items()):
        if not include_fully_transparent and value.a == 0:
            continue
        groups.setdefault(value, []).append(token)
        first_seen.setdefault(value, index)

    ranked = sorted(
        groups.items(),
        key=lambda item: (-len(item[1]), first_seen[item[0]]),
    )
    return tuple(
        (value, tuple(tokens))
        for value, tokens in ranked[:limit]
    )


def solve_layer_for_target(
    *,
    selected_token: str,
    relation: LayerRelation,
    colors: dict[str, Rgba],
    target_rgb: tuple[int, int, int],
) -> tuple[Rgba | None, str]:
    """Solve the selected simple alpha-over layer at its current alpha."""

    if relation.kind != "composite" or not relation.reverse_solve:
        return None, "This relationship is not a reversible alpha-over mapping."
    if relation.lower not in colors or relation.upper not in colors:
        return None, "One of the mapped semantic colour roles is unavailable."
    if selected_token not in {relation.lower, relation.upper}:
        return None, "The selected token is not part of this relationship."

    lower = colors[relation.lower]
    upper = colors[relation.upper]
    ta = upper.a / 255.0
    ba = lower.a / 255.0
    out_a = ta + ba * (1.0 - ta)
    if out_a <= 1e-9:
        return None, "Both layers are fully transparent; visible RGB is undefined."

    target = tuple(max(0, min(255, int(v))) for v in target_rgb)

    def solve_channels(denominator: float, fixed_terms: Iterable[float]) -> list[float] | None:
        if denominator <= 1e-9:
            return None
        return [
            (target_channel * out_a - fixed_term) / denominator
            for target_channel, fixed_term in zip(target, fixed_terms)
        ]

    if selected_token == relation.upper:
        fixed = (
            lower.r * ba * (1.0 - ta),
            lower.g * ba * (1.0 - ta),
            lower.b * ba * (1.0 - ta),
        )
        raw = solve_channels(ta, fixed)
        selected_alpha = upper.a
    else:
        fixed = (upper.r * ta, upper.g * ta, upper.b * ta)
        raw = solve_channels(ba * (1.0 - ta), fixed)
        selected_alpha = lower.a

    if raw is None:
        return None, (
            "The selected layer contributes no visible colour at its current alpha. "
            "Increase its opacity (or reduce the covering layer) and try again."
        )
    if any(value < -0.5 or value > 255.5 for value in raw):
        return None, (
            "That visible target cannot be produced with the selected layer's current opacity "
            "without clipping RGB channels. Adjust opacity and try again."
        )

    solved = Rgba(
        max(0, min(255, round(raw[0]))),
        max(0, min(255, round(raw[1]))),
        max(0, min(255, round(raw[2]))),
        selected_alpha,
    )
    predicted = alpha_over(
        solved if selected_token == relation.upper else upper,
        lower if selected_token == relation.upper else solved,
    )
    error = max(
        abs(predicted.r - target[0]),
        abs(predicted.g - target[1]),
        abs(predicted.b - target[2]),
    )
    if error > 2:
        return None, (
            "The fixed-alpha inverse was numerically too far from the requested target. "
            "Adjust opacity and try again."
        )
    return solved, (
        f"Solved `{selected_token}` at alpha {selected_alpha}/255. "
        f"Predicted visible RGB is ({predicted.r}, {predicted.g}, {predicted.b})."
    )


def rgba_summary(value: Rgba) -> str:
    return f"#{value.r:02X}{value.g:02X}{value.b:02X} · a{value.a}"


def shadow_summary(value: ShadowStyle) -> str:
    return (
        f"{rgba_summary(value.color)} · blur {value.blur_radius:g} · "
        f"off {value.offset_x:g},{value.offset_y:g}"
    )


def gradient_summary(value: GradientStyle) -> str:
    return f"{len(value.stops)} stops"


def matching_acrylic_preset(tint: Rgba) -> str | None:
    for preset in ACRYLIC_TINT_PRESETS:
        if preset.tint == tint:
            return preset.name
    return None


__all__ = [
    "ACRYLIC_TINT_PRESETS",
    "BACKDROP_MODE_DESCRIPTIONS",
    "BACKDROP_MODE_LABELS",
    "LAYER_RELATIONS",
    "AcrylicTintPreset",
    "LayerRelation",
    "ThemeDraft",
    "alpha_over",
    "color_category",
    "friendly_token_label",
    "gradient_summary",
    "matching_acrylic_preset",
    "matching_color_tokens",
    "most_used_colors",
    "replace_matching_color_roles",
    "nearest_composite_relation",
    "relations_for",
    "rgba_summary",
    "semantic_description",
    "shadow_summary",
    "solve_layer_for_target",
]

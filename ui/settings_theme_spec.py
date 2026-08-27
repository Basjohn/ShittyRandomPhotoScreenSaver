"""Semantic Settings GUI theme specification.

This module centralises Settings *visual decisions* while deliberately leaving
rendering mechanisms in their existing owners:

* ``core/windows/dwm_blur.py`` owns Windows/DWM acrylic implementation.
* ``ui/widgets/control_shadow.py`` owns the proven Settings shadow renderers.
* ``ui/settings_dialog.py`` owns frameless-window lifecycle and the forged
  outer-edge painter.
* QSS/component modules own how Qt controls are rendered.

Renderers consume values from :data:`DEFAULT_DARK_SETTINGS_THEME` instead of
inventing their own colour/opacity/shadow constants. Geometry that is known to
be fragile (the forged acrylic outer-corner radius/overlap maths in particular)
is intentionally not theme data.

The forged edge has one additional invariant: its opaque camouflage colour is
derived by the renderer from the adjacent shell surface. It is therefore not an
independently themeable colour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


SETTINGS_THEME_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class Rgba:
    """One 8-bit RGBA colour used by the Settings theme."""

    r: int
    g: int
    b: int
    a: int = 255

    def __post_init__(self) -> None:
        for channel_name, value in (
            ("r", self.r),
            ("g", self.g),
            ("b", self.b),
            ("a", self.a),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"RGBA channel {channel_name!r} must be an int")
            if value < 0 or value > 255:
                raise ValueError(
                    f"RGBA channel {channel_name!r} must be in 0..255, got {value}"
                )

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.r, self.g, self.b, self.a)

    def as_list(self) -> list[int]:
        return [self.r, self.g, self.b, self.a]


TRANSPARENT = Rgba(0, 0, 0, 0)
WHITE = Rgba(255, 255, 255, 255)
BLACK = Rgba(0, 0, 0, 255)


@dataclass(frozen=True, slots=True)
class AcrylicStyle:
    """Theme-facing request for the Settings native acrylic backdrop.

    ``enabled`` is deliberately separate from tint alpha. Disabling acrylic
    calls the platform disable path rather than relying on an alpha-zero
    acrylic request, which is an unreliable/degenerate Windows edge case on
    some compositor versions.
    """

    enabled: bool
    tint: Rgba

    def __post_init__(self) -> None:
        if self.enabled and self.tint.a == 0:
            raise ValueError(
                "Enabled Settings acrylic must use non-zero tint alpha; "
                "use enabled=False to disable acrylic"
            )


@dataclass(frozen=True, slots=True)
class ShadowStyle:
    """Theme data for one existing Settings shadow renderer."""

    blur_radius: float
    offset_x: float
    offset_y: float
    color: Rgba
    disabled_alpha_scale: float = 0.4

    def __post_init__(self) -> None:
        if self.blur_radius < 0:
            raise ValueError("Shadow blur_radius cannot be negative")
        if not 0.0 <= self.disabled_alpha_scale <= 1.0:
            raise ValueError("Shadow disabled_alpha_scale must be in 0..1")


@dataclass(frozen=True, slots=True)
class GradientStop:
    """One semantic colour stop in a renderer-owned linear gradient."""

    position: float
    color: Rgba

    def __post_init__(self) -> None:
        if isinstance(self.position, bool) or not isinstance(
            self.position,
            (int, float),
        ):
            raise TypeError("Gradient stop position must be numeric")
        position = float(self.position)
        if not 0.0 <= position <= 1.0:
            raise ValueError(
                f"Gradient stop position must be in 0..1, got {position}"
            )
        object.__setattr__(self, "position", position)


@dataclass(frozen=True, slots=True)
class GradientStyle:
    """Theme colours for a gradient whose direction/geometry stays renderer-owned."""

    stops: tuple[GradientStop, ...]

    def __post_init__(self) -> None:
        stops = tuple(self.stops)
        if len(stops) < 2:
            raise ValueError("A Settings theme gradient needs at least two stops")
        previous = -1.0
        for stop in stops:
            if not isinstance(stop, GradientStop):
                raise TypeError("GradientStyle stops must be GradientStop values")
            if stop.position < previous:
                raise ValueError("Gradient stop positions must be non-decreasing")
            previous = stop.position
        object.__setattr__(self, "stops", stops)


@dataclass(frozen=True, slots=True)
class SettingsThemeSpec:
    """Resolved semantic theme values consumed by Settings renderers.

    The maps use semantic keys rather than source-file identities. That is an
    intentional break from Theme Foundry's old source-location-shaped token
    discovery and allows a future selectable theme to change appearance without
    rewriting Python files.
    """

    name: str
    acrylic: AcrylicStyle
    colors: Mapping[str, Rgba]
    shadows: Mapping[str, ShadowStyle]
    gradients: Mapping[str, GradientStyle] = field(default_factory=dict)
    schema_version: int = SETTINGS_THEME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Settings theme name cannot be empty")
        if self.schema_version != SETTINGS_THEME_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported Settings theme schema version: "
                f"{self.schema_version}"
            )

        for collection_name, mapping in (
            ("colors", self.colors),
            ("shadows", self.shadows),
            ("gradients", self.gradients),
        ):
            for key in mapping:
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(
                        f"Settings theme {collection_name} keys must be non-empty strings"
                    )

        # Prevent accidental mutation of a supposedly frozen theme through the
        # underlying dictionaries supplied by a caller.
        object.__setattr__(self, "colors", MappingProxyType(dict(self.colors)))
        object.__setattr__(self, "shadows", MappingProxyType(dict(self.shadows)))
        object.__setattr__(
            self,
            "gradients",
            MappingProxyType(dict(self.gradients)),
        )

    def color(self, token: str) -> Rgba:
        """Return one semantic colour or raise a useful error."""

        try:
            return self.colors[token]
        except KeyError as exc:
            raise KeyError(f"Unknown Settings theme colour token: {token}") from exc

    def shadow(self, token: str) -> ShadowStyle:
        """Return one semantic shadow style or raise a useful error."""

        try:
            return self.shadows[token]
        except KeyError as exc:
            raise KeyError(f"Unknown Settings theme shadow token: {token}") from exc

    def gradient(self, token: str) -> GradientStyle:
        """Return one semantic gradient palette or raise a useful error."""

        try:
            return self.gradients[token]
        except KeyError as exc:
            raise KeyError(
                f"Unknown Settings theme gradient token: {token}"
            ) from exc


# ---------------------------------------------------------------------------
# Default Dark — current approved Settings visual language
# ---------------------------------------------------------------------------
#
# Intentionally represented here:
#   * native acrylic request;
#   * Settings shell/navigation/panel colours;
#   * forged outer-border colour, but never forged-corner geometry/camouflage;
#   * the approved central Settings shadow language.
#
# Intentionally represented here before shared_styles.py consumes it:
#   * reusable input/combo/tooltip/text colours;
#   * slider state colours + gradient stop palettes;
#   * the recommended-slider marker colour.
#
# Intentionally deferred until their owning renderer/tab is migrated:
#   * tab-local palettes (RSS/accessibility/etc.);
#   * About/local popup palettes;
#   * typography/spacing/geometry;
#   * resource-backed checkbox artwork;
#   * context-menu theme data.

_DEFAULT_DARK_COLORS: dict[str, Rgba] = {
    # Top-level/window layering from ui/settings_theme.py.
    "window.dialog_glass": Rgba(60, 60, 60, 20),
    "window.titlebar.surface": Rgba(12, 12, 12, 209),
    "window.titlebar.text": WHITE,
    "window.titlebar.button.surface": TRANSPARENT,
    "window.titlebar.button.hover": Rgba(62, 62, 62, 204),
    "window.titlebar.button.pressed": Rgba(50, 50, 50, 220),
    "window.titlebar.close.hover": Rgba(232, 17, 35, 204),

    # Left navigation / right content shell from ui/settings_theme.py.
    "navigation.sidebar.surface": Rgba(40, 40, 40, 32),
    "navigation.tab.surface": Rgba(20, 20, 20, 48),
    "navigation.tab.text": Rgba(204, 204, 204, 255),
    "navigation.tab.hover_surface": Rgba(62, 62, 62, 120),
    "navigation.tab.hover_text": WHITE,
    "navigation.tab.selected_surface": Rgba(62, 62, 62, 140),
    "navigation.tab.selected_text": WHITE,
    "content.surface": TRANSPARENT,

    # Global + mature local panel layers. Both remain separate because the
    # local subsection style intentionally masks the global QGroupBox surface
    # on many mature Settings sections.
    "panel.group.surface": Rgba(60, 60, 60, 115),
    "panel.subsection.surface": Rgba(60, 60, 60, 102),
    "panel.border": WHITE,

    # Reusable text roles from ui/tabs/shared_styles.py.
    "text.primary": WHITE,
    "text.disabled": Rgba(102, 102, 102, 255),
    "text.secondary": Rgba(170, 170, 170, 255),
    "text.tertiary": Rgba(136, 136, 136, 255),
    "text.helper": Rgba(220, 220, 220, 153),
    "text.helper_disabled": Rgba(85, 85, 85, 255),

    # Shared spin/line-edit/combo state palette.
    "control.input.surface": Rgba(31, 31, 31, 255),
    "control.input.hover_surface": Rgba(22, 22, 22, 255),
    "control.input.focus_surface": Rgba(20, 20, 20, 255),
    "control.input.text": WHITE,
    "control.input.border": WHITE,
    "control.input.disabled_text": Rgba(255, 255, 255, 115),
    "control.input.disabled_border": Rgba(106, 106, 106, 255),
    "control.stepper.surface": WHITE,
    "control.stepper.hover_surface": Rgba(77, 77, 77, 255),
    "control.stepper.pressed_surface": Rgba(45, 45, 45, 255),
    "control.stepper.disabled_surface": Rgba(106, 106, 106, 255),

    # Shared custom-combo popup palette.
    "combo.popup.surface": Rgba(18, 18, 18, 242),
    "combo.popup.border": WHITE,
    "combo.popup.selection_surface": Rgba(255, 255, 255, 56),
    "combo.popup.text": WHITE,
    "combo.popup.selection_text": WHITE,

    # Shared tooltip palette.
    "tooltip.surface": Rgba(30, 30, 30, 255),
    "tooltip.text": WHITE,
    "tooltip.border": WHITE,

    # Shared slider colours that are not gradient stops.
    "slider.groove.border": Rgba(12, 12, 12, 230),
    "slider.groove.top_border": Rgba(0, 0, 0, 179),
    "slider.groove.bottom_border": Rgba(70, 70, 70, 64),
    "slider.fill.border": Rgba(35, 35, 35, 217),
    "slider.fill.top_border": Rgba(25, 25, 25, 179),
    "slider.fill.bottom_border": Rgba(80, 80, 80, 64),
    "slider.handle.border": Rgba(103, 103, 103, 255),
    "slider.handle.hover_border": Rgba(153, 153, 153, 255),
    "slider.handle.pressed_border": Rgba(42, 42, 42, 255),
    "slider.handle.disabled_surface": Rgba(90, 90, 90, 255),
    "slider.handle.active_border": Rgba(17, 17, 17, 255),
    "slider.recommended_mark": Rgba(210, 210, 210, 170),

    # The visible forged outer border may be themed. The backing/corner
    # camouflage is intentionally absent: settings_dialog.py derives opaque RGB
    # from the adjacent shell surface so the illusion cannot be desynchronised.
    "chrome.outer_border": WHITE,
    "chrome.size_grip": Rgba(255, 255, 255, 200),
}


_DEFAULT_DARK_GRADIENTS: dict[str, GradientStyle] = {
    # Direction, dimensions and radii remain ui/tabs/shared_styles.py concerns.
    "slider.groove.surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(8, 8, 8, 242)),
            GradientStop(0.35, Rgba(20, 20, 20, 230)),
            GradientStop(0.65, Rgba(30, 30, 30, 217)),
            GradientStop(1.0, Rgba(45, 45, 45, 179)),
        )
    ),
    "slider.fill.surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(50, 50, 50, 230)),
            GradientStop(0.5, Rgba(65, 65, 65, 217)),
            GradientStop(1.0, Rgba(50, 50, 50, 191)),
        )
    ),
    "slider.handle.surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(46, 46, 46, 255)),
            GradientStop(0.85, Rgba(26, 26, 26, 255)),
            GradientStop(1.0, Rgba(17, 17, 17, 255)),
        )
    ),
    "slider.handle.hover_surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(58, 58, 58, 255)),
            GradientStop(0.85, Rgba(36, 36, 36, 255)),
            GradientStop(1.0, Rgba(24, 24, 24, 255)),
        )
    ),
    "slider.handle.pressed_surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(34, 34, 34, 255)),
            GradientStop(1.0, Rgba(20, 20, 20, 255)),
        )
    ),
    # The active/last-moved handle currently reuses the normal handle gradient.
    "slider.handle.active_surface": GradientStyle(
        stops=(
            GradientStop(0.0, Rgba(46, 46, 46, 255)),
            GradientStop(0.85, Rgba(26, 26, 26, 255)),
            GradientStop(1.0, Rgba(17, 17, 17, 255)),
        )
    ),
}


_DEFAULT_DARK_SHADOWS: dict[str, ShadowStyle] = {
    # Current approved values consumed by ui/widgets/control_shadow.py.
    # QLineEdit intentionally shares this crisp input style; there is no
    # separate legacy blurred-line-edit token anymore.
    "input.spin_combo": ShadowStyle(
        blur_radius=0.0,
        offset_x=6.0,
        offset_y=8.0,
        color=Rgba(0, 0, 0, 120),
    ),
    "button.pill": ShadowStyle(
        blur_radius=0.0,
        offset_x=5.0,
        offset_y=6.0,
        color=Rgba(0, 0, 0, 95),
    ),
    "navigation.tab": ShadowStyle(
        blur_radius=0.0,
        offset_x=5.0,
        offset_y=6.0,
        color=Rgba(0, 0, 0, 110),
    ),
    "bucket.closed": ShadowStyle(
        blur_radius=0.0,
        offset_x=3.0,
        offset_y=4.0,
        color=Rgba(0, 0, 0, 60),
    ),
    "bucket.open": ShadowStyle(
        blur_radius=0.0,
        offset_x=5.0,
        offset_y=6.0,
        color=Rgba(0, 0, 0, 105),
    ),
    "text.section": ShadowStyle(
        blur_radius=0.0,
        offset_x=2.0,
        offset_y=2.0,
        color=Rgba(0, 0, 0, 125),
    ),
    "text.page": ShadowStyle(
        blur_radius=0.0,
        offset_x=2.0,
        offset_y=3.0,
        color=Rgba(0, 0, 0, 140),
    ),
    "text.title": ShadowStyle(
        blur_radius=0.0,
        offset_x=3.0,
        offset_y=4.0,
        color=Rgba(0, 0, 0, 140),
    ),
    "shell.panel": ShadowStyle(
        blur_radius=0.0,
        offset_x=6.0,
        offset_y=8.0,
        color=Rgba(0, 0, 0, 96),
    ),
    "scrollbar": ShadowStyle(
        blur_radius=0.0,
        offset_x=4.0,
        offset_y=5.0,
        color=Rgba(0, 0, 0, 110),
    ),
    "panel.group": ShadowStyle(
        blur_radius=0.0,
        offset_x=6.0,
        offset_y=8.0,
        color=Rgba(0, 0, 0, 90),
    ),
}


DEFAULT_DARK_SETTINGS_THEME = SettingsThemeSpec(
    name="Default Dark",
    acrylic=AcrylicStyle(
        enabled=True,
        tint=Rgba(24, 24, 24, 80),
    ),
    colors=_DEFAULT_DARK_COLORS,
    shadows=_DEFAULT_DARK_SHADOWS,
    gradients=_DEFAULT_DARK_GRADIENTS,
)


__all__ = [
    "AcrylicStyle",
    "BLACK",
    "DEFAULT_DARK_SETTINGS_THEME",
    "GradientStop",
    "GradientStyle",
    "Rgba",
    "SETTINGS_THEME_SCHEMA_VERSION",
    "SettingsThemeSpec",
    "ShadowStyle",
    "TRANSPARENT",
    "WHITE",
]

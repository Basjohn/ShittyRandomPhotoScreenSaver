"""QSS colour serialization for semantic Settings themes.

Qt style-sheet colour properties accept alpha-capable QColor syntax. Keep the
historical compact ``#RRGGBB`` spelling for fully opaque values, but never make
opacity a semantic restriction: translucent values render as integer-alpha
``rgba(r, g, b, a)``.
"""

from __future__ import annotations

from ui.settings_theme_spec import Rgba


def render_qss_rgba255(value: Rgba) -> str:
    """Render one RGBA value using Qt's integer-alpha QSS syntax."""

    return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"


def render_qss_color(value: Rgba) -> str:
    """Render one semantic colour without imposing an opacity constraint."""

    if value.a == 255:
        return f"#{value.r:02x}{value.g:02x}{value.b:02x}"
    return render_qss_rgba255(value)


__all__ = ["render_qss_color", "render_qss_rgba255"]

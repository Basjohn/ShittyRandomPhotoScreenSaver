"""Shared derived palette semantics; no stored roles or theme-name rules."""
from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass

from ui.settings_theme_spec import Rgba


def _relative_luminance(color: Rgba) -> float:
    channels = [value / 255.0 for value in (color.r, color.g, color.b)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def relative_luminance(color: Rgba) -> float:
    """WCAG relative luminance of ``color``'s RGB (alpha ignored)."""
    return _relative_luminance(color)


def contrast_ratio(first: Rgba, second: Rgba) -> float:
    """WCAG contrast ratio of two colours' RGB (alpha ignored: composite first, see :func:`composite_over`)."""
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def composite_over(top: Rgba, bottom: Rgba) -> Rgba:
    """``top`` source-over an opaque ``bottom``, as the compositor blends a translucent surface; opaque result."""
    weight = top.a / 255.0
    return Rgba(*(round(t * weight + b * (1.0 - weight))
                  for t, b in ((top.r, bottom.r), (top.g, bottom.g), (top.b, bottom.b))), 255)


def uses_dark_text_on_light_surface(foreground: Rgba, surface: Rgba) -> bool:
    """The existing light-palette hierarchy, independent of backdrop/material alpha.

    Alpha remains authored composition data. This identifies the palette's text
    polarity; it does not repair, recolour or make its surfaces more opaque.
    """
    return _relative_luminance(foreground) <= 0.18 and _relative_luminance(surface) >= 0.55


def settings_theme_is_light(theme) -> bool:
    return uses_dark_text_on_light_surface(theme.color("text.primary"), theme.color("panel.group.surface"))


def widget_theme_is_light(theme) -> bool:
    return uses_dark_text_on_light_surface(theme.color("card.text"), theme.color("card.background"))


# ---------------------------------------------------------------------------
# Theme filter terms (Themes tab type-in filter; Settings_Theme_Architecture.md "Theme filter")
# ---------------------------------------------------------------------------

THEME_TONES = ("Dark", "Light")
GREY_FAMILY = "Grey"
# Named hue families in canonical (completer) order; Grey stands for a low-saturation theme.
THEME_COLOUR_FAMILIES = ("Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink", GREY_FAMILY)
# Upper hue bound (degrees, exclusive) of each family, walked in order; red wraps around 0/360.
_HUE_FAMILY_BOUNDS = ((15.0, "Red"), (45.0, "Orange"), (70.0, "Yellow"), (160.0, "Green"), (195.0, "Teal"),
                      (250.0, "Blue"), (290.0, "Purple"), (345.0, "Pink"), (360.0, "Red"))
# An accent is neutral (no hue family) below this chroma (max - min channel, 0..255) or HSV saturation.
NEUTRAL_CHROMA = 18
NEUTRAL_SATURATION = 0.22  # steel/slate-grey accents (Graphite, Ghost, Chrome greys) stay Grey
# A surface names a colour only when it is clearly coloured to the eye: both a real saturation and enough
# chroma, so the faintly tinted near-black (navy, plum) and near-white surfaces most themes use stay neutral.
SURFACE_MIN_CHROMA = 56
SURFACE_MIN_SATURATION = 0.5


@dataclass(frozen=True, slots=True)
class ThemeFilterTerms:
    """What a theme is, derived from its own colours and material: never a hand-kept tag."""

    tone: str                      # one of THEME_TONES
    material: str                  # a SURFACE_MATERIAL_LABELS label ("Normal", "Glass", ...)
    colours: tuple[str, ...]       # THEME_COLOUR_FAMILIES members, canonical order

    @property
    def terms(self) -> tuple[str, ...]:
        return (self.tone, self.material, *self.colours)


def colour_family(color: Rgba, *, min_chroma: int = NEUTRAL_CHROMA,
                  min_saturation: float = NEUTRAL_SATURATION) -> str:
    """The named hue family of ``color``'s RGB (alpha ignored), or Grey below the neutral limits."""
    high, low = max(color.r, color.g, color.b), min(color.r, color.g, color.b)
    chroma = high - low
    if chroma < min_chroma or chroma / high < min_saturation:
        return GREY_FAMILY
    hue = colorsys.rgb_to_hsv(color.r / 255.0, color.g / 255.0, color.b / 255.0)[0] * 360.0
    return next(family for bound, family in _HUE_FAMILY_BOUNDS if hue < bound)


def _signature_colours(theme) -> tuple[Rgba, Rgba, Rgba | None]:
    """(ink, surface, accent) of a Settings or Widget theme, read from its authored role map."""
    colors = theme.colors
    if hasattr(theme, "backdrop"):  # SettingsThemeSpec
        return colors["text.primary"], colors["panel.group.surface"], colors.get("control.list.selected_accent")
    return colors["card.text"], colors["card.background"], colors.get("widget.accent", colors.get("card.border"))


def _theme_material_label(theme) -> str:
    from rendering.quick.widgets.surface_material import NORMAL, SURFACE_MATERIAL_LABELS, normalize_surface_material

    if hasattr(theme, "backdrop"):
        mode = theme.backdrop.mode
        return SURFACE_MATERIAL_LABELS[NORMAL if mode == "off" else mode]
    return SURFACE_MATERIAL_LABELS[normalize_surface_material(getattr(theme, "surface_material", None)) or NORMAL]


def theme_filter_terms(theme) -> ThemeFilterTerms:
    """Derive a Settings or Widget theme's filter terms from the theme's own data.

    * Tone: Light when its ink is dark on a light surface (``uses_dark_text_on_light_surface``), else Dark.
    * Material: the Settings backdrop mode (``off`` is Normal) or the Widget card ``surface_material``,
      labelled by the card material owner.
    * Colours: the visible identity: the accent's hue family always, the surface's only when the surface is
      clearly coloured (``SURFACE_MIN_CHROMA`` and ``SURFACE_MIN_SATURATION``); Grey when neither names one.

    Pure: authored role maps only (no active-theme or opacity state), so imported and user themes are covered.
    """
    ink, surface, accent = _signature_colours(theme)
    tone = THEME_TONES[1] if uses_dark_text_on_light_surface(ink, surface) else THEME_TONES[0]
    found = {colour_family(surface, min_chroma=SURFACE_MIN_CHROMA, min_saturation=SURFACE_MIN_SATURATION)}
    if accent is not None:
        found.add(colour_family(accent))
    found.discard(GREY_FAMILY)
    colours = tuple(family for family in THEME_COLOUR_FAMILIES if family in found) or (GREY_FAMILY,)
    return ThemeFilterTerms(tone=tone, material=_theme_material_label(theme), colours=colours)


def filter_words(text: str) -> tuple[str, ...]:
    """The case-folded words of a filter query; empty means show everything."""
    return tuple(word.casefold() for word in str(text or "").split())


_WORD_RE = re.compile(r"[^\W_]+")


def name_words(name: str) -> tuple[str, ...]:
    """A display name's case-folded words, split on non-alphanumerics ("[Glass]" -> "glass")."""
    return tuple(_WORD_RE.findall(str(name).casefold()))


def _word_matches_name(word: str, words: tuple[str, ...]) -> bool:
    # A query word may itself span words ("two-tone", "[glass]"): its pieces must match consecutive name words,
    # every piece but the last exactly and the last by prefix.
    pieces = _WORD_RE.findall(word)
    if not pieces:
        return True
    *whole, last = pieces
    span = len(pieces)
    return any(list(words[start:start + span - 1]) == whole and words[start + span - 1].startswith(last)
               for start in range(len(words) - span + 1))


def theme_matches_filter(words, name: str, terms) -> bool:
    """Every word (AND) starts one of ``name``'s words or equals/prefixes one of ``terms``, ignoring case."""
    folded_words = name_words(name)
    folded_terms = tuple(str(term).casefold() for term in terms)
    return all(_word_matches_name(word, folded_words) or any(term.startswith(word) for term in folded_terms)
               for word in words)

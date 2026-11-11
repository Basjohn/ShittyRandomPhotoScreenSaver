"""Theme filter terms derive from a theme's own data (synthetic, test-owned specs; never shipped theme values)."""
from __future__ import annotations

import colorsys
from dataclasses import replace

import pytest

from rendering.quick.widgets.surface_material import SURFACE_MATERIAL_LABELS, SURFACE_MATERIALS
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NATIVE_BACKDROP_MODES, NativeBackdropStyle, Rgba
from ui.theme_semantics import (_HUE_FAMILY_BOUNDS, GREY_FAMILY, THEME_COLOUR_FAMILIES, THEME_TONES,
                                colour_family, filter_words, theme_filter_terms, theme_matches_filter)
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

WHITE, BLACK = Rgba(250, 250, 250), Rgba(12, 12, 12)


def _hue_colour(hue: float, value: float = 0.8) -> Rgba:
    r, g, b = colorsys.hsv_to_rgb((hue % 360.0) / 360.0, 0.8, value)
    return Rgba(round(r * 255), round(g * 255), round(b * 255))


def _family_centres() -> list[tuple[float, str]]:
    centres, lower = [], 0.0
    for upper, family in _HUE_FAMILY_BOUNDS:
        centres.append(((lower + upper) / 2.0, family))
        lower = upper
    return centres


def _settings(*, ink, surface, accent, mode="glass"):
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors.update({"text.primary": ink, "panel.group.surface": surface, "control.list.selected_accent": accent})
    return replace(DEFAULT_DARK_SETTINGS_THEME, name="Synthetic", colors=colors,
                   backdrop=NativeBackdropStyle(mode, Rgba(30, 30, 30, 120)))


def _widget(*, ink, surface, accent=None, border=WHITE, material=None):
    colors = dict(DEFAULT_DARK_WIDGET_THEME.colors)
    colors.update({"card.text": ink, "card.background": surface, "card.border": border})
    colors.pop("widget.accent", None)
    if accent is not None:
        colors["widget.accent"] = accent
    return replace(DEFAULT_DARK_WIDGET_THEME, theme_id="synthetic", name="Synthetic", colors=colors,
                   surface_material=material)


@pytest.mark.parametrize("hue,family", _family_centres())
def test_every_hue_family_is_reached_by_its_own_hues(hue, family):
    assert colour_family(_hue_colour(hue)) == family
    assert colour_family(_hue_colour(hue, value=0.3)) == family  # dark surfaces keep their hue


def test_low_chroma_and_low_saturation_colours_are_grey():
    for colour in (WHITE, BLACK, Rgba(60, 60, 64), Rgba(200, 205, 210), Rgba(40, 40, 40, 0)):
        assert colour_family(colour) == GREY_FAMILY
    assert colour_family(Rgba(30, 30, 200)) != GREY_FAMILY  # negative control: a saturated blue has a hue


def test_tone_follows_ink_on_surface_for_both_theme_kinds():
    dark_s = _settings(ink=WHITE, surface=BLACK, accent=WHITE)
    light_s = _settings(ink=BLACK, surface=WHITE, accent=BLACK)
    assert (theme_filter_terms(dark_s).tone, theme_filter_terms(light_s).tone) == THEME_TONES
    dark_w = _widget(ink=WHITE, surface=BLACK)
    light_w = _widget(ink=BLACK, surface=WHITE)
    assert (theme_filter_terms(dark_w).tone, theme_filter_terms(light_w).tone) == THEME_TONES


@pytest.mark.parametrize("mode", sorted(NATIVE_BACKDROP_MODES))
def test_settings_material_comes_from_the_backdrop_through_the_material_owner(mode):
    terms = theme_filter_terms(_settings(ink=WHITE, surface=BLACK, accent=WHITE, mode=mode))
    assert terms.material == SURFACE_MATERIAL_LABELS["normal" if mode == "off" else mode]


@pytest.mark.parametrize("material", [None, *SURFACE_MATERIALS])
def test_widget_material_comes_from_surface_material(material):
    terms = theme_filter_terms(_widget(ink=WHITE, surface=BLACK, material=material))
    assert terms.material == SURFACE_MATERIAL_LABELS[material or "normal"]


def test_colours_are_the_accent_and_surface_families_in_canonical_order():
    (blue_hue, blue), (orange_hue, orange) = [(h, f) for h, f in _family_centres() if f in ("Blue", "Orange")]
    two_tone = _settings(ink=WHITE, surface=_hue_colour(blue_hue, 0.3), accent=_hue_colour(orange_hue))
    assert theme_filter_terms(two_tone).colours == tuple(f for f in THEME_COLOUR_FAMILIES if f in (blue, orange))
    single = _settings(ink=WHITE, surface=Rgba(40, 40, 40), accent=_hue_colour(blue_hue))
    assert theme_filter_terms(single).colours == (blue,)
    neutral = _settings(ink=WHITE, surface=Rgba(40, 40, 40), accent=WHITE)
    assert theme_filter_terms(neutral).colours == (GREY_FAMILY,)


def test_widget_accent_falls_back_to_the_card_border():
    hue, family = next((h, f) for h, f in _family_centres() if f == "Green")
    without_accent = _widget(ink=WHITE, surface=Rgba(40, 40, 40), border=_hue_colour(hue))
    assert theme_filter_terms(without_accent).colours == (family,)
    other_hue, other = next((h, f) for h, f in _family_centres() if f == "Purple")
    with_accent = _widget(ink=WHITE, surface=Rgba(40, 40, 40), border=_hue_colour(hue), accent=_hue_colour(other_hue))
    assert theme_filter_terms(with_accent).colours == (other,)


def test_terms_list_tone_material_then_colours():
    terms = theme_filter_terms(_settings(ink=WHITE, surface=BLACK, accent=WHITE, mode="mica"))
    assert terms.terms == (terms.tone, terms.material, *terms.colours)


def test_matching_is_case_insensitive_and_and_narrows():
    terms = ("Dark", "Glass", "Blue", "Orange")
    assert theme_matches_filter(filter_words(""), "Anything", terms)
    assert theme_matches_filter(filter_words("blue"), "Night Sky", terms)          # term
    assert theme_matches_filter(filter_words("BL"), "Night Sky", terms)            # term prefix
    assert theme_matches_filter(filter_words("sky"), "Night Sky", terms)           # name substring
    assert theme_matches_filter(filter_words("ght s"), "Night Sky", terms)         # each word a substring
    assert theme_matches_filter(filter_words("dark   glass blue"), "Night Sky", terms)
    # Negative controls: a word inside a term (not a prefix) and a failing word in an AND query.
    assert not theme_matches_filter(filter_words("lue"), "Night Sky", terms)
    assert not theme_matches_filter(filter_words("dark light"), "Night Sky", terms)

"""Cached Settings surface composition and real semantic ink locations.

No Qt objects, palette files, paint callbacks or persistence owners live here.
Neutral fills solve a combined density target once; ink never adds panel density.
"""
from __future__ import annotations

from collections import defaultdict
from core.settings.surface_opacity import is_surface_role, settings_surface_density
from ui.settings_theme_spec import Rgba
from ui.theme_semantics import composite_over, contrast_ratio, relative_luminance

# Shell layers every Settings text sits on, bottom to top, above the material.
_SHELL = ("window.dialog_glass",)
_CONTENT = (*_SHELL, "content.surface")
_GROUP = (*_CONTENT, "panel.group.surface")
_SUBSECTION = (*_CONTENT, "panel.subsection.surface")
_SIDEBAR = (*_SHELL, "navigation.sidebar.surface")

# (text role, surfaces it sits on, large text). Each role may sit on several stacks; the worst counts.
SETTINGS_TEXT_STACKS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("window.titlebar.text", (*_SHELL, "window.titlebar.surface"), True),
    ("navigation.tab.text", (*_SIDEBAR, "navigation.tab.surface"), False),
    ("navigation.tab.hover_text", (*_SIDEBAR, "navigation.tab.hover_surface"), False),
    ("navigation.tab.selected_text", (*_SIDEBAR, "navigation.tab.selected_surface"), False),
    ("navigation.subtab.text", (*_CONTENT, "navigation.subtab.surface"), False),
    ("navigation.subtab.text", (*_CONTENT, "navigation.subtab.selected_surface"), False),
    ("text.primary", _CONTENT, False),
    ("text.primary", _GROUP, False),
    ("text.primary", _SUBSECTION, False),
    ("text.secondary", _CONTENT, False),
    ("text.secondary", _GROUP, False),
    ("text.secondary", _SUBSECTION, False),
    ("text.tertiary", _SUBSECTION, False),
    ("text.helper", _SUBSECTION, False),
    ("text.tertiary", _GROUP, False),
    ("text.helper", _GROUP, False),
    ("panel.group.text", _GROUP, False),
    ("panel.group.title_text", _GROUP, False),
    ("bucket.closed.text", (*_GROUP, "bucket.closed.surface"), False),
    ("bucket.open.text", (*_GROUP, "bucket.open.surface"), False),
    ("control.input.text", (*_GROUP, "control.input.surface"), False),
    ("control.input.text", (*_SUBSECTION, "control.input.surface"), False),
    ("control.button.text", (*_GROUP, "control.button.surface"), False),
    ("control.list.text", (*_SUBSECTION, "control.list.surface"), False),
    ("control.list.text", (*_SUBSECTION, "control.list.surface", "control.list.selected_surface"), False),
    ("control.checkbox.text", _GROUP, False),
    ("control.mode.text", (*_GROUP, "control.mode.surface"), False),
    ("control.mode.text", (*_SUBSECTION, "control.mode.surface"), False),
    ("control.setup_action.text", (*_GROUP, "control.setup_action.surface"), False),
    ("control.ghost_action.text", (*_GROUP, "control.ghost_action.surface"), False),
    ("about.blurb.text", (*_CONTENT, "about.card.surface"), False),
    ("about.hotkeys.text", (*_CONTENT, "about.card.surface"), False),
    ("about.link.text", (*_CONTENT, "about.card.surface", "about.link.surface"), False),
    ("about.notice.text", (*_CONTENT, "about.card.surface", "about.notice.surface"), False),
)


# Neutral fill parents follow the existing QSS/component owners. Shared controls
# keep their independent state recipe where they occur under different parents.
NEUTRAL_SURFACE_PARENTS = {
    "window.dialog_glass": (),
    "window.titlebar.surface": _SHELL,
    "content.surface": _SHELL,
    "navigation.sidebar.surface": _SHELL,
    "navigation.tab.surface": _SIDEBAR,
    "navigation.subtab.surface": _CONTENT,
    "panel.group.surface": _CONTENT,
    "panel.subsection.surface": _CONTENT,
    "control.list.surface": _SUBSECTION,
    "control.input.surface": _SUBSECTION,
    "about.card.surface": _CONTENT,
}


CONTROL_STATE_SURFACES = {"checked": "control.mode.checked_surface", "hover": "control.mode.hover_surface"}
CONTROL_STATE_TEXT_STACKS = tuple(
    (state, (*parent, surface))
    for state, surface in CONTROL_STATE_SURFACES.items() for parent in (_GROUP, _SUBSECTION)
)


def _state_inks(raw, colors, native):
    locations = defaultdict(list)
    for state, stack in CONTROL_STATE_TEXT_STACKS:
        locations[state].extend((_surface(native, colors, stack, pole), 5.1) for pole in (0, 255))
    for state, surfaces in locations.items():
        colors[f"@control.mode.{state}"] = _correct_ink(raw["control.mode.text"], surfaces)
    colors["@window.composed"] = combine_surface_tint(colors["window.dialog_glass"], native)
    return colors, native


def combine_surface_tint(surface, tint):
    """Source-over to transparent; preserve alpha rather than baking a desktop."""
    if tint is None:
        return surface
    top, bottom = surface.a / 255.0, tint.a / 255.0
    alpha = top + bottom * (1.0 - top)
    if alpha <= 0.0:
        return Rgba(0, 0, 0, 0)
    channels = [round((a * top + b * bottom * (1.0 - top)) / alpha)
                for a, b in zip(surface.as_tuple()[:3], tint.as_tuple()[:3])]
    return Rgba(*channels, round(alpha * 255))


def native_backdrop_request(mode):
    """Shared native mechanism: Qt owns tint; every enabled material uses blur."""
    return ("off" if mode == "off" else "glass", None)


def _density(tint, colors, stack):
    transmission = 1.0 if tint is None else 1.0 - tint.a / 255.0
    for role in stack:
        transmission *= 1.0 - colors[role].a / 255.0
    return 1.0 - transmission


def _surface(tint, colors, stack, pole):
    base = Rgba(pole, pole, pole)
    if tint is not None:
        base = composite_over(tint, base)
    for role in stack:
        base = composite_over(colors[role], base)
    return base


def _correct_ink(ink, locations):
    """Raise alpha, then correct contrast without reversing authored ink polarity."""
    def quality(candidate):
        return min(contrast_ratio(composite_over(candidate, surface), surface) / bar
                   for surface, bar in locations)

    if quality(ink) >= 1.0:
        return ink
    opaque = Rgba(ink.r, ink.g, ink.b)
    if quality(opaque) >= 1.0:
        low, high = ink.a, 255
        while low < high:
            middle = (low + high) // 2
            if quality(Rgba(ink.r, ink.g, ink.b, middle)) >= 1.0:
                high = middle
            else:
                low = middle + 1
        return Rgba(ink.r, ink.g, ink.b, low)

    # The same text can sit above both black and white desktops. An unconstrained
    # worst-case solver can turn authored white-on-dark ink into a mid-grey (or
    # dark ink into light grey) just to balance those extreme samples. Preserve
    # whichever polarity the authored ink already supports most strongly.
    luminances = [(relative_luminance(surface), bar) for surface, bar in locations]
    ink_luminance = relative_luminance(opaque)
    reference_luminance = max(
        luminances,
        key=lambda entry: (max(ink_luminance, entry[0]) + .05)
                          / (min(ink_luminance, entry[0]) + .05),
    )[0]
    pole = 255 if ink_luminance >= reference_luminance else 0
    def opaque_quality(candidate):
        light = relative_luminance(candidate)
        return min(((max(light, background) + .05) / (min(light, background) + .05)) / bar
                   for background, bar in luminances)

    # Retain useful corrections for truly light/dark surfaces, without ever
    # crossing to the opposite foreground polarity. No surface fills are edited.
    for amount in range(1, 256):
        candidate = Rgba(*(round(channel + (pole - channel) * amount / 255)
                           for channel in (ink.r, ink.g, ink.b)))
        if opaque_quality(candidate) >= 1.0:
            return candidate
    # If the requested contrast cannot coexist with the theme's ink polarity,
    # return its authored RGB at full alpha. The background owner, not an
    # unintended text recolouring, must resolve any remaining contrast failure.
    return opaque


def project_settings_composition(theme, adjustment):
    """One finite derived colour/native map per immutable theme and override."""
    raw = theme.colors
    native_raw = theme.backdrop.native_tint()
    mode = theme.backdrop.mode
    if mode == "off" and adjustment == 0:
        return _state_inks(raw, dict(raw), native_raw)
    native = native_raw
    if native_raw is not None:
        dark = (.2126 * native_raw.r + .7152 * native_raw.g + .0722 * native_raw.b) < 128
        alpha = max(1, round(255 * settings_surface_density(mode, native_raw.a / 255,
                                                           dark_surface=dark, adjustment=adjustment)))
        native = Rgba(native_raw.r, native_raw.g, native_raw.b, alpha)
    colors = dict(raw)
    for role, color in raw.items():
        if not is_surface_role(role) or color.a == 0:
            continue
        dark = (.2126 * color.r + .7152 * color.g + .0722 * color.b) < 128
        parents = NEUTRAL_SURFACE_PARENTS.get(role)
        if parents is None:
            alpha = settings_surface_density(mode, color.a / 255, dark_surface=dark, adjustment=adjustment)
        else:
            # Resolve parent overlays first, regardless of authored map order.
            continue
        colors[role] = Rgba(color.r, color.g, color.b, round(255 * alpha))
    for role, parents in NEUTRAL_SURFACE_PARENTS.items():
        if role not in raw or any(parent not in raw for parent in parents):
            continue
        color = raw[role]
        if color.a == 0:
            continue
        dark = (.2126 * color.r + .7152 * color.g + .0722 * color.b) < 128
        target = settings_surface_density(mode, _density(native_raw, raw, (*parents, role)),
                                          dark_surface=dark, adjustment=adjustment)
        parent_density = _density(native, colors, parents)
        alpha = 0.0 if parent_density >= 1.0 else (target - parent_density) / (1.0 - parent_density)
        colors[role] = Rgba(color.r, color.g, color.b, round(255 * max(0.0, min(1.0, alpha))))
    locations = defaultdict(list)
    for role, stack, large in SETTINGS_TEXT_STACKS:
        if role not in raw or any(layer not in raw for layer in stack):
            continue
        # These actual shared styles render faint 10–11px runs; reserve only
        # the ink headroom needed by native core-glyph antialiasing evidence.
        minimum = 4.8 if role in ("text.tertiary", "text.helper") else 3.0 if large else 4.5
        for pole in (0, 255):
            locations[role].append((_surface(native, colors, stack, pole), minimum))
    for role, surfaces in locations.items():
        colors[role] = _correct_ink(raw[role], surfaces)
    return _state_inks(raw, colors, native)

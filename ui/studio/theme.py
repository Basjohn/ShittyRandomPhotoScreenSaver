"""Studio chrome colours, derived entirely from the active SRPSS Settings theme.

The Settings window composes translucent semantic surfaces over a native backdrop.
Every Studio surface token is composited over an opaque base taken from the theme's
own backdrop tint (so contrast is checked against a known colour); under a Glass or
Acrylic theme the Studio window takes the same native backdrop as Settings and the
window surface, title bar and large panels then let it through (``panelAlpha``). Off Windows there is no native
material: the window surface is composed over Settings' opaque material underlay instead. The accent is the theme's
most saturated interaction colour (slider fill, focus, selection, outer border).
Contrast is enforced after derivation (text >= 4.5:1 on surfaces, accent and
outlines >= 3:1 / 1.6:1), so any theme stays legible. Scene colours never pass
through here: a theme change cannot recolour any authored scene colour or material.
"""
from __future__ import annotations

import colorsys
from typing import Callable

RGB = tuple[float, float, float]
# Settings' panel shadow offsets (6, 8) fill the Studio's 10 px gutters; half fits and still reads.
SHADOW_SCALE = 0.5
# The least opacity a large Studio panel keeps over Glass/Acrylic.
PANEL_MATERIAL_FLOOR = 0.58


def _rgb(colour) -> tuple[RGB, float]:
    r, g, b, a = colour.as_tuple()
    return (r / 255.0, g / 255.0, b / 255.0), a / 255.0


def _over(top: RGB, alpha: float, base: RGB) -> RGB:
    return tuple(t * alpha + b * (1.0 - alpha) for t, b in zip(top, base))


def _mix(a: RGB, b: RGB, share_b: float) -> RGB:
    return tuple(x * (1.0 - share_b) + y * share_b for x, y in zip(a, b))


def _luminance(c: RGB) -> float:
    lin = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def contrast(a: RGB, b: RGB) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


def _ensure_on_surfaces(colour: RGB, backgrounds, minimum: float, light_theme: bool) -> RGB:
    """Smallest 8-bit hue-preserving ink movement across actual finite surfaces."""
    def admitted(candidate):
        return tuple(round(channel*255)/255 for channel in candidate)
    def quality(candidate):
        return min(contrast(candidate, surface) for surface in backgrounds)
    original = admitted(colour)
    target = minimum + .06  # emitted 8-bit ink and surface-alpha quantization
    if quality(original) >= target:
        return original
    candidates = []
    best, best_score = original, quality(original)
    poles = ((0.,0.,0.), (1.,1.,1.)) if light_theme else ((1.,1.,1.), (0.,0.,0.))
    for pole in poles:
        for step in range(1, 256):
            candidate = admitted(_mix(colour, pole, step/255))
            score = quality(candidate)
            if score > best_score:
                best, best_score = candidate, score
            if score >= target:
                distance = sum((a-b)**2 for a,b in zip(candidate, original))
                candidates.append((distance, candidate))
                break
    return min(candidates, key=lambda entry: entry[0])[1] if candidates else best


def _ensure(colour: RGB, against: RGB, minimum: float, light_theme: bool) -> RGB:
    """Preserve the existing opaque-palette derivation and quantized headroom."""
    pole = (0.,0.,0.) if light_theme else (1.,1.,1.)
    out = colour
    for step in range(1, 21):
        quantized = tuple(round(channel*255)/255 for channel in out)
        if contrast(quantized, against) >= minimum + .06:
            return quantized
        out = _mix(colour, pole, step/20)
    return out


def _hex(c: RGB, alpha: float = 1.0) -> str:
    r, g, b = (max(0, min(255, round(v * 255))) for v in c)
    return "#%02x%02x%02x" % (r, g, b) if alpha >= 1.0 else "#%02x%02x%02x%02x" % (round(alpha * 255), r, g, b)


def _readable_alpha(colour: RGB, alpha: float, backgrounds, inks) -> float:
    """Smallest chrome density carrying its inks over either desktop pole."""
    def readable(amount):
        return all(contrast(ink, _over(colour, amount, base)) >= minimum + .03
                   for base in backgrounds for ink, minimum in inks)

    if readable(alpha) or not readable(1.0):
        return alpha
    low, high = alpha, 1.0
    for _ in range(9):
        middle = (low + high) * .5
        if readable(middle):
            high = middle
        else:
            low = middle
    return high


def _saturation(c: RGB) -> float:
    return colorsys.rgb_to_hls(*c)[2]


def studio_theme(theme=None) -> dict[str, str]:
    from ui.settings_theme_runtime import get_active_settings_theme
    from ui.theme_semantics import settings_theme_is_light
    theme = theme or get_active_settings_theme()
    light = settings_theme_is_light(theme)

    def token(name: str, fallback: tuple[int, int, int, int]) -> tuple[RGB, float]:
        try:
            return _rgb(theme.color(name))
        except KeyError:
            r, g, b, a = fallback
            return (r / 255, g / 255, b / 255), a / 255

    tint, _ = _rgb(theme.backdrop.tint)
    # Opaque base: the theme's backdrop tint, pushed toward its polarity so translucent surfaces read.
    pole = (1.0, 1.0, 1.0) if light else (0.0, 0.0, 0.0)
    primary = token("text.primary", (255, 255, 255, 255))[0]
    # Opaque base: the backdrop tint pushed toward the theme's polarity, further when needed so the
    # theme's own primary text keeps 4.5:1 on its composited panels (glass themes rely on a backdrop).
    for depth in (.35, .5, .62, .74, .85, .93):
        base = _mix(tint, pole, depth)
        panel_colour, panel_alpha = token("panel.group.surface", (60, 60, 60, 120))
        if contrast(primary, _over(panel_colour, panel_alpha, base)) >= 4.5:
            break

    def surface(name: str, fallback=(60, 60, 60, 120), over: RGB | None = None) -> RGB:
        colour, alpha = token(name, fallback)
        return _over(colour, alpha, over or base)

    bg = base
    panel = surface("panel.group.surface")
    raised = surface("control.button.surface", over=panel)
    header = surface("window.titlebar.surface")
    text = _ensure(token("text.primary", (255, 255, 255, 255))[0], panel, 4.5, light)
    dim = _ensure(token("text.secondary", (170, 170, 170, 255))[0], panel, 3.0, light)
    disabled = token("text.disabled", (102, 102, 102, 255))[0]
    border = token("panel.border", (255, 255, 255, 255))[0]
    outline = _ensure(_mix(panel, border, .32), panel, 1.6, light)
    outline_soft = _mix(panel, border, .14)

    candidates: list[RGB] = []
    for name in ("popup.input.focus_border", "control.list.selected_accent", "chrome.outer_border",
                 "bucket.open.border", "control.mode.checked_surface", "navigation.tab.selected_surface"):
        try:
            candidates.append(_rgb(theme.color(name))[0])
        except KeyError:
            pass
    for name in ("slider.fill.surface", "slider.handle.active_surface"):
        try:
            candidates.extend(_rgb(stop.color)[0] for stop in theme.gradient(name).stops)
        except KeyError:
            pass
    candidates.append(tint)
    accent = max(candidates, key=_saturation) if candidates else text
    if _saturation(accent) < .2:
        accent = _mix(text, panel, .15)            # a monochrome theme gets a monochrome Studio
    accent = _ensure(accent, panel, 3.0, light)
    accent_soft = _mix(panel, accent, .28)
    # Selected chips/tabs carry text on accent_soft: pick the most readable text, then settle the surface.
    accent_text = max((text, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0)), key=lambda c: contrast(c, accent_soft))
    away = (0.0, 0.0, 0.0) if _luminance(accent_text) > .5 else (1.0, 1.0, 1.0)
    for step in range(1, 21):
        if contrast(accent_text, accent_soft) >= 4.5:
            break
        accent_soft = _mix(_mix(panel, accent, .28), away, step / 20.0)
    focus = _ensure(token("popup.input.focus_border", (106, 169, 217, 255))[0], panel, 3.0, light)
    track = _mix(panel, text, .14)
    input_surface = surface("control.input.surface", over=panel)
    viewport = _mix(bg, (0.0, 0.0, 0.0), .65)
    # Every instrument well uses the theme's input surface. The viewport's fixed
    # backing is reserved for authored scene pixels. Check text and trace inks here.
    well = input_surface
    well_light = contrast(well, (0.0, 0.0, 0.0)) > contrast(well, (1.0, 1.0, 1.0))   # inks move away from it
    well_text = _ensure(text, well, 4.5, well_light)
    well_dim = _ensure(dim, well, 3.0, well_light)
    danger = _ensure(token("popup.icon.error", (255, 100, 100, 255))[0], panel, 3.0, light)

    # Window chrome, as Settings draws it: the theme's native backdrop mode, the title bar roles and the forged
    # window edge (ui/settings_window_edge.py). Normal ("off") keeps every surface opaque, as before. Under
    # Glass/Acrylic the window surface and the title bar take the theme's own translucent roles, and the large
    # panels let the material through at the theme's polarity with an opacity floor (dense instruments sit on
    # them over an arbitrary desktop), their colour the contrast-checked one above.
    mode = str(theme.backdrop.mode)
    translucent = mode != "off"
    titlebar_colour, titlebar_alpha = token("window.titlebar.surface", (12, 12, 12, 209))
    title_text = _ensure(token("window.titlebar.text", (255, 255, 255, 255))[0], header, 4.5, light)

    def role(name: str, fallback, over: RGB) -> str:
        colour, alpha = token(name, fallback)
        return _hex(_over(colour, alpha, over))

    if translucent:
        window_colour, window_alpha = _rgb(theme.window_surface())
        from core import platform_paths
        if platform_paths.IS_WINDOWS:
            window_surface = _hex(window_colour, window_alpha)
        else:
            # No native material off Windows (core/windows/dwm_blur.py is never called there): the window surface
            # is composed over Settings' own opaque material underlay (ui/settings_material_underlay.py), the same
            # stand-in Settings paints for every material, so nothing beneath the window shows through.
            from ui.settings_material_underlay import material_underlay
            underlay = material_underlay(theme)
            window_surface = _hex(_over(window_colour, window_alpha,
                                        (underlay.r / 255.0, underlay.g / 255.0, underlay.b / 255.0)))
        titlebar = _hex(titlebar_colour, titlebar_alpha)
        _panel_colour, panel_alpha = token("panel.group.surface", (60, 60, 60, 120))
        # The retained panel paints above window_surface, which already owns
        # the window/tint density. Start from this child fill's own alpha only.
        panel_alpha = max(PANEL_MATERIAL_FLOOR, panel_alpha)
        chrome_bases = [_over(window_colour, window_alpha, (pole, pole, pole))
                        for pole in (0.0, 1.0)]
        # Resolve ink on intended translucent stacks before considering any
        # body-only density bound. Decorative/control accent never plates a panel.
        def projected_bases(colour, alpha):
            return [_over(colour, alpha, base) for base in chrome_bases]
        def own_alpha(role):
            return max(PANEL_MATERIAL_FLOOR, token(role, (60,60,60,120))[1])
        panel_bases = projected_bases(panel, panel_alpha)
        header_bases = projected_bases(header, own_alpha("window.titlebar.surface"))
        raised_bases = projected_bases(raised, own_alpha("control.button.surface"))
        input_bases = projected_bases(input_surface, own_alpha("control.input.surface"))
        ink_bases = panel_bases + header_bases + raised_bases + input_bases
        solid_ink_bases = (panel, header, raised, input_surface, accent_soft)
        text = _ensure_on_surfaces(text, (*ink_bases, *solid_ink_bases), 4.5, light)
        dim = _ensure_on_surfaces(dim, (*ink_bases, *solid_ink_bases), 3.0, light)
        panel_alpha = _readable_alpha(panel, panel_alpha, chrome_bases, ((text,4.5), (dim,3.0)))
        panel_bases = projected_bases(panel, panel_alpha)
        ink_bases = panel_bases + header_bases + raised_bases + input_bases
        accent = _ensure_on_surfaces(accent, (*ink_bases, *solid_ink_bases), 4.5, light)
        focus = _ensure_on_surfaces(focus, (*ink_bases, *solid_ink_bases), 3.0, light)
        outline = _ensure_on_surfaces(outline, (*panel_bases, panel), 1.6, light)
        well_text = _ensure_on_surfaces(well_text, (*input_bases, well), 4.5, well_light)
        well_dim = _ensure_on_surfaces(well_dim, (*input_bases, well), 3.0, well_light)
        titlebar = _hex(titlebar_colour, _readable_alpha(titlebar_colour, titlebar_alpha,
            chrome_bases, ((title_text, 4.5),)))
    else:
        window_surface = _hex(bg)
        titlebar = _hex(header)
        panel_alpha = 1.0
    if translucent:
        accent_text = max((text, (1.,1.,1.), (0.,0.,0.)), key=lambda ink: contrast(ink, accent))
        accent_text = _ensure(accent_text, accent, 4.5, _luminance(accent) > .5)
        trace_bases = (*panel_bases, *input_bases, well)
        trace2 = _ensure_on_surfaces(_mix(text, panel, .25), trace_bases, 3.0, well_light)
        well_trace2 = trace2
    else:
        # accentText is drawn on the accent fill (the checked box's tick), not on accent_soft, which settled it above.
        # Same ink rule as the cards (Card_Surface_Materials.md, M2b): an ink that misses its ratio on the fill it sits
        # on corrects itself away from that fill; an ink that reads keeps its value byte for byte.
        if contrast(accent_text, accent) < 4.5:
            accent_on_light = contrast(accent, (0., 0., 0.)) > contrast(accent, (1., 1., 1.))
            accent_text = _ensure(accent_text, accent, 4.5, accent_on_light)
        trace2 = _mix(text, panel, .25)
        well_trace2 = _ensure(trace2, well, 3.0, well_light)
    outer_border = token("chrome.outer_border", (255, 255, 255, 255))
    shadow = theme.shadow("panel.group")
    shadow_rgb = (shadow.color.r / 255.0, shadow.color.g / 255.0, shadow.color.b / 255.0)
    # Chrome uses semantic translucent fills instead of baking every region onto the opaque
    # viewport backing. The viewport and its small scene overlays retain their own backing.
    def chrome_surface(name: str, composed: RGB, inks=None, floor: float = PANEL_MATERIAL_FLOOR) -> str:
        if not translucent:
            return _hex(composed)
        _colour, alpha = token(name, (60, 60, 60, 120))
        alpha = _readable_alpha(composed, max(floor, alpha), chrome_bases,
            inks if inks is not None else ((text, 4.5), (dim, 3.0)))
        return _hex(composed, alpha)

    return {
        "backdrop": mode, "windowSurface": window_surface, "titlebar": titlebar,
        "titlebarText": _hex(title_text),
        "titlebarHover": role("window.titlebar.button.hover", (62, 62, 62, 204), header),
        "titlebarPressed": role("window.titlebar.button.pressed", (50, 50, 50, 220), header),
        "closeHover": role("window.titlebar.close.hover", (232, 17, 35, 204), header),
        "outerBorder": _hex(*outer_border),
        "panelAlpha": "%.3f" % panel_alpha,
        # Settings' panel cast (panel.group), scaled to the Studio's tight gutters; hard and static, like Settings'.
        "shadow": _hex(shadow_rgb, shadow.color.a / 255.0),
        "shadowX": "%.2f" % (shadow.offset_x * SHADOW_SCALE), "shadowY": "%.2f" % (shadow.offset_y * SHADOW_SCALE),
        "bg": _hex(bg), "header": chrome_surface("window.titlebar.surface", header),
        "panel": _hex(panel), "panelRaised": chrome_surface("control.button.surface", raised),
        "viewportBg": _hex(viewport), "outline": _hex(outline), "outlineSoft": _hex(outline_soft),
        "accent": _hex(accent), "accentSoft": _hex(accent_soft), "accentText": _hex(accent_text),
        "track": _hex(track), "text": _hex(text), "textDim": _hex(dim), "textDisabled": _hex(disabled),
        "input": chrome_surface("control.input.surface", input_surface), "inputText": _hex(_ensure(text, input_surface, 4.5, light)),
        "focus": _hex(focus), "danger": _hex(danger), "light": "true" if light else "false",
        "trace1": _hex(accent), "trace2": _hex(trace2), "trace3": _hex(focus),
        "well": chrome_surface("control.input.surface", well, ((well_text, 4.5), (well_dim, 3.0))), "wellText": _hex(well_text), "wellDim": _hex(well_dim),
        "wellTrace1": _hex(_ensure(accent, well, 3.0, well_light)),
        "wellTrace2": _hex(well_trace2),
        "wellTrace3": _hex(_ensure(focus, well, 3.0, well_light)),
    }


def subscribe_studio_theme(listener: Callable[[dict[str, str]], None]) -> Callable[[], None]:
    from ui.settings_theme_runtime import subscribe_settings_theme
    return subscribe_settings_theme(lambda theme: listener(studio_theme(theme)))


__all__ = ["contrast", "studio_theme", "subscribe_studio_theme"]

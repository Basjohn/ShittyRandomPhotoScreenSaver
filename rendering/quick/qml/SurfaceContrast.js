.pragma library

// Required reference contrast for the actual steady ink (including its effective
// alpha), evaluated at ink/style edges, never per fragment or per frame.
function luminance(r, g, b) {
    function linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

function _readable(ink, grey, lightInk) {
    var backgroundL = luminance(grey, grey, grey)
    var inkL = luminance(ink.r * ink.a + grey * (1 - ink.a),
                         ink.g * ink.a + grey * (1 - ink.a),
                         ink.b * ink.a + grey * (1 - ink.a))
    var ratio = (Math.max(inkL, backgroundL) + 0.05) / (Math.min(inkL, backgroundL) + 0.05)
    return ratio >= 4.8 // headroom for coloured backgrounds, 8-bit output and material grain
        && (lightInk ? inkL > backgroundL : inkL < backgroundL)
}

function requiredReferenceContrast(reference, ink) {
    var referenceL = luminance(reference.r, reference.g, reference.b)
    var lightInk = 0.2126 * reference.r + 0.7152 * reference.g + 0.0722 * reference.b >= 0.5
    // Dark ink at a faint alpha cannot reach the ratio on any surface (black at 55 % reaches
    // 4.76:1 on white): the panel would saturate to white. That case resolves to the bounded
    // surface (panelCeiling) plus corrected ink (legibleInk), so the panel answers for the
    // full-strength reference ink only. Light ink is unchanged.
    if (!lightInk && !_readable(ink, 1.0, false))
        ink = { "r": reference.r, "g": reference.g, "b": reference.b, "a": 1.0 }
    var low = 0, high = 1
    // The luminance boundary is monotone while we move the neutral surface
    // toward/away from the ink's pole. Twelve steps exceed 8-bit surface precision.
    for (var i = 0; i < 12; ++i) {
        var grey = (low + high) / 2
        var readable = _readable(ink, grey, lightInk)
        if (lightInk ? readable : !readable) low = grey; else high = grey
    }
    var limitL = luminance(lightInk ? low : high, lightInk ? low : high, lightInk ? low : high)
    return lightInk ? (referenceL + 0.05) / (limitL + 0.05)
                    : (limitL + 0.05) / (referenceL + 0.05)
}

function limits(reference, ratio) {
    var encodedInk = 0.2126 * reference.r + 0.7152 * reference.g + 0.0722 * reference.b
    var lightInk = encodedInk >= 0.5
    var referenceL = luminance(reference.r, reference.g, reference.b)
    var limit = lightInk ? (referenceL + 0.05) / ratio - 0.05 : ratio * (referenceL + 0.05) - 0.05
    limit = Math.max(0, Math.min(1, limit))
    var encodedLimit = limit <= 0.0031308 ? limit * 12.92 : 1.055 * Math.pow(limit, 1 / 2.4) - 0.055
    // The accepted dense-panel recipe is an encoded tone anchor. It is not the
    // WCAG floor; the actual ink's linear-light limit occupies the other fields.
    var anchor = lightInk ? (encodedInk + 0.05) / 7 - 0.05 : 7 * (encodedInk + 0.05) - 0.05
    return [anchor, lightInk ? 1 : 0, limit, encodedLimit]
}

// ---------------------------------------------------------------- bounded surface (dark ink)

// The Settings variant's material calibration of combined surface density
// (core/settings/surface_opacity.py SETTINGS_DENSITY_BASELINE / settings_surface_density;
// tests/test_surface_materials.py keeps the two tables equal).
var SETTINGS_DENSITY_BASELINE = { "acrylic": -0.10, "frosted": -0.20, "mica": -0.20, "glass": 0.10,
                                  "smoked": -0.10 }

function adjustedDensity(density, amount) {
    density = Math.max(0, Math.min(1, density))
    amount = Math.max(-1, Math.min(1, isFinite(amount) ? amount : 0))
    return amount < 0 ? density * (1 + amount) : density + (1 - density) * amount
}

function _encodedLuma(c) { return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] }
function _linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
function _encoded(v) {
    v = Math.max(0, v)
    return v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(v, 1 / 2.4) - 0.055
}
function _mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t] }
function _term(value, adjustment) { return value > 0 ? adjustedDensity(value, adjustment) : 0 }

// The theme's Settings-variant shell density for this card: the authored surface alpha under
// the Settings calibration of its material, then the Widget Opacity Adjust.
function shellDensity(material, tint, adjustment) {
    var darkSurface = _encodedLuma([tint.r, tint.g, tint.b]) < 0.5
    var baseline = material === "smoked" && !darkSurface ? 0 : (SETTINGS_DENSITY_BASELINE[material] || 0)
    return adjustedDensity(adjustedDensity(tint.a, baseline), adjustment)
}

// Fraction of the backdrop's luminance swing the material terms (pull, haze, smoke, tint) keep,
// before any legibility panel (the shader's surfaceAt up to its tint mix).
function materialTransmission(params, tint, adjustment) {
    var tintOpacity = params[0].y + (params[0].z - params[0].y) * Math.max(0, Math.min(1, tint.a))
    return (1 - _term(params[1].x, adjustment)) * (1 - _term(params[1].z, adjustment))
        * (1 - _term(params[1].w, adjustment)) * (1 - adjustedDensity(tintOpacity, adjustment))
}

// The panel interior over a uniform grey backdrop: surfaceAt's colour terms (no rim), each at
// its worst for the card's ink, in the shader's order: for dark ink the grain at its darkest
// (the Glass sheen only lightens, so it is left out); for light ink the face's sheen at its
// brightest before the legibility layer (whose guard then bounds it, as in the shader) and the
// grain at its lightest after it.
function _panelOver(grey, params, tint, panelLimits, ceiling, adjustment, applyPanel) {
    var t = [tint.r, tint.g, tint.b]
    var c = [grey, grey, grey]
    var lightInk = panelLimits[1] > 0.5
    var pull = _term(params[1].x, adjustment)
    var shift = (_encodedLuma(t) - grey) * pull
    c = [c[0] + shift, c[1] + shift, c[2] + shift]
    c = _mix(c, [1, 1, 1], _term(params[1].z, adjustment))
    var keep = 1 - _term(params[1].w, adjustment)
    c = [c[0] * keep, c[1] * keep, c[2] * keep]
    var tintOpacity = params[0].y + (params[0].z - params[0].y) * Math.max(0, Math.min(1, tint.a))
    c = _mix(c, t, adjustedDensity(tintOpacity, adjustment))
    if (!applyPanel)
        return c
    if (lightInk && params[2].x > 0) {
        var sheen = params[2].x * 0.10
        c = [c[0] + sheen, c[1] + sheen, c[2] + sheen]
    }
    var unplated = c
    var anchor = panelLimits[0]
    var currentL = _encodedLuma(c)
    var dense = c
    if (lightInk && currentL > anchor && currentL > 0)
        dense = [c[0] * Math.max(anchor, 0) / currentL, c[1] * Math.max(anchor, 0) / currentL,
                 c[2] * Math.max(anchor, 0) / currentL]
    else if (!lightInk && currentL < anchor)
        dense = _mix(c, [1, 1, 1], Math.max(0, Math.min(1, (anchor - currentL) / Math.max(1 - currentL, 1e-3))))
    var relief = 1 - adjustedDensity(1 - params[2].z, adjustment)
    c = _mix(dense, c, relief)
    var clamped = [Math.max(0, Math.min(1, c[0])), Math.max(0, Math.min(1, c[1])), Math.max(0, Math.min(1, c[2]))]
    var mayNeedGuard = lightInk ? Math.max(c[0], c[1], c[2]) > panelLimits[3]
                                : Math.min(c[0], c[1], c[2]) < panelLimits[3]
    if (mayNeedGuard) {
        var lin = [_linear(clamped[0]), _linear(clamped[1]), _linear(clamped[2])]
        var cl = _encodedLuma(lin)
        if (lightInk && cl > panelLimits[2] && cl > 0)
            c = [_encoded(lin[0] * panelLimits[2] / cl), _encoded(lin[1] * panelLimits[2] / cl),
                 _encoded(lin[2] * panelLimits[2] / cl)]
        else if (!lightInk && cl < panelLimits[2]) {
            lin = _mix(lin, [1, 1, 1], Math.max(0, Math.min(1, (panelLimits[2] - cl) / Math.max(1 - cl, 1e-3))))
            c = [_encoded(lin[0]), _encoded(lin[1]), _encoded(lin[2])]
        }
    }
    var grain = 0.5 * params[1].y
    if (!lightInk) {
        var bound = _mix(unplated, [1, 1, 1], ceiling)
        c = [Math.min(c[0], bound[0]), Math.min(c[1], bound[1]), Math.min(c[2], bound[2])]
        c = [c[0] - grain, c[1] - grain, c[2] - grain]
    } else {
        c = [c[0] + grain, c[1] + grain, c[2] + grain]
    }
    return [Math.max(0, Math.min(1, c[0])), Math.max(0, Math.min(1, c[1])), Math.max(0, Math.min(1, c[2]))]
}

// The dark-ink panel's furthest move toward its anchor (a lift toward white, 0..1): only as far
// as the Settings-variant shell density (the card's total density then equals the shell's), but
// never less than the full-strength reference ink needs over a black backdrop. Light ink: 1
// (unused; the shader applies the ceiling to dark ink only).
function panelCeiling(material, params, tint, panelLimits, adjustment) {
    if (panelLimits[1] > 0.5)
        return 1.0
    var transmission = materialTransmission(params, tint, adjustment)
    var shell = transmission > 1e-4
        ? Math.max(0, Math.min(1, 1 - (1 - shellDensity(material, tint, adjustment)) / transmission)) : 0
    var black = _panelOver(0, params, tint, panelLimits, 1, adjustment, false)
    var grain = 0.5 * params[1].y        // the static grain at its darkest
    function reads(lift) {
        var c = _mix(black, [1, 1, 1], lift)
        return luminance(Math.max(0, c[0] - grain), Math.max(0, c[1] - grain), Math.max(0, c[2] - grain))
            >= panelLimits[2]
    }
    var low = 0, high = 1
    if (reads(0))
        high = 0
    for (var i = 0; high > 0 && i < 14; ++i) {
        var lift = (low + high) / 2
        if (reads(lift)) high = lift; else low = lift
    }
    return Math.max(shell, high)
}

// The composed panel over a black and a white backdrop: every wallpaper lies between the
// two (compositing is affine in the backdrop), as the Settings ink check's desktop poles.
function inkPoles(params, tint, panelLimits, ceiling, adjustment) {
    return [_panelOver(0, params, tint, panelLimits, ceiling, adjustment, true),
            _panelOver(1, params, tint, panelLimits, ceiling, adjustment, true)]
}

function _contrast(a, b) {
    var la = luminance(a[0], a[1], a[2]), lb = luminance(b[0], b[1], b[2])
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

// WCAG contrast of a straight-alpha run composited over bg (the legibility row's contrastOver).
function _contrastOver(bg, run) {
    return _contrast(_mix(bg, [run.r, run.g, run.b], run.a), bg)
}

// The legibility row's overlay toward its pole for one run colour over c (text_legibility's
// overlayFor, the same 10 % margin): 0 when c already meets the floor or the pole cannot.
function _rowOverlayFor(c, run, ratio, lift) {
    var pole = lift ? [1, 1, 1] : [0, 0, 0]
    if (run.a < 1 && _contrastOver(pole, run) < ratio)
        run = { "r": run.r, "g": run.g, "b": run.b, "a": 1 }
    if (_contrastOver(c, run) >= ratio || _contrastOver(pole, run) < ratio)
        return 0
    var lo = 0, hi = 1
    for (var i = 0; i < 12; ++i) {
        var mid = (lo + hi) / 2
        if (_contrastOver(_mix(c, pole, mid), run) >= ratio) hi = mid; else lo = mid
    }
    return hi
}

// The poles as a run sitting on a further fill sees them (a metric panel, a tile, a capsule
// between the run and its card). `underlay` is that fill (a colour, straight alpha) or
// {color, rowColors, rowFloor}: the fill plus the LegibilityRow on it, which lifts the surface
// until each of its run colours holds its floor (TextLegibilityPlate, text_legibility.vert:
// side from the row's mean against its primary run, 10 % margin). The fill is composited over
// each pole, then that row's lift is applied as the shader applies it. A transparent or absent
// underlay leaves the card's own poles.
function underlaidPoles(poles, underlay) {
    if (!underlay)
        return poles
    var fill = underlay.color !== undefined ? underlay.color : underlay
    var rowColors = underlay.rowColors || []
    var ratio = (underlay.rowFloor || 4.5) * 1.10
    if (!(fill.a > 0) && rowColors.length === 0)
        return poles
    var result = []
    for (var i = 0; i < poles.length; ++i) {
        var c = fill.a > 0 ? _mix(poles[i], [fill.r, fill.g, fill.b], Math.min(1, fill.a)) : poles[i]
        if (rowColors.length > 0) {
            var surfaceL = luminance(c[0], c[1], c[2])
            var primary = rowColors[0]
            var runL = luminance(primary.r, primary.g, primary.b)
            var lift = surfaceL >= runL ? ratio * (runL + 0.05) - 0.05 <= 1.0 : (runL + 0.05) / ratio - 0.05 < 0.0
            var amount = 0
            for (var k = 0; k < rowColors.length; ++k)
                amount = Math.max(amount, _rowOverlayFor(c, rowColors[k], ratio, lift))
            c = _mix(c, lift ? [1, 1, 1] : [0, 0, 0], amount)
        }
        result.push(c)
    }
    return result
}

// A text run's ink on its card's composed panel, corrected the way the Settings variant
// corrects semantic ink (ui/settings_surface_composition.py _correct_ink), on every theme:
// judged at its real alpha (colour alpha x the run's opacity) over both poles (through the
// fill the run sits on, `underlay`, when it sits on one); kept when it reads, else its alpha
// rises, else it moves toward the card's ink pole keeping its hue (darker toward black on a
// light panel, lighter toward white on a dark one). Returns [r, g, b, a, reachable] (straight
// alpha, colour only: the run's own opacity stays). When even the pole at the run's own
// opacity cannot read (an item-opacity fade), the result is the pole and reachable is false:
// the run then takes a text-local plate (ShadowedText). small: 4.8:1 (4.5 plus the solver's
// headroom), else 3.2:1. lightInk: the card's ink pole.
function legibleInk(ink, opacity, poles, small, lightInk, underlay) {
    var ratio = small ? 4.8 : 3.2
    poles = underlaidPoles(poles, underlay)
    opacity = Math.max(0, Math.min(1, opacity))
    function quality(rgb, alpha) {
        var worst = Infinity
        for (var i = 0; i < poles.length; ++i) {
            var pole = poles[i]
            worst = Math.min(worst, _contrast(_mix(pole, rgb, alpha), pole) / ratio)
        }
        return worst
    }
    var rgb = [ink.r, ink.g, ink.b]
    if (quality(rgb, ink.a * opacity) >= 1)
        return [ink.r, ink.g, ink.b, ink.a, true]
    if (quality(rgb, opacity) >= 1) {
        var low = ink.a, high = 1
        for (var step = 0; step < 12; ++step) {
            var middle = (low + high) / 2
            if (quality(rgb, middle * opacity) >= 1) high = middle; else low = middle
        }
        return [ink.r, ink.g, ink.b, high, true]
    }
    var pole = lightInk ? [1, 1, 1] : [0, 0, 0]
    if (quality(pole, opacity) < 1)
        return [pole[0], pole[1], pole[2], 1, false]
    var low = 0, high = 1              // how far the authored channels move toward the pole
    for (var i = 0; i < 12; ++i) {
        var amount = (low + high) / 2
        if (quality(_mix(rgb, pole, amount), opacity) >= 1) high = amount; else low = amount
    }
    var moved = _mix(rgb, pole, high)
    return [moved[0], moved[1], moved[2], 1, true]
}

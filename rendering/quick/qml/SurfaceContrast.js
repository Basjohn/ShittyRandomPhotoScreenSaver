.pragma library

// Required reference contrast for the actual steady ink (including its effective
// alpha), evaluated at ink/style edges, never per fragment or per frame.
function luminance(r, g, b) {
    function linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

function requiredReferenceContrast(reference, ink) {
    var referenceL = luminance(reference.r, reference.g, reference.b)
    var lightInk = 0.2126 * reference.r + 0.7152 * reference.g + 0.0722 * reference.b >= 0.5
    var low = 0, high = 1
    // The luminance boundary is monotone while we move the neutral surface
    // toward/away from the ink's pole. Twelve steps exceed 8-bit surface precision.
    for (var i = 0; i < 12; ++i) {
        var grey = (low + high) / 2
        var backgroundL = luminance(grey, grey, grey)
        var inkL = luminance(ink.r * ink.a + grey * (1 - ink.a),
                             ink.g * ink.a + grey * (1 - ink.a),
                             ink.b * ink.a + grey * (1 - ink.a))
        var ratio = (Math.max(inkL, backgroundL) + 0.05) / (Math.min(inkL, backgroundL) + 0.05)
        var readable = ratio >= 4.8 // headroom for coloured backgrounds, 8-bit output and material grain
            && (lightInk ? inkL > backgroundL : inkL < backgroundL)
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

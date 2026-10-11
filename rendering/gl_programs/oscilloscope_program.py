"""Oscilloscope: trace building, reaction rules and shaders (loaded only when the mode runs).

The mode draws the audio itself, as an analog scope's beam would. The capture keeps a contiguous
history of the newest samples while Oscilloscope is active (``BeatEngine.get_waveform_history``);
each logical frame turns it into one trace of ``TRACE_POINTS`` points in the content's unit square
(-1..1 both ways, y up):

- **Trace**: ``span`` of audio after a rising zero crossing of the smoothed signal (the trigger),
  chosen among the recent crossings as the one whose shape best continues the previous trace, so a
  steady tone stands still and music scrolls only as much as it changes. Longer spans than the trace
  has points are drawn as each bin's low and high (in the order they happened), the envelope a scope
  shows of dense audio, never an aliased subsample.
- **Ring**: the same trace wrapped clockwise around a circle from the top; its ends ease to the
  circle so the seam closes.
- **Phase**: the signal against itself ``delay`` later, turned 45 degrees: the swirling figures of
  an X/Y scope (a pure tone draws an ellipse, a chord a knot, noise a cloud).

Amplitude is the audio's own on a fixed scale: ``gain`` times the DC-free signal, softly limited by
tanh. Nothing is learned from the track (``Docs/Guides/Visualizer_Reactivity_Authoring.md`` 2A).

Reactions follow the shared musical rule in ``transient_bus``: the beam's **drive** (how brightly
it burns and glows) is the passage's share (``passage_ramp``) of how much the moment counts
(``musical_weight``), eased up quickly and down gently; each musical **onset** fires a flare
(``flare_strength``: its weight and emphasis on the fixed loudness scale times the passage's
share), which thickens and brightens the beam and decays over ``FLARE_DECAY`` seconds. The tone
(how bright the music sounds) is the centroid of the pre-AGC analysis spectrum, eased; the renderer
may tint the beam by it.

**Afterglow** keeps earlier traces (one per ``GHOST_INTERVAL``, at most ``GHOST_CAPACITY``) that
fade on the logical clock, so the phosphor's persistence is authored state, never render history.

The renderer draws every trace in one instanced pass: each segment a quad around it whose fragment
measures the distance to the segment (an anti-aliased beam of the authored width), dimmer where the
beam moved faster when Analog Beam is up (a real CRT's writing speed), with a white-hot centre.
Overlapping segments and traces combine by their maximum, so joints never bead; the beam's light goes
to the emission attachment and the shared bloom spreads it into the glow.
"""

from __future__ import annotations

import math

import numpy as np

from widgets.spotify_visualizer.transient_bus import musical_emphasis, musical_weight, passage_ramp

SAMPLE_RATE = 48000              # capture's rate (audio_worker opens 48 kHz)
TRACE_POINTS = 384               # points per trace (low/high pairs of 192 bins for a long span)
GHOST_INTERVAL = 1.0 / 45.0      # seconds between kept afterglow traces
GHOST_CAPACITY = 15              # afterglow traces held (plus the live one)
MAX_TRACES = GHOST_CAPACITY + 1
TRIGGER_CANDIDATES = 12          # recent rising crossings the trigger compares
TEMPLATE_POINTS = 48             # samples of a trace the trigger compares with the previous one
SMOOTH_SAMPLES = 8               # the trigger's smoothing (samples): crossings of the low end
MAX_SMOOTHING = 32               # the drawn audio's widest moving average (samples at 48 kHz)
PHASE_MAX_STRETCH = 6.0          # how far the Phase figure's narrow axis may be widened
RING_RADIUS = 0.6                # the ring's rest radius (share of the half extent)
RING_SWING = 0.34                # how far the signal swings it in and out
RING_SEAM = 0.06                 # share of the ring over which each end eases to the circle
PHASE_SCALE = 0.82               # the phase figure's size at full signal
DRIVE_RISE = 0.08                # seconds: the drive's rise
DRIVE_FALL = 0.7                 # and its gentle fall
DRIVE_QUIET_SHARE = 0.3          # the drive's share in the track's quietest passage
FLARE_DECAY = 0.3                # seconds for a flare to fall to 1/e
FLARE_RISE = 0.03                # seconds: its rise toward a hit
FLARE_MAX_AGE = 0.5              # an onset taken later than this after it happened flares nothing
FLARE_QUIET_SHARE = 0.45
FLARE_MAX = 1.6
TONE_EASE = 0.35                 # seconds: the tone's easing
AFTERGLOW_MIN_S = 0.035          # the persistence time constant at Afterglow 0+ and its range
AFTERGLOW_RANGE_S = 0.3


def smoothing_samples(detail: float, rate: int = SAMPLE_RATE) -> int:
    """The drawn audio's moving-average width for Detail 0..1: about 1.5 kHz at 0 (flowing waves),
    every sample at 1 (the hiss of cymbals and breath)."""
    width = 1.0 + (1.0 - max(0.0, min(1.0, float(detail)))) ** 1.5 * (MAX_SMOOTHING - 1)
    return max(1, int(round(width * rate / SAMPLE_RATE)))


def condition(samples, gain: float, smoothing: int = 1) -> np.ndarray:
    """DC-free samples, averaged over ``smoothing`` samples (``smoothing_samples``), at ``gain``,
    softly limited to -1..1 (a fixed scale)."""
    signal = np.asarray(samples, dtype=np.float32)
    if signal.size == 0:
        return signal
    signal = signal - np.float32(signal.mean())
    if smoothing > 1 and signal.size > smoothing:
        signal = np.convolve(signal, np.full(smoothing, 1.0 / smoothing, dtype=np.float32), mode="same")
    return np.tanh(signal * np.float32(gain))


def _smoothed(signal: np.ndarray) -> np.ndarray:
    kernel = np.full(SMOOTH_SAMPLES, 1.0 / SMOOTH_SAMPLES, dtype=np.float32)
    return np.convolve(signal, kernel, mode="same")


def _template_positions(window: int) -> np.ndarray:
    return (np.arange(TEMPLATE_POINTS) * (window / TEMPLATE_POINTS)).astype(np.int64)


def trace_template(signal: np.ndarray, start: int, window: int) -> np.ndarray:
    """The trace's coarse shape the next frame's trigger matches."""
    return signal[start + _template_positions(window)]


def trigger_start(signal: np.ndarray, window: int, previous: np.ndarray | None) -> int:
    """Where a ``window``-sample trace starts: a recent rising zero crossing of the smoothed
    signal with ``window`` samples after it, the one that best continues ``previous`` (a
    ``trace_template``), slightly favouring the newest; the newest window when none crosses."""
    count = signal.size
    newest = max(0, count - window)
    if count <= window + 2:
        return newest
    search = min(newest - 1, max(window // 2, 512))
    low = newest - search
    smooth = _smoothed(signal[low - 1:newest + 1])
    rising = np.nonzero((smooth[:-1] < 0.0) & (smooth[1:] >= 0.0))[0] + low
    rising = rising[rising <= newest]
    if rising.size == 0:
        return newest
    candidates = rising[-TRIGGER_CANDIDATES:]
    if previous is None or previous.size != TEMPLATE_POINTS:
        return int(candidates[-1])
    shapes = signal[candidates[:, None] + _template_positions(window)[None, :]]
    error = np.abs(shapes - previous[None, :]).mean(axis=1)
    error += 0.02 * (candidates[-1] - candidates) / max(1, window)
    return int(candidates[int(np.argmin(error))])


def _envelope(segment: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(x 0..1, y) of ``TRACE_POINTS`` points along ``segment``."""
    count = segment.size
    if count <= TRACE_POINTS:
        x = np.linspace(0.0, 1.0, TRACE_POINTS, dtype=np.float32)
        y = np.interp(x * (count - 1), np.arange(count, dtype=np.float32), segment).astype(np.float32)
        return x, y
    bins = TRACE_POINTS // 2
    edges = np.linspace(0, count, bins + 1).astype(np.int64)
    lows = np.minimum.reduceat(segment, edges[:-1])
    highs = np.maximum.reduceat(segment, edges[:-1])
    rising = segment[edges[1:] - 1] >= segment[edges[:-1]]
    y = np.empty(TRACE_POINTS, dtype=np.float32)
    y[0::2] = np.where(rising, lows, highs)
    y[1::2] = np.where(rising, highs, lows)
    width = (edges[1:] - edges[:-1]).astype(np.float32)
    x = np.empty(TRACE_POINTS, dtype=np.float32)
    x[0::2] = (edges[:-1] + 0.25 * width) / count
    x[1::2] = (edges[:-1] + 0.75 * width) / count
    return x, y


def _bin_means(segment: np.ndarray) -> np.ndarray:
    count = segment.size
    if count <= TRACE_POINTS:
        x = np.linspace(0.0, count - 1, TRACE_POINTS, dtype=np.float32)
        return np.interp(x, np.arange(count, dtype=np.float32), segment).astype(np.float32)
    edges = np.linspace(0, count, TRACE_POINTS + 1).astype(np.int64)
    sums = np.add.reduceat(segment, edges[:-1])
    return (sums / (edges[1:] - edges[:-1])).astype(np.float32)


def trace_points(display: str, signal: np.ndarray, start: int, window: int) -> np.ndarray:
    """The Trace or Ring display's points (``TRACE_POINTS`` x 2, float32) for ``window`` samples
    of ``signal`` from ``start``."""
    x, y = _envelope(signal[start:start + window])
    if display == "Ring":
        t = np.minimum(x, 1.0 - x) / RING_SEAM
        ease = np.where(t < 1.0, t * t * (3.0 - 2.0 * t), 1.0).astype(np.float32)
        radius = RING_RADIUS + RING_SWING * y * ease
        angle = 0.5 * math.pi - x * (2.0 * math.pi)
        return np.stack((radius * np.cos(angle), radius * np.sin(angle)), axis=1).astype(np.float32)
    return np.stack((x * 2.0 - 1.0, y), axis=1).astype(np.float32)


def phase_points(signal: np.ndarray, window: int, delay: int) -> np.ndarray:
    """The Phase display's points: the newest ``window`` samples against themselves ``delay``
    later, averaged into ``TRACE_POINTS`` bins and turned 45 degrees."""
    count = signal.size
    delay = max(1, min(int(delay), max(1, count // 4)))
    window = max(2, min(int(window), count - delay))
    start = count - window - delay
    a = _bin_means(signal[start:start + window])
    b = _bin_means(signal[start + delay:start + delay + window])
    scale = PHASE_SCALE / math.sqrt(2.0)
    difference, total = (a - b) * scale, (a + b) * scale
    # A delay short against the music's low notes leaves the two moments nearly equal, so the
    # difference axis is thin: widen it toward the other's spread (its shape only; the size stays
    # the audio's own on the fixed scale).
    spread = float(np.sqrt(np.mean(total * total)))
    narrow = float(np.sqrt(np.mean(difference * difference)))
    if narrow > 1e-6 and spread > narrow:
        difference *= min(PHASE_MAX_STRETCH, spread / narrow)
    return np.stack((difference, total), axis=1).astype(np.float32)


def flat_points(display: str) -> np.ndarray:
    """A resting trace: a flat line, the ring's circle, or the phase figure's dot."""
    zeros = np.zeros(TRACE_POINTS, dtype=np.float32)
    if display == "Phase":
        return np.stack((zeros, zeros), axis=1)
    x = np.linspace(0.0, 1.0, TRACE_POINTS, dtype=np.float32)
    if display == "Ring":
        angle = 0.5 * math.pi - x * (2.0 * math.pi)
        return np.stack((RING_RADIUS * np.cos(angle), RING_RADIUS * np.sin(angle)), axis=1).astype(np.float32)
    return np.stack((x * 2.0 - 1.0, zeros), axis=1)


def beam_drive_target(loudness: float, presence: float, intensity: float) -> float:
    """0..1: how brightly the beam burns now (the passage's share of how much the moment counts)."""
    return musical_weight(loudness, presence) * passage_ramp(intensity, DRIVE_QUIET_SHARE)


def flare_strength(magnitude: float, loudness: float, presence: float, intensity: float) -> float:
    """A flare's strength (0 .. ``FLARE_MAX``) for an onset (``MusicalOnset``) at passage ``intensity``."""
    hit = 0.4 + 0.6 * max(0.0, min(1.0, float(magnitude) / 3.0))
    strength = (musical_weight(loudness, presence) * musical_emphasis(loudness) * hit
                * passage_ramp(intensity, FLARE_QUIET_SHARE))
    return max(0.0, min(FLARE_MAX, strength))


def spectral_tone(spectrum) -> float | None:
    """0..1: how bright the music sounds (the analysis spectrum's centroid), None in silence."""
    values = np.asarray(spectrum, dtype=np.float32)
    if values.size < 2:
        return None
    total = float(values.sum())
    if not math.isfinite(total) or total <= 1e-6:
        return None
    centroid = float((values * np.arange(values.size, dtype=np.float32)).sum()) / total / (values.size - 1)
    return max(0.0, min(1.0, (centroid - 0.12) / 0.45))


def ghost_alpha(age: float, afterglow: float) -> float:
    """An afterglow trace's brightness after ``age`` seconds (0 when Afterglow is 0)."""
    if afterglow <= 0.0:
        return 0.0
    tau = AFTERGLOW_MIN_S + AFTERGLOW_RANGE_S * float(afterglow)
    return 0.6 * math.exp(-max(0.0, float(age)) / tau)


def ghost_lifetime(afterglow: float) -> float:
    return 3.0 * (AFTERGLOW_MIN_S + AFTERGLOW_RANGE_S * float(afterglow))


# ---- Shaders --------------------------------------------------------------------------------------

POINT_BINDING = 3

OSC_BEAM_VERTEX_SOURCE = """#version 460 core
layout(std430, binding = 3) readonly buffer OscPoints { vec2 oscPoint[]; };
uniform mat4 uMatrix;
uniform vec4 uField;          // the content rect (item logical px)
uniform vec2 uScale;          // logical px per unit along x and y
uniform int uPoints;          // points per trace
uniform float uAlpha[16];     // each trace's brightness, oldest first
uniform float uReach;         // the quad's half width around a segment (px)
uniform vec2 uOriented;       // the content's (rotated) logical size
uniform int uQuarters;        // CUSTOM quarter turns of the content
// The drawing happens in the rotated (logical) space; only the final position turns into the
// item's physical space, a rigid quarter turn (the shared quad's logicalUvFromPhysicalUv inverted).
vec2 physicalPoint(vec2 p) {
    int q = uQuarters & 3;
    if (q == 1) return vec2(uOriented.y - p.y, p.x);
    if (q == 2) return vec2(uOriented.x - p.x, uOriented.y - p.y);
    if (q == 3) return vec2(p.y, uOriented.x - p.x);
    return p;
}
out vec2 vLocal;
out vec2 vA;
out vec2 vB;
flat out float vAlpha;
flat out float vLength;
flat out float vRadius;       // the segment's distance from the centre (units)
void main() {
    int segments = uPoints - 1;
    int trace = gl_InstanceID / segments;
    int base = trace * uPoints + (gl_InstanceID - trace * segments);
    vec2 centre = uField.xy + 0.5 * uField.zw;
    vec2 a = centre + oscPoint[base] * vec2(uScale.x, -uScale.y);
    vec2 b = centre + oscPoint[base + 1] * vec2(uScale.x, -uScale.y);
    vec2 d = b - a;
    float len = length(d);
    vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
    vec2 normal = vec2(-dir.y, dir.x);
    float side = (gl_VertexID & 1) == 1 ? 1.0 : -1.0;
    vec2 end = gl_VertexID < 2 ? a - dir * uReach : b + dir * uReach;
    vLocal = end + normal * side * uReach;
    vA = a;
    vB = b;
    vAlpha = uAlpha[trace];
    vLength = len;
    vRadius = length(0.5 * (oscPoint[base] + oscPoint[base + 1]));
    gl_Position = uMatrix * vec4(physicalPoint(vLocal), 0.0, 1.0);
}
"""

OSC_BEAM_FRAGMENT_SOURCE = """#version 460 core
layout(location = 0) out vec4 FragColor;
layout(location = 1) out vec4 Emission;
in vec2 vLocal;
in vec2 vA;
in vec2 vB;
flat in float vAlpha;
flat in float vLength;
flat in float vRadius;
uniform float uCentreFade;    // Phase: the beam fades where quiet scribbles pile up at the centre
uniform float uCore;          // the beam's half width (px)
uniform float uPixel;         // one device pixel in logical px (the anti-aliased edge)
uniform vec3 uBeam;
uniform vec3 uGlowColour;
uniform float uGlow;          // the light the beam sends to the bloom
uniform float uBright;        // the beam's brightness (drive, flare)
uniform float uAnalog;        // dimming where the beam moves fast
uniform float uFocus;         // segment length (px) still drawn at full brightness
uniform float uHot;           // the white-hot centre
void main() {
    vec2 pa = vLocal - vA;
    vec2 ba = vB - vA;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    float dist = length(pa - ba * h);
    float core = 1.0 - smoothstep(uCore - uPixel, uCore + uPixel, dist);
    if (core <= 0.0) discard;
    float speed = clamp(uFocus / max(vLength, uFocus * 0.2), 0.2, 1.0);
    float centre_fade = mix(1.0, smoothstep(0.03, 0.22, vRadius), uCentreFade);
    float intensity = clamp(core * vAlpha * uBright * mix(1.0, speed, uAnalog) * centre_fade, 0.0, 1.0);
    float centre = 1.0 - smoothstep(0.0, uCore, dist);
    vec3 colour = mix(uBeam, vec3(1.0), centre * centre * centre * uHot);
    FragColor = vec4(colour * intensity, intensity);
    vec3 light = uGlowColour * (intensity * uGlow);
    Emission = vec4(light, dot(light, vec3(0.2126, 0.7152, 0.0722)));
}
"""

OSC_GRATICULE_VERTEX_SOURCE = """#version 460 core
uniform mat4 uMatrix;
uniform vec4 uField;
uniform vec2 uOriented;       // the content's (rotated) logical size
uniform int uQuarters;        // CUSTOM quarter turns of the content
// The drawing happens in the rotated (logical) space; only the final position turns into the
// item's physical space, a rigid quarter turn (the shared quad's logicalUvFromPhysicalUv inverted).
vec2 physicalPoint(vec2 p) {
    int q = uQuarters & 3;
    if (q == 1) return vec2(uOriented.y - p.y, p.x);
    if (q == 2) return vec2(uOriented.x - p.x, uOriented.y - p.y);
    if (q == 3) return vec2(p.y, uOriented.x - p.x);
    return p;
}
out vec2 vUnit;
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));
    vUnit = corner * 2.0 - 1.0;
    gl_Position = uMatrix * vec4(physicalPoint(uField.xy + corner * uField.zw), 0.0, 1.0);
}
"""

OSC_GRATICULE_FRAGMENT_SOURCE = """#version 460 core
layout(location = 0) out vec4 FragColor;
layout(location = 1) out vec4 Emission;
in vec2 vUnit;
uniform vec4 uColour;
uniform int uStyle;           // 1 grid, 2 crosshair
uniform vec2 uDivisions;
float lineCoverage(float distancePx) { return 1.0 - clamp(distancePx - 0.25, 0.0, 1.0); }
void main() {
    vec2 grid = (vUnit * 0.5 + 0.5) * uDivisions;
    vec2 gridWidth = max(fwidth(grid), vec2(1e-5));
    vec2 toLine = abs(fract(grid + 0.5) - 0.5) / gridWidth;
    float lines = lineCoverage(min(toLine.x, toLine.y));
    vec2 axisWidth = max(fwidth(vUnit), vec2(1e-5));
    vec2 toAxis = abs(vUnit) / axisWidth;
    float axes = lineCoverage(min(toAxis.x, toAxis.y));
    // Minor ticks: five per division along the centre axes.
    vec2 ticks = abs(fract(grid * 5.0 + 0.5) - 0.5) / (gridWidth * 5.0);
    float tickX = lineCoverage(ticks.x) * step(toAxis.y, 4.0);
    float tickY = lineCoverage(ticks.y) * step(toAxis.x, 4.0);
    float tick = max(tickX, tickY) * 0.8;
    float cover = uStyle == 1 ? max(max(lines * 0.45, axes), tick) : max(axes, tick);
    float edge = 1.0 - smoothstep(0.97, 1.0, max(abs(vUnit.x), abs(vUnit.y)));
    float a = uColour.a * cover * edge;
    FragColor = vec4(uColour.rgb * a, a);
    Emission = vec4(0.0);
}
"""

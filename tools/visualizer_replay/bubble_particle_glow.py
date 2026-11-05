"""Bubble particle glow: measured light profiles, a temporal flicker metric and paired GPU cost.

Offscreen only (no window). Replays a real recording through the production logical path, renders the
published Quick snapshots with the production ``QuickVisualizerRenderHost`` and measures the *particle*
contribution as ``render(snapshot) - render(snapshot without particle records)`` in linear light, so the
gradient, heroes, wakes and microbubbles cancel out.

Subcommands::

    # radial core/halo luminance profiles + 4x crops (dark and busy backgrounds)
    python -m tools.visualizer_replay.bubble_particle_glow profile --out-dir <dir> [--extent tv]
    # per-particle frame-to-frame light change vs motion on 45/60 fps captures
    python -m tools.visualizer_replay.bubble_particle_glow flicker --out-dir <dir> --fps 45 [--variant aliased]
    # 16 sub-pixel offsets of one particle through the production ambient pass (static shimmer)
    python -m tools.visualizer_replay.bubble_particle_glow shimmer --out-dir <dir>
    # paired GPU/CPU timing (TIME_ELAPSED, median/p90) against the Crossfade control
    python -m tools.visualizer_replay.bubble_particle_glow perf --out-dir <dir> --extent canonical tv

``--variant aliased`` swaps in a deliberately aliased particle shader (hard-edged core, no filtering) as
the negative control the flicker metric must fail. ``--recordings`` defaults to the main checkout's
``logs/visualizer_recordings`` when the tool runs from a worktree.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import statistics
from pathlib import Path

import numpy as np

RECORD = 6                       # ambient record stride: x, y, diameter, alpha, glow, kind
TV_EXTENT = (3874.7, 1449.5)


def _default_recordings() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "logs" / "visualizer_recordings"
        if candidate.is_dir() and any(candidate.glob("*.jsonl")):
            return candidate
    return here.parents[2] / "logs" / "visualizer_recordings"


def _extent(name: str):
    if name == "canonical":
        return None
    if name == "tv":
        return TV_EXTENT
    width, height = (float(v) for v in name.lower().split("x"))
    return (width, height)


def _overrides(pairs):
    parsed = {}
    for pair in pairs or ():
        key, _, raw = pair.partition("=")
        value = json.loads(raw)
        parsed[key] = tuple(value) if isinstance(value, list) else value
    return parsed


# ---------------------------------------------------------------------------------------------------------
# Deliberately aliased negative control: hard-edged core and halo sampled at pixel centres, no filtering.
ALIASED_FRAGMENT = """#version 460 core
in float vOpacity;
in float vGlow;
in float vClass;
in float vCoreRatio;
uniform vec4 uMicroColor;
uniform vec4 uParticleColor;
layout(location=0) out vec4 fragColor;
layout(location=1) out vec4 fragLight;  // absent on revisions without a light target: ignored there
void main() {
    vec2 p = 2.0 * (gl_PointCoord - vec2(0.5));
    float d = length(p);
    fragLight = vec4(0.0);
    if (d > 1.0) discard;
    if (vClass < 0.5) {
        float ring = step(0.6, d);
        fragColor = vec4(uMicroColor.rgb * uMicroColor.a, uMicroColor.a) * ring;
        return;
    }
    float core = d < 0.8 * vCoreRatio ? 1.0 : 0.0;
    float halo = d < 3.0 * vCoreRatio ? 0.35 : 0.0;
    float alpha = core * uParticleColor.a * vOpacity;
    vec3 emission = uParticleColor.rgb * halo * clamp(vGlow / 3.0, 0.0, 1.0) * vOpacity;
    if (alpha < 0.002 && max(max(emission.r, emission.g), emission.b) < 0.002) discard;
    fragColor = vec4(uParticleColor.rgb * alpha + emission, alpha);
}
"""


def install_variant(variant: str) -> None:
    if variant == "production":
        return
    from rendering.quick.visualizer.implementations import bubble_ambient_gl
    if variant == "aliased":
        # Works for both the single-target and the coverage+light layout: all of its light goes
        # through the 8-bit coverage target (as before the light target existed).
        bubble_ambient_gl._POINT_FRAGMENT = ALIASED_FRAGMENT
        return
    raise SystemExit(f"unknown variant {variant}")


# ---------------------------------------------------------------------------------------------------------
class Renderer:
    """Offscreen production render host on one GL 4.6 context (y-up readback flipped to y-down)."""

    def __init__(self, width: int, height: int):
        from .bubble_shape_strip import _OffscreenTarget
        self.target = _OffscreenTarget(width, height)
        self.gl = self.target.gl

    def render(self, snapshot, width: int, height: int) -> np.ndarray:
        gl = self.gl
        # Quick item coordinates are y-down (as in production and tools/visualizer_cost_probe.py);
        # the readback is bottom-up, so flipping it gives the item's own top-down image.
        matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.target.fbo)
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if self.target.host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                                   logical_size=(float(width), float(height)),
                                   matrix_values=matrix) != "bubble":
            raise RuntimeError("host did not render Bubble")
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.target.fbo)
        data = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        image = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)[::-1, :, :3]
        return np.ascontiguousarray(image)

    def bubble(self):
        return self.target.host._implementations["bubble"]

    def release(self):
        self.target.release()


def strip_particles(snapshot):
    """The same snapshot with its particle records removed (microbubbles and everything else kept)."""
    source = snapshot.logical.mode_state.ambient_points
    kept = [v for i in range(0, len(source), RECORD) if source[i + 5] <= 0.5 for v in source[i:i + RECORD]]
    return with_points(snapshot, kept)


def with_points(snapshot, points):
    points = tuple(float(v) for v in points)
    state = snapshot.logical.mode_state
    occluders = state.ambient_occluders if points else ()
    state = dataclasses.replace(state, ambient_points=points, ambient_occluders=occluders)
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))


def particles(snapshot):
    points = snapshot.logical.mode_state.ambient_points
    return [tuple(points[i:i + RECORD]) for i in range(0, len(points), RECORD) if points[i + 5] > 0.5]


def srgb_to_linear(image: np.ndarray) -> np.ndarray:
    c = image.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(linear: np.ndarray) -> np.ndarray:
    return linear[..., 0] * 0.2126 + linear[..., 1] * 0.7152 + linear[..., 2] * 0.0722


def occluder_circles(snapshot, renderer, width, height):
    """Visible hero circles in pixels (x, y, r) from the same snapshot (ambient-occluder payload)."""
    layout = renderer.bubble()._layout_cache
    cx, cy, cw, ch = layout.content_rect
    occ = snapshot.logical.mode_state.ambient_occluders
    return [(cx + occ[i] * cw, cy + occ[i + 1] * ch, occ[i + 2] * layout.response_radius_scale * ch)
            for i in range(0, len(occ), 4) if occ[i + 3] > 0.0]


def particle_pixels(snapshot, renderer):
    layout = renderer.bubble()._layout_cache
    cx, cy, cw, ch = layout.content_rect
    return [(cx + p[0] * cw, cy + p[1] * ch, p) for p in particles(snapshot)]


def isolated(points, circles, radius, width, height, *, others=None):
    """Indices of particles with a clean window: away from heroes, edges and other particles."""
    others = points if others is None else others
    result = []
    for index, (x, y, _record) in enumerate(points):
        if x < radius or y < radius or x > width - radius or y > height - radius:
            continue
        if any(math.hypot(x - ox, y - oy) < radius * 2.0 for j, (ox, oy, _r) in enumerate(others) if j != index):
            continue
        if any(math.hypot(x - hx, y - hy) < hr + radius for hx, hy, hr in circles):
            continue
        result.append(index)
    return result


def radial_profile(added_lum: np.ndarray, x: float, y: float, radius: float, step: float = 0.5):
    x0, x1 = int(math.floor(x - radius)), int(math.ceil(x + radius))
    y0, y1 = int(math.floor(y - radius)), int(math.ceil(y + radius))
    window = added_lum[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dist = np.hypot(xx + 0.5 - x, yy + 0.5 - y)
    bins = np.minimum((dist / step).astype(int), int(radius / step))
    sums = np.bincount(bins.ravel(), weights=window.ravel(), minlength=int(radius / step) + 1)
    counts = np.bincount(bins.ravel(), minlength=int(radius / step) + 1)
    return sums[:-1] / np.maximum(counts[:-1], 1), float(window[dist <= radius].sum())


def window_light(added_lum, x, y, radius):
    x0, x1 = max(0, int(math.floor(x - radius))), int(math.ceil(x + radius))
    y0, y1 = max(0, int(math.floor(y - radius))), int(math.ceil(y + radius))
    window = added_lum[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dist = np.hypot(xx + 0.5 - x, yy + 0.5 - y)
    inside = window[dist <= radius]
    core = window[dist <= 1.5]
    return float(inside.sum()), float(core.max() if core.size else 0.0)


def _snapshots(clip_name, recordings, preset, extent, frames, overrides):
    from .bubble_shape_invariance import load_clip
    from .driver import replay_clip
    last = max(frames)
    clip = load_clip(clip_name, fixture=False, seconds=0.0, recordings=recordings)
    clip = dataclasses.replace(clip, frames=clip.frames[:last + 2])
    result = replay_clip(clip, "bubble", preset=preset, viewport_extent=extent, snapshots_at=frames,
                         overrides=overrides or None)
    return clip, result


def _frame_at(clip_name, recordings, seconds):
    from .bubble_shape_invariance import load_clip
    clip = load_clip(clip_name, fixture=False, seconds=seconds + 0.2, recordings=recordings)
    first = clip.frames[0].timestamp_us
    return next(i for i, f in enumerate(clip.frames) if f.timestamp_us - first >= seconds * 1e6)


def _size(extent):
    from .bubble_shape_invariance import CANONICAL
    w, h = extent if extent is not None else CANONICAL
    return int(round(w)), int(round(h))


# ---------------------------------------------------------------------------------------------------------
def cmd_profile(args) -> dict:
    from PIL import Image
    extent = _extent(args.extent)
    width, height = _size(extent)
    frames = [_frame_at(args.clip, args.recordings, t) for t in args.at]
    _clip, result = _snapshots(args.clip, args.recordings, args.preset, extent, frames, _overrides(args.set))
    renderer = Renderer(width, height)
    radius = args.radius
    report = {"extent": [width, height], "preset": args.preset, "clip": args.clip, "variant": args.variant,
              "frames": []}
    crops_dark, crops_busy = [], []
    try:
        for index in frames:
            snapshot = result["snapshots"][index]
            full = renderer.render(snapshot, width, height)
            ambient_fbo = _read_ambient(renderer)
            bg = renderer.render(strip_particles(snapshot), width, height)
            lin_full, lin_bg = srgb_to_linear(full), srgb_to_linear(bg)
            added = luminance(lin_full) - luminance(lin_bg)
            points = particle_pixels(snapshot, renderer)
            circles = occluder_circles(snapshot, renderer, width, height)
            chosen = isolated(points, circles, radius, width, height)
            profiles, rows = [], []
            for i in chosen:
                x, y, record = points[i]
                profile, total = radial_profile(added, x, y, radius)
                bg_lum = float(luminance(lin_bg[int(y), int(x)]))
                xi, yi = int(x), int(y)
                core_code = int(full[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2].max())
                core_bg_code = int(bg[max(0, yi - 1):yi + 2, max(0, xi - 1):xi + 2].max())
                rows.append(_profile_stats(profile, total, record, bg_lum, core_code, core_bg_code,
                                           _halo_colour(lin_full, lin_bg, x, y)))
                profiles.append(profile)
                crop = full[yi - 12:yi + 13, xi - 12:xi + 13]
                if crop.shape[:2] == (25, 25):
                    (crops_busy if bg_lum > 0.02 else crops_dark).append(crop)
            frame_report = {"frame": index, "particles": len(points), "isolated": len(chosen),
                            "background_median_lum": float(np.median(luminance(lin_bg))),
                            "rows": rows}
            if profiles:
                stack = np.vstack(profiles)
                frame_report["median_profile"] = [round(float(v), 5) for v in np.median(stack, axis=0)]
            report["frames"].append(frame_report)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            Image.fromarray(full).save(args.out_dir / f"{args.prefix}_frame{index}.png")
            if ambient_fbo is not None:
                Image.fromarray(ambient_fbo).save(args.out_dir / f"{args.prefix}_ambient_fbo{index}.png")
    finally:
        renderer.release()
    report["summary"] = _summarise_profiles(report)
    for name, crops in (("dark", crops_dark), ("busy", crops_busy)):
        if crops:
            _crop_sheet(crops[:24], args.out_dir / f"{args.prefix}_crops_{name}_4x.png")
    path = args.out_dir / f"{args.prefix}_profile.json"
    path.write_text(json.dumps(report, indent=1))
    print(json.dumps(report["summary"], indent=1))
    print(path)
    return report


def _read_ambient(renderer):
    gl = renderer.gl
    ambient = getattr(renderer.bubble(), "_ambient_renderer", None)
    if ambient is None or not getattr(ambient, "_fbo", 0):
        return None
    w, h = ambient._target_size
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, ambient._fbo)
    gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
    data = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
    return np.ascontiguousarray(np.frombuffer(data, dtype=np.uint8).reshape(h, w, 4)[::-1, :, :])


def _halo_colour(lin_full, lin_bg, x, y):
    """Mean added linear RGB in the 2.5..8 px annulus: the halo's own colour."""
    yi, xi = int(y), int(x)
    window_f = lin_full[yi - 9:yi + 10, xi - 9:xi + 10]
    window_b = lin_bg[yi - 9:yi + 10, xi - 9:xi + 10]
    if window_f.shape[:2] != (19, 19):
        return None
    yy, xx = np.mgrid[yi - 9:yi + 10, xi - 9:xi + 10]
    dist = np.hypot(xx + 0.5 - x, yy + 0.5 - y)
    ring = (dist >= 2.5) & (dist <= 8.0)
    added = (window_f - window_b)[ring].mean(axis=0)
    return [float(v) for v in added]


def _saturation(rgb):
    if rgb is None:
        return None
    hi, lo = max(rgb), min(rgb)
    return 0.0 if hi <= 1e-9 else (hi - lo) / hi


def _profile_stats(profile, total, record, bg_lum, core_code, core_bg_code, halo_rgb):
    step = 0.5
    radii = (np.arange(len(profile)) + 0.5) * step
    ring_light = profile * 2 * math.pi * radii * step
    cumulative = np.cumsum(ring_light)
    whole = cumulative[-1] if cumulative[-1] > 0 else 1.0
    half_r = float(radii[min(len(radii) - 1, np.searchsorted(cumulative, 0.5 * whole))])
    r90 = float(radii[min(len(radii) - 1, np.searchsorted(cumulative, 0.9 * whole))])
    peak = float(profile[:3].max())
    # Non-monotonic falloff: largest rise after the profile has fallen (a dark gap between core and halo).
    running_min = np.minimum.accumulate(profile)
    rise = float((profile - running_min).max() / peak) if peak > 0 else 0.0
    halo_at = {r: float(profile[int(r / step)]) / peak if peak > 0 else 0.0 for r in (2, 4, 6, 8, 12)}
    return {"diameter_logical": round(record[2], 3), "alpha": round(record[3], 3), "glow": round(record[4], 3),
            "bg_lum": round(bg_lum, 5), "core_peak_added_lum": round(peak, 5), "total_added_lum": round(total, 4),
            "half_light_r_px": half_r, "r90_px": r90, "falloff_rise": round(rise, 4),
            "relative_at_px": {str(k): round(v, 4) for k, v in halo_at.items()},
            "core_code_max": core_code, "core_bg_code_max": core_bg_code,
            "halo_rgb_linear": None if halo_rgb is None else [round(v, 5) for v in halo_rgb],
            "halo_saturation": None if halo_rgb is None else round(_saturation(halo_rgb), 4)}


def _summarise_profiles(report):
    rows = [row for frame in report["frames"] for row in frame["rows"]]
    if not rows:
        return {}
    pick = lambda key: [row[key] for row in rows if row.get(key) is not None]  # noqa: E731
    med = lambda key: round(statistics.median(pick(key)), 5)  # noqa: E731
    return {"isolated_particles": len(rows), "core_peak_added_lum_median": med("core_peak_added_lum"),
            "total_added_lum_median": med("total_added_lum"), "half_light_r_px_median": med("half_light_r_px"),
            "r90_px_median": med("r90_px"), "falloff_rise_median": med("falloff_rise"),
            "falloff_rise_max": round(max(pick("falloff_rise")), 4),
            "core_code_max_median": med("core_code_max"), "core_bg_code_max_median": med("core_bg_code_max"),
            "saturated_cores_255": sum(1 for row in rows if row["core_code_max"] >= 255),
            "halo_saturation_median": med("halo_saturation") if pick("halo_saturation") else None}


def _crop_sheet(crops, path, scale=4):
    from PIL import Image
    columns = 6
    tile = crops[0].shape[0] * scale
    rows = (len(crops) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (tile + 2), rows * (tile + 2)), (60, 60, 60))
    for i, crop in enumerate(crops):
        image = Image.fromarray(crop).resize((tile, tile), Image.Resampling.NEAREST)
        sheet.paste(image, ((i % columns) * (tile + 2), (i // columns) * (tile + 2)))
    sheet.save(path)


# ---------------------------------------------------------------------------------------------------------
def cmd_flicker(args) -> dict:
    """Per particle, frame-to-frame change of its integrated light and core peak, on steady drive only.

    A pair counts when the particle's authored drive (alpha and glow from the logical packet) changed by
    less than ``--steady`` between the two presented frames, it stayed clear of heroes, edges and other
    particles, and it moved: any light change left is the renderer reacting to sub-pixel motion.
    """
    from PIL import Image
    extent = _extent(args.extent)
    width, height = _size(extent)
    start = _frame_at(args.clip, args.recordings, args.start)
    stride = 90.0 / args.fps
    count = int(args.seconds * args.fps)
    frames = sorted({start + int(math.floor(k * stride)) for k in range(count)})
    _clip, result = _snapshots(args.clip, args.recordings, args.preset, extent, frames, _overrides(args.set))
    renderer = Renderer(width, height)
    radius = args.radius
    per_frame = []
    strip_rows = []
    try:
        for n, index in enumerate(frames):
            snapshot = result["snapshots"][index]
            full = renderer.render(snapshot, width, height)
            bg = renderer.render(strip_particles(snapshot), width, height)
            added = luminance(srgb_to_linear(full)) - luminance(srgb_to_linear(bg))
            points = particle_pixels(snapshot, renderer)
            circles = occluder_circles(snapshot, renderer, width, height)
            clean = set(isolated(points, circles, radius, width, height))
            entries = []
            for i, (x, y, record) in enumerate(points):
                light, peak = window_light(added, x, y, radius) if i in clean else (None, None)
                entries.append((x, y, record[3], record[4], light, peak))
            per_frame.append(entries)
            if n < args.strip_frames:
                strip_rows.append(full)
    finally:
        renderer.release()
    def change(x, y):
        # Symmetric relative change, bounded at 2: a core that vanishes counts as 2, never as infinity.
        return abs(y - x) / max((x + y) * 0.5, 1e-9)

    def steady(pa, pb):
        return (abs(pb[2] - pa[2]) <= args.steady * max(pa[2], 1e-6)
                and abs(pb[3] - pa[3]) <= args.steady * max(pa[3], 1e-6))

    pairs = []
    for a, b in zip(per_frame, per_frame[1:]):
        if len(a) != len(b):
            continue
        for pa, pb in zip(a, b):
            if pa[4] is None or pb[4] is None or not steady(pa, pb):
                continue
            motion = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            if motion < 0.05 or pa[4] + pb[4] <= 1e-6:
                continue
            pairs.append({"motion_px": motion, "light_change": change(pa[4], pb[4]),
                          "peak_change": change(pa[5], pb[5])})
    # Per particle coefficient of variation over contiguous clean, steady runs of >= 12 frames.
    cov_light, cov_peak = [], []
    if per_frame and all(len(f) == len(per_frame[0]) for f in per_frame):
        for i in range(len(per_frame[0])):
            run = []
            for f in per_frame + [None]:
                entry = None if f is None else f[i]
                ok = entry is not None and entry[4] is not None and (not run or steady(run[0], entry))
                if ok:
                    run.append(entry)
                    continue
                if len(run) >= 12:
                    lights, peaks = [r[4] for r in run], [r[5] for r in run]
                    if statistics.mean(lights) > 0:
                        cov_light.append(statistics.pstdev(lights) / statistics.mean(lights))
                    if statistics.mean(peaks) > 0:
                        cov_peak.append(statistics.pstdev(peaks) / statistics.mean(peaks))
                run = [entry] if entry is not None and entry[4] is not None else []

    def q(values, p):
        if not values:
            return None
        ordered = sorted(values)
        return round(ordered[min(len(ordered) - 1, int(round(p * (len(ordered) - 1))))], 5)

    light = [p["light_change"] for p in pairs]
    peak = [p["peak_change"] for p in pairs]
    motion = [p["motion_px"] for p in pairs]
    share = lambda values, limit: round(sum(v > limit for v in values) / len(values), 4) if values else None  # noqa: E731
    report = {"extent": [width, height], "preset": args.preset, "clip": args.clip, "fps": args.fps,
              "start_s": args.start, "frames": len(frames), "variant": args.variant, "set": args.set or [],
              "steady_pairs": len(pairs), "motion_px_median": q(motion, 0.5),
              "light_change_median": q(light, 0.5), "light_change_p95": q(light, 0.95), "light_change_max": q(light, 1.0),
              "light_change_over_5pct": share(light, 0.05), "light_change_over_10pct": share(light, 0.10),
              "peak_change_median": q(peak, 0.5), "peak_change_p95": q(peak, 0.95), "peak_change_max": q(peak, 1.0),
              "peak_change_over_10pct": share(peak, 0.10),
              "steady_runs": len(cov_light),
              "light_cov_median": q(cov_light, 0.5), "light_cov_p95": q(cov_light, 0.95),
              "peak_cov_median": q(cov_peak, 0.5), "peak_cov_p95": q(cov_peak, 0.95)}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{args.prefix}_flicker.json"
    path.write_text(json.dumps(report, indent=1))
    if strip_rows:
        _strip(strip_rows, args.out_dir / f"{args.prefix}_strip.png", args.crop)
    print(json.dumps(report, indent=1))
    print(path)
    return report


def _strip(frames, path, crop):
    """Consecutive frames of one region, 4x nearest, side by side in rows of 6, for frame-by-frame review."""
    from PIL import Image
    x, y, w, h = crop
    tiles = [Image.fromarray(frame[y:y + h, x:x + w]).resize((w * 4, h * 4), Image.Resampling.NEAREST)
             for frame in frames]
    columns = 6
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (w * 4 + 2), rows * (h * 4 + 2)), (90, 90, 90))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * (w * 4 + 2), (i // columns) * (h * 4 + 2)))
    sheet.save(path)


# ---------------------------------------------------------------------------------------------------------
def cmd_shimmer(args) -> dict:
    """One isolated particle at 16 sub-pixel offsets through the production renderer: CoV of light/peak."""
    extent = _extent(args.extent)
    width, height = _size(extent)
    frame = _frame_at(args.clip, args.recordings, args.start)
    _clip, result = _snapshots(args.clip, args.recordings, args.preset, extent, [frame], _overrides(args.set))
    snapshot = result["snapshots"][frame]
    renderer = Renderer(width, height)
    rows = {}
    try:
        renderer.render(snapshot, width, height)          # layout cache
        layout = renderer.bubble()._layout_cache
        cx, cy, cw, ch = layout.content_rect
        circles = occluder_circles(snapshot, renderer, width, height)
        margin = args.radius + 2.0
        candidates = [(cx + cw * (i + 0.5) / 24.0, cy + ch * (j + 0.5) / 16.0) for i in range(24) for j in range(16)]
        candidates = [(x, y) for x, y in candidates
                      if margin < x < width - margin and margin < y < height - margin]
        # The emptiest spot: farthest from every visible hero's rim, so nothing covers the test particle.
        base_x, base_y = max(candidates, key=lambda c: min(
            (math.hypot(c[0] - hx, c[1] - hy) - hr for hx, hy, hr in circles), default=1e9))
        quiet = with_points(snapshot, ())
        bg = luminance(srgb_to_linear(renderer.render(quiet, width, height)))
        for diameter in args.diameters:
            for glow in args.glows:
                lights, peaks = [], []
                for k in range(16):
                    ox, oy = (k % 4) / 4.0 + 0.125, (k // 4) / 4.0 + 0.125
                    px, py = math.floor(base_x) + ox, math.floor(base_y) + oy
                    record = ((px - cx) / cw, (py - cy) / ch, diameter, 1.0, glow, 1.0)
                    image = renderer.render(with_points(snapshot, record), width, height)
                    added = luminance(srgb_to_linear(image)) - bg
                    light, peak = window_light(added, px, py, args.radius)
                    lights.append(light)
                    peaks.append(peak)
                mean_l, mean_p = statistics.mean(lights), statistics.mean(peaks)
                rows[f"d{diameter}_g{glow}"] = {
                    "light_mean": round(mean_l, 5), "peak_mean": round(mean_p, 5),
                    "light_cov": round(statistics.pstdev(lights) / mean_l, 5) if mean_l > 0 else None,
                    "peak_cov": round(statistics.pstdev(peaks) / mean_p, 5) if mean_p > 0 else None}
    finally:
        renderer.release()
    report = {"extent": [width, height], "variant": args.variant, "cases": rows}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{args.prefix}_shimmer.json"
    path.write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return report


# ---------------------------------------------------------------------------------------------------------
def cmd_perf(args) -> dict:
    """Paired GPU (TIME_ELAPSED) and CPU submit timing, glow scene vs the same scene without particles."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.bench_stability import BenchCase, PairedBench, crossfade_control
    from tools.transition_contact_sheet import TransitionCapture

    report = {"variant": args.variant, "set": args.set or [], "cases": {}}
    for extent_name in args.extent_list:
        extent = _extent(extent_name)
        width, height = _size(extent)
        start = _frame_at(args.clip, args.recordings, args.start)
        frames = [start + 2 * k for k in range(args.frames)]
        _clip, result = _snapshots(args.clip, args.recordings, args.preset, extent, frames, _overrides(args.set))
        snapshots = [result["snapshots"][i] for i in frames]
        stripped = [strip_particles(s) for s in snapshots]
        capture = TransitionCapture(width, height)
        hosts = {"glow": QuickVisualizerRenderHost(), "no_particles": QuickVisualizerRenderHost()}
        matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)

        def case(host, series):
            def point(index):
                snapshot = series[index % len(series)]

                def render():
                    gl.glViewport(0, 0, width, height)
                    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
                    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
                    host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                                logical_size=(float(width), float(height)), matrix_values=matrix)
                return render

            def warm():
                for i in range(8):
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                    point(i)()
            return BenchCase(point, warm, lambda: {"particles": len(particles(series[0]))})
        def ambient_case(series):
            """The decoration pass alone (its own FBO), with the exact arguments the Bubble renderer passes."""
            from rendering.quick.visualizer.implementations import bubble as bubble_impl
            from widgets.spotify_visualizer.bubble_ambient_geometry import ambient_sprite_scale
            host = hosts["glow"]

            def point(index):
                snapshot = series[index % len(series)]
                implementation = host._implementations["bubble"]
                layout = implementation._layout_cache
                ambient = implementation._ambient_renderer
                parameters = snapshot.logical.mode_state.parameters
                payload = bubble_impl.resolve_quick_bubble_payload(snapshot)

                def render():
                    ambient.render_texture(
                        layout.content_rect, snapshot.presentation.dpr, payload.ambient_points,
                        sprite_scale=ambient_sprite_scale(layout.effect_scale),
                        glow_spread=float(bubble_impl.parameter(parameters, "bubble_particle_glow_spread")),
                        micro_color=bubble_impl.rgba(bubble_impl.parameter(parameters, "bubble_outline_color")),
                        particle_color=bubble_impl.rgba(bubble_impl.parameter(parameters, "bubble_particle_color")),
                        occluders=payload.ambient_occluders, response_radius_scale=layout.response_radius_scale)
                return render

            def warm():
                for i in range(8):
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                    host.render(snapshot=series[i % len(series)], viewport=(0, 0, width, height),
                                logical_size=(float(width), float(height)), matrix_values=matrix)
            return BenchCase(point, warm, lambda: {"particles": len(particles(series[0]))})
        try:
            bench = PairedBench(gl, capture, crossfade_control(capture))
            cases = {"glow": case(hosts["glow"], snapshots), "no_particles": case(hosts["no_particles"], stripped),
                     "ambient_pass": ambient_case(snapshots)}
            measured = bench.measure(extent_name, cases, len(frames), args.passes, args.max_rounds)
            load = bench.load()
            for key, stats in measured.items():
                stats.pop("env", None)
                report["cases"][f"{extent_name}/{key}"] = {
                    k: (round(v, 4) if isinstance(v, float) else v) for k, v in stats.items()}
            report["cases"][f"{extent_name}/load"] = load
        finally:
            for host in hosts.values():
                host.release_resources()
            capture.close()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{args.prefix}_perf.json"
    path.write_text(json.dumps(report, indent=1))
    print(path)
    return report


def cmd_frames(args) -> None:
    """Full production frames as PNG (optionally without particle records), for revision-to-revision diffs."""
    from PIL import Image
    extent = _extent(args.extent)
    width, height = _size(extent)
    frames = [_frame_at(args.clip, args.recordings, t) for t in args.at]
    _clip, result = _snapshots(args.clip, args.recordings, args.preset, extent, frames, _overrides(args.set))
    renderer = Renderer(width, height)
    try:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for index in frames:
            snapshot = result["snapshots"][index]
            if args.strip_particles:
                snapshot = strip_particles(snapshot)
            path = args.out_dir / f"{args.prefix}_frame{index}.png"
            Image.fromarray(renderer.render(snapshot, width, height)).save(path)
            print(path)
    finally:
        renderer.release()


def cmd_packets(args) -> dict:
    """SHA-256 of every logical tick's complete frame (``repr`` of the frozen packet: positions, extras, trails,
    ambient points/occluders, parameters, timestamps) on real replays, per preset and card shape. Run on two
    revisions and compare: a render-only change must leave every digest identical (BTF)."""
    import hashlib
    from .bubble_shape_invariance import load_clip
    from .driver import replay_clip
    report = {"clips": {}}
    for clip_name in args.clips:
        clip = load_clip(clip_name, fixture=False, seconds=args.seconds, recordings=args.recordings)
        for preset in args.presets:
            for extent_name in args.extent_list:
                result = replay_clip(clip, "bubble", preset=preset, viewport_extent=_extent(extent_name),
                                     overrides=_overrides(args.set) or None)
                digests = [hashlib.sha256(repr(frame).encode()).hexdigest() for frame in result["logical_series"]]
                whole = hashlib.sha256("".join(digests).encode()).hexdigest()
                ambient = sum(1 for frame in result["logical_series"]
                              if getattr(frame.mode_state, "ambient_points", ()))
                report["clips"][f"{clip_name}/p{preset}/{extent_name}"] = {
                    "ticks": len(digests), "ticks_with_ambient": ambient, "digest": whole}
                print(clip_name, preset, extent_name, len(digests), ambient, whole, flush=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{args.prefix}_packets.json"
    path.write_text(json.dumps(report, indent=1))
    print(path)
    return report


def main() -> None:
    from PySide6.QtGui import QGuiApplication

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--out-dir", type=Path, required=True)
        p.add_argument("--prefix", default="glow")
        p.add_argument("--clip", default="balanced")
        p.add_argument("--recordings", type=Path, default=_default_recordings())
        p.add_argument("--preset", type=int, default=0)
        p.add_argument("--extent", default="canonical", help="canonical | tv | WxH")
        p.add_argument("--set", nargs="*", help="Settings-model overrides key=json")
        p.add_argument("--variant", default="production", choices=("production", "aliased"))
        p.add_argument("--radius", type=float, default=16.0, help="measurement window radius, px")

    p = sub.add_parser("profile")
    common(p)
    p.add_argument("--at", type=float, nargs="+", default=[12.0, 24.0, 36.0])
    p = sub.add_parser("flicker")
    common(p)
    p.add_argument("--start", type=float, default=20.0)
    p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("--fps", type=float, default=45.0)
    p.add_argument("--steady", type=float, default=0.01, help="max relative authored drive change per pair")
    p.add_argument("--strip-frames", type=int, default=18)
    p.add_argument("--crop", type=int, nargs=4, default=[0, 0, 120, 80], metavar=("X", "Y", "W", "H"))
    p = sub.add_parser("shimmer")
    common(p)
    p.add_argument("--start", type=float, default=20.0)
    p.add_argument("--diameters", type=float, nargs="+", default=[0.93, 1.5, 2.4, 4.0])
    p.add_argument("--glows", type=float, nargs="+", default=[0.0, 0.12, 2.0])
    p = sub.add_parser("perf")
    common(p)
    p.add_argument("--start", type=float, default=20.0)
    p.add_argument("--frames", type=int, default=24)
    p.add_argument("--passes", type=int, default=3)
    p.add_argument("--max-rounds", type=int, default=8)
    p.add_argument("--extent-list", nargs="+", default=["canonical", "tv"])
    p = sub.add_parser("frames")
    common(p)
    p.add_argument("--at", type=float, nargs="+", default=[12.0, 24.0, 36.0])
    p.add_argument("--strip-particles", action="store_true")
    p = sub.add_parser("packets")
    common(p)
    p.add_argument("--clips", nargs="+", default=["balanced", "heavy1", "quiet_intro"])
    p.add_argument("--presets", type=int, nargs="+", default=[0, 1])
    p.add_argument("--seconds", type=float, default=20.0)
    p.add_argument("--extent-list", nargs="+", default=["canonical", "tv"])
    args = parser.parse_args()
    QGuiApplication.instance() or QGuiApplication([])
    install_variant(args.variant)
    {"profile": cmd_profile, "flicker": cmd_flicker, "shimmer": cmd_shimmer, "perf": cmd_perf,
     "packets": cmd_packets, "frames": cmd_frames}[args.command](args)


if __name__ == "__main__":
    main()

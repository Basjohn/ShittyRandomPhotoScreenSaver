"""Bubble on its card and display-wide: the same recorded take's motion and breathing at both sizes.

Replays a recorded take through the production logical path (``driver.replay_clip``: configured controller,
deterministic clock and seed, the real authored tick, ``BubbleFrameRuntime``) twice: on the card (its committed
world) and display-wide (the same card, with the display-wide card's grown world handed to the controller through the
owner's seam, ``VisualizerRuntimeController.set_drawn_world_extent``). The display-wide world is the production
resolver's (``resolve_expanded_visualizer_presentation`` of the card on the display). A third column, ``before``, is
the card run laid out on the display-wide world, which is what the scene drew before 21 Nov (the simulation kept the
card's world while the renderer drew the grown one).

Motion is measured as ``bubble_shape_invariance.measure`` measures it (canonical-card pixels against the drawn
bubbles' own size); breathing per stable identity as ``bubble_breathing_continuity`` does (displayed radius over
nominal radius per mature segment: range, swings per second, flat share). The music above the traces is the take's
own PCM (RMS dBFS of each frame's capture history), so a response that saturates, dies or races shows against it.

By default logical frames only (no renderer, no window, no display). ``--render-fps N`` also draws both cards (the
card's ordinary record at ``--card-scale``, its display-wide record, both at ``--dpr``) through the production render
host offscreen, N frames per second of the take, keeps those frames, and measures each mature big hero's drawn ring
from the pixels it changes when drawn alone: its outer radius in device pixels against its own nominal drawn size,
the drawn card's short side and its equal-area side (``drawn`` in the report, a fourth trace under the music). No
window is shown; not display-cadence or listening acceptance.

    python -m tools.visualizer_replay.bubble_display_wide_response --clip <recording.jsonl> --output <evidence dir>
        [--seconds 60] [--preset 0] [--card 1204x144] [--display 2560x1440]
        [--render-fps 2 --card-scale 2 --dpr 1.5]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from unittest.mock import patch
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[2]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from tools import artifact_paths  # noqa: E402


def _size(text: str) -> tuple[float, float]:
    width, _, height = text.lower().partition("x")
    return float(width), float(height)


def drawn_presentations(card: tuple[float, float], display: tuple[float, float], *, scale: float = 1.0,
                        dpr: float = 1.0):
    """(the card's ordinary record, its display-wide record) on ``display`` (the production resolvers; the card at
    uniform ``scale``, both at ``dpr``): the two drawn cards the renderer lays Bubble's frames onto."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tools.expanded_visualizer_evidence import CARD
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_expanded_visualizer_presentation, resolve_visualizer_presentation,
    )

    ordinary = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"), display_size=display, outer_origin=(40.0, 40.0),
        dpr=float(dpr), uniform_visual_scale=float(scale), viewport_extent=card, **CARD)
    return ordinary, resolve_expanded_visualizer_presentation(ordinary, display_size=display)


def display_wide_world(card: tuple[float, float], display: tuple[float, float]) -> tuple[float, float]:
    """The display-wide card's world for ``card`` on ``display`` (the production resolvers, uniform scale 1)."""
    return tuple(float(v) for v in drawn_presentations(card, display)[1].viewport_extent)


#: A raised hero capacity for a candidate whose live population passes the renderer's 110 (tool only): a multiple
#: of 32 so the big-class words stay whole (two uvec4 words of 32 heroes each per 128).
CANDIDATE_CAPACITY = 256


def candidate_world_resolver(exponent: float, density: str):
    """A CANDIDATE capacity zoom (tool only, never product): ``resolve_bubble_world`` with the zoom
    ``(needed / capacity) ** exponent`` instead of its square root (0.5 is production). ``density``: ``"count"``
    keeps the production world's live count (so a smaller zoom spaces fewer-than-area heroes out), ``"area"`` keeps
    density by area (so a smaller zoom needs more heroes), ``"mid"`` takes the population halfway between the two.
    A world the production resolver does not zoom is returned unchanged."""
    from widgets.spotify_visualizer import bubble_viewport_profile as profile

    if density not in ("count", "area", "mid"):
        raise ValueError("density is 'count', 'area' or 'mid'")
    production = profile.resolve_bubble_world

    def resolve(viewport_extent, *, authored_population, baseline_viewport_size=(
            profile.CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE)):
        world = production(viewport_extent, authored_population=authored_population,
                           baseline_viewport_size=baseline_viewport_size)
        if world.world_scale == 1.0:
            return world
        baseline_w, baseline_h = (float(v) for v in baseline_viewport_size)
        cards_w, cards_h = world.width / baseline_w, world.height / baseline_h
        zoom = (world.world_scale ** 2) ** float(exponent)       # (needed / capacity) ** exponent
        domain_w, domain_h = cards_w / zoom, cards_h / zoom
        population = {"count": world.population_scale, "area": domain_w * domain_h,
                      "mid": 0.5 * (world.population_scale + domain_w * domain_h)}[density]
        return profile.BubbleWorld(width=world.width, height=world.height, domain_w=domain_w, domain_h=domain_h,
                                   world_scale=zoom, population_scale=population)

    return resolve


def raised_logical_capacity(stack, capacity: int) -> None:
    """Tool-only: the simulation, population scaling and big-class words hold ``capacity`` heroes."""
    from widgets.spotify_visualizer import bubble_hero_occlusion as occlusion
    from widgets.spotify_visualizer import bubble_simulation, bubble_viewport_profile as profile

    words = capacity // 32

    def pack(bubbles):
        result = [0] * words
        for index, bubble in enumerate(bubbles):
            if index >= capacity:
                raise ValueError("Bubble candidate class map exceeds its raised capacity")
            if bool(bubble.is_big):
                result[index >> 5] |= 1 << (index & 31)
        return tuple(result)

    def admit(bits, bubble_count):
        bits = tuple(bits)
        if len(bits) != words or not 0 <= int(bubble_count) <= capacity:
            raise ValueError("Bubble candidate class words do not match its raised capacity")
        return bits

    from widgets.spotify_visualizer import bubble_ambient_geometry as ambient

    select = ambient.select_ambient_occluders

    def occluders(bubbles, positions):
        # The frame holds at most 110 ambient occluder circles: the first 110 visible heroes mask the ambience.
        return select(bubbles, positions)[:110 * 4]

    stack.enter_context(patch.object(ambient, "select_ambient_occluders", occluders))
    stack.enter_context(patch.object(bubble_simulation, "MAX_BUBBLES", capacity))
    stack.enter_context(patch.object(profile, "BUBBLE_RENDER_CAPACITY", capacity))
    stack.enter_context(patch.object(occlusion, "pack_big_class_bits", pack))
    stack.enter_context(patch.object(occlusion, "admit_big_class_bits", admit))


def raised_render_capacity(stack, capacity: int) -> None:
    """Tool-only: the Python Bubble renderer and its shader hold ``capacity`` heroes (arrays sized, the class words
    split into two uvec4 members). Enter before the render host makes its Bubble renderer."""
    from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl
    from rendering.quick.visualizer.implementations import bubble as renderer
    from rendering.quick.visualizer.render_contract import quick_visualizer_vertex_source
    from widgets.spotify_visualizer.shaders import load_fragment_shader

    if capacity != 256:
        raise ValueError("the raised render capacity is drawn with exactly 256 heroes (two class uvec4s)")
    source = load_fragment_shader("bubble")
    replacements = (("uvec4 u_big_class_bits;", "uvec4 u_big_class_bits;\n    uvec4 u_big_class_bits2;"),
                    ("u_bubbles_pos[110]", "u_bubbles_pos[256]"), ("u_bubbles_extra[110]", "u_bubbles_extra[256]"),
                    ("u_bubbles_trail[330]", "u_bubbles_trail[768]"),
                    ("min(u_bubble_count, 110)", "min(u_bubble_count, 256)"),
                    ("(u_big_class_bits[i >> 5] & (1u << uint(i & 31)))",
                     "((((i >> 5) < 4) ? u_big_class_bits[i >> 5] : u_big_class_bits2[(i >> 5) - 4])"
                     " & (1u << uint(i & 31)))"))
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"bubble.frag no longer has exactly one {old!r}: the candidate shader is stale")
        source = source.replace(old, new)
    declaration = block_declaration(source, "BubbleDraw")
    frame_scalars = renderer.bubble_frame_scalars

    def scalars(mode_state, payload):
        values = frame_scalars(mode_state, payload)
        bits = tuple(values["u_big_class_bits"]) + (0,) * 8
        values["u_big_class_bits"], values["u_big_class_bits2"] = bits[:4], bits[4:8]
        return values

    for name, value in (("_MAX_BUBBLES", capacity), ("_BUBBLE_POS_SIZE", capacity * 4),
                        ("_BUBBLE_EXTRA_SIZE", capacity * 4), ("_BUBBLE_TRAIL_SIZE", capacity * 9),
                        ("BUBBLE_VERTEX_SOURCE", quick_visualizer_vertex_source(declaration)),
                        ("BUBBLE_BLOCK", block_layout_from_glsl(declaration)),
                        ("load_fragment_shader", lambda _name: source), ("bubble_frame_scalars", scalars)):
        stack.enter_context(patch.object(renderer, name, value))


def observe(clip, card, *, preset: int, drawn_world=None, snapshots_at=(), snapshots=None, candidate=None):
    """One record per published Bubble snapshot: shape-invariance samples plus nominal radii for breathing.
    ``snapshots``: a dict that receives the published Quick snapshots of the frames in ``snapshots_at``.
    ``candidate``: (exponent, density) replays with ``candidate_world_resolver`` (never product); an ``"area"``
    candidate holds ``CANDIDATE_CAPACITY`` heroes."""
    from contextlib import ExitStack

    from widgets.spotify_visualizer import bubble_simulation
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
    from . import driver

    if candidate is not None:
        exponent, density = candidate
        with ExitStack() as stack:
            stack.enter_context(patch.object(bubble_simulation, "resolve_bubble_world",
                                             candidate_world_resolver(exponent, density)))
            if density != "count":
                raised_logical_capacity(stack, CANDIDATE_CAPACITY)
            return observe(clip, card, preset=preset, drawn_world=drawn_world, snapshots_at=snapshots_at,
                           snapshots=snapshots)

    frames, identities, resolved = [], {}, {}
    snapshot = BubbleSimulation.snapshot

    def recorder(simulation, *args, **kwargs):
        payload = snapshot(simulation, *args, **kwargs)
        samples, breath = [], []
        for index, bubble in enumerate(simulation._bubbles):
            key = id(bubble)
            if key not in identities or identities[key][0] is not bubble:
                identities[key] = (bubble, len(identities))
            track = identities[key][1]
            x, y, radius, alpha = payload[0][index * 4:index * 4 + 4]
            samples.append((track, x, y, radius, alpha, bubble.popping, bubble.exiting, bubble.is_big,
                            bubble.reaches_surface))
            mature = alpha > 0.999 and not bubble.popping and not bubble.exiting and not bubble.promoted
            breath.append((track, radius / bubble.radius, bool(bubble.is_big), bool(mature)))
        frames.append({"samples": samples, "breath": breath,
                       "world_scale": float(getattr(simulation, "_world_scale", 1.0)),
                       "domain": (float(simulation._domain_w), float(simulation._domain_h))})
        return payload

    configure = driver._configure

    def configured(controller, *args, **kwargs):
        configure(controller, *args, **kwargs)
        if drawn_world is not None:
            controller.set_drawn_world_extent(drawn_world)   # the owner's display-wide commit edge
        model = controller.settings_model
        resolved.update(stream=model.bubble_stream_direction, drift=model.bubble_drift_direction,
                        big=int(model.bubble_big_count), small=int(model.bubble_small_count))

    with patch.object(BubbleSimulation, "snapshot", recorder), patch.object(driver, "_configure", configured):
        result = driver.replay_clip(clip, "bubble", preset=preset, viewport_extent=card, snapshots_at=snapshots_at)
    if snapshots is not None:
        snapshots.update(result["snapshots"])
    if len(frames) != len(clip.frames):
        raise RuntimeError("Bubble replay did not observe one snapshot per input frame")
    return frames, [frame.timestamp_us / 1e6 for frame in clip.frames], resolved


def breathing(frames, times, *, min_seconds: float = 2.0):
    from .bubble_breathing_continuity import mature_segments, segment_metrics, summarize

    series: dict[int, list] = {}
    for frame, t in zip(frames, times):
        for track, ratio, large, mature in frame["breath"]:
            series.setdefault(track, []).append((t, ratio, large, mature))
    cadence = median(b - a for a, b in zip(times, times[1:]))
    rows = [m for samples in series.values() for segment in mature_segments(samples, min_seconds, cadence)
            if (m := segment_metrics(segment)) is not None]
    return summarize(rows)


def music_envelope(clip):
    """(time s, RMS dBFS) of each frame's newest 1024 captured samples (None where a frame has no capture)."""
    import numpy as np

    origin = clip.frames[0].timestamp_us
    out = []
    for frame in clip.frames:
        history = frame.capture_history
        if history is None:
            continue
        pcm = np.frombuffer(history.pcm_f32le, "<f4").astype(np.float64)[-1024:]
        if not pcm.size:
            continue
        out.append(((frame.timestamp_us - origin) / 1e6, 20.0 * math.log10(max(1e-6, float(np.sqrt(np.mean(pcm * pcm)))))))
    return out


def speed_series(frames, times, extent, *, bin_s: float = 0.5):
    """Median along-axis speed per ``bin_s`` (canonical-card pixels against the bubbles' own size, both axes)."""
    from .bubble_shape_invariance import CANONICAL, reference_px

    ref = reference_px(extent, frames[-1]["world_scale"])
    to_canon = CANONICAL[1] / ref
    previous, bins = {}, {}
    origin = times[0]
    for index, frame in enumerate(frames):
        current = {}
        for track, x, y, _r, alpha, popping, exiting, _big, _surface in frame["samples"]:
            current[track] = (x * extent[0], y * extent[1], alpha >= 0.99 and not popping and not exiting)
            before = previous.get(track)
            if before is None or not before[2] or not current[track][2] or index == 0:
                continue
            dt = times[index] - times[index - 1]
            if dt > 0.0:
                speed = math.hypot(current[track][0] - before[0], current[track][1] - before[1]) / dt * to_canon
                bins.setdefault(int((times[index] - origin) / bin_s), []).append(speed)
        previous = current
    return [((key + 0.5) * bin_s, median(values)) for key, values in sorted(bins.items())]


def ratio_series(frames, times):
    origin = times[0]
    return [((t - origin), median(r for _track, r, big, mature in frame["breath"] if big and mature))
            for frame, t in zip(frames, times)
            if any(big and mature for _track, _r, big, mature in frame["breath"])]


def drawn_radii(snapshots, frames, times, presentation, frame_dir: Path | None = None):
    """Bubble's big heroes as drawn: each sampled snapshot on its drawn card (``presentation``) through the production
    render host, offscreen; each mature big hero then drawn alone on the same card and its ring's outer radius read
    from the pixels it changed against the card drawn empty. One row per hero and frame: drawn outer radius in device
    pixels, the renderer's own projection of its payload and nominal radius (``bubble_presentation_layout``), and the
    drawn card's content size. ``frame_dir``: the full frames are kept there as PNG."""
    from dataclasses import replace

    import numpy as np
    from PIL import Image

    from rendering.quick.visualizer.implementations.bubble import bubble_presentation_layout
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.transition_contact_sheet import TransitionCapture

    outer_x, outer_y, outer_w, outer_h = presentation.outer_rect
    size = (int(round(outer_w)), int(round(outer_h)))
    cx0, cy0, content_w, content_h = presentation.content_rect
    cx0, cy0 = cx0 - outer_x, cy0 - outer_y
    dpr = float(presentation.dpr)
    target = TransitionCapture(int(round(outer_w * dpr)), int(round(outer_h * dpr)))   # device pixels
    host = QuickVisualizerRenderHost()
    rows = []
    origin = times[0]
    try:
        def draw(snapshot, state):
            logical = replace(snapshot.logical, mode_state=state)
            rgba, _ms = _draw(host, target, replace(snapshot, logical=logical), size, size)
            return rgba

        for index in sorted(snapshots):
            snapshot = replace(snapshots[index], presentation=presentation)
            state = snapshot.logical.mode_state
            layout = bubble_presentation_layout(presentation, (cx0, cy0, content_w, content_h), state.world_scale)
            px_per_unit = layout.response_radius_scale * content_h * dpr
            whole = draw(snapshot, state)
            if frame_dir is not None:
                Image.fromarray(whole).convert("RGB").save(frame_dir / f"frame_{index:05d}.png")
            words = len(state.big_class_bits)       # 4, or more on a raised-capacity candidate
            empty = replace(state, positions=(), extras=(), trails=(), bubble_count=0, big_class_bits=(0,) * words,
                            ambient_points=(), ambient_occluders=())
            background = draw(snapshot, empty).astype(np.int16)
            for i, ((track, _x, _y, radius, _a, *_rest), (_t, ratio, large, mature)) in enumerate(
                    zip(frames[index]["samples"], frames[index]["breath"])):
                if not (large and mature) or ratio <= 0.0:
                    continue
                alone = replace(empty, positions=state.positions[4 * i:4 * i + 4],
                                extras=state.extras[4 * i:4 * i + 4], bubble_count=1,
                                big_class_bits=(1,) + (0,) * (words - 1))
                changed = np.abs(draw(snapshot, alone).astype(np.int16) - background).max(axis=2) > 24
                ys, xs = np.nonzero(changed)
                if not len(xs):
                    continue
                left, right, top, bottom = xs.min(), xs.max(), ys.min(), ys.max()
                lo_x, lo_y = cx0 * dpr, cy0 * dpr
                hi_x, hi_y = (cx0 + content_w) * dpr - 1, (cy0 + content_h) * dpr - 1
                if left <= lo_x + 1 or top <= lo_y + 1 or right >= hi_x - 1 or bottom >= hi_y - 1:
                    continue  # clipped by the card's edge: its extent is not its radius
                drawn = ((right - left + 1) + (bottom - top + 1)) / 4.0
                rows.append({"t": times[index] - origin, "track": track, "drawn_px": float(drawn),
                             "projected_px": radius * px_per_unit, "nominal_px": radius / ratio * px_per_unit,
                             "content_px": (content_w * dpr, content_h * dpr)})
    finally:
        host.release_resources()
        target.close()
    return rows


def drawn_frames(snapshots, presentation, *, width: int):
    """Each snapshot (index order) on its drawn card through the production render host, offscreen, downscaled to
    ``width`` pixels across (for motion sheets)."""
    from dataclasses import replace

    from PIL import Image

    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.extruded_bubble_capture import _draw
    from tools.transition_contact_sheet import TransitionCapture

    _x, _y, outer_w, outer_h = presentation.outer_rect
    size = (int(round(outer_w)), int(round(outer_h)))
    dpr = float(presentation.dpr)
    target = TransitionCapture(int(round(outer_w * dpr)), int(round(outer_h * dpr)))
    host = QuickVisualizerRenderHost()
    images = []
    try:
        for index in sorted(snapshots):
            rgba, _ms = _draw(host, target, replace(snapshots[index], presentation=presentation), size, size)
            image = Image.fromarray(rgba).convert("RGB")
            images.append(image.resize((width, round(image.height * width / image.width)), Image.LANCZOS))
    finally:
        host.release_resources()
        target.close()
    return images


def moment_sheet(output: Path, sampled, stamps, moments, names, labels, clearest=None) -> None:
    """One column per moment (the nearest drawn frame): each run's kept frame stacked at one width. ``clearest``:
    that run's frames at the moments are also kept alone at full size (``moment_<run>_<t>s.png``)."""
    import shutil

    from PIL import Image

    width, columns = 1280, []
    for moment in moments:
        index = min(sampled, key=lambda i: abs(stamps[i] - moment))
        if clearest is not None:
            shutil.copyfile(output / f"frames_{clearest}" / f"frame_{index:05d}.png",
                            output / f"moment_{clearest}_{stamps[index]:.1f}s.png")
        tiles = []
        for name in names:
            image = Image.open(output / f"frames_{name}" / f"frame_{index:05d}.png").convert("RGB")
            image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
            tiles.append(_labelled(image, f"{labels.get(name, name)}  t={stamps[index]:.1f}s"))
        column = Image.new("RGB", (width, sum(t.height for t in tiles) + 8 * (len(tiles) - 1)), (0, 0, 0))
        y = 0
        for tile in tiles:
            column.paste(tile, (0, y))
            y += tile.height + 8
        columns.append(column)
    sheet = Image.new("RGB", (sum(c.width for c in columns) + 12 * (len(columns) - 1),
                              max(c.height for c in columns)), (0, 0, 0))
    x = 0
    for column in columns:
        sheet.paste(column, (x, 0))
        x += column.width + 12
    sheet.save(output / "moments.png")


def _labelled(image, text):
    from PIL import ImageDraw

    out = image.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle((0, 0, 8 + 7 * len(text), 18), fill=(0, 0, 0))
    draw.text((4, 3), text, fill=(240, 240, 240))
    return out


def _p10_p90(values):
    ordered = sorted(values)
    return ordered[int(0.1 * (len(ordered) - 1))], ordered[int(0.9 * (len(ordered) - 1))]


def drawn_summary(rows, *, min_samples: int = 4):
    """The drawn reaction: per frame, a hero's drawn radius over its own nominal drawn size and over the drawn card's
    short side and equal-area side; per hero (``min_samples`` frames or more), the swing (max - min) of those."""
    if not rows:
        return {}
    by_track: dict[int, list] = {}
    for row in rows:
        by_track.setdefault(row["track"], []).append(row)
    short = min(rows[0]["content_px"])
    side = math.sqrt(rows[0]["content_px"][0] * rows[0]["content_px"][1])
    swings_own, swings_short, swings_side = [], [], []
    for samples in by_track.values():
        if len(samples) < min_samples:
            continue
        drawn = [s["drawn_px"] for s in samples]
        swings_own.append((max(drawn) - min(drawn)) / median(s["nominal_px"] for s in samples))
        swings_short.append((max(drawn) - min(drawn)) / short)
        swings_side.append((max(drawn) - min(drawn)) / side)
    return {
        "heroes": len(by_track), "samples": len(rows), "content_px": rows[0]["content_px"],
        "drawn_px_median": median(r["drawn_px"] for r in rows),
        "drawn_over_projected_median": median(r["drawn_px"] / r["projected_px"] for r in rows),
        "drawn_over_nominal_median": median(r["drawn_px"] / r["nominal_px"] for r in rows),
        "drawn_over_nominal_p10_p90": _p10_p90([r["drawn_px"] / r["nominal_px"] for r in rows]),
        "drawn_over_short_side_median": median(r["drawn_px"] / short for r in rows),
        "drawn_over_equal_area_side_median": median(r["drawn_px"] / side for r in rows),
        "swing_over_nominal_median": median(swings_own) if swings_own else None,
        "swing_over_short_side_median": median(swings_short) if swings_short else None,
        "swing_over_equal_area_side_median": median(swings_side) if swings_side else None,
    }


def plot(path: Path, music, curves: dict, ratios: dict, title: str, drawn: dict | None = None) -> None:
    from PIL import Image, ImageDraw

    width, panel, pad = 1600, 220, 60
    colours = {"card": (80, 170, 255), "display_wide": (255, 170, 60), "before": (230, 70, 70),
               "candidate_A": (120, 220, 120), "candidate_B": (200, 120, 230), "candidate_C": (240, 240, 120)}
    panels = 4 if drawn else 3
    image = Image.new("RGB", (width, pad + panels * (panel + pad)), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    draw.text((pad, 15), title, fill=(230, 230, 230))
    duration = max([t for t, _ in music] + [t for c in curves.values() for t, _ in c] + [1.0])

    def lines(top, series_by_name, label, lo=None, hi=None):
        values = [v for series in series_by_name.values() for _t, v in series]
        if not values:
            return
        lo = min(values) if lo is None else lo
        hi = max(values) if hi is None else hi
        hi = hi if hi > lo else lo + 1.0
        draw.rectangle((pad, top, width - pad, top + panel), outline=(70, 70, 80))
        draw.text((pad + 6, top + 4), f"{label}  [{lo:.2f} .. {hi:.2f}]", fill=(200, 200, 200))
        for index, (name, series) in enumerate(series_by_name.items()):
            colour = colours.get(name, (200, 200, 200))
            points = [(pad + (width - 2 * pad) * t / duration, top + panel - panel * (v - lo) / (hi - lo))
                      for t, v in series]
            if len(points) > 1:
                draw.line(points, fill=colour, width=2)
            draw.text((width - pad - 160, top + 4 + 14 * index), name, fill=colour)

    lines(pad + 20, {"music": [(t, max(-60.0, v)) for t, v in music]}, "music RMS dBFS (newest 1024 samples)",
          lo=-60.0)
    lines(pad + 20 + panel + pad, ratios, "big bubbles: median displayed / nominal radius (breathing)")
    lines(pad + 20 + 2 * (panel + pad), curves, "median speed, canonical px/s against own size (0.5 s bins)", lo=0.0)
    if drawn:
        lines(pad + 20 + 3 * (panel + pad), drawn,
              "drawn: big heroes' median drawn outer radius / own nominal drawn radius (device px, offscreen)")
    image.save(path)


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    from .extruded_bubble_forensics import load_clip
    from .bubble_shape_invariance import measure

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clip", type=Path, required=True, help="a recording (.jsonl)")
    parser.add_argument("--output", type=artifact_paths.evidence_arg, required=True, help="a new evidence folder")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--preset", type=int, default=0, help="curated preset index (0-based)")
    parser.add_argument("--card", default="1204x144", help="the card's committed world, WxH")
    parser.add_argument("--display", default="2560x1440", help="the display's logical size, WxH")
    parser.add_argument("--render-fps", type=float, default=0.0,
                        help="also draw the two cards offscreen at this many frames per second of the take and "
                             "measure the big heroes' drawn radii in device pixels (0: logical frames only)")
    parser.add_argument("--card-scale", type=float, default=1.0, help="the card's uniform visual scale (drawn only)")
    parser.add_argument("--dpr", type=float, default=1.0, help="the display's device pixel ratio (drawn only)")
    parser.add_argument("--candidates", default="",
                        help="NAME:P:DENSITY,... also replay display-wide with CANDIDATE capacity zooms "
                             "(needed/capacity)**P (production 0.5), DENSITY count|area|mid (candidate_world_resolver); "
                             "tool-only comparisons, never product")
    parser.add_argument("--moments", default="", help="seconds of the take, comma-separated: a sheet of the card, "
                                                      "display-wide and each candidate at each (needs --render-fps)")
    parser.add_argument("--motion", default="", help="START,SECONDS: an animated WebP of display-wide beside the "
                                                     "candidates over that span of the take")
    parser.add_argument("--motion-fps", type=float, default=24.0)
    parser.add_argument("--clearest", default="", help="a candidate whose moments and motion are also kept alone at "
                                                       "full size")
    args = parser.parse_args()
    candidates = {}
    for item in filter(None, args.candidates.split(",")):
        name, exponent, density = item.split(":")
        candidates[f"candidate_{name}"] = (float(exponent), density)
    if args.motion and not candidates:
        parser.error("--motion compares display-wide with candidates: give --candidates")
    if args.render_fps > 0.0 or args.motion:
        from PySide6.QtGui import QGuiApplication
        QCoreApplication.instance() or QGuiApplication([])
    else:
        QCoreApplication.instance() or QCoreApplication([])
    card, display = _size(args.card), _size(args.display)
    ordinary_drawn, wide_drawn = drawn_presentations(card, display, scale=args.card_scale, dpr=args.dpr)
    wide = tuple(float(v) for v in wide_drawn.viewport_extent)
    clip = load_clip(args.clip, args.seconds)
    args.output.mkdir(parents=True, exist_ok=False)
    stamps = [(frame.timestamp_us - clip.frames[0].timestamp_us) / 1e6 for frame in clip.frames]

    def every(start, stop, fps):
        out, next_t = [], start
        for index, t in enumerate(stamps):
            if start <= t < stop and t >= next_t:
                out.append(index)
                next_t += 1.0 / fps
        return out

    sampled = every(2.0, float("inf"), args.render_fps) if args.render_fps > 0.0 else []   # past the cold start
    motion = []
    if args.motion:
        start, span = (float(v) for v in args.motion.split(","))
        motion = every(start, start + span, args.motion_fps)
    snaps = {"card": {}, "display_wide": {}}
    card_frames, times, resolved = observe(clip, card, preset=args.preset, snapshots_at=sampled,
                                           snapshots=snaps["card"])
    wide_frames, wide_times, _ = observe(clip, card, preset=args.preset, drawn_world=wide,
                                         snapshots_at=sorted({*sampled, *motion}), snapshots=snaps["display_wide"])
    if wide_times != times:
        raise RuntimeError("the two replays published different frame times")
    runs = {"card": (card_frames, card), "display_wide": (wide_frames, wide), "before": (card_frames, wide)}
    for name, candidate in candidates.items():
        snaps[name] = {}
        cand_frames, cand_times, _ = observe(clip, card, preset=args.preset, drawn_world=wide,
                                             snapshots_at=sorted({*sampled, *motion}), snapshots=snaps[name],
                                             candidate=candidate)
        if cand_times != times:
            raise RuntimeError("a candidate replay published different frame times")
        runs[name] = (cand_frames, wide)

    def drawing(name):
        """The candidate's raised capacity while it is drawn (an ExitStack; empty for production runs)."""
        from contextlib import ExitStack

        stack = ExitStack()
        if name in candidates and candidates[name][1] != "count":
            raised_logical_capacity(stack, CANDIDATE_CAPACITY)
            raised_render_capacity(stack, CANDIDATE_CAPACITY)
        return stack
    report = {"clip": str(args.clip), "seconds": args.seconds, "preset": args.preset, "card": card,
              "display": display, "display_wide_world": wide, "stream": resolved.get("stream"),
              "drift": resolved.get("drift"), "runs": {}}
    curves, ratios = {}, {}
    for name, (frames, extent) in runs.items():
        stats = measure(frames, times, extent, resolved)
        stats["domain"] = frames[-1]["domain"]
        if name != "before":
            stats["breathing"] = breathing(frames, times)
            ratios[name] = ratio_series(frames, times)
        report["runs"][name] = stats
        curves[name] = speed_series(frames, times, extent)
    base = report["runs"]["card"]
    report["candidates"] = {name: {"exponent": c[0], "density": c[1]} for name, c in candidates.items()}
    for name in report["runs"]:
        if name == "card":
            continue
        row = report["runs"][name]
        report["runs"][name]["relative_to_card"] = {
            key: row[key] / base[key] - 1.0 for key in ("speed_median", "speed_x_median", "speed_y_median",
                                                       "stream_along_median", "radius_big_median",
                                                       "density_per_canonical_card")
            if base[key] and math.isfinite(base[key]) and math.isfinite(row[key])}
    drawn_series = {}
    if sampled:
        drawn_runs = [("card", card_frames, ordinary_drawn), ("display_wide", wide_frames, wide_drawn)]
        drawn_runs += [(name, runs[name][0], wide_drawn) for name in candidates]
        for name, frames, presentation in drawn_runs:
            frame_dir = args.output / f"frames_{name}"
            frame_dir.mkdir()
            with drawing(name):
                rows = drawn_radii({i: snaps[name][i] for i in sampled}, frames, times, presentation, frame_dir)
            report["runs"][name]["drawn"] = drawn_summary(rows)
            (args.output / f"drawn_{name}.json").write_text(json.dumps(rows) + "\n", encoding="utf-8")
            per_t: dict[float, list] = {}
            for row in rows:
                per_t.setdefault(row["t"], []).append(row["drawn_px"] / row["nominal_px"])
            drawn_series[name] = [(t, median(v)) for t, v in sorted(per_t.items())]
        from widgets.spotify_visualizer import bubble_viewport_profile as profile
        from widgets.spotify_visualizer.bubble_viewport_profile import resolve_bubble_world, scale_bubble_population

        authored = (resolved["big"], resolved["small"])

        def targets(world):
            # scale_bubble_population's rounding without its 110 cap (the raised candidates hold up to 256).
            with patch.object(profile, "BUBBLE_RENDER_CAPACITY", CANDIDATE_CAPACITY):
                big, small = scale_bubble_population(*authored, world.population_scale)
            return {"big": big, "small": small, "live": big + small}

        report["live_targets"] = {"card": targets(resolve_bubble_world(card, authored_population=sum(authored))),
                                  "display_wide": targets(resolve_bubble_world(wide,
                                                                               authored_population=sum(authored)))}
        meaning = {"count": "today's count", "area": "today's density", "mid": "count halfway"}
        labels = {"card": "card",
                  "display_wide": f"fullscreen now: zoom {runs['display_wide'][0][-1]['world_scale']:.2f}, "
                                  f"{report['live_targets']['display_wide']['live']} heroes"}
        for name, (exponent, density) in candidates.items():
            world = candidate_world_resolver(exponent, density)(wide, authored_population=sum(authored))
            report["live_targets"][name] = targets(world)   # area/mid: before any capacity cap (raised to 256 here)
            labels[name] = (f"{name.removeprefix('candidate_')}: zoom {world.world_scale:.2f}, "
                            f"{report['live_targets'][name]['live']} heroes ({meaning[density]})")
        report["labels"] = labels
        if args.moments:
            moment_sheet(args.output, sampled, stamps, [float(v) for v in args.moments.split(",")],
                         [name for name, *_rest in drawn_runs], labels,
                         clearest=f"candidate_{args.clearest}" if args.clearest else None)
    if motion:
        from PIL import Image

        width = 800
        names = ["display_wide", *candidates]
        panes = {}
        for name in names:
            with drawing(name):
                panes[name] = drawn_frames({i: snaps[name][i] for i in motion}, wide_drawn, width=width)
        columns = 2
        rows_n = math.ceil(len(names) / columns)
        pictures = []
        for frame_index in range(len(motion)):
            height = panes[names[0]][frame_index].height
            frame = Image.new("RGB", (columns * width + 8 * (columns - 1), rows_n * height + 8 * (rows_n - 1)),
                              (0, 0, 0))
            for slot, name in enumerate(names):
                frame.paste(_labelled(panes[name][frame_index], labels[name]),
                            ((slot % columns) * (width + 8), (slot // columns) * (height + 8)))
            pictures.append(frame)
        pictures[0].save(args.output / "motion_current_vs_candidates.webp", save_all=True,
                         append_images=pictures[1:], duration=round(1000 / args.motion_fps), loop=0, quality=75,
                         method=4)
        if args.clearest:
            name = f"candidate_{args.clearest}"
            with drawing(name):
                alone = drawn_frames({i: snaps[name][i] for i in motion}, wide_drawn, width=1280)
            alone = [_labelled(image, labels[name]) for image in alone]
            alone[0].save(args.output / f"motion_{name}.webp", save_all=True, append_images=alone[1:],
                          duration=round(1000 / args.motion_fps), loop=0, quality=80, method=4)
    (args.output / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    music = music_envelope(clip)
    plot(args.output / "response.png", music, curves, ratios,
         f"Bubble card {card[0]:g}x{card[1]:g} vs display-wide {wide[0]:.0f}x{wide[1]:.0f} on "
         f"{display[0]:g}x{display[1]:g}; {Path(args.clip).name} first {args.seconds:g} s, preset index {args.preset}",
         drawn=drawn_series)
    for name, row in report["runs"].items():
        line = {k: round(v, 3) for k, v in row.items() if k in ("zoom", "world_scale", "speed_median",
                                                                 "stream_along_median", "radius_big_median",
                                                                 "density_per_canonical_card", "visible_mean")}
        print(name, line, {k: f"{100 * v:+.1f}%" for k, v in row.get("relative_to_card", {}).items()})
        if "breathing" in row:
            print("   breathing", row["breathing"])
        if row.get("drawn"):
            print("   drawn", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in row["drawn"].items()})
    print("->", args.output)


if __name__ == "__main__":
    main()

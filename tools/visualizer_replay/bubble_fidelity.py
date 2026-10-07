"""Offline, identity-preserving Bubble observations and frame-aligned A/B evidence.

The observer wraps the production snapshot only inside a replay. It adds no
runtime IDs, telemetry, timers or work to the product. Object references are kept
for the replay so a retired bubble's Python ID cannot identify a later birth.
"""
from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left
from dataclasses import asdict
import hashlib
import json
from unittest.mock import patch

from .driver import replay_clip


def replay_bubbles(clip, *, settings=None):
    from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation, BubbleState

    observations, identities, resolved_settings = [], {}, {}
    snapshot = BubbleSimulation.snapshot
    # Presentation history must not be mistaken for authored simulation state.
    physics_fields = tuple(name for name in BubbleState.__dataclass_fields__
                           if name not in ("display_radius", "size_gate_energy"))

    def observe(simulation, *args, **kwargs):
        payload = snapshot(simulation, *args, **kwargs)
        samples = []
        for index, bubble in enumerate(simulation._bubbles):
            identity = id(bubble)
            if identity not in identities:
                identities[identity] = (bubble, len(identities))
            x, y, radius, alpha = payload[0][index * 4:index * 4 + 4]
            samples.append({
                "track": identities[identity][1], "x": x, "y": y,
                "radius": radius, "alpha": alpha,
                "big": bubble.is_big, "promoted": bubble.promoted,
                "popping": bubble.popping, "exiting": bubble.exiting,
                "physics": tuple(getattr(bubble, name) for name in physics_fields),
                "authority_height": simulation._viewport_profile.height,
            })
        observations.append(samples)
        return payload

    # Capture the exact resolved configuration, including a curated preset's
    # values, without adding another Settings resolver to the diagnostic.
    from . import driver
    configure = driver._configure

    def configure_and_record(controller, *args, **kwargs):
        configure(controller, *args, **kwargs)
        resolved_settings.update(asdict(controller.settings_model))

    with patch.object(BubbleSimulation, "snapshot", observe), patch.object(driver, "_configure", configure_and_record):
        result = replay_clip(clip, "bubble", settings=settings)
    if len(observations) != len(clip.frames):
        raise RuntimeError("Bubble replay did not observe exactly one snapshot per input frame")
    return result, observations, resolved_settings


def tracks(observations):
    result = defaultdict(list)
    for frame, samples in enumerate(observations):
        for sample in samples:
            result[sample["track"]].append((frame, sample))
    return result


def radius_response(samples, *, px_per_unit):
    """Absolute frame indices; no lag search or time alignment can hide a delay.

    First change is radius movement from this window's baseline, not a causal
    audio-response claim in an already moving continuous musical passage.
    """
    values = [sample["radius"] * px_per_unit for _frame, sample in samples]
    if not values:
        return None
    first = next((frame for (frame, _sample), value in zip(samples, values)
                  if abs(value - values[0]) > 1e-9), None)
    signs = [(index, 1 if right > left else -1)
             for index, (left, right) in enumerate(zip(values, values[1:]))
             if abs(right - left) > 1e-9]
    # A turn is the first frame moving in the new direction, not the preceding extremum.
    turns = [samples[right[0] + 1][0] for left, right in zip(signs, signs[1:]) if left[1] != right[1]]
    return {
        "first_radius_change_frame": first,
        "peak_frame": samples[values.index(max(values))][0],
        "trough_frame": samples[values.index(min(values))][0],
        "peak_px": max(values), "trough_px": min(values),
        "excursion_px": max(values) - min(values), "turn_frames": turns,
    }


def _compact_response(response):
    """Keep timing fingerprints and a small preview, not repeated huge turn lists."""
    turns = response["turn_frames"]
    return {**{key: value for key, value in response.items() if key != "turn_frames"},
            "turn_count": len(turns), "turn_frames_preview": turns[:20],
            "turn_frames_sha256": hashlib.sha256(json.dumps(turns).encode()).hexdigest()}


def response_windows(clip):
    """One-second input-anchored windows around starts, hits and level rises.

    A 0.1 normalised upward level edge is a diagnostic selector, not a product
    default or an acceptance tolerance. The full-clip per-track responses are
    retained separately, so ramps and unselected passages remain observable.
    """
    starts = {0}
    previous = 0.0
    for index, frame in enumerate(clip.frames):
        level = frame.energy.bubble.overall
        real = frame.real
        if ((level > 0.02 and previous <= 0.02) or level - previous >= 0.1
                or frame.energy.transient.onset_detected
                or (real is not None and (real.events or real.onsets))):
            starts.add(index)
        previous = level
    timestamps = [frame.timestamp_us for frame in clip.frames]
    # Linear moving endpoint; long recordings do not need a quadratic scan.
    end = 0
    for start in sorted(starts):
        end = max(end, start + 1)
        while end < len(timestamps) and timestamps[end] - timestamps[start] <= 1_000_000:
            end += 1
        yield start, end


def compare_observations(clip, off, on, *, px_per_unit, tiny_max_px=8.0):
    off_tracks, on_tracks = tracks(off), tracks(on)
    counts = defaultdict(int)
    maximum_error = 0.0
    examples = []
    for frame, (left, right) in enumerate(zip(off, on)):
        left_by_id = {sample["track"]: sample for sample in left}
        right_by_id = {sample["track"]: sample for sample in right}
        if left_by_id.keys() != right_by_id.keys():
            counts["identity_mismatch_frames"] += 1
            continue
        for identity, raw in left_by_id.items():
            assisted = right_by_id[identity]
            counts["samples"] += 1
            if raw["physics"] != assisted["physics"]:
                counts["physics_changed_samples"] += 1
            raw_px = raw["radius"] * px_per_unit
            on_px = assisted["radius"] * px_per_unit
            error = abs(on_px - raw_px)
            maximum_error = max(maximum_error, error)
            if error <= 1e-9:
                continue
            counts["changed_radius_samples"] += 1
            if (raw_px > tiny_max_px or raw["big"] or raw["promoted"] or raw["popping"] or raw["exiting"]):
                counts["outside_radius_or_lifecycle_changed_samples"] += 1
            if error > 1.0 + 1e-9:
                counts["over_one_pixel_samples"] += 1
            if (raw_px < 4.0) != (on_px < 4.0):
                counts["representation_changed_samples"] += 1
            if len(examples) < 20:
                examples.append({"frame": frame, "track": identity, "off_px": raw_px, "on_px": on_px})
    if len(off) != len(on):
        counts["identity_mismatch_frames"] += abs(len(off) - len(on))

    responses, reaction_examples = [], []
    windows = [(None, 0, len(clip.frames)), *((start, max(0, start - 1), end)
                for start, end in response_windows(clip))]
    for identity in sorted(off_tracks.keys() & on_tracks.keys()):
        left, right = off_tracks[identity], on_tracks[identity]
        left_frames, right_frames = [row[0] for row in left], [row[0] for row in right]
        for trigger, start, end in windows:
            left_window = left[bisect_left(left_frames, start):bisect_left(left_frames, end)]
            right_window = right[bisect_left(right_frames, start):bisect_left(right_frames, end)]
            if len(left_window) < 2 or [row[0] for row in left_window] != [row[0] for row in right_window]:
                continue
            # A bubble born after the trigger is a birth, not reaction-latency evidence.
            if trigger is not None and left_window[0][0] > max(0, trigger - 1):
                continue
            raw_response = radius_response(left_window, px_per_unit=px_per_unit)
            on_response = radius_response(right_window, px_per_unit=px_per_unit)
            if trigger is not None:
                counts["reaction_windows"] += 1
                for field in ("first_radius_change_frame", "peak_frame", "trough_frame", "turn_frames"):
                    if raw_response[field] != on_response[field]:
                        counts[field + "_changed_windows"] += 1
                if abs(raw_response["excursion_px"] - on_response["excursion_px"]) > 1e-9:
                    counts["excursion_changed_windows"] += 1
            if trigger is None or (raw_response != on_response and len(reaction_examples) < 20):
                row = {"track": identity, "trigger_frame": trigger,
                       "start_frame": start, "end_frame": end,
                       "off": _compact_response(raw_response), "on": _compact_response(on_response)}
                (responses if trigger is None else reaction_examples).append(row)
    return {"counts": dict(counts), "max_radius_error_px": maximum_error,
            "changed_examples": examples, "responses": responses,
            "reaction_examples": reaction_examples,
            "simulation_viewport_heights": sorted({sample["authority_height"] for row in off for sample in row})}


def settings_digest(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

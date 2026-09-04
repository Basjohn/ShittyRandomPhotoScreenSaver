"""Production-shaped standalone threaded Qt Quick runtime lifecycle smoke."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

from rendering.quick.bootstrap import (
    configure_quick_environment,
    configure_quick_graphics,
)


# Fix process-owned Quick environment before importing Qt.
configure_quick_environment()

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QEvent,
    QObject,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QScreen,
)
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface  # noqa: E402

from rendering.quick.image_boundary import capture_qimage  # noqa: E402
from rendering.quick.image_state import PresentationImage  # noqa: E402
from rendering.quick.render import RenderNodeSnapshot, RenderNodeTelemetry  # noqa: E402
from rendering.quick.render.background_node import (  # noqa: E402
    TRANSITION_DENSE_SAMPLE_AXIS_COUNT,
)
from rendering.quick.runtime import QuickDisplayRuntime  # noqa: E402
from rendering.quick.scene_controller import (  # noqa: E402
    QuickSceneController,
    QuickSceneFactory,
)
from rendering.quick.state import QuickWindowPolicy  # noqa: E402
from rendering.quick.transitions import (  # noqa: E402
    TransitionCompletion,
    TransitionRequest,
    TransitionRun,
)
from rendering.quick.window import QuickDisplayWindow  # noqa: E402


_TRANSITION_IDS = (
    "crossfade",
    "slide",
    "wipe",
    "warp_dissolve",
    "block_flip",
    "block_spins",
)
_TRANSITION_SMOKE_DIRECTIONS = {
    "crossfade": (None,),
    "slide": ("left", "right", "up", "down"),
    "wipe": (
        "left_to_right",
        "right_to_left",
        "top_to_bottom",
        "bottom_to_top",
        "diag_tl_br",
        "diag_tr_bl",
    ),
    "warp_dissolve": (None,),
    "block_flip": (
        "left",
        "right",
        "up",
        "down",
        "diag_tl_br",
        "diag_tr_bl",
    ),
    "block_spins": (
        "left",
        "right",
        "up",
        "down",
        "diag_tl_br",
        "diag_tr_bl",
    ),
}
_TRANSITION_DIRECTION_CHOICES = tuple(
    sorted(
        {
            direction
            for directions in _TRANSITION_SMOKE_DIRECTIONS.values()
            for direction in directions
            if direction is not None
        }
    )
)
# The shared sparse grid the geometry-precise transition oracles are tuned to.
# Do not change: block_spins/block_flip encode 5x5 geometry (divmod(index, 5)).
_SAMPLE_FRACTIONS = (1.0 / 12.0, 0.25, 0.5, 0.75, 11.0 / 12.0)
_TRANSITION_SAMPLE_COORDINATES = tuple(
    (sample_x, 1.0 - readback_y)
    for readback_y in _SAMPLE_FRACTIONS
    for sample_x in _SAMPLE_FRACTIONS
)
# The dense midpoint grid, mirroring the render node's dense readback exactly so
# each dense colour lines up with its coordinate. Consumed only by the Phase-C
# effect oracles (see qtquick_phase_c_effect_smoke), never by the geometry
# oracles above.
_DENSE_SAMPLE_FRACTIONS = tuple(
    (index + 0.5) / TRANSITION_DENSE_SAMPLE_AXIS_COUNT
    for index in range(TRANSITION_DENSE_SAMPLE_AXIS_COUNT)
)
_TRANSITION_DENSE_SAMPLE_COORDINATES = tuple(
    (sample_x, 1.0 - readback_y)
    for readback_y in _DENSE_SAMPLE_FRACTIONS
    for sample_x in _DENSE_SAMPLE_FRACTIONS
)
# Transition ids whose midpoint oracle consumes the dense grid. Populated by the
# Phase-C effect smoke wrapper via _install_contract.
_DENSE_MIDPOINT_TRANSITION_IDS: set[str] = set()
_DIRECTIONAL_PALETTE_RGB = {
    "initial": (
        (12, 32, 120),
        (16, 48, 145),
        (20, 64, 170),
        (24, 80, 195),
        (28, 96, 220),
        (32, 112, 235),
    ),
    "replacement": (
        (120, 24, 12),
        (145, 32, 16),
        (170, 40, 20),
        (195, 48, 24),
        (220, 56, 28),
        (235, 64, 32),
    ),
}
_TRANSITION_PALETTE_RGB = {
    "crossfade": {
        "initial": (
            (16, 52, 120),
            (22, 108, 184),
            (28, 168, 192),
            (64, 188, 128),
            (154, 206, 72),
            (230, 220, 54),
        ),
        "replacement": (
            (212, 40, 52),
            (230, 82, 42),
            (236, 132, 36),
            (206, 66, 132),
            (150, 54, 176),
            (92, 60, 188),
        ),
    },
    "slide": _DIRECTIONAL_PALETTE_RGB,
    "wipe": _DIRECTIONAL_PALETTE_RGB,
    "warp_dissolve": _DIRECTIONAL_PALETTE_RGB,
    "block_flip": _DIRECTIONAL_PALETTE_RGB,
    "block_spins": _DIRECTIONAL_PALETTE_RGB,
}
_TRANSITION_SMOKE_PARAMETERS = {
    # Thirteen strips place the fixed 5x5 sample grid on both projected faces
    # and exposed voids during the first eligible midpoint frame.
    "block_flip": {"cols": 13, "rows": 13},
}
_TRANSITION_PIXEL_PROBES = {
    "block_spins": (0.42, 0.50, 0.60),
}
_TRANSITION_SMOKE_DURATIONS_MS = {
    "block_spins": 600,
}


@dataclass
class _WindowProbe:
    index: int
    generation: int
    screen_name: str
    runtime: QuickDisplayRuntime
    window: QuickDisplayWindow
    scene: QuickSceneController
    telemetry: RenderNodeTelemetry
    qml_object_name: str
    qml_runtime_role: str
    qml_screen_index: int
    qml_runtime_generation: int | None
    target_geometry: tuple[int, int, int, int]
    qml_root_identity: int
    proof_progress_on_construction: float
    presentation_state_replayed: bool
    replayed_from_generation: int | None
    presentation_image: PresentationImage
    replacement_image: PresentationImage
    retired_proof_progress: float | None = None
    initial_capture: dict[str, Any] | None = None
    resized_capture: dict[str, Any] | None = None
    replacement_capture: dict[str, Any] | None = None
    initial_scene_state: dict[str, object] | None = None
    hide_show_cycles: list[dict[str, Any]] = field(default_factory=list)
    topology_loss_events: list[dict[str, Any]] = field(default_factory=list)
    display_identity_events: list[dict[str, Any]] = field(default_factory=list)
    transition_run_id: int | None = None
    transition_run: TransitionRun | None = None
    transition_state_at_start: dict[str, object] | None = None
    transition_completion: dict[str, object] | None = None
    stale_transition_rejected: bool = False


def _parse_size(value: str) -> QSize:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if width < 64 or height < 64:
        raise argparse.ArgumentTypeError("size must be at least 64x64")
    return QSize(width, height)


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--hide-show-cycles", type=int, default=0)
    parser.add_argument("--exit-via-input", action="store_true")
    parser.add_argument("--topology-recreate", action="store_true")
    parser.add_argument("--size", type=_parse_size, default=QSize(480, 270))
    parser.add_argument("--phase-delay-ms", type=int, default=350)
    parser.add_argument(
        "--transition-id",
        choices=_TRANSITION_IDS,
        default="crossfade",
    )
    parser.add_argument(
        "--transition-direction",
        choices=_TRANSITION_DIRECTION_CHOICES,
    )
    parser.add_argument(
        "--slide-motion-style",
        choices=("Linear", "Elastic", "Wobble", "Flex"),
        default="Linear",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.windows < 1:
        parser.error("--windows must be positive")
    if not 1 <= args.generations <= 3:
        parser.error("--generations must be between 1 and 3")
    if not 0 <= args.hide_show_cycles <= 3:
        parser.error("--hide-show-cycles must be between 0 and 3")
    if args.exit_via_input and args.generations != 1:
        parser.error("--exit-via-input requires exactly one generation")
    if args.topology_recreate and (
        args.windows != 2
        or args.generations != 3
        or args.hide_show_cycles != 0
        or args.exit_via_input
    ):
        parser.error(
            "--topology-recreate requires --windows 2 --generations 3 "
            "without hide/show or input-exit scenarios"
        )
    if not 100 <= args.phase_delay_ms <= 5000:
        parser.error("--phase-delay-ms must be between 100 and 5000")
    allowed_directions = _TRANSITION_SMOKE_DIRECTIONS[args.transition_id]
    if args.transition_direction is None:
        args.transition_direction = allowed_directions[0]
    elif args.transition_direction not in allowed_directions:
        parser.error(
            f"--transition-direction {args.transition_direction!r} is invalid for "
            f"{args.transition_id}"
        )
    if args.transition_id != "slide" and args.slide_motion_style != "Linear":
        parser.error("--slide-motion-style applies only to --transition-id slide")
    return args


def _capture_from_snapshot(snapshot: RenderNodeSnapshot) -> dict[str, Any]:
    return {
        "size": list(snapshot.render_target_size),
        "viewport": list(snapshot.viewport),
        "device_pixel_ratio": float(snapshot.device_pixel_ratio),
        "sample_count": int(snapshot.pixel_sample_count),
        "colors": sorted(set(snapshot.sample_colors)),
        "ordered_colors": list(snapshot.sample_colors),
        "active_image_identity": snapshot.active_image_identity,
        "image_upload_count": int(snapshot.image_upload_count),
        "image_release_count": int(snapshot.image_release_count),
    }


def _argb_components(color: object) -> tuple[int, int, int, int]:
    text = str(color)
    if len(text) != 9 or not text.startswith("#"):
        raise ValueError(f"invalid ARGB sample: {text!r}")
    return tuple(int(text[index : index + 2], 16) for index in (1, 3, 5, 7))


def _matches_crossfade_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    _direction: object = None,
    *,
    tolerance: int = 4,
) -> bool:
    if not all(isinstance(value, (tuple, list)) for value in (
        source,
        destination,
        midpoint,
    )):
        return False
    if not source or len(source) != len(destination) or len(source) != len(midpoint):
        return False
    amount = max(0.0, min(1.0, float(progress)))
    for old_color, new_color, mixed_color in zip(
        source,
        destination,
        midpoint,
        strict=True,
    ):
        old = _argb_components(old_color)
        new = _argb_components(new_color)
        mixed = _argb_components(mixed_color)
        expected = tuple(
            round(old_channel * (1.0 - amount) + new_channel * amount)
            for old_channel, new_channel in zip(old, new, strict=True)
        )
        if any(
            abs(actual - target) > tolerance
            for actual, target in zip(mixed, expected, strict=True)
        ):
            return False
    return True


def _slide_color_domain(color: object) -> str | None:
    _alpha, red, _green, blue = _argb_components(color)
    if blue - red >= 48:
        return "source"
    if red - blue >= 48:
        return "destination"
    return None


def _matches_slide_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if not source or not destination or not midpoint or not 0.0 < progress < 1.0:
        return False
    if len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False
    direction_text = str(direction)
    if direction_text not in {"left", "right", "up", "down"}:
        return False

    compared = 0
    expected_domains: set[str] = set()
    for color, (sample_x, sample_y) in zip(
        midpoint,
        _TRANSITION_SAMPLE_COORDINATES,
        strict=True,
    ):
        axis = sample_x if direction_text in {"left", "right"} else sample_y
        boundary = 1.0 - progress if direction_text in {"left", "up"} else progress
        if abs(axis - boundary) <= 0.025:
            continue
        if direction_text in {"left", "up"}:
            destination_owns = axis >= boundary
        else:
            destination_owns = axis < boundary
        expected = "destination" if destination_owns else "source"
        expected_domains.add(expected)
        if _slide_color_domain(color) != expected:
            return False
        compared += 1
    return compared >= 16 and expected_domains == {"source", "destination"}


_WIPE_AXES = {
    "left_to_right": lambda x, y: x,
    "right_to_left": lambda x, y: 1.0 - x,
    "top_to_bottom": lambda x, y: y,
    "bottom_to_top": lambda x, y: 1.0 - y,
    "diag_tl_br": lambda x, y: (x + y) * 0.5,
    "diag_tr_bl": lambda x, y: ((1.0 - x) + y) * 0.5,
}


def _matches_wipe_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if not source or not destination or not midpoint or not 0.0 < progress < 1.0:
        return False
    if len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False
    axis_for = _WIPE_AXES.get(str(direction))
    if axis_for is None:
        return False

    compared = 0
    expected_domains: set[str] = set()
    for color, (sample_x, sample_y) in zip(
        midpoint,
        _TRANSITION_SAMPLE_COORDINATES,
        strict=True,
    ):
        axis = axis_for(sample_x, sample_y)
        if abs(axis - progress) <= 0.025:
            continue
        expected = "destination" if axis < progress else "source"
        expected_domains.add(expected)
        if _slide_color_domain(color) != expected:
            return False
        compared += 1
    return compared >= 16 and expected_domains == {"source", "destination"}


def _matches_warp_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    _direction: object = None,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        not source
        or len(source) != len(destination)
        or len(source) != len(midpoint)
        or len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES)
        or not 0.35 <= progress <= 0.65
    ):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False

    # The centre has fully dissolved by this stage in the canonical shader.
    # A plain Crossfade would still be purple here, so this is a strong real
    # Warp-vs-fallback discriminator in addition to the spatial samples below.
    centre_index = len(midpoint) // 2
    if _slide_color_domain(midpoint[centre_index]) != "destination":
        return False

    materially_non_crossfade = 0
    largest_error = 0
    amount = max(0.0, min(1.0, float(progress)))
    for old_color, new_color, warped_color in zip(
        source,
        destination,
        midpoint,
        strict=True,
    ):
        old = _argb_components(old_color)
        new = _argb_components(new_color)
        warped = _argb_components(warped_color)
        crossfade = tuple(
            round(old_channel * (1.0 - amount) + new_channel * amount)
            for old_channel, new_channel in zip(old, new, strict=True)
        )
        error = max(
            abs(actual - fallback)
            for actual, fallback in zip(warped, crossfade, strict=True)
        )
        largest_error = max(largest_error, error)
        if error >= 18:
            materially_non_crossfade += 1
    return materially_non_crossfade >= 8 and largest_error >= 48


def _block_flip_expected_sample(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
) -> tuple[str, tuple[float, float] | None] | None:
    """Mirror the slab projection far from anti-aliased face boundaries."""

    x, y = coordinate
    direction_text = str(direction)
    cols = float(_TRANSITION_SMOKE_PARAMETERS["block_flip"]["cols"])
    rows = float(_TRANSITION_SMOKE_PARAMETERS["block_flip"]["rows"])
    if direction_text == "left":
        strip_axis, strip_count = x, cols
        strip_basis = (1.0, 0.0)
    elif direction_text == "right":
        strip_axis, strip_count = 1.0 - x, cols
        strip_basis = (-1.0, 0.0)
    elif direction_text == "down":
        strip_axis, strip_count = y, rows
        strip_basis = (0.0, 1.0)
    elif direction_text == "up":
        strip_axis, strip_count = 1.0 - y, rows
        strip_basis = (0.0, -1.0)
    elif direction_text == "diag_tl_br":
        strip_axis = (x + y) * 0.5
        strip_count = max(cols, rows)
        strip_basis = (1.0, 1.0)
    elif direction_text == "diag_tr_bl":
        strip_axis = ((1.0 - x) + y) * 0.5
        strip_count = max(cols, rows)
        strip_basis = (-1.0, 1.0)
    else:
        return None

    scaled_axis = min(max(strip_axis, 0.0), 0.999999) * strip_count
    strip_index = math.floor(scaled_axis)
    strip_local = scaled_axis - strip_index
    order = strip_index / max(1.0, strip_count - 1.0)
    start = 0.03 + order * 0.64
    local_linear = max(0.0, min(1.0, (progress - start) / 0.33))
    if local_linear <= 0.0:
        return "source", coordinate
    if local_linear >= 1.0:
        return "destination", coordinate

    local_turn = 0.5 - 0.5 * math.cos(local_linear * math.pi)
    face_scale = abs(math.cos(local_turn * math.pi))
    distance = abs(strip_local - 0.5)
    half_width = 0.5 * face_scale
    boundary_margin = 0.04
    if distance > half_width + boundary_margin:
        return "void", None
    if distance < max(0.0, half_width - boundary_margin):
        shows_destination = local_turn >= 0.5
        face_local = (strip_local - 0.5) / max(face_scale, 0.0001) + 0.5
        if shows_destination:
            face_local = 1.0 - face_local
        axis_delta = (face_local - strip_local) / strip_count
        sample_uv = (
            min(1.0, max(0.0, x + strip_basis[0] * axis_delta)),
            min(1.0, max(0.0, y + strip_basis[1] * axis_delta)),
        )
        return (
            "destination" if shows_destination else "source",
            sample_uv,
        )
    return None


def _block_flip_color_domain(color: object) -> str | None:
    _alpha, red, green, blue = _argb_components(color)
    if max(red, green, blue) <= 14:
        return "void"
    if blue - red >= 16:
        return "source"
    if red - blue >= 16:
        return "destination"
    return None


def _block_flip_decoded_uv(
    color: object,
    domain: str,
) -> tuple[float, float] | None:
    """Decode the 2D coordinate fixture independently of slab lighting."""

    _alpha, red, green, blue = _argb_components(color)
    if domain == "source" and blue > 0:
        return (
            ((red / blue) * 220.0 - 32.0) / 96.0,
            ((green / blue) * 220.0 - 32.0) / 96.0,
        )
    if domain == "destination" and red > 0:
        return (
            ((green / red) * 220.0 - 32.0) / 96.0,
            ((blue / red) * 220.0 - 32.0) / 96.0,
        )
    return None


def _matches_block_flip_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        not source
        or len(source) != len(destination)
        or len(source) != len(midpoint)
        or len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES)
        or not 0.35 <= progress <= 0.75
    ):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False

    counts = {"source": 0, "destination": 0, "void": 0}
    compared = 0
    projected_faces = 0
    for color, coordinate in zip(
        midpoint,
        _TRANSITION_SAMPLE_COORDINATES,
        strict=True,
    ):
        expected = _block_flip_expected_sample(
            direction,
            progress,
            coordinate,
        )
        if expected is None:
            continue
        expected_domain, expected_uv = expected
        if _block_flip_color_domain(color) != expected_domain:
            return False
        if expected_uv is not None:
            actual_uv = _block_flip_decoded_uv(color, expected_domain)
            if actual_uv is None or any(
                abs(actual - target) > 0.11
                for actual, target in zip(actual_uv, expected_uv, strict=True)
            ):
                return False
            if any(
                abs(target - original) >= 0.035
                for target, original in zip(
                    expected_uv,
                    coordinate,
                    strict=True,
                )
            ):
                projected_faces += 1
        counts[expected_domain] += 1
        compared += 1
    # The flip is proven by projected faces (rotated UVs displaced from the raw
    # coordinate) plus the per-sample domain/UV checks above. An absolute void
    # count is intentionally NOT required: exposed inter-strip void is only
    # sampled by the sparse grid within a ~0.03 progress window (0.35..0.38),
    # narrower than one 60 Hz frame step, so a coarse-cadence display cannot land
    # in it. Void is still verified per-sample wherever the model predicts it, so
    # a flat fullscreen fallback (proj_faces == 0, or void mismatch where
    # expected) still fails.
    return bool(
        compared >= 12
        and counts["source"] >= 2
        and counts["destination"] >= 2
        and projected_faces >= 2
    )


# Ambiguous band just outside the slab silhouette where the authored white edge
# rim and anti-aliasing bleed into the void; samples here are skipped rather than
# asserted as clean void (observed rim extent ~1.086 on the 60 Hz early probe).
_BLOCK_SPIN_EDGE_MARGIN = 0.14

_BLOCK_SPIN_DIRECTION_STATES = {
    "left": (0, 1.0),
    "right": (0, -1.0),
    "up": (1, 1.0),
    "down": (1, -1.0),
    "diag_tl_br": (2, 1.0),
    "diag_tr_bl": (3, -1.0),
}


def _block_spin_progress(progress: float) -> float:
    value = max(0.0, min(1.0, float(progress)))
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def _block_spin_rotation(
    axis_mode: int,
    angle: float,
) -> tuple[tuple[float, float, float], ...]:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    if axis_mode == 0:
        return (
            (cosine, 0.0, -sine),
            (0.0, 1.0, 0.0),
            (sine, 0.0, cosine),
        )
    if axis_mode == 1:
        return (
            (1.0, 0.0, 0.0),
            (0.0, cosine, sine),
            (0.0, -sine, cosine),
        )
    inverse_root_two = 1.0 / math.sqrt(2.0)
    axis = (
        (inverse_root_two, -inverse_root_two, 0.0)
        if axis_mode == 2
        else (inverse_root_two, inverse_root_two, 0.0)
    )
    x, y, z = axis
    one_minus_cosine = 1.0 - cosine
    return (
        (
            cosine + x * x * one_minus_cosine,
            x * y * one_minus_cosine - z * sine,
            x * z * one_minus_cosine + y * sine,
        ),
        (
            y * x * one_minus_cosine + z * sine,
            cosine + y * y * one_minus_cosine,
            y * z * one_minus_cosine - x * sine,
        ),
        (
            z * x * one_minus_cosine - y * sine,
            z * y * one_minus_cosine + x * sine,
            cosine + z * z * one_minus_cosine,
        ),
    )


def _block_spin_expected_sample(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
) -> tuple[str, tuple[float, float] | None] | None:
    state = _BLOCK_SPIN_DIRECTION_STATES.get(str(direction))
    if state is None:
        return None
    axis_mode, spin_direction = state
    spin = _block_spin_progress(progress)
    angle = math.pi * spin * spin_direction
    rotation = _block_spin_rotation(axis_mode, angle)
    face_z = 0.0 if spin < 0.5 else -0.05
    screen_x, screen_y = coordinate
    projected_x = screen_x * 2.0 - 1.0
    projected_y = 1.0 - screen_y * 2.0
    target_x = projected_x - rotation[0][2] * face_z
    target_y = projected_y - rotation[1][2] * face_z
    determinant = (
        rotation[0][0] * rotation[1][1]
        - rotation[0][1] * rotation[1][0]
    )
    if abs(determinant) < 0.04:
        return None
    object_x = (
        target_x * rotation[1][1] - rotation[0][1] * target_y
    ) / determinant
    object_y = (
        rotation[0][0] * target_y - target_x * rotation[1][0]
    ) / determinant
    extent = max(abs(object_x), abs(object_y))
    # Skip an ambiguous band on BOTH sides of the slab silhouette (extent 1.0):
    # inside (0.86..1.0) the projected face edge, and outside (1.0..1.0+margin)
    # the authored white edge rim + anti-aliasing bleed into the void. Only
    # samples clearly beyond the rim assert clean "void"; faces (extent <= 0.86)
    # still assert domain + UV. This makes the coarse 60 Hz early-probe frame
    # (slab edge crossing a sample column) robust without weakening the geometry.
    if extent >= 1.0 + _BLOCK_SPIN_EDGE_MARGIN:
        return "void", None
    if extent > 0.86:
        return None

    u = object_x * 0.5 + 0.5
    v = object_y * 0.5 + 0.5
    if spin < 0.5:
        return "source", (u, 1.0 - v)
    if axis_mode == 0:
        destination_uv = (1.0 - u, 1.0 - v)
    elif axis_mode == 1:
        destination_uv = (u, v)
    elif axis_mode == 2:
        destination_uv = (1.0 - v, u)
    else:
        destination_uv = (v, 1.0 - u)
    return "destination", destination_uv


def _matches_block_spins_samples(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    direction: object,
) -> bool:
    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        not source
        or len(source) != len(destination)
        or len(source) != len(midpoint)
        or len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES)
        or not 0.30 <= progress <= 0.75
    ):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False

    counts = {"source": 0, "destination": 0, "void": 0}
    compared = 0
    for color, coordinate in zip(
        midpoint,
        _TRANSITION_SAMPLE_COORDINATES,
        strict=True,
    ):
        expected = _block_spin_expected_sample(direction, progress, coordinate)
        if expected is None:
            continue
        expected_domain, expected_uv = expected
        actual_domain = _block_flip_color_domain(color)
        if actual_domain != expected_domain:
            return False
        if expected_uv is not None:
            actual_uv = _block_flip_decoded_uv(color, expected_domain)
            if actual_uv is None or any(
                abs(actual - target) > 0.13
                for actual, target in zip(actual_uv, expected_uv, strict=True)
            ):
                return False
        counts[expected_domain] += 1
        compared += 1
    visible_domain = "source" if _block_spin_progress(progress) < 0.5 else "destination"
    # This face-proving check (early: source, late: destination) verifies the
    # correct textured face and its rotated UVs. It intentionally does NOT
    # require an absolute void count: the two probe frames drift toward face-on
    # (spin -> 0 / -> 1) on coarse-cadence displays, where the slab legitimately
    # exposes no void. Void is proven independently by the edge-on middle probe
    # (visible_indices) and the generic midpoint oracle; and any sample the model
    # DOES predict as void is still checked per-sample above, so a fullscreen
    # fallback (no void where the model expects it, or wrong rotated UVs) still
    # fails.
    return bool(compared >= 9 and counts[visible_domain] >= 3)


def _matches_block_spins_midpoint(
    source: object,
    destination: object,
    midpoint: object,
    progress: float,
    _direction: object,
) -> bool:
    """Keep the generic first-midpoint check cadence-tolerant.

    The nearest-target probe sequence below owns exact projection/UV checks.
    This uncontrolled first sample only proves that the real slab exposes its
    black void instead of silently drawing a fullscreen fallback.
    """

    if not all(
        isinstance(value, (tuple, list))
        for value in (source, destination, midpoint)
    ):
        return False
    if (
        len(source) != len(_TRANSITION_SAMPLE_COORDINATES)
        or len(destination) != len(_TRANSITION_SAMPLE_COORDINATES)
        or len(midpoint) != len(_TRANSITION_SAMPLE_COORDINATES)
        or not 0.30 <= progress <= 0.75
    ):
        return False
    if {_slide_color_domain(color) for color in source} != {"source"}:
        return False
    if {_slide_color_domain(color) for color in destination} != {"destination"}:
        return False
    black = sum(
        max(_argb_components(color)[1:]) <= 14 for color in midpoint
    )
    face_or_edge = len(midpoint) - black
    return bool(
        black >= 1
        and face_or_edge >= 3
        and tuple(midpoint) != tuple(source)
        and tuple(midpoint) != tuple(destination)
    )


def _matches_block_spins_probe_sequence(
    source: object,
    destination: object,
    progresses: object,
    samples: object,
    direction: object,
) -> bool:
    if not isinstance(progresses, (tuple, list)) or not isinstance(
        samples,
        (tuple, list),
    ):
        return False
    if len(progresses) != 3 or len(samples) != 3:
        return False
    early_progress, edge_progress, late_progress = (
        float(progress) for progress in progresses
    )
    if not (
        0.34 <= early_progress < 0.50
        and 0.44 <= edge_progress <= 0.56
        and 0.52 < late_progress < 0.76
    ):
        return False
    if not _matches_block_spins_samples(
        source,
        destination,
        samples[0],
        early_progress,
        direction,
    ):
        return False
    if not _matches_block_spins_samples(
        source,
        destination,
        samples[2],
        late_progress,
        direction,
    ):
        return False

    edge_colors = tuple(samples[1])
    if len(edge_colors) != len(_TRANSITION_SAMPLE_COORDINATES):
        return False
    visible_indices = tuple(
        index
        for index, color in enumerate(edge_colors)
        if max(_argb_components(color)[1:]) > 14
    )
    if not visible_indices:
        # A scheduler can land exactly on the edge-on frame.  The authored
        # unlit side may then be indistinguishable from the surrounding black
        # void for one direction; the early/late probes still prove both
        # projected faces and their texture coordinates.
        return abs(edge_progress - 0.5) <= 0.03
    if not 3 <= len(visible_indices) <= 13:
        return False
    direction_text = str(direction)
    diagonal_core = 0
    for index in visible_indices:
        row, column = divmod(index, 5)
        if direction_text in {"left", "right"} and abs(column - 2) > 1:
            return False
        if direction_text in {"up", "down"} and abs(row - 2) > 1:
            return False
        if direction_text == "diag_tl_br":
            distance = abs(row + column - 4)
            if distance > 2:
                return False
            diagonal_core += int(distance <= 1)
        if direction_text == "diag_tr_bl":
            distance = abs(row - column)
            if distance > 2:
                return False
            diagonal_core += int(distance <= 1)
    return bool(
        direction_text not in {"diag_tl_br", "diag_tr_bl"}
        or diagonal_core >= 3
    )


_TRANSITION_MIDPOINT_ORACLES = {
    "crossfade": _matches_crossfade_samples,
    "slide": _matches_slide_samples,
    "wipe": _matches_wipe_samples,
    "warp_dissolve": _matches_warp_samples,
    "block_flip": _matches_block_flip_samples,
    "block_spins": _matches_block_spins_midpoint,
}
_TRANSITION_PROBE_ORACLES = {
    "block_spins": _matches_block_spins_probe_sequence,
}


def _presentation_image(
    *,
    screen_index: int,
    generation: int,
    variant: str,
    transition_id: str,
) -> PresentationImage:
    if transition_id in {"block_flip", "block_spins"}:
        image = QImage(32, 24, QImage.Format.Format_RGBA8888)
        for x in range(image.width()):
            normalized_x = x / max(1, image.width() - 1)
            for y in range(image.height()):
                normalized_y = y / max(1, image.height() - 1)
                if variant == "initial":
                    color = QColor(
                        round(32 + 96 * normalized_x),
                        round(32 + 96 * normalized_y),
                        220,
                    )
                else:
                    color = QColor(
                        220,
                        round(32 + 96 * normalized_x),
                        round(32 + 96 * normalized_y),
                    )
                image.setPixelColor(x, y, color)
        return capture_qimage(
            image,
            identity=(
                f"quick-smoke:g{generation}:screen{screen_index}:variant:{variant}"
            ),
            source_path=f"synthetic://quick-smoke/{variant}",
        )

    colors = tuple(
        QColor(*rgb)
        for rgb in _TRANSITION_PALETTE_RGB[transition_id][variant]
    )
    image = QImage(12, 8, QImage.Format.Format_RGBA8888)
    for x in range(image.width()):
        base = colors[min(len(colors) - 1, x // 2)]
        for y in range(image.height()):
            color = base if y >= image.height() // 2 else base.lighter(145)
            image.setPixelColor(x, y, color)
    return capture_qimage(
        image,
        identity=(
            f"quick-smoke:g{generation}:screen{screen_index}:variant:{variant}"
        ),
        source_path=f"synthetic://quick-smoke/{variant}",
    )


def _snapshot_dict(snapshot: RenderNodeSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


class _SmokeRunner(QObject):
    def __init__(self, app: QGuiApplication, args: argparse.Namespace) -> None:
        super().__init__()
        self._app = app
        self._args = args
        self._probes: list[_WindowProbe] = []
        self._initial_snapshots: list[RenderNodeSnapshot] = []
        self._reports: list[dict[str, Any]] = []
        self._errors: list[str] = []
        self._scene_factory = QuickSceneFactory(self)
        self._generation = 0
        self._completed_generations = 0
        self._retired_runtime_ids: set[int] = set()
        self._cycle_token = 0
        self._hide_show_cycle = 0
        self._active_hide_records: dict[int, dict[str, Any]] = {}
        self._visibility_deadline = 0.0
        self._retirement_started = False
        self._exit_request_count = 0
        self._exit_retirement_scheduled = False
        self._exit_sequence: dict[str, Any] | None = None
        self._report_finished = False
        self._pending_runtime_root_ids: set[int] = set()
        self._destroyed_runtime_root_ids: set[int] = set()
        self._runtime_root_destruction_barriers: list[dict[str, Any]] = []
        self._active_runtime_root_barrier: dict[str, Any] | None = None
        self._presentation_state_by_screen_key: dict[str, dict[str, Any]] = {}
        self._topology_generations: list[dict[str, Any]] = []
        self._topology_replacements: list[dict[str, Any]] = []
        self._active_topology_generation: dict[str, Any] | None = None
        self._topology_displacement: dict[str, Any] | None = None

    def start(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            self._finish_with_error("Qt reported no physical screens")
            return
        if self._args.topology_recreate and len(screens) < 2:
            self._finish_with_error(
                "topology recreate requires two physical QScreens"
            )
            return
        window_count = min(self._args.windows, len(screens))
        if window_count < self._args.windows:
            print(
                f"[QUICK-A2] requested={self._args.windows} available={len(screens)} "
                f"using={window_count}",
                flush=True,
            )
        self._window_count = window_count
        self._start_generation()

    def _start_generation(self) -> None:
        if self._generation > 0 and self._runtime_root_destruction_barriers:
            previous_barrier = self._runtime_root_destruction_barriers[-1]
            previous_barrier["next_generation_started"] = True
            previous_barrier["next_generation_started_after_crossing"] = bool(
                previous_barrier.get("crossed")
            )
        self._cycle_token += 1
        token = self._cycle_token
        self._probes = []
        self._initial_snapshots = []
        self._retired_runtime_ids = set()
        self._hide_show_cycle = 0
        self._active_hide_records = {}
        self._retirement_started = False
        self._exit_retirement_scheduled = False
        self._pending_runtime_root_ids = set()
        self._destroyed_runtime_root_ids = set()
        self._active_runtime_root_barrier = None
        current_screens = list(QGuiApplication.screens())
        selected_indices = self._selected_screen_indices()
        missing_indices = [
            index for index in selected_indices if index >= len(current_screens)
        ]
        if missing_indices:
            self._errors.append(
                f"generation{self._generation} cannot bind physical screens "
                f"{missing_indices}; available={len(current_screens)}"
            )
            self._finish_report()
            return
        self._current_screen_by_index = {
            index: current_screens[index] for index in selected_indices
        }
        try:
            for position, index in enumerate(selected_indices):
                screen = self._current_screen_by_index[index]
                self._probes.append(
                    self._create_window(
                        index,
                        screen,
                        generation=self._generation,
                        accepts_focus=position == 0,
                    )
                )
        except Exception as exc:
            self._errors.append(
                f"generation{self._generation} construction failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._finish_report()
            return

        self._record_topology_generation(selected_indices)

        # Construct the complete display generation before any native window
        # is shown, matching production multi-display ownership ordering.
        for probe in self._probes:
            if probe.window.screen() is not self._current_screen_by_index[probe.index]:
                self._errors.append(
                    f"generation{self._generation} screen{probe.index} "
                    "was not bound before show"
                )
            probe.runtime.show_on_screen()
            probe.window.setGeometry(*probe.target_geometry)
            probe.window.update()
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_initial(token))

    def _create_window(
        self,
        index: int,
        screen: QScreen,
        *,
        generation: int,
        accepts_focus: bool,
    ) -> _WindowProbe:
        telemetry = RenderNodeTelemetry(
            gui_thread_id=threading.get_ident(),
            capture_pixels=True,
            transition_probe_progresses=_TRANSITION_PIXEL_PROBES.get(
                self._args.transition_id,
                (),
            ),
        )
        runtime = QuickDisplayRuntime(
            screen_index=index,
            runtime_generation=generation,
            screen=screen,
            scene_factory=self._scene_factory,
            window_policy=QuickWindowPolicy(
                always_on_top=False,
                accepts_focus=accepts_focus,
                blank_cursor=False,
            ),
            telemetry=telemetry,
            parent=self,
        )
        runtime.retirement_completed.connect(
            lambda retired_generation, runtime=runtime: self._on_runtime_retired(
                runtime,
                retired_generation,
            )
        )
        if self._args.exit_via_input:
            runtime.exit_requested.connect(
                lambda runtime=runtime: self._on_runtime_exit_requested(runtime)
            )
        window = runtime.window
        window.setColor(QColor("#080b14"))

        size: QSize = self._args.size
        geometry = screen.availableGeometry()
        x = geometry.x() + max(0, (geometry.width() - size.width()) // 2)
        y = geometry.y() + max(0, (geometry.height() - size.height()) // 2)
        target_geometry = (x, y, size.width(), size.height())
        window.setGeometry(*target_geometry)

        scene = runtime.scene_controller
        screen_key = runtime.display_identity.screen_key
        saved_state = self._presentation_state_by_screen_key.get(screen_key)
        if saved_state is None:
            proof_progress = 0.36 + (0.08 * index)
            replayed_from_generation = None
        else:
            proof_progress = float(saved_state["proof_progress"])
            replayed_from_generation = int(saved_state["generation"])
        scene.set_background_proof_progress(proof_progress)
        presentation_image = _presentation_image(
            screen_index=index,
            generation=generation,
            variant="initial",
            transition_id=self._args.transition_id,
        )
        replacement_image = _presentation_image(
            screen_index=index,
            generation=generation,
            variant="replacement",
            transition_id=self._args.transition_id,
        )
        runtime.set_presentation_image(presentation_image)
        scene_root = scene.scene_root
        probe = _WindowProbe(
            index=index,
            generation=generation,
            screen_name=screen.name(),
            runtime=runtime,
            window=window,
            scene=scene,
            telemetry=telemetry,
            qml_object_name=scene_root.objectName(),
            qml_runtime_role=str(scene_root.property("runtimeRole")),
            qml_screen_index=int(scene_root.property("screenIndex")),
            qml_runtime_generation=scene_root.property("runtimeGeneration"),
            target_geometry=target_geometry,
            qml_root_identity=id(scene_root),
            proof_progress_on_construction=proof_progress,
            presentation_state_replayed=saved_state is not None,
            replayed_from_generation=replayed_from_generation,
            presentation_image=presentation_image,
            replacement_image=replacement_image,
        )
        runtime.topology_loss_detected.connect(
            lambda loss, probe=probe: probe.topology_loss_events.append(
                loss.as_dict()
            )
        )
        runtime.display_identity_changed.connect(
            lambda identity, probe=probe: probe.display_identity_events.append(
                identity.as_dict()
            )
        )
        return probe

    def _selected_screen_indices(self) -> list[int]:
        if not self._args.topology_recreate:
            return list(range(self._window_count))
        topology_plan = ([0, 1], [1], [0, 1])
        return list(topology_plan[self._generation])

    def _record_topology_generation(self, selected_indices: list[int]) -> None:
        if not self._args.topology_recreate:
            return
        generation_record = {
            "generation": self._generation,
            "selected_screen_indices": list(selected_indices),
            "construction_after_completed_generations": self._completed_generations,
            "construction_after_root_barriers": sum(
                1
                for barrier in self._runtime_root_destruction_barriers
                if barrier.get("crossed")
            ),
            "screens": [
                {
                    "screen_index": probe.index,
                    "screen_key": probe.runtime.display_identity.screen_key,
                    "display_identity": probe.runtime.display_identity.as_dict(),
                    "window_object_name": probe.window.objectName(),
                    "qml_runtime_generation": probe.qml_runtime_generation,
                    "proof_progress_on_construction": (
                        probe.proof_progress_on_construction
                    ),
                    "presentation_state_replayed": (
                        probe.presentation_state_replayed
                    ),
                    "replayed_from_generation": probe.replayed_from_generation,
                    "retired_proof_progress": None,
                }
                for probe in self._probes
            ],
            "retirement_complete": False,
            "runtime_root_barrier_crossed": False,
        }
        if self._topology_generations:
            previous = self._topology_generations[-1]
            old_keys = {
                screen["screen_key"] for screen in previous["screens"]
            }
            new_keys = {
                screen["screen_key"] for screen in generation_record["screens"]
            }
            self._topology_replacements.append(
                {
                    "from_generation": previous["generation"],
                    "to_generation": self._generation,
                    "old_screen_keys": sorted(old_keys),
                    "new_screen_keys": sorted(new_keys),
                    "removed_screen_keys": sorted(old_keys - new_keys),
                    "added_screen_keys": sorted(new_keys - old_keys),
                    "old_generation_retired": previous["retirement_complete"],
                    "old_runtime_root_barrier_crossed": previous[
                        "runtime_root_barrier_crossed"
                    ],
                    "replayed_screen_keys": sorted(
                        screen["screen_key"]
                        for screen in generation_record["screens"]
                        if screen["presentation_state_replayed"]
                    ),
                }
            )
        self._active_topology_generation = generation_record
        self._topology_generations.append(generation_record)

    def _capture_initial(self, token: int) -> None:
        if token != self._cycle_token:
            return
        initial_ready = all(
            probe.runtime.scene_readiness.ready_for_reveal
            and probe.telemetry.snapshot().render_count >= 1
            and probe.telemetry.snapshot().pixel_sample_count >= 1
            and probe.telemetry.snapshot().image_upload_count == 1
            and probe.telemetry.snapshot().active_image_identity
            == probe.presentation_image.identity
            for probe in self._probes
        )
        if not initial_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(10, lambda token=token: self._capture_initial(token))
            return
        if not initial_ready:
            self._errors.append(
                f"generation{self._generation} initial reveal readiness timed out"
            )
        try:
            for probe in self._probes:
                snapshot = probe.telemetry.snapshot()
                probe.initial_capture = _capture_from_snapshot(snapshot)
                probe.initial_scene_state = probe.scene.describe_scene_state()
                self._initial_snapshots.append(snapshot)
                # Re-admit the same immutable identity and force further frames;
                # the render owner must not upload it again.
                probe.runtime.set_presentation_image(probe.presentation_image)
                probe.scene.set_background_proof_progress(0.68)
                probe.window.resize(
                    probe.window.width() + 80,
                    probe.window.height() + 45,
                )
                probe.window.update()
        except Exception as exc:
            self._errors.append(f"initial capture failed: {type(exc).__name__}: {exc}")
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_resized(token))

    def _capture_resized(self, token: int) -> None:
        if token != self._cycle_token:
            return
        resized_ready = len(self._initial_snapshots) == len(self._probes) and all(
            (
                probe.telemetry.snapshot().render_target_size
                != self._initial_snapshots[position].render_target_size
                and probe.telemetry.snapshot().pixel_sample_count
                > self._initial_snapshots[position].pixel_sample_count
                and probe.telemetry.snapshot().image_upload_count
                == self._initial_snapshots[position].image_upload_count
                and probe.telemetry.snapshot().active_image_identity
                == probe.presentation_image.identity
                and probe.runtime.scene_readiness.ready_for_reveal
            )
            for position, probe in enumerate(self._probes)
        )
        if not resized_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(10, lambda token=token: self._capture_resized(token))
            return
        if not resized_ready:
            self._errors.append(
                f"generation{self._generation} resized presentation timed out"
            )
        try:
            for probe in self._probes:
                probe.resized_capture = _capture_from_snapshot(
                    probe.telemetry.snapshot()
                )
                request = TransitionRequest(
                    runtime_generation=probe.generation,
                    transition_id=self._args.transition_id,
                    requested_name=self._args.transition_id,
                    selected_from_random=False,
                    duration_ms=max(
                        _TRANSITION_SMOKE_DURATIONS_MS.get(
                            self._args.transition_id,
                            80,
                        ),
                        min(250, self._args.phase_delay_ms // 2),
                    ),
                    direction=self._args.transition_direction,
                    parameters={
                        "smoke": "c3-transition-renderer",
                        **_TRANSITION_SMOKE_PARAMETERS.get(
                            self._args.transition_id,
                            {},
                        ),
                        **(
                            {"motion_style": self._args.slide_motion_style}
                            if self._args.transition_id == "slide"
                            else {}
                        ),
                    },
                    source_image=probe.presentation_image,
                    destination_image=probe.replacement_image,
                )
                run = probe.runtime.start_transition(
                    request,
                    on_finalized=(
                        lambda completion, probe=probe: (
                            self._on_probe_transition_finalized(
                                probe,
                                completion,
                            )
                        )
                    ),
                )
                probe.transition_run_id = run.run_id
                probe.transition_run = run
                probe.transition_state_at_start = (
                    probe.runtime.transition_controller.describe()
                )
        except Exception as exc:
            self._errors.append(f"resized capture failed: {type(exc).__name__}: {exc}")
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._capture_replacement(token))

    def _capture_replacement(self, token: int) -> None:
        if token != self._cycle_token:
            return
        replacement_ready = all(
            probe.resized_capture is not None
            and probe.telemetry.snapshot().image_upload_count
            == int(probe.resized_capture["image_upload_count"]) + 1
            and probe.telemetry.snapshot().active_image_identity
            == probe.replacement_image.identity
            and probe.telemetry.snapshot().pixel_sample_count
            > int(probe.resized_capture["sample_count"])
            and probe.telemetry.snapshot().sampled_sync_count
            == probe.telemetry.snapshot().sync_count
            and probe.telemetry.snapshot().transition_sample_count >= 1
            and probe.telemetry.snapshot().last_transition_run_id
            == probe.transition_run_id
            and probe.telemetry.snapshot().last_transition_generation
            == probe.generation
            and probe.telemetry.snapshot().last_transition_id
            == self._args.transition_id
            and probe.transition_completion is not None
            and not probe.runtime.transition_controller.is_active
            and probe.scene.background_item.transition_run is None
            and probe.scene.presentation_image == probe.replacement_image
            and probe.runtime.scene_readiness.ready_for_reveal
            for probe in self._probes
        )
        if not replacement_ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(
                10,
                lambda token=token: self._capture_replacement(token),
            )
            return
        if not replacement_ready:
            self._errors.append(
                f"generation{self._generation} replacement image timed out"
            )
        try:
            for probe in self._probes:
                run = probe.transition_run
                probe.stale_transition_rejected = bool(
                    run is not None
                    and not probe.scene.set_transition_run(run)
                    and probe.scene.background_item.transition_run is None
                )
                probe.replacement_capture = _capture_from_snapshot(
                    probe.telemetry.snapshot()
                )
        except Exception as exc:
            self._errors.append(
                f"replacement capture failed: {type(exc).__name__}: {exc}"
            )
        if self._args.topology_recreate and not self._errors:
            self._advance_topology_presentation_state()
            if self._generation == 0:
                self._begin_topology_displacement(token)
                return
        if self._args.hide_show_cycles > 0 and not self._errors:
            self._begin_hide_show_cycle(token)
            return
        self._finish_presentation_sequence(token)

    def _on_probe_transition_finalized(
        self,
        probe: _WindowProbe,
        completion: TransitionCompletion,
    ) -> None:
        if probe.transition_completion is not None:
            self._errors.append(
                f"generation{probe.generation} screen{probe.index} "
                "transition finalized more than once"
            )
            return
        probe.transition_completion = {
            "run_id": completion.run_id,
            "runtime_generation": completion.runtime_generation,
            "outcome": completion.outcome.value,
            "destination_image_identity": (
                completion.destination_image_identity
            ),
            "finalized_at_ns": completion.finalized_at_ns,
            "reason": completion.reason,
        }

    def _begin_hide_show_cycle(self, token: int) -> None:
        if token != self._cycle_token:
            return
        self._active_hide_records = {}
        try:
            for probe in self._probes:
                # This harness deliberately simulates a visualizer pacing
                # consumer without constructing the product visualizer owner.
                # Install the corresponding inert GUI-sync edge explicitly;
                # production visualizer demand remains callback-required.
                probe.runtime.frame_pacer.set_visualizer_sync(lambda: False)
                probe.runtime.frame_pacer.set_visualizer_active(True)
                before = probe.telemetry.snapshot()
                geometry = probe.window.geometry()
                self._active_hide_records[id(probe)] = {
                    "cycle": self._hide_show_cycle,
                    "before": _snapshot_dict(before),
                    "resume_geometry": list(geometry.getRect()),
                }
                probe.runtime.hide()
        except Exception as exc:
            self._errors.append(
                f"hide/show cycle {self._hide_show_cycle} hide failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._retire_generation(token)
            return
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._poll_hidden(token))

    def _poll_hidden(self, token: int) -> None:
        if token != self._cycle_token:
            return
        hidden_ready = True
        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            before = record["before"]
            snapshot = probe.telemetry.snapshot()
            readiness = probe.runtime.scene_readiness
            if (
                probe.window.isVisible()
                or probe.runtime.phase.value != "paused"
                or not readiness.scene_graph_invalidated
                or snapshot.invalidation_count <= before["invalidation_count"]
                or snapshot.release_count <= before["release_count"]
                or snapshot.image_release_count <= before["image_release_count"]
                or snapshot.active_image_identity is not None
                or snapshot.pending_image_release_count != 0
            ):
                hidden_ready = False
                break

        if not hidden_ready:
            if time.monotonic() < self._visibility_deadline:
                QTimer.singleShot(10, lambda token=token: self._poll_hidden(token))
                return
            self._errors.append(
                f"generation{self._generation} hide/show cycle "
                f"{self._hide_show_cycle} did not reach hidden invalidation"
            )
            self._retire_generation(token)
            return

        try:
            for probe in self._probes:
                record = self._active_hide_records[id(probe)]
                record["hidden"] = _snapshot_dict(probe.telemetry.snapshot())
                record["hidden_runtime_state"] = (
                    probe.runtime.describe_runtime_state()
                )
                record["qml_root_preserved_while_hidden"] = (
                    id(probe.scene.scene_root) == probe.qml_root_identity
                )
                probe.runtime.show_on_screen()
                probe.window.setGeometry(*record["resume_geometry"])
                probe.window.update()
        except Exception as exc:
            self._errors.append(
                f"hide/show cycle {self._hide_show_cycle} show failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._retire_generation(token)
            return
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(10, lambda token=token: self._poll_resumed(token))

    def _poll_resumed(self, token: int) -> None:
        if token != self._cycle_token:
            return
        resumed_ready = True
        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            before = record["before"]
            snapshot = probe.telemetry.snapshot()
            if (
                not probe.window.isVisible()
                or probe.runtime.phase.value != "visible"
                or not probe.runtime.scene_readiness.ready_for_reveal
                or snapshot.initialize_count <= before["initialize_count"]
                or snapshot.render_count <= before["render_count"]
                or snapshot.image_upload_count <= before["image_upload_count"]
                or snapshot.active_image_identity
                != probe.replacement_image.identity
                or not probe.runtime.frame_pacer.is_active()
            ):
                resumed_ready = False
                break

        if not resumed_ready:
            if time.monotonic() < self._visibility_deadline:
                QTimer.singleShot(10, lambda token=token: self._poll_resumed(token))
                return
            self._errors.append(
                f"generation{self._generation} hide/show cycle "
                f"{self._hide_show_cycle} did not reach resumed readiness"
            )
            self._retire_generation(token)
            return

        for probe in self._probes:
            record = self._active_hide_records[id(probe)]
            record["resumed"] = _snapshot_dict(probe.telemetry.snapshot())
            record["resumed_capture"] = _capture_from_snapshot(
                probe.telemetry.snapshot()
            )
            record["resumed_runtime_state"] = probe.runtime.describe_runtime_state()
            record["qml_root_preserved_after_resume"] = (
                id(probe.scene.scene_root) == probe.qml_root_identity
            )
            probe.hide_show_cycles.append(record)

        self._hide_show_cycle += 1
        if self._hide_show_cycle < self._args.hide_show_cycles:
            QTimer.singleShot(0, lambda token=token: self._begin_hide_show_cycle(token))
            return
        self._finish_presentation_sequence(token)

    def _finish_presentation_sequence(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if self._args.exit_via_input:
            self._request_exit_via_input(token)
            return
        self._retire_generation(token)

    def _request_exit_via_input(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if not self._probes:
            self._errors.append("input exit requested without an active runtime")
            self._retire_generation(token)
            return

        source = self._probes[0]
        event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        try:
            QCoreApplication.sendEvent(source.window, event)
        except Exception as exc:
            self._errors.append(
                f"input exit dispatch failed: {type(exc).__name__}: {exc}"
            )
            QTimer.singleShot(0, lambda token=token: self._retire_generation(token))
            return

        if self._exit_sequence is not None:
            self._exit_sequence["source_event_accepted"] = event.isAccepted()
        if self._exit_request_count != 1:
            self._errors.append(
                f"input exit emitted {self._exit_request_count} requests instead of one"
            )
            if not self._exit_retirement_scheduled:
                QTimer.singleShot(0, lambda token=token: self._retire_generation(token))

    def _on_runtime_exit_requested(self, runtime: QuickDisplayRuntime) -> None:
        self._exit_request_count += 1
        if all(probe.runtime is not runtime for probe in self._probes):
            self._errors.append("exit request came from a runtime outside the active set")
            return
        if runtime.runtime_generation != self._generation:
            self._errors.append(
                f"stale exit request generation={runtime.runtime_generation} "
                f"current={self._generation}"
            )
            return

        if self._exit_sequence is None:
            self._exit_sequence = {
                "source_screen_index": runtime.screen_index,
                "source_runtime_generation": runtime.runtime_generation,
                "source_event_accepted": False,
                "request_count": self._exit_request_count,
                "runtime_state_at_request": runtime.describe_runtime_state(),
                "runtime_phases_at_request": [
                    probe.runtime.phase.value for probe in self._probes
                ],
                "retirement_deferred": True,
            }
        else:
            self._exit_sequence["request_count"] = self._exit_request_count

        if self._exit_retirement_scheduled:
            return
        self._exit_retirement_scheduled = True
        token = self._cycle_token
        # Leave the QQuickWindow keyPressEvent stack before beginning teardown.
        QTimer.singleShot(0, lambda token=token: self._begin_exit_retirement(token))

    def _begin_exit_retirement(self, token: int) -> None:
        if token != self._cycle_token:
            return
        self._retire_generation(token)
        sequence = self._exit_sequence
        if sequence is None or not self._probes:
            return

        target = self._probes[-1]
        post_close_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        try:
            QCoreApplication.sendEvent(target.window, post_close_event)
        except Exception as exc:
            self._errors.append(
                f"post-close input fence dispatch failed: {type(exc).__name__}: {exc}"
            )
            return
        sequence.update(
            {
                "coordinated_runtime_count": len(self._probes),
                "post_close_event_screen_index": target.index,
                "post_close_event_accepted": post_close_event.isAccepted(),
                "request_count_after_post_close_event": self._exit_request_count,
                "runtime_states_after_admission_close": [
                    probe.runtime.describe_runtime_state() for probe in self._probes
                ],
            }
        )
        if self._exit_request_count != 1:
            self._errors.append(
                "closed Quick input admitted a duplicate exit request"
            )

    def _visibility_timeout_deadline(self) -> float:
        timeout_ms = max(1500, self._args.phase_delay_ms * 8)
        return time.monotonic() + (timeout_ms / 1000.0)

    def _advance_topology_presentation_state(self) -> None:
        """Change per-screen model state so replacement must replay, not default."""

        for probe in self._probes:
            progress = round(
                0.61 + (0.07 * self._generation) + (0.03 * probe.index),
                6,
            )
            probe.scene.set_background_proof_progress(progress)

    def _begin_topology_displacement(self, token: int) -> None:
        """Exercise Qt moving one live window onto another physical screen."""

        if token != self._cycle_token:
            return
        try:
            displaced = next(probe for probe in self._probes if probe.index == 0)
            fallback = next(probe for probe in self._probes if probe.index == 1)
            fallback_screen = self._current_screen_by_index[1]
            # Topology smoke simulates a presentation consumer only; it does
            # not construct the product visualizer owner.
            displaced.runtime.frame_pacer.set_visualizer_sync(lambda: False)
            displaced.runtime.frame_pacer.set_visualizer_active(True)
            self._topology_displacement = {
                "generation": self._generation,
                "displaced_screen_index": displaced.index,
                "fallback_screen_index": fallback.index,
                "expected_identity_before": (
                    displaced.runtime.display_identity.as_dict()
                ),
                "pacer_before": displaced.runtime.frame_pacer.describe(),
                "fallback_refresh_rate_hz": float(fallback_screen.refreshRate()),
                "fallback_window_object_name": fallback.window.objectName(),
            }
            if self._active_topology_generation is not None:
                self._active_topology_generation[
                    "unexpected_screen_displacement"
                ] = self._topology_displacement
            displaced.window.setScreen(fallback_screen)
        except Exception as exc:
            self._errors.append(
                "topology displacement failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._retire_generation(token)
            return
        self._visibility_deadline = self._visibility_timeout_deadline()
        QTimer.singleShot(
            10,
            lambda token=token: self._poll_topology_displacement(token),
        )

    def _poll_topology_displacement(self, token: int) -> None:
        if token != self._cycle_token:
            return
        displaced = next(probe for probe in self._probes if probe.index == 0)
        fallback = next(probe for probe in self._probes if probe.index == 1)
        fallback_screen = self._current_screen_by_index[1]
        runtime_state = displaced.runtime.describe_runtime_state()
        pacer_state = runtime_state.get("frame_pacer", {})
        scene_state = runtime_state.get("scene_readiness", {})
        input_state = runtime_state.get("input", {})
        visible_on_fallback = [
            probe.window.objectName()
            for probe in self._probes
            if probe.window.isVisible() and probe.window.screen() is fallback_screen
        ]
        ready = bool(
            len(displaced.topology_loss_events) == 1
            and displaced.runtime.binding_loss is not None
            and displaced.window.binding_loss is not None
            and not displaced.window.isVisible()
            and displaced.runtime.phase.value == "paused"
            and pacer_state.get("paused")
            and not pacer_state.get("active")
            and pacer_state.get("demands") == ["visualizer"]
            and not input_state.get("admission_open")
            and scene_state.get("scene_graph_invalidated")
            and displaced.window.screen() is fallback_screen
            and visible_on_fallback == [fallback.window.objectName()]
        )
        if not ready and time.monotonic() < self._visibility_deadline:
            QTimer.singleShot(
                10,
                lambda token=token: self._poll_topology_displacement(token),
            )
            return
        if not ready:
            self._errors.append(
                "generation0 displaced runtime did not quiesce on the fallback screen"
            )

        original_loss = displaced.runtime.binding_loss
        displaced.window._on_window_screen_changed(fallback_screen)
        displaced.window._on_window_screen_changed(None)
        duplicate_callbacks_ignored = bool(
            original_loss is not None
            and displaced.runtime.binding_loss is original_loss
            and displaced.window.binding_loss == original_loss
            and len(displaced.topology_loss_events) == 1
        )

        record = self._topology_displacement
        if record is None:
            self._errors.append("topology displacement record was lost")
        else:
            record.update(
                {
                    "topology_loss_signal_count": len(
                        displaced.topology_loss_events
                    ),
                    "topology_loss": (
                        displaced.topology_loss_events[0]
                        if displaced.topology_loss_events
                        else None
                    ),
                    "identity_change_signal_count": len(
                        displaced.display_identity_events
                    ),
                    "duplicate_callbacks_ignored": duplicate_callbacks_ignored,
                    "identity_after_loss": (
                        displaced.runtime.display_identity.as_dict()
                    ),
                    "pacer_after_loss": pacer_state,
                    "runtime_state_after_loss": runtime_state,
                    "actual_window_screen_name_after_loss": str(
                        displaced.window.screen().name()
                        if displaced.window.screen() is not None
                        else ""
                    ),
                    "displaced_presenter_active": bool(
                        displaced.window.isVisible()
                        or displaced.runtime.frame_pacer.is_active()
                    ),
                    "visible_presenters_on_fallback": visible_on_fallback,
                }
            )
        self._finish_presentation_sequence(token)

    def _retire_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        if self._retirement_started:
            return
        self._retirement_started = True
        if self._args.topology_recreate:
            self._capture_topology_presentation_state()
        for probe in self._probes:
            try:
                if not probe.runtime.close_runtime():
                    self._errors.append(
                        f"generation{probe.generation} screen{probe.index} "
                        "runtime retirement was not admitted"
                    )
            except Exception as exc:
                self._errors.append(
                    f"generation{probe.generation} screen{probe.index} "
                    f"runtime retirement failed: {type(exc).__name__}: {exc}"
                )
        QTimer.singleShot(
            max(1500, self._args.phase_delay_ms * 8),
            lambda token=token: self._retirement_timeout(token),
        )

    def _capture_topology_presentation_state(self) -> None:
        generation_record = self._active_topology_generation
        screens_by_index = (
            {
                int(screen["screen_index"]): screen
                for screen in generation_record["screens"]
            }
            if generation_record is not None
            else {}
        )
        for probe in self._probes:
            try:
                progress = float(probe.scene.background_item.getProofProgress())
            except Exception as exc:
                self._errors.append(
                    f"generation{probe.generation} screen{probe.index} "
                    f"presentation-state capture failed: {type(exc).__name__}: {exc}"
                )
                continue
            probe.retired_proof_progress = progress
            screen_key = probe.runtime.display_identity.screen_key
            self._presentation_state_by_screen_key[screen_key] = {
                "generation": probe.generation,
                "proof_progress": progress,
            }
            screen_record = screens_by_index.get(probe.index)
            if screen_record is not None:
                screen_record["retired_proof_progress"] = progress

    def _on_runtime_retired(
        self,
        runtime: QuickDisplayRuntime,
        retired_generation: int,
    ) -> None:
        if retired_generation != self._generation:
            self._errors.append(
                f"stale runtime retirement generation={retired_generation} "
                f"current={self._generation}"
            )
            return
        self._retired_runtime_ids.add(id(runtime))
        if len(self._retired_runtime_ids) == len(self._probes):
            token = self._cycle_token
            QTimer.singleShot(0, lambda token=token: self._finish_generation(token))

    def _retirement_timeout(self, token: int) -> None:
        if token != self._cycle_token:
            return
        pending = [
            f"screen{probe.index}:{probe.runtime.phase.value}"
            for probe in self._probes
            if id(probe.runtime) not in self._retired_runtime_ids
        ]
        if pending:
            self._errors.append(
                f"generation{self._generation} retirement timed out: {pending}"
            )
            self._finish_report()

    def _finish_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        for position, probe in enumerate(self._probes):
            initial = self._initial_snapshots[position]
            final = probe.telemetry.snapshot()
            initial_capture = probe.initial_capture or {}
            resized_capture = probe.resized_capture or {}
            replacement_capture = probe.replacement_capture or {}
            runtime_state = probe.runtime.describe_runtime_state()
            errors = self._validate_probe(
                probe,
                initial,
                final,
                initial_capture,
                resized_capture,
                replacement_capture,
                runtime_state,
            )
            self._errors.extend(errors)
            self._reports.append(
                {
                    "index": probe.index,
                    "generation": probe.generation,
                    "screen": probe.screen_name,
                    "runtime_type": type(probe.runtime).__name__,
                    "window_type": type(probe.window).__name__,
                    "display_identity": probe.runtime.display_identity.as_dict(),
                    "runtime_state": runtime_state,
                    "window_state": runtime_state.get("window"),
                    "initial_scene_state": probe.initial_scene_state,
                    "final_scene_state": runtime_state.get("scene"),
                    "initial": _snapshot_dict(initial),
                    "final": _snapshot_dict(final),
                    "initial_capture": initial_capture,
                    "resized_capture": resized_capture,
                    "replacement_capture": replacement_capture,
                    "transition_run_id": probe.transition_run_id,
                    "transition_state_at_start": probe.transition_state_at_start,
                    "transition_completion": probe.transition_completion,
                    "stale_transition_rejected": (
                        probe.stale_transition_rejected
                    ),
                    "hide_show_cycles": probe.hide_show_cycles,
                    "proof_progress_on_construction": (
                        probe.proof_progress_on_construction
                    ),
                    "presentation_state_replayed": (
                        probe.presentation_state_replayed
                    ),
                    "replayed_from_generation": probe.replayed_from_generation,
                    "retired_proof_progress": probe.retired_proof_progress,
                    "errors": errors,
                }
            )
        if self._active_topology_generation is not None:
            self._active_topology_generation["retirement_complete"] = all(
                probe.runtime.phase.value == "retired" for probe in self._probes
            )
            self._active_topology_generation["render_resources_released"] = all(
                probe.telemetry.snapshot().release_count
                == 1 + self._args.hide_show_cycles
                for probe in self._probes
            )
        self._pending_runtime_root_ids = {
            id(probe.runtime) for probe in self._probes
        }
        self._destroyed_runtime_root_ids = set()
        barrier = {
            "generation": self._generation,
            "expected_runtime_roots": len(self._pending_runtime_root_ids),
            "destroyed_runtime_roots": 0,
            "crossed": False,
            "next_generation_started": False,
            "next_generation_started_after_crossing": False,
        }
        self._active_runtime_root_barrier = barrier
        self._runtime_root_destruction_barriers.append(barrier)
        for probe in self._probes:
            runtime_root_id = id(probe.runtime)
            probe.runtime.destroyed.connect(
                lambda *_args, runtime_root_id=runtime_root_id, token=token: (
                    self._on_runtime_root_destroyed(runtime_root_id, token)
                )
            )
            probe.runtime.deleteLater()
        QTimer.singleShot(
            max(1500, self._args.phase_delay_ms * 8),
            lambda token=token: self._runtime_root_destruction_timeout(token),
        )

    def _on_runtime_root_destroyed(self, runtime_root_id: int, token: int) -> None:
        if token != self._cycle_token:
            return
        if runtime_root_id not in self._pending_runtime_root_ids:
            self._errors.append(
                f"generation{self._generation} destroyed an untracked runtime root"
            )
            return
        self._destroyed_runtime_root_ids.add(runtime_root_id)
        barrier = self._active_runtime_root_barrier
        if barrier is not None:
            barrier["destroyed_runtime_roots"] = len(
                self._destroyed_runtime_root_ids
            )
        if self._destroyed_runtime_root_ids == self._pending_runtime_root_ids:
            if barrier is not None:
                barrier["crossed"] = True
            if self._active_topology_generation is not None:
                self._active_topology_generation[
                    "runtime_root_barrier_crossed"
                ] = True
            QTimer.singleShot(0, lambda token=token: self._complete_generation(token))

    def _runtime_root_destruction_timeout(self, token: int) -> None:
        if token != self._cycle_token:
            return
        pending = self._pending_runtime_root_ids - self._destroyed_runtime_root_ids
        if not pending:
            return
        self._errors.append(
            f"generation{self._generation} runtime-root destruction timed out: "
            f"{len(pending)} pending"
        )
        self._finish_report()

    def _complete_generation(self, token: int) -> None:
        if token != self._cycle_token:
            return
        barrier = self._active_runtime_root_barrier
        if barrier is None or not barrier.get("crossed"):
            self._errors.append(
                f"generation{self._generation} completed before its runtime-root barrier"
            )
            self._finish_report()
            return

        self._completed_generations += 1
        if self._errors or self._completed_generations >= self._args.generations:
            self._finish_report()
            return
        self._generation += 1
        QTimer.singleShot(0, self._start_generation)

    def _finish_report(self) -> None:
        if self._report_finished:
            return
        self._report_finished = True
        self._errors.extend(self._validate_exit_sequence())
        self._errors.extend(self._validate_runtime_root_barriers())
        self._errors.extend(self._validate_topology_recreate())
        report = {
            "valid": not self._errors,
            "requested_windows": self._args.windows,
            "requested_generations": self._args.generations,
            "requested_hide_show_cycles": self._args.hide_show_cycles,
            "requested_exit_via_input": self._args.exit_via_input,
            "requested_topology_recreate": self._args.topology_recreate,
            "requested_transition_id": self._args.transition_id,
            "requested_transition_direction": self._args.transition_direction,
            "requested_slide_motion_style": self._args.slide_motion_style,
            "exit_sequence": self._exit_sequence,
            "runtime_root_destruction_barriers": (
                self._runtime_root_destruction_barriers
            ),
            "topology_generations": self._topology_generations,
            "topology_replacements": self._topology_replacements,
            "topology_displacement": self._topology_displacement,
            "presentation_state_by_screen_key": (
                self._presentation_state_by_screen_key
            ),
            "completed_generations": self._completed_generations,
            "physical_screens": len(QGuiApplication.screens()),
            "created_windows": len(self._reports),
            "concurrent_windows": self._window_count,
            "render_loop": os.environ.get("QSG_RENDER_LOOP"),
            "graphics_api": QQuickWindow.graphicsApi().name,
            "qml_url": self._scene_factory.qml_url.toLocalFile(),
            "qml_loaded": self._scene_factory.is_ready,
            "windows": self._reports,
            "errors": self._errors,
        }
        rendered = json.dumps(report, indent=2, sort_keys=True)
        print(rendered, flush=True)
        if self._args.output is not None:
            self._args.output.parent.mkdir(parents=True, exist_ok=True)
            self._args.output.write_text(rendered + "\n", encoding="utf-8")
        self._app.exit(0 if report["valid"] else 1)

    def _validate_topology_recreate(self) -> list[str]:
        if not self._args.topology_recreate:
            if (
                self._topology_generations
                or self._topology_replacements
                or self._topology_displacement is not None
            ):
                return ["unexpected topology replacement records were created"]
            return []

        errors: list[str] = []
        expected_indices = ([0, 1], [1], [0, 1])
        if len(self._topology_generations) != len(expected_indices):
            return ["topology recreate did not complete all three generations"]

        retired_progress: dict[tuple[int, str], float] = {}
        window_names: list[str] = []
        for expected_generation, (record, indices) in enumerate(
            zip(self._topology_generations, expected_indices)
        ):
            if record.get("generation") != expected_generation:
                errors.append("topology generation order changed")
            if record.get("selected_screen_indices") != list(indices):
                errors.append(
                    f"generation{expected_generation} selected the wrong QScreens"
                )
            if record.get("construction_after_completed_generations") != (
                expected_generation
            ):
                errors.append(
                    f"generation{expected_generation} constructed before retirement completion"
                )
            if record.get("construction_after_root_barriers") != expected_generation:
                errors.append(
                    f"generation{expected_generation} constructed before root destruction"
                )
            if not record.get("retirement_complete"):
                errors.append(
                    f"generation{expected_generation} did not retire its runtime set"
                )
            if not record.get("render_resources_released"):
                errors.append(
                    f"generation{expected_generation} retained render resources"
                )
            if not record.get("runtime_root_barrier_crossed"):
                errors.append(
                    f"generation{expected_generation} retained runtime roots"
                )
            for screen in record.get("screens", []):
                screen_index = int(screen["screen_index"])
                identity = screen.get("display_identity", {})
                if identity.get("screen_index") != screen_index:
                    errors.append("topology screen identity was renumbered")
                if identity.get("runtime_generation") != expected_generation:
                    errors.append("topology runtime generation identity is stale")
                if screen.get("qml_runtime_generation") != expected_generation:
                    errors.append("topology QML generation identity is stale")
                window_names.append(str(screen.get("window_object_name")))
                retired = screen.get("retired_proof_progress")
                if retired is None:
                    errors.append("topology presentation state was not captured")
                else:
                    retired_progress[
                        (expected_generation, str(screen["screen_key"]))
                    ] = float(retired)
                replayed_from = screen.get("replayed_from_generation")
                if replayed_from is None:
                    if expected_generation != 0:
                        errors.append("replacement scene did not replay presentation state")
                    continue
                source = retired_progress.get(
                    (int(replayed_from), str(screen["screen_key"]))
                )
                applied = float(screen["proof_progress_on_construction"])
                if source is None or abs(source - applied) > 1e-6:
                    errors.append("replacement scene replayed stale presentation state")

        if len(window_names) != len(set(window_names)):
            errors.append("topology replacement reused a Quick window owner")

        displacement = self._topology_displacement
        if displacement is None:
            errors.append("topology recreate did not exercise screen displacement")
        else:
            before_identity = displacement.get("expected_identity_before", {})
            after_identity = displacement.get("identity_after_loss", {})
            loss = displacement.get("topology_loss", {})
            before_pacer = displacement.get("pacer_before", {})
            after_pacer = displacement.get("pacer_after_loss", {})
            runtime_after = displacement.get("runtime_state_after_loss", {})
            scene_after = runtime_after.get("scene_readiness", {})
            if displacement.get("topology_loss_signal_count") != 1:
                errors.append("topology loss was not published exactly once")
            if displacement.get("identity_change_signal_count") != 0:
                errors.append("displaced runtime published a fallback identity")
            if not displacement.get("duplicate_callbacks_ignored"):
                errors.append("topology loss was not one-shot across stale callbacks")
            if before_identity != after_identity:
                errors.append("displaced runtime mutated its physical identity")
            if (
                loss.get("screen_index") != 0
                or loss.get("runtime_generation") != 0
                or loss.get("expected_screen_key")
                != before_identity.get("screen_key")
            ):
                errors.append("topology loss did not preserve generation identity")
            if before_pacer.get("target_hz") != after_pacer.get("target_hz"):
                errors.append("displaced runtime retargeted its frame pacer")
            if (
                runtime_after.get("phase") != "paused"
                or runtime_after.get("window", {}).get("visible")
                or not after_pacer.get("paused")
                or after_pacer.get("active")
                or runtime_after.get("input", {}).get("admission_open")
            ):
                errors.append("displaced runtime remained presentation-active")
            if (
                runtime_after.get("close_meta_calls_queued")
                or runtime_after.get("window_delete_queued")
                or runtime_after.get("retirement_completed")
                or scene_after.get("qml_objects_retired")
            ):
                errors.append("topology loss bypassed generation retirement barriers")
            if displacement.get("displaced_presenter_active"):
                errors.append("displaced runtime remained a fallback presenter")
            if displacement.get("visible_presenters_on_fallback") != [
                displacement.get("fallback_window_object_name")
            ]:
                errors.append("fallback display retained two active presenters")
        if len(self._topology_replacements) != 2:
            errors.append("topology recreate did not record remove and add replacements")
        else:
            remove_event, add_event = self._topology_replacements
            if len(remove_event.get("removed_screen_keys", [])) != 1 or remove_event.get(
                "added_screen_keys"
            ):
                errors.append("topology removal event is incorrect")
            if len(add_event.get("added_screen_keys", [])) != 1 or add_event.get(
                "removed_screen_keys"
            ):
                errors.append("topology addition event is incorrect")
            for event in self._topology_replacements:
                if not event.get("old_generation_retired"):
                    errors.append("topology replacement started before old retirement")
                if not event.get("old_runtime_root_barrier_crossed"):
                    errors.append("topology replacement started before root destruction")
                if sorted(event.get("replayed_screen_keys", [])) != sorted(
                    event.get("new_screen_keys", [])
                ):
                    errors.append("topology replacement did not replay every selected screen")
        return errors

    def _validate_runtime_root_barriers(self) -> list[str]:
        barriers = self._runtime_root_destruction_barriers
        if len(barriers) != self._completed_generations:
            return ["not every completed generation crossed a runtime-root barrier"]

        errors: list[str] = []
        for position, barrier in enumerate(barriers):
            if not barrier.get("crossed"):
                errors.append(
                    f"generation{barrier.get('generation')} runtime-root barrier was not crossed"
                )
            if barrier.get("destroyed_runtime_roots") != barrier.get(
                "expected_runtime_roots"
            ):
                errors.append(
                    f"generation{barrier.get('generation')} retained runtime roots"
                )
            if position < len(barriers) - 1 and not barrier.get(
                "next_generation_started_after_crossing"
            ):
                errors.append(
                    f"generation{barrier.get('generation')} replacement started before destruction"
                )
        return errors

    def _validate_exit_sequence(self) -> list[str]:
        if not self._args.exit_via_input:
            if self._exit_sequence is not None or self._exit_request_count:
                return ["unexpected input exit occurred during lifecycle smoke"]
            return []

        sequence = self._exit_sequence
        if sequence is None:
            return ["Quick runtime input exit was not observed"]

        errors: list[str] = []
        if sequence.get("request_count") != 1 or self._exit_request_count != 1:
            errors.append("Quick runtime input exit was not emitted exactly once")
        if not sequence.get("source_event_accepted"):
            errors.append("Quick window did not accept the exit key event")
        if sequence.get("source_runtime_generation") != self._generation:
            errors.append("Quick runtime exit used the wrong generation")
        runtime_at_request = sequence.get("runtime_state_at_request", {})
        input_at_request = runtime_at_request.get("input", {})
        if runtime_at_request.get("phase") != "visible":
            errors.append("Quick runtime exit was not observed from a visible runtime")
        if not input_at_request.get("admission_open") or not input_at_request.get(
            "exiting"
        ):
            errors.append("Quick input state did not publish the admitted exit")
        if sequence.get("runtime_phases_at_request") != [
            "visible"
        ] * self._window_count:
            errors.append("Quick runtime teardown began reentrantly inside keyPressEvent")
        if not sequence.get("retirement_deferred"):
            errors.append("Quick runtime exit retirement was not deferred")
        if sequence.get("coordinated_runtime_count") != self._window_count:
            errors.append("Quick input exit did not coordinate the complete runtime set")
        if not sequence.get("post_close_event_accepted"):
            errors.append("closed Quick input did not consume a stale exit event")
        if sequence.get("request_count_after_post_close_event") != 1:
            errors.append("closed Quick input emitted a stale exit request")
        states_after_close = sequence.get("runtime_states_after_admission_close", [])
        if len(states_after_close) != self._window_count:
            errors.append("Quick input exit did not capture every retiring runtime")
        for state in states_after_close:
            if state.get("phase") != "retiring":
                errors.append("Quick input exit left a runtime outside retirement")
            if state.get("input", {}).get("admission_open"):
                errors.append("Quick input remained open after coordinated exit")
            if not state.get("close_meta_calls_queued"):
                errors.append("Quick input exit bypassed queued window teardown")
        return errors

    def _validate_probe(
        self,
        probe: _WindowProbe,
        initial: RenderNodeSnapshot,
        final: RenderNodeSnapshot,
        initial_capture: dict[str, Any],
        resized_capture: dict[str, Any],
        replacement_capture: dict[str, Any],
        runtime_state: dict[str, Any],
    ) -> list[str]:
        prefix = f"generation{probe.generation}.screen{probe.index}"
        errors: list[str] = []
        if final.error:
            errors.append(f"{prefix} render error: {final.error}")
        if probe.qml_object_name != "displaySceneRoot":
            errors.append(f"{prefix} did not instantiate DisplayScene.qml")
        if probe.qml_runtime_role != "display-scene":
            errors.append(f"{prefix} QML runtime role is incorrect")
        if probe.qml_screen_index != probe.index:
            errors.append(f"{prefix} QML screen identity is incorrect")
        if probe.qml_runtime_generation != probe.generation:
            errors.append(f"{prefix} QML runtime generation is incorrect")
        initial_scene = probe.initial_scene_state or {}
        initial_readiness = initial_scene.get("readiness", {})
        if not isinstance(initial_readiness, dict) or not initial_readiness.get(
            "ready_for_reveal"
        ):
            errors.append(f"{prefix} scene never reached explicit reveal readiness")
        initial_image_state = initial_scene.get("presentation_image")
        if (
            not isinstance(initial_image_state, dict)
            or initial_image_state.get("identity")
            != probe.presentation_image.identity
            or "rgba8" in initial_image_state
        ):
            errors.append(f"{prefix} scene did not expose detached image metadata")
        final_scene = runtime_state.get("scene", {})
        if not isinstance(final_scene, dict):
            final_scene = {}
        final_readiness = final_scene.get("readiness", {})
        if not isinstance(final_readiness, dict):
            errors.append(f"{prefix} final scene readiness is unavailable")
        else:
            if not final_readiness.get("scene_graph_invalidated"):
                errors.append(f"{prefix} scene controller missed invalidation")
            if not final_readiness.get("qml_objects_retired"):
                errors.append(f"{prefix} scene controller retained QML objects")
        identity = probe.runtime.display_identity
        if identity.screen_index != probe.index:
            errors.append(f"{prefix} display identity index is incorrect")
        if identity.runtime_generation != probe.generation:
            errors.append(f"{prefix} display runtime generation is incorrect")
        if identity.name != probe.screen_name:
            errors.append(f"{prefix} display identity name is incorrect")
        if runtime_state.get("phase") != "retired":
            errors.append(f"{prefix} runtime did not reach retired phase")
        if not runtime_state.get("close_meta_calls_queued"):
            errors.append(f"{prefix} runtime did not use queued window teardown")
        if not runtime_state.get("window_delete_queued"):
            errors.append(f"{prefix} window deletion was not queued")
        if not runtime_state.get("retirement_completed"):
            errors.append(f"{prefix} window destruction was not observed")
        transition_at_start = probe.transition_state_at_start or {}
        transition_completion = probe.transition_completion or {}
        final_transition = runtime_state.get("transition", {})
        final_completion = (
            final_transition.get("last_completion", {})
            if isinstance(final_transition, dict)
            else {}
        )
        if not isinstance(final_completion, dict):
            final_completion = {}
        if (
            not transition_at_start.get("active")
            or transition_at_start.get("active_run_id")
            != probe.transition_run_id
            or transition_at_start.get("active_transition_id")
            != self._args.transition_id
            or transition_at_start.get("active_source_identity")
            != probe.presentation_image.identity
            or transition_at_start.get("active_destination_identity")
            != probe.replacement_image.identity
        ):
            errors.append(f"{prefix} transition controller did not admit the run")
        if (
            transition_completion.get("run_id") != probe.transition_run_id
            or transition_completion.get("runtime_generation") != probe.generation
            or transition_completion.get("outcome") != "completed"
            or transition_completion.get("reason") != "deadline"
            or transition_completion.get("destination_image_identity")
            != probe.replacement_image.identity
        ):
            errors.append(f"{prefix} transition did not finalize its destination once")
        if (
            not isinstance(final_transition, dict)
            or final_transition.get("active")
            or not final_transition.get("closed")
            or final_transition.get("completion_count") != 1
            or final_completion.get("run_id") != probe.transition_run_id
        ):
            errors.append(f"{prefix} transition controller did not retire cleanly")
        if (
            final.transition_sample_count < 1
            or final.last_transition_run_id != probe.transition_run_id
            or final.last_transition_generation != probe.generation
            or final.last_transition_id != self._args.transition_id
        ):
            errors.append(f"{prefix} render node did not sample the transition run")
        if (
            final.transition_draw_count < 1
            or final.last_transition_renderer_id != self._args.transition_id
        ):
            errors.append(
                f"{prefix} {self._args.transition_id} renderer did not draw the run"
            )
        midpoint_progress = final.transition_midpoint_eased_progress
        uses_dense_midpoint = (
            self._args.transition_id in _DENSE_MIDPOINT_TRANSITION_IDS
        )
        midpoint_colors_for_oracle = (
            final.transition_midpoint_dense_colors
            if uses_dense_midpoint
            else final.transition_midpoint_colors
        )
        if (
            final.transition_midpoint_run_id != probe.transition_run_id
            or midpoint_progress is None
            or not final.transition_midpoint_colors
            or (uses_dense_midpoint and not final.transition_midpoint_dense_colors)
        ):
            errors.append(
                f"{prefix} {self._args.transition_id} midpoint was not captured"
            )
        elif not _TRANSITION_MIDPOINT_ORACLES[self._args.transition_id](
            resized_capture.get("ordered_colors"),
            replacement_capture.get("ordered_colors"),
            midpoint_colors_for_oracle,
            midpoint_progress,
            self._args.transition_direction,
        ):
            errors.append(
                f"{prefix} {self._args.transition_id} midpoint pixels are incorrect"
            )
        probe_oracle = _TRANSITION_PROBE_ORACLES.get(self._args.transition_id)
        if probe_oracle is not None and not probe_oracle(
            resized_capture.get("ordered_colors"),
            replacement_capture.get("ordered_colors"),
            final.transition_probe_eased_progresses,
            final.transition_probe_colors,
            self._args.transition_direction,
        ):
            errors.append(
                f"{prefix} {self._args.transition_id} authored pixel probes are "
                "incorrect"
            )
        if final_scene.get("transition_run") is not None:
            errors.append(f"{prefix} scene retained a finalized transition run")
        if final_scene.get("last_transition_run_id") != probe.transition_run_id:
            errors.append(f"{prefix} scene lost its stale-run fence")
        if not probe.stale_transition_rejected:
            errors.append(f"{prefix} scene re-admitted a stale transition run")
        if initial.render_thread_id is None:
            errors.append(f"{prefix} never rendered")
        elif initial.render_thread_id == initial.gui_thread_id:
            errors.append(f"{prefix} render callback ran on the GUI thread")
        expected_resource_cycles = 1 + self._args.hide_show_cycles
        if final.initialize_count != expected_resource_cycles:
            errors.append(
                f"{prefix} GL initialized {final.initialize_count} times; "
                f"expected {expected_resource_cycles}"
            )
        if final.render_count < 2 + self._args.hide_show_cycles:
            errors.append(f"{prefix} rendered only {final.render_count} frames")
        if final.release_count != expected_resource_cycles:
            errors.append(
                f"{prefix} GL released {final.release_count} times; "
                f"expected {expected_resource_cycles}"
            )
        if final.release_thread_id != final.render_thread_id:
            errors.append(f"{prefix} GL release did not run on its render thread")
        expected_image_cycles = 2 + self._args.hide_show_cycles
        if final.image_upload_count != expected_image_cycles:
            errors.append(
                f"{prefix} image uploaded {final.image_upload_count} times; "
                f"expected {expected_image_cycles}"
            )
        if final.image_release_count != expected_image_cycles:
            errors.append(
                f"{prefix} image released {final.image_release_count} times; "
                f"expected {expected_image_cycles}"
            )
        if final.image_upload_thread_id != final.render_thread_id:
            errors.append(f"{prefix} image upload did not run on its render thread")
        if final.image_release_thread_id != final.render_thread_id:
            errors.append(f"{prefix} image release did not run on its render thread")
        if final.active_image_identity is not None:
            errors.append(f"{prefix} retained an active image after retirement")
        if final.pending_image_release_count:
            errors.append(f"{prefix} retained pending image texture deletion")
        if final.image_upload_bytes <= 0:
            errors.append(f"{prefix} did not account uploaded image bytes")
        if final.image_upload_bytes != final.image_release_bytes:
            errors.append(f"{prefix} image byte ownership did not balance")
        if final.invalidation_count < expected_resource_cycles:
            errors.append(
                f"{prefix} scene graph invalidated {final.invalidation_count} times; "
                f"expected at least {expected_resource_cycles}"
            )
        if final.invalidation_thread_id != final.render_thread_id:
            errors.append(f"{prefix} invalidation did not run on its render thread")
        if not final.gl_version:
            errors.append(f"{prefix} did not report a live GL context/version")
        if initial.logical_size == final.logical_size:
            errors.append(f"{prefix} item geometry did not follow window resize")
        if initial.device_pixel_ratio <= 0.0 or final.device_pixel_ratio <= 0.0:
            errors.append(f"{prefix} reported an invalid DPR")
        if initial_capture.get("sample_count", 0) < 1:
            errors.append(f"{prefix} initial render-thread pixel sample was missing")
        if resized_capture.get("sample_count", 0) < 2:
            errors.append(f"{prefix} resized render-thread pixel sample was missing")
        if replacement_capture.get("sample_count", 0) < 3:
            errors.append(f"{prefix} replacement image pixel sample was missing")
        if initial_capture.get("image_upload_count") != 1:
            errors.append(f"{prefix} initial image was not uploaded exactly once")
        if resized_capture.get("image_upload_count") != 1:
            errors.append(f"{prefix} stable image was re-uploaded during resize")
        if replacement_capture.get("image_upload_count") != 2:
            errors.append(f"{prefix} replacement identity did not upload once")
        if (
            replacement_capture.get("active_image_identity")
            != probe.replacement_image.identity
        ):
            errors.append(f"{prefix} replacement identity did not reach render state")
        if len(initial_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} initial capture did not contain deterministic bands")
        if len(resized_capture.get("colors", ())) < 2:
            errors.append(f"{prefix} resized capture did not contain deterministic bands")
        if len(replacement_capture.get("colors", ())) < 2:
            errors.append(
                f"{prefix} replacement capture did not contain deterministic bands"
            )
        if initial_capture.get("colors") == replacement_capture.get("colors"):
            errors.append(f"{prefix} replacement image did not change rendered pixels")
        if initial_capture.get("size") == resized_capture.get("size"):
            errors.append(f"{prefix} physical capture size did not change after resize")
        if len(probe.hide_show_cycles) != self._args.hide_show_cycles:
            errors.append(
                f"{prefix} completed {len(probe.hide_show_cycles)} hide/show cycles; "
                f"expected {self._args.hide_show_cycles}"
            )
        for cycle_index, cycle in enumerate(probe.hide_show_cycles):
            cycle_prefix = f"{prefix}.hide_show{cycle_index}"
            hidden_runtime = cycle.get("hidden_runtime_state", {})
            hidden_snapshot = cycle.get("hidden", {})
            hidden_window = hidden_runtime.get("window", {})
            hidden_scene = hidden_runtime.get("scene_readiness", {})
            hidden_pacer = hidden_runtime.get("frame_pacer", {})
            resumed_runtime = cycle.get("resumed_runtime_state", {})
            resumed_window = resumed_runtime.get("window", {})
            resumed_scene = resumed_runtime.get("scene_readiness", {})
            resumed_pacer = resumed_runtime.get("frame_pacer", {})
            if hidden_runtime.get("phase") != "paused" or hidden_window.get(
                "visible"
            ):
                errors.append(f"{cycle_prefix} did not become hidden/paused")
            if (
                not hidden_scene.get("scene_graph_invalidated")
                or not hidden_scene.get("qml_root_created")
                or hidden_scene.get("qml_objects_retired")
                or not hidden_scene.get("admission_open")
            ):
                errors.append(
                    f"{cycle_prefix} did not preserve the invalidated QML scene"
                )
            if (
                not hidden_pacer.get("paused")
                or hidden_pacer.get("active")
                or hidden_pacer.get("demands") != ["visualizer"]
            ):
                errors.append(f"{cycle_prefix} did not preserve paused frame demand")
            if not cycle.get("qml_root_preserved_while_hidden"):
                errors.append(f"{cycle_prefix} replaced its QML root while hidden")
            if hidden_snapshot.get("release_thread_id") != hidden_snapshot.get(
                "render_thread_id"
            ):
                errors.append(f"{cycle_prefix} released off its render thread")
            if hidden_snapshot.get("active_image_identity") is not None:
                errors.append(f"{cycle_prefix} retained an image while invalidated")
            if hidden_snapshot.get("pending_image_release_count"):
                errors.append(f"{cycle_prefix} left image deletion pending")
            if resumed_runtime.get("phase") != "visible" or not resumed_window.get(
                "visible"
            ):
                errors.append(f"{cycle_prefix} did not become visible again")
            if not resumed_scene.get("ready_for_reveal"):
                errors.append(f"{cycle_prefix} did not regain reveal readiness")
            if (
                resumed_pacer.get("paused")
                or not resumed_pacer.get("active")
                or resumed_pacer.get("demands") != ["visualizer"]
            ):
                errors.append(f"{cycle_prefix} did not resume frame demand")
            if not cycle.get("qml_root_preserved_after_resume"):
                errors.append(f"{cycle_prefix} replaced its QML root on resume")
            resumed_snapshot = cycle.get("resumed", {})
            if (
                resumed_snapshot.get("active_image_identity")
                != probe.replacement_image.identity
            ):
                errors.append(f"{cycle_prefix} did not recreate its image texture")
            if cycle.get("resumed_capture", {}).get("sample_count", 0) < 3:
                errors.append(f"{cycle_prefix} did not render resumed pixels")
        viewport_size = list(final.viewport[2:])
        if viewport_size != list(final.render_target_size):
            errors.append(
                f"{prefix} viewport {viewport_size} does not match render target "
                f"{list(final.render_target_size)}"
            )
        capture_size = resized_capture.get("size", [0, 0])
        if any(
            viewport_extent < capture_extent
            for viewport_extent, capture_extent in zip(viewport_size, capture_size)
        ):
            errors.append(
                f"{prefix} viewport {viewport_size} did not contain item pixels "
                f"{capture_size}"
            )
        return errors

    def _finish_with_error(self, message: str) -> None:
        print(json.dumps({"valid": False, "errors": [message]}), flush=True)
        self._app.exit(1)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    bootstrap = configure_quick_graphics(reason="a2-render-node-smoke")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("SRPSSQuickRenderNodeSmoke")
    app.setQuitOnLastWindowClosed(False)

    if QQuickWindow.graphicsApi() != QSGRendererInterface.GraphicsApi.OpenGL:
        print(
            json.dumps(
                {
                    "valid": False,
                    "errors": [
                        f"Quick graphics API is {QQuickWindow.graphicsApi().name}, "
                        f"expected {bootstrap.graphics_api}"
                    ],
                }
            ),
            flush=True,
        )
        return 1

    runner = _SmokeRunner(app, args)
    QTimer.singleShot(0, runner.start)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())

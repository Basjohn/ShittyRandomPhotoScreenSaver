"""Lazy Quick renderer for Beam: a beam of light crosses the picture, leaving the next one.

On the native core (N5.2b's leftover) the beam's fragment is drawn between the two pictures and its sparks after it, as
instanced quads of their own vertex stage (``NativeQuadInstances``), from the same texts and ``block_values``."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.beam_program import (
    BEAM_FRAGMENT_SOURCE,
    BEAM_SPARK_FRAGMENT_SOURCE,
    BEAM_SPARK_VERTEX_SOURCE,
    BEAM_SPARKS,
    beam_cure,
    beam_direction,
    beam_intensity,
    beam_line,
    beam_path,
    beam_reach,
    beam_span,
    beam_spark_life_limit,
    beam_sweep_end,
)
from ..fullscreen_pass import NativeFragmentPass, NativeQuadInstances
from ..render_contract import QuickTransitionRenderFrame

_CODES = frozenset(("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl", "diag_bl_tr", "diag_br_tl"))
#: The sparks: the item quad drawn once a spark, light added (ONE, ONE, as the Python renderer blends them).
BEAM_SPARK_PASS = NativeQuadInstances("beam_sparks", BEAM_SPARK_VERTEX_SOURCE, BEAM_SPARK_FRAGMENT_SOURCE, BEAM_SPARKS,
                                      "additive")


def beam_parameters(parameters: Mapping[str, object]
                    ) -> tuple[tuple[float, float, float], float, float, float, bool, int]:
    """The resolved colour, glow, scorch, cure time, sparks and seed, validated before any GL
    state changes."""
    color, glow, scorch = parameters.get("color"), parameters.get("glow"), parameters.get("scorch")
    cure, sparks, seed = parameters.get("cure"), parameters.get("sparks"), parameters.get("seed")
    if (not isinstance(color, (tuple, list)) or len(color) < 3
            or not all(isinstance(c, (int, float)) and 0.0 <= float(c) <= 1.0 for c in color[:3])):
        raise ValueError("Beam needs a resolved colour with channels between 0 and 1")
    for name, value in (("glow", glow), ("scorch", scorch), ("cure", cure)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Beam needs a resolved {name} between 0 and 1")
    if not isinstance(sparks, bool):
        raise ValueError("Beam needs a resolved sparks switch")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Beam needs a resolved seed")
    return (float(color[0]), float(color[1]), float(color[2])), float(glow), float(scorch), float(cure), sparks, seed


class QuickBeamRenderer(NativeFragmentPass):
    transition_id = "beam"
    fragment_source = BEAM_FRAGMENT_SOURCE
    instanced_passes = (BEAM_SPARK_PASS,)

    # Every other value is in the programs' pass blocks (BEAM_BLOCK, BEAM_SPARK_BLOCK).
    _BEAM_SAMPLERS = ("uOldTex", "uNewTex")

    def native_instanced_passes(self, parameters: Mapping[str, object]) -> tuple[NativeQuadInstances, ...]:
        """The sparks pass while the run's Sparks switch is on; none otherwise."""
        return self.instanced_passes if beam_parameters(parameters)[4] else ()

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the beam's block and, with Sparks on, the sparks' block for this frame (validated first; no
        GL): the one owner, packed by ``render`` and filled by the native core (N5.2b's leftover)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        code = str(frame.run.request.direction)
        if code not in _CODES:
            raise ValueError(f"unknown resolved Beam direction: {code!r}")
        color, glow, scorch, cure_time, sparks, seed = beam_parameters(frame.run.request.parameter_dict())
        width, height = frame.logical_size
        aspect = width / height
        direction = beam_direction(code, aspect)
        span = beam_span(direction, aspect)
        reach = beam_reach(glow)
        path = beam_path(*span, reach)
        sweep_end = beam_sweep_end(beam_cure(cure_time))
        line = beam_line(progress, *path, sweep_end)
        values: dict[str, object] = {
            "uMatrix": frame.matrix_values, "uItemSize": frame.logical_size,
            "uSweepEnd": sweep_end, "uDirection": direction, "uProgress": progress, "uLine": line, "uPath": path,
            "uReach": reach, "uColor": color, "uGlow": glow, "uIntensity": beam_intensity(progress, sweep_end),
            "uSeed": float(seed), "uScorch": scorch, "uCure": beam_cure(cure_time)}
        if sparks:
            duration_s = frame.run.request.duration_ms / 1000.0
            values["uDurationS"] = duration_s
            values["uMaxLife"] = beam_spark_life_limit(duration_s, sweep_end)
            values["uSpan"] = span
        return values


def create_transition_renderer() -> QuickBeamRenderer:
    return QuickBeamRenderer()

"""Bounded diagnostics for visualizer source admission and Play/Pause edges.

This module is deliberately observational.  It owns no timer, cadence, source,
queue, or visualizer state transition.  Callers invoke it from already-existing
authored/presentation boundaries, and it returns immediately unless visualizer
diagnostics are enabled.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from core.logging.logger import is_viz_diagnostics_enabled


_DIAG_SAMPLE_INTERVAL_S = 1.5
_NOT_READY_REPEAT_S = 1.0
_MATERIAL_LEVEL = 0.01


def _coerce_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _energy_values(value: object) -> tuple[float, float, float, float]:
    if isinstance(value, Mapping):
        return (
            _coerce_float(value.get("overall", 0.0)),
            _coerce_float(value.get("bass", 0.0)),
            _coerce_float(value.get("mid", 0.0)),
            _coerce_float(value.get("high", 0.0)),
        )
    return (
        _coerce_float(getattr(value, "overall", 0.0)),
        _coerce_float(getattr(value, "bass", 0.0)),
        _coerce_float(getattr(value, "mid", 0.0)),
        _coerce_float(getattr(value, "high", 0.0)),
    )


def _sequence_level(values: object) -> float:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return 0.0
    level = 0.0
    for value in values:
        level = max(level, _coerce_float(value))
    return level


def _format_energy(value: object) -> str:
    overall, bass, mid, high = _energy_values(value)
    return f"o={overall:.3f},b={bass:.3f},m={mid:.3f},h={high:.3f}"


def begin_playback_edge(
    host: Any,
    *,
    now_ts: float,
    playing: bool,
) -> int:
    """Record one diagnostics-only Play/Pause edge and return its sequence id."""

    if not is_viz_diagnostics_enabled():
        return 0
    sequence = int(getattr(host, "_reactivity_diag_edge_seq", 0) or 0) + 1
    host._reactivity_diag_edge_seq = sequence
    host._reactivity_diag_edge_playing = bool(playing)
    host._reactivity_diag_edge_started_ts = float(now_ts)
    host._reactivity_diag_edge_t3_logged = False
    host._reactivity_diag_edge_t4_logged = False
    host._reactivity_diag_edge_t5_logged = False
    host._reactivity_diag_edge_t6_logged = False
    return sequence


def maybe_log_reactivity_boundary(
    host: Any,
    logger: logging.Logger,
    *,
    now_ts: float,
    mode: str,
    playing: bool,
    source_ready: bool,
    runtime_generation: int,
    engine_generation: int,
    engine_activation: int,
    source_generation: int,
    source_activation: int,
    source_timestamp: float | None,
    input_energy: object | None = None,
    resolved_energy: object | None = None,
    input_values: object | None = None,
    resolved_values: object | None = None,
    event_summary: str = "",
) -> None:
    """Log one compact source->resolved sample plus unthrottled edge milestones.

    T3/T4 are evaluated before the periodic sample throttle.  The first version
    checked them only when the 1.5 s VIS_REACTIVITY sampler happened to fire,
    which made a healthy ~70 ms fresh source look like a 1.5 s source delay.
    """

    if not (
        is_viz_diagnostics_enabled()
        and logger.isEnabledFor(logging.DEBUG)
    ):
        return

    timestamp = float(now_ts)
    canonical_mode = str(mode or "unknown")
    ready = bool(source_ready)
    active = bool(playing)
    source_age_ms = -1.0
    if source_timestamp is not None and _coerce_float(source_timestamp) > 0.0:
        source_age_ms = max(0.0, (timestamp - float(source_timestamp)) * 1000.0)

    # Play/Pause edge milestones must not be delayed by the ordinary bounded
    # sampler.  They observe existing authored ticks only; no new cadence exists.
    edge_seq = int(getattr(host, "_reactivity_diag_edge_seq", 0) or 0)
    edge_started = float(getattr(host, "_reactivity_diag_edge_started_ts", 0.0) or 0.0)
    edge_playing = bool(getattr(host, "_reactivity_diag_edge_playing", active))
    if edge_seq > 0 and edge_playing == active and edge_started > 0.0:
        fresh_after_edge = bool(
            source_timestamp is not None
            and float(source_timestamp) >= edge_started - 0.050
            and int(source_generation) == int(engine_generation)
            and int(source_activation) == int(engine_activation)
        )
        if fresh_after_edge and not bool(
            getattr(host, "_reactivity_diag_edge_t3_logged", False)
        ):
            host._reactivity_diag_edge_t3_logged = True
            logger.debug(
                "[VIS_PLAYBACK_EDGE] stage=T3 edge=%d mode=%s playing=%s dt_ms=%.1f "
                "source=%d/%d source_age_ms=%.1f",
                edge_seq,
                canonical_mode,
                active,
                max(0.0, (timestamp - edge_started) * 1000.0),
                int(source_generation),
                int(source_activation),
                source_age_ms,
            )
        if ready and not bool(getattr(host, "_reactivity_diag_edge_t4_logged", False)):
            host._reactivity_diag_edge_t4_logged = True
            logger.debug(
                "[VIS_PLAYBACK_EDGE] stage=T4 edge=%d mode=%s playing=%s dt_ms=%.1f "
                "ready=%s source=%d/%d",
                edge_seq,
                canonical_mode,
                active,
                max(0.0, (timestamp - edge_started) * 1000.0),
                ready,
                int(source_generation),
                int(source_activation),
            )

    signature = (
        canonical_mode,
        active,
        ready,
        int(runtime_generation),
        int(engine_generation),
        int(engine_activation),
        int(source_generation),
        int(source_activation),
    )
    previous_signature = getattr(host, "_reactivity_diag_last_signature", None)
    last_log_ts = float(getattr(host, "_reactivity_diag_last_ts", 0.0) or 0.0)
    identity_or_state_changed = signature != previous_signature
    repeat_interval = (
        _NOT_READY_REPEAT_S if active and not ready else _DIAG_SAMPLE_INTERVAL_S
    )
    if not identity_or_state_changed and timestamp - last_log_ts < repeat_interval:
        return

    previous_playing = getattr(host, "_reactivity_diag_last_playing", None)
    previous_ready = getattr(host, "_reactivity_diag_last_ready", None)
    if previous_playing is None or bool(previous_playing) != active:
        reason = "playback_edge"
    elif previous_ready is None or bool(previous_ready) != ready:
        reason = "source_ready_change"
    elif previous_signature is not None and signature[3:] != previous_signature[3:]:
        reason = "identity_change"
    elif active and not ready:
        reason = "not_ready_persisted"
    else:
        reason = "sample"

    raw_energy = _format_energy(input_energy) if input_energy is not None else "n/a"
    out_energy = _format_energy(resolved_energy) if resolved_energy is not None else "n/a"
    raw_level = _sequence_level(input_values) if input_values is not None else -1.0
    out_level = _sequence_level(resolved_values) if resolved_values is not None else -1.0
    event_suffix = f" events={event_summary}" if event_summary else ""

    logger.debug(
        "[VIS_REACTIVITY] mode=%s reason=%s edge=%d playing=%s ready=%s "
        "runtime=%d engine=%d/%d source=%d/%d source_age_ms=%.1f "
        "raw_energy=(%s) resolved_energy=(%s) raw_level=%.3f resolved_level=%.3f%s",
        canonical_mode,
        reason,
        edge_seq,
        active,
        ready,
        int(runtime_generation),
        int(engine_generation),
        int(engine_activation),
        int(source_generation),
        int(source_activation),
        source_age_ms,
        raw_energy,
        out_energy,
        raw_level,
        out_level,
        event_suffix,
    )

    host._reactivity_diag_last_signature = signature
    host._reactivity_diag_last_playing = active
    host._reactivity_diag_last_ready = ready
    host._reactivity_diag_last_ts = timestamp


def maybe_log_logical_publication(
    host: Any,
    logger: logging.Logger,
    *,
    now_ts: float,
    logical: Any,
    revision: int,
) -> None:
    """Mark T5 on the first current, materially reactive logical publication."""

    if not (
        is_viz_diagnostics_enabled()
        and logger.isEnabledFor(logging.DEBUG)
    ):
        return
    edge_seq = int(getattr(host, "_reactivity_diag_edge_seq", 0) or 0)
    if edge_seq <= 0 or bool(getattr(host, "_reactivity_diag_edge_t5_logged", False)):
        return
    edge_playing = bool(getattr(host, "_reactivity_diag_edge_playing", False))
    if bool(getattr(logical, "playing", False)) != edge_playing:
        return

    source_generation = int(getattr(logical, "source_generation", -1))
    source_activation = int(getattr(logical, "source_activation_id", -1))
    engine_generation = int(getattr(logical, "engine_generation", -1))
    activation_id = int(getattr(logical, "activation_id", -1))
    if source_generation != engine_generation or source_activation != activation_id:
        return
    edge_started = float(getattr(host, "_reactivity_diag_edge_started_ts", 0.0) or 0.0)
    source_timestamp = getattr(logical, "source_timestamp", None)
    if edge_playing and (
        source_timestamp is None
        or float(source_timestamp) < edge_started - 0.050
    ):
        return

    common = getattr(logical, "common", None)
    energy = getattr(common, "energy", None)
    energy_level = max(_energy_values(energy)) if energy is not None else 0.0
    bars_level = _sequence_level(getattr(common, "bars", ())) if common is not None else 0.0
    waveform = getattr(common, "waveform", ()) if common is not None else ()
    waveform_level = max((abs(_coerce_float(value)) for value in waveform), default=0.0)
    if edge_playing and max(energy_level, bars_level, waveform_level) <= _MATERIAL_LEVEL:
        return

    host._reactivity_diag_edge_t5_logged = True
    logger.debug(
        "[VIS_PLAYBACK_EDGE] stage=T5 edge=%d mode=%s playing=%s dt_ms=%.1f "
        "revision=%d energy_level=%.3f bars_level=%.3f waveform_level=%.3f",
        edge_seq,
        str(getattr(logical, "mode_id", "unknown")),
        edge_playing,
        max(0.0, (float(now_ts) - edge_started) * 1000.0) if edge_started > 0.0 else -1.0,
        int(revision),
        energy_level,
        bars_level,
        waveform_level,
    )


def maybe_log_snapshot_publication(
    controller: Any,
    logger: logging.Logger,
    *,
    now_ts: float,
    logical: Any,
    revision: int,
) -> None:
    """Mark T6 when the corresponding logical edge reaches the Quick bridge."""

    if not (
        is_viz_diagnostics_enabled()
        and logger.isEnabledFor(logging.DEBUG)
    ):
        return
    host = getattr(controller, "logical_tick_state", None)
    if host is None:
        return
    edge_seq = int(getattr(host, "_reactivity_diag_edge_seq", 0) or 0)
    if edge_seq <= 0 or bool(getattr(host, "_reactivity_diag_edge_t6_logged", False)):
        return
    if not bool(getattr(host, "_reactivity_diag_edge_t5_logged", False)):
        return
    edge_playing = bool(getattr(host, "_reactivity_diag_edge_playing", False))
    if bool(getattr(logical, "playing", False)) != edge_playing:
        return
    host._reactivity_diag_edge_t6_logged = True
    edge_started = float(getattr(host, "_reactivity_diag_edge_started_ts", 0.0) or 0.0)
    logger.debug(
        "[VIS_PLAYBACK_EDGE] stage=T6 edge=%d mode=%s playing=%s dt_ms=%.1f revision=%d",
        edge_seq,
        str(getattr(logical, "mode_id", "unknown")),
        edge_playing,
        max(0.0, (float(now_ts) - edge_started) * 1000.0) if edge_started > 0.0 else -1.0,
        int(revision),
    )


__all__ = [
    "begin_playback_edge",
    "maybe_log_logical_publication",
    "maybe_log_reactivity_boundary",
    "maybe_log_snapshot_publication",
]

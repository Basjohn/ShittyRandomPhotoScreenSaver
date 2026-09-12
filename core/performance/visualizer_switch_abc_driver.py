"""Opt-in, deterministic in-app A/B/C driver for the post-switch tail experiment (P4).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` phase P4.
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

This drives the phase-P4 A/B/C visualizer interactions through the app's **real**
product paths — the same canonical direct visualizer mode-request used by the
double/middle-click action and the same saved-layout load used for a runtime
recreation — so the experiment measures real scheduler/QML/scene behaviour rather
than a synthetic harness. It is installed only when ``--abc-drive=<A|B|C>`` was
admitted by the diagnostics resolver (opt-in, dev-only, never active in
production) and it emits distinct named phase-window markers so an offline scorer
can slice exactly the settled steady window(s).

Determinism and matched control (this is the corrective contract):

* every condition begins from the **same saved layout slot**, recreated through
  the real fenced reload, and the intended extreme-vertical CUSTOM Bubble baseline
  is *verified* (runtime generation changed, Bubble active, CUSTOM layout mode
  selected, owner/source healthy) before any measurement — so **A really is
  Bubble**, not merely "some visualizer is active";
* condition **A** holds the verified Bubble baseline (control) — no switching, no
  further recreation;
* conditions **B** and **C** perform the exact exposure ``Sphere -> Spectrum ->
  Oscilloscope -> Sine -> Bubble`` repeated for exactly 5 full cycles (DevCurve is
  deliberately excluded), each switch advancing only on a **genuine completion
  edge** (fully-presented target), then settle on Bubble;
* condition **C** additionally, after its post-switch hold, loads the *same* slot
  again to force the existing Quick-runtime recreation boundary, verifies the
  recreation, then holds Bubble again — producing both a pre-recreation and a
  post-recreation scored window.

Fail-closed: a rejected/incomplete/wrong-mode switch, a disabled required mode, a
failed/unverified recreation, or any watchdog expiry marks the run **INVALID**
(machine-readable reason) rather than continuing. An invalid run is never
performance evidence. Recreation here is the P4 intervention, not a production
self-healing fallback.

All DM interactions and timing are injected as callables so the state machine is
unit-testable without a live GL surface. Progression uses completion edges, not a
recurring poll; only bounded one-shot watchdogs/hold timers remain.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from enum import Enum, auto

from PySide6.QtCore import QObject, QTimer

logger = logging.getLogger(__name__)

# The exact P4 exposure. DevCurve is intentionally excluded; the sequence ends on
# the settle mode so five full cycles finish on a verified Bubble.
EXPOSURE_SEQUENCE: tuple[str, ...] = (
    "sphere",
    "spectrum",
    "oscilloscope",
    "sine_wave",
    "bubble",
)
SETTLE_MODE = "bubble"
EXPOSURE_CYCLES = 5


class _Phase(Enum):
    IDLE = auto()
    RUNNING = auto()
    DONE = auto()


class VisualizerSwitchAbcDriver(QObject):
    """Drive one A/B/C condition deterministically through real product seams."""

    def __init__(
        self,
        *,
        condition: str,
        load_layout: Callable[[], bool],
        active_mode: Callable[[], str | None],
        runtime_generation: Callable[[], int | None],
        request_mode: Callable[[str, Callable[[str], None]], bool],
        mode_enabled: Callable[[str], bool],
        custom_baseline_ok: Callable[[], bool],
        owner_healthy: Callable[[], bool],
        await_baseline: Callable[[Callable[[], None]], None],
        watch_recreation: Callable[[int | None, Callable[[int | None], None]], None],
        on_complete: Callable[[dict], None] | None = None,
        attribution_snapshot: Callable[[], dict | None] | None = None,
        exposure_sequence: Sequence[str] = EXPOSURE_SEQUENCE,
        cycles: int = EXPOSURE_CYCLES,
        settle_mode: str = SETTLE_MODE,
        exclude_seconds: float = 15.0,
        hold_seconds: float = 120.0,
        switch_timeout_s: float = 8.0,
        recreate_timeout_s: float = 30.0,
        schedule: Callable[[int, str, Callable[[], None]], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._condition = str(condition).strip().upper()
        if self._condition not in {"A", "B", "C"}:
            raise ValueError(f"unsupported A/B/C condition: {condition!r}")
        self._load_layout = load_layout
        self._active_mode = active_mode
        self._runtime_generation = runtime_generation
        self._request_mode = request_mode
        self._mode_enabled = mode_enabled
        self._custom_baseline_ok = custom_baseline_ok
        self._owner_healthy = owner_healthy
        self._await_baseline = await_baseline
        self._watch_recreation = watch_recreation
        self._on_complete = on_complete
        self._attribution_snapshot = attribution_snapshot
        self._settle_mode = str(settle_mode).strip().lower()
        self._exposure = tuple(str(m).strip().lower() for m in exposure_sequence)
        self._cycles = max(1, int(cycles))
        self._flat_sequence = self._exposure * self._cycles
        self._required_modes = frozenset(self._exposure)
        self._exclude_ms = max(0, int(float(exclude_seconds) * 1000))
        self._hold_ms = max(1, int(float(hold_seconds) * 1000))
        self._switch_timeout_ms = max(1, int(float(switch_timeout_s) * 1000))
        self._recreate_timeout_ms = max(1, int(float(recreate_timeout_s) * 1000))
        self._schedule_impl = schedule or self._default_schedule

        self._phase = _Phase.IDLE
        self._done = False
        self._generation_before: int | None = None
        self._baseline_token = 0
        self._recreate_token = 0
        self._recreate_next: Callable[[], None] | None = None
        self._switch_token = 0
        self._exposure_index = 0
        self._pending_target: str | None = None

    # -- scheduling ------------------------------------------------------------

    def _default_schedule(self, delay_ms: int, kind: str, callback: Callable[[], None]) -> None:
        # Bounded one-shot only. No recurring cadence: switch/recreation progress
        # arrives on completion edges, holds/watchdogs are single fires.
        QTimer.singleShot(int(delay_ms), callback)

    # -- lifecycle -------------------------------------------------------------

    def start(self) -> None:
        if self._phase is not _Phase.IDLE:
            return
        self._phase = _Phase.RUNNING
        logger.info(
            "[ABC] driver start condition=%s cycles=%d exposure=%s exclude_s=%.1f "
            "hold_s=%.1f",
            self._condition,
            self._cycles,
            "->".join(self._exposure),
            self._exclude_ms / 1000.0,
            self._hold_ms / 1000.0,
        )
        self._mark("driver", "start")
        # The saved layout (slot 1) is already the prepped, live baseline at launch,
        # so no baseline slot-load/recreation is needed or wanted: just wait for the
        # rebuilt owner to settle on the intended CUSTOM Bubble, then proceed. Only
        # condition C loads the slot later, as its recreation intervention.
        self._begin_baseline_wait()

    def _begin_baseline_wait(self) -> None:
        self._baseline_token += 1
        token = self._baseline_token
        self._mark("baseline", "wait")
        self._await_baseline(lambda: self._on_baseline_ready(token))
        self._schedule_impl(
            self._recreate_timeout_ms,
            "baseline_watchdog",
            lambda: self._on_baseline_watchdog(token),
        )

    def _on_baseline_watchdog(self, token: int) -> None:
        if token != self._baseline_token or self._done:
            return
        self._invalidate("CUSTOM Bubble baseline did not become ready (watchdog)")

    def _on_baseline_ready(self, token: int) -> None:
        if token != self._baseline_token or self._done:
            return
        self._baseline_token += 1  # invalidate the pending watchdog
        # Defensive re-verification of the settled baseline the wait reported.
        if (self._active_mode() or "").strip().lower() != self._settle_mode:
            self._invalidate(f"baseline is not Bubble (mode={self._active_mode()})")
            return
        if not bool(self._custom_baseline_ok()):
            self._invalidate("required CUSTOM Bubble baseline unavailable")
            return
        if not bool(self._owner_healthy()):
            self._invalidate("visualizer owner/source unhealthy at baseline")
            return
        self._mark("baseline", "verified")
        self._after_baseline()

    # -- markers ---------------------------------------------------------------

    def _mark(self, phase: str, state: str) -> None:
        # The [PERF] tag co-locates these scored markers with the event-loop /
        # PERF_HUD / integration metric plane in screensaver_perf.log, so the
        # offline scorer reads markers and metrics from one file. The harness
        # matches [ABC] via search(), so the prefix is transparent to it.
        logger.info(
            "[PERF] [ABC] condition=%s phase=%s state=%s epoch=%.3f runtime_generation=%s",
            self._condition,
            phase,
            state,
            time.time(),
            self._runtime_generation(),
        )

    def _mark_invalid(self, reason: str) -> None:
        logger.error(
            "[PERF] [ABC] condition=%s INVALID reason=%s epoch=%.3f runtime_generation=%s",
            self._condition,
            reason,
            time.time(),
            self._runtime_generation(),
        )

    # -- recreation (baseline + condition-C intervention) ----------------------

    def _begin_recreation(self, next_step: Callable[[], None], *, purpose: str) -> None:
        self._generation_before = self._runtime_generation()
        self._recreate_token += 1
        token = self._recreate_token
        self._recreate_next = next_step
        self._mark("recreate", f"request purpose={purpose}")
        # Observe the existing fenced reload/readiness seam rather than polling
        # the runtime generation. The observer fires once, on the first ready
        # generation that differs from the pre-load generation.
        self._watch_recreation(
            self._generation_before,
            lambda generation: self._on_recreation_ready(generation, token),
        )
        if not bool(self._load_layout()):
            self._invalidate("layout slot load failed")
            return
        self._schedule_impl(
            self._recreate_timeout_ms,
            "recreate_watchdog",
            lambda: self._on_recreate_watchdog(token),
        )

    def _on_recreate_watchdog(self, token: int) -> None:
        if token != self._recreate_token or self._done:
            return  # recreation already completed; watchdog is stale
        self._invalidate("runtime recreation did not complete (watchdog)")

    def _on_recreation_ready(self, generation: int | None, token: int) -> None:
        if token != self._recreate_token or self._done:
            return  # stale/duplicate emit
        self._recreate_token += 1  # invalidate the pending watchdog
        current = self._runtime_generation()
        if current is None or current == self._generation_before:
            self._invalidate("runtime generation did not change on recreation")
            return
        active = (self._active_mode() or "").strip().lower()
        if active != self._settle_mode:
            self._invalidate(f"Bubble not restored after recreation (mode={active})")
            return
        if not bool(self._custom_baseline_ok()):
            self._invalidate("required CUSTOM Bubble baseline unavailable")
            return
        if not bool(self._owner_healthy()):
            self._invalidate("visualizer owner/source unhealthy after recreation")
            return
        self._mark("recreate", f"verified generation={current}")
        next_step, self._recreate_next = self._recreate_next, None
        if next_step is not None:
            next_step()

    # -- post-baseline branch --------------------------------------------------

    def _after_baseline(self) -> None:
        if self._condition == "A":
            # Control: hold the verified Bubble baseline, no switching.
            self._enter_hold("steady_A", self._finish_valid)
            return
        # B/C: preflight the exact required modes. Do not mutate/enable settings;
        # an unavailable required mode invalidates the run.
        missing = sorted(m for m in self._required_modes if not bool(self._mode_enabled(m)))
        if missing:
            self._invalidate(
                "required exposure modes disabled/unavailable: " + ",".join(missing)
            )
            return
        self._exposure_index = 0
        self._begin_next_switch()

    # -- switch exposure (B/C) -------------------------------------------------

    def _begin_next_switch(self) -> None:
        if self._exposure_index >= len(self._flat_sequence):
            active = (self._active_mode() or "").strip().lower()
            if active != self._settle_mode:
                self._invalidate(f"exposure did not settle on Bubble (mode={active})")
                return
            if self._condition == "B":
                self._enter_hold("steady_B", self._finish_valid)
            else:
                self._enter_hold("steady_C_pre", self._after_c_pre_hold)
            return
        target = self._flat_sequence[self._exposure_index]
        self._pending_target = target
        self._switch_token += 1
        token = self._switch_token
        if not bool(self._request_mode(target, self._on_switch_complete)):
            self._invalidate(f"target mode request rejected: {target}")
            return
        self._schedule_impl(
            self._switch_timeout_ms,
            "switch_watchdog",
            lambda: self._on_switch_watchdog(token),
        )

    def _on_switch_watchdog(self, token: int) -> None:
        if token != self._switch_token or self._done:
            return  # this switch already completed; watchdog is stale
        # A timeout is a watchdog FAILURE, never an alternate success condition.
        self._invalidate(f"mode transition did not complete: {self._pending_target}")

    def _on_switch_complete(self, completed_mode_id: str) -> None:
        if self._done:
            return
        completed = str(completed_mode_id or "").strip().lower()
        if completed != self._pending_target:
            self._invalidate(
                f"completed mode wrong: expected {self._pending_target}, got {completed}"
            )
            return
        self._switch_token += 1  # invalidate the pending watchdog
        self._exposure_index += 1
        self._begin_next_switch()

    def _after_c_pre_hold(self) -> None:
        # Condition-C intervention: recreate the same slot, verify, then hold again.
        self._begin_recreation(
            lambda: self._enter_hold("steady_C_post", self._finish_valid),
            purpose="c_intervention",
        )

    # -- scored hold windows ---------------------------------------------------

    def _enter_hold(self, window_name: str, next_action: Callable[[], None]) -> None:
        # Exclude the first N seconds after activation/recreation, then bracket the
        # scored window with start/end markers. Bounded one-shot timers only.
        self._schedule_impl(
            self._exclude_ms,
            "exclusion",
            lambda: self._begin_scored_window(window_name, next_action),
        )

    def _begin_scored_window(self, window_name: str, next_action: Callable[[], None]) -> None:
        if self._done:
            return
        self._mark(window_name, "start")
        self._log_attribution(window_name, "start")
        self._schedule_impl(
            self._hold_ms,
            "hold",
            lambda: self._end_scored_window(window_name, next_action),
        )

    def _end_scored_window(self, window_name: str, next_action: Callable[[], None]) -> None:
        if self._done:
            return
        self._log_attribution(window_name, "end")
        self._mark(window_name, "end")
        next_action()

    def _log_attribution(self, window_name: str, state: str) -> None:
        """Log the H1/H2 attribution snapshot at a scored-window boundary.

        Read/log only — this is the boundary snapshot, never a per-frame or
        cadence read. Deltas between the start and end of a window give per-window
        presentation/update rates (H2); the start snapshot gives the settled
        ownership state (H1). No-op when no attribution seam is injected.
        """
        if self._attribution_snapshot is None:
            return
        try:
            payload = self._attribution_snapshot()
        except Exception:
            logger.exception("[ABC] attribution snapshot failed")
            return
        if payload is None:
            return
        import json

        logger.info(
            "[PERF] [ABC-ATTR] condition=%s window=%s state=%s epoch=%.3f data=%s",
            self._condition,
            window_name,
            state,
            time.time(),
            json.dumps(payload, sort_keys=True, default=str),
        )

    # -- completion ------------------------------------------------------------

    def _finish_valid(self) -> None:
        self._finish(valid=True, reason=None)

    def _invalidate(self, reason: str) -> None:
        self._finish(valid=False, reason=reason)

    def _finish(self, *, valid: bool, reason: str | None) -> None:
        if self._done:
            return
        self._done = True
        self._phase = _Phase.DONE
        if valid:
            self._mark("driver", "complete valid=true")
            logger.info("[ABC] driver complete condition=%s valid", self._condition)
        else:
            self._mark_invalid(reason or "unspecified")
            logger.error(
                "[ABC] driver INVALID condition=%s reason=%s", self._condition, reason
            )
        result = {
            "condition": self._condition,
            "valid": bool(valid),
            "reason": reason,
        }
        if self._on_complete is not None:
            try:
                self._on_complete(result)
            except Exception:
                logger.exception("[ABC] on_complete callback failed")


def install_abc_driver_if_enabled(engine, app, *, layout_slot: str = "1"):
    """Install the deterministic driver when ``--abc-drive`` is admitted; else None.

    Wires the driver to the engine's real DisplayManager seams: the canonical
    direct visualizer mode-request (with the experimental completion observer), the
    saved-layout slot load, the runtime generation, the effective-enabled-mode
    admission, the global CUSTOM-layout baseline check and the authoritative
    first-frame readiness signal used to observe a recreation. ``on_complete``
    exits the app so a harness can treat process exit as the run boundary — exit
    code 0 for a valid run, non-zero for INVALID. Kept defensive: any missing seam
    disables the driver.
    """
    from core.diagnostics.experiment_flags import abc_drive_condition

    condition = abc_drive_condition()
    if condition is None:
        return None

    slot = str(layout_slot)

    # Read the DisplayManager lazily each call: RUN mode creates/recreates display
    # units after this install, and condition C intentionally rebuilds them, so a
    # stale captured reference would break mid-experiment. The DisplayManager
    # object itself persists across those unit recreations.
    def _dm():
        return getattr(engine, "display_manager", None)

    def _owner():
        display_manager = _dm()
        return None if display_manager is None else getattr(
            display_manager, "_quick_visualizer_owner", None
        )

    def _active_mode() -> str | None:
        owner = _owner()
        controller = getattr(owner, "controller", None) if owner is not None else None
        mode = getattr(controller, "mode_id", None)
        return None if mode is None else str(mode).strip().lower()

    def _runtime_generation() -> int | None:
        display_manager = _dm()
        value = getattr(display_manager, "_runtime_generation", None)
        try:
            return None if value is None else int(value)
        except (TypeError, ValueError):
            return None

    def _load_layout() -> bool:
        display_manager = _dm()
        if display_manager is None:
            return False
        return bool(display_manager._load_layout_slot(slot))

    def _request_mode(target: str, on_complete: Callable[[str], None]) -> bool:
        display_manager = _dm()
        if display_manager is None:
            return False
        return bool(
            display_manager._request_quick_visualizer_mode(
                target, completion_observer=on_complete
            )
        )

    def _mode_enabled(mode: str) -> bool:
        display_manager = _dm()
        settings = getattr(display_manager, "settings_manager", None) if display_manager else None
        if settings is None:
            return False
        try:
            from core.settings.visualizer_mode_registry import (
                coerce_visualizer_mode_id,
                is_mode_active,
                resolve_effective_enabled_modes,
            )

            target = str(mode).strip().lower()
            if coerce_visualizer_mode_id(target) != target or not is_mode_active(target):
                return False
            section = settings.get("widgets.spotify_visualizer")
            if not isinstance(section, dict):
                return False
            enabled = resolve_effective_enabled_modes(section.get("mode_activation"))
            return target in enabled
        except Exception:
            logger.exception("[ABC] mode_enabled preflight failed for %s", mode)
            return False

    def _custom_baseline_ok() -> bool:
        display_manager = _dm()
        settings = getattr(display_manager, "settings_manager", None) if display_manager else None
        if settings is None:
            return False
        try:
            from rendering.widget_descriptors import (
                is_global_custom_layout_mode_selected,
            )

            return bool(is_global_custom_layout_mode_selected(settings.get_widgets_map()))
        except Exception:
            logger.exception("[ABC] CUSTOM baseline check failed")
            return False

    def _owner_healthy() -> bool:
        owner = _owner()
        if owner is None or getattr(owner, "is_retired", True):
            return False
        controller = getattr(owner, "controller", None)
        return controller is not None and getattr(controller, "mode_id", None) is not None

    def _await_baseline(on_ready: Callable[[], None]) -> None:
        # The prepped slot-1 CUSTOM Bubble is the live baseline at launch; no load
        # is performed. Wait (bounded one-shot) for the freshly built owner to
        # settle on Bubble with CUSTOM active, then fire once. Stops on success;
        # on timeout the driver's baseline watchdog fails the run closed.
        from PySide6.QtCore import QTimer

        poll_ms = 250
        max_ms = 28_000
        state = {"fired": False, "elapsed_ms": 0}
        timer = QTimer(app)
        timer.setInterval(poll_ms)

        def _check() -> None:
            if state["fired"]:
                timer.stop()
                return
            state["elapsed_ms"] += poll_ms
            if _owner_healthy() and _active_mode() == "bubble" and _custom_baseline_ok():
                state["fired"] = True
                timer.stop()
                on_ready()
            elif state["elapsed_ms"] >= max_ms:
                timer.stop()

        timer.timeout.connect(_check)
        timer.start()

    def _watch_recreation(generation_before, on_ready: Callable[[int | None], None]) -> None:
        # The fenced saved-layout reload DESTROYS and recreates the whole
        # DisplayManager (engine.display_manager = None -> new DisplayManager(...)),
        # and the engine exposes no generation-ready signal. A signal connected to
        # the pre-reload manager therefore cannot survive to report the rebuild.
        # Observe readiness on the freshly-installed manager instead, via a bounded
        # one-shot poll of the EXISTING runtime-generation counter (read lazily so
        # it resolves to the new manager): fire once the generation has advanced
        # past the pre-load value AND the rebuilt owner is the settled CUSTOM
        # Bubble baseline. This is not a steady-state cadence and not a second
        # lifecycle authority — it is a bounded post-reload settle check that stops
        # on success, leaving the driver's own recreate watchdog to fail closed.
        from PySide6.QtCore import QTimer

        poll_ms = 250
        max_ms = 28_000  # just under the driver's recreate watchdog
        state = {"fired": False, "elapsed_ms": 0}
        timer = QTimer(app)
        timer.setInterval(poll_ms)

        def _check() -> None:
            if state["fired"]:
                timer.stop()
                return
            state["elapsed_ms"] += poll_ms
            current = _runtime_generation()
            advanced = current is not None and (
                generation_before is None or current != int(generation_before)
            )
            if (
                advanced
                and _owner_healthy()
                and _active_mode() == "bubble"
                and _custom_baseline_ok()
            ):
                state["fired"] = True
                timer.stop()
                on_ready(current)
            elif state["elapsed_ms"] >= max_ms:
                timer.stop()  # let the driver's recreate watchdog fail the run closed

        timer.timeout.connect(_check)
        timer.start()

    def _attribution_snapshot() -> dict | None:
        # Assemble the boundary attribution snapshot: H1 ownership + identity from
        # the display unit's existing resource_ownership_snapshot, the render-node
        # sync/render/draw counts from the existing per-node telemetry, and the
        # opt-in GUI presentation counters (H2). Read-only; called only at scored
        # window start/end, never per frame.
        display_manager = _dm()
        if display_manager is None:
            return None
        from core.diagnostics import visualizer_attribution

        ownership = None
        node = None
        try:
            for unit in list(getattr(display_manager, "displays", []) or []):
                getter = getattr(unit, "resource_ownership_snapshot", None)
                if callable(getter) and ownership is None:
                    ownership = getter(first_frame_ready=True)
                try:
                    item = unit._runtime.scene_controller.visualizer_item
                except Exception:
                    item = None
                telemetry = getattr(item, "telemetry", None)
                if telemetry is not None and node is None:
                    from dataclasses import asdict

                    node = asdict(telemetry.snapshot())
                if ownership is not None and node is not None:
                    break
        except Exception:
            logger.exception("[ABC] attribution ownership/node walk failed")
        fence = visualizer_attribution.fence_timing()
        sync_present = visualizer_attribution.sync_present_timing()
        return {
            "runtime_generation": _runtime_generation(),
            "active_mode": _active_mode(),
            "ownership": ownership,
            "node_telemetry": node,
            "presentation": visualizer_attribution.snapshot(),
            "fence": None if fence is None else fence.snapshot(),
            "sync_present": None if sync_present is None else sync_present.snapshot(),
        }

    def _on_complete(result: dict) -> None:
        code = 0 if result.get("valid") else 3
        logger.info(
            "[ABC] experiment complete condition=%s valid=%s reason=%s exit=%d",
            result.get("condition"),
            result.get("valid"),
            result.get("reason"),
            code,
        )
        # Clean teardown before exit: mirror the tray/normal exit path
        # (engine.stop() then quit) so worker threads/runtime release and the
        # process actually terminates instead of hanging after app.exec() returns.
        try:
            engine.stop()
        except Exception:
            logger.exception("[ABC] engine.stop() during experiment completion failed")
        app.exit(code)

    driver = VisualizerSwitchAbcDriver(
        condition=condition,
        load_layout=_load_layout,
        active_mode=_active_mode,
        runtime_generation=_runtime_generation,
        request_mode=_request_mode,
        mode_enabled=_mode_enabled,
        custom_baseline_ok=_custom_baseline_ok,
        owner_healthy=_owner_healthy,
        await_baseline=_await_baseline,
        watch_recreation=_watch_recreation,
        on_complete=_on_complete,
        attribution_snapshot=_attribution_snapshot,
        parent=app,
    )
    driver.start()
    return driver


__all__ = [
    "VisualizerSwitchAbcDriver",
    "install_abc_driver_if_enabled",
    "EXPOSURE_SEQUENCE",
    "SETTLE_MODE",
    "EXPOSURE_CYCLES",
]

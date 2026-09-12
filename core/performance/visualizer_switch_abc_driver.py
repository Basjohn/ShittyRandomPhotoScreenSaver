"""Opt-in, dev-gated in-app A/B/C driver for the post-switch tail experiment (P4).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` phase P4.
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

This drives the phase-P4 A/B/C visualizer interactions through the app's **real**
product paths — the same mode-cycle used by the double/middle-click action and
the same saved-layout load used for a runtime recreation — so the experiment
measures the real scheduler/QML/scene behaviour rather than a synthetic harness.
It is installed only when ``--abc-drive=<A|B|C>`` is present (opt-in, dev-only,
never active in production) and it emits distinct phase-window markers so an
offline scorer can slice exactly the settled steady window.

It is a diagnostic experiment, not a product feature:

* condition **A** holds settled Bubble (control) — no switching, no recreation;
* condition **B** performs N full mode cycles through the real cycle action, then
  holds Bubble — no recreation;
* condition **C** performs the same B exposure, holds to establish the post-switch
  tail, then loads the saved layout to force the existing Quick-runtime
  recreation boundary, then holds Bubble again.

The DM interactions are injected as callables so the state machine is unit
testable without a live GL surface. Recreation here is the P4 intervention, not
a production self-healing fallback.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import QObject, QTimer

logger = logging.getLogger(__name__)


class _Phase(Enum):
    WARMUP = auto()
    SWITCHING = auto()
    HOLD_POST_SWITCH = auto()
    RECREATE = auto()
    HOLD_POST_RECREATE = auto()
    DONE = auto()


class VisualizerSwitchAbcDriver(QObject):
    """Drive one A/B/C condition through the real product mode-switch/recreate seams."""

    def __init__(
        self,
        *,
        condition: str,
        cycle_mode: Callable[[], None],
        active_mode: Callable[[], str | None],
        load_layout: Callable[[], bool],
        runtime_generation: Callable[[], int | None],
        on_complete: Callable[[], None] | None = None,
        settle_mode: str = "bubble",
        cycles: int = 5,
        exclude_seconds: float = 15.0,
        hold_seconds: float = 120.0,
        poll_ms: int = 250,
        switch_timeout_s: float = 8.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._condition = str(condition).strip().upper()
        if self._condition not in {"A", "B", "C"}:
            raise ValueError(f"unsupported A/B/C condition: {condition!r}")
        self._cycle_mode = cycle_mode
        self._active_mode = active_mode
        self._load_layout = load_layout
        self._runtime_generation = runtime_generation
        self._on_complete = on_complete
        self._settle_mode = str(settle_mode).strip().lower()
        self._cycles = max(1, int(cycles))
        self._exclude_seconds = max(0.0, float(exclude_seconds))
        self._hold_seconds = max(1.0, float(hold_seconds))
        self._poll_ms = max(20, int(poll_ms))
        self._switch_timeout_s = max(0.5, float(switch_timeout_s))

        self._phase = _Phase.WARMUP
        self._switches_remaining = 0
        self._num_modes_seen: set[str] = set()
        self._pending_from_mode: str | None = None
        self._pending_since = 0.0
        self._window_deadline: float | None = None
        self._recreate_generation_before: int | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_ms)
        self._timer.timeout.connect(self._tick)

    # ---- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        logger.info(
            "[ABC] driver start condition=%s cycles=%d exclude_s=%.1f hold_s=%.1f",
            self._condition,
            self._cycles,
            self._exclude_seconds,
            self._hold_seconds,
        )
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # ---- phase-window markers ------------------------------------------------

    def _mark(self, phase: str, state: str) -> None:
        logger.info(
            "[ABC] condition=%s phase=%s state=%s epoch=%.3f runtime_generation=%s",
            self._condition,
            phase,
            state,
            time.time(),
            self._runtime_generation(),
        )

    def _begin_window(self, phase_name: str) -> None:
        # Exclude the first N seconds after activation/recreation, then score a
        # settled window; the markers bracket exactly the scored interval.
        self._pending_window_phase = phase_name
        self._window_deadline = time.monotonic() + self._exclude_seconds
        self._window_open = False

    # ---- state machine -------------------------------------------------------

    def _tick(self) -> None:
        try:
            handler = {
                _Phase.WARMUP: self._tick_warmup,
                _Phase.SWITCHING: self._tick_switching,
                _Phase.HOLD_POST_SWITCH: self._tick_hold_post_switch,
                _Phase.RECREATE: self._tick_recreate,
                _Phase.HOLD_POST_RECREATE: self._tick_hold_post_recreate,
                _Phase.DONE: self._tick_done,
            }[self._phase]
            handler()
        except Exception:
            logger.exception("[ABC] driver tick failed; stopping")
            self._finish()

    def _tick_warmup(self) -> None:
        # Wait until the visualizer owner exists and reports an active mode.
        if self._active_mode() is None:
            return
        if self._condition == "A":
            self._enter_hold(_Phase.HOLD_POST_SWITCH, "steady_A")
            return
        # B/C: switch exposure = `cycles` full passes through the enabled modes.
        # We complete a full pass each time we revisit the starting mode.
        self._switches_remaining = self._cycles * self._estimate_mode_count()
        self._num_modes_seen = set()
        self._phase = _Phase.SWITCHING
        self._request_switch()

    def _estimate_mode_count(self) -> int:
        # Conservative: the five permanent modes plus experimental Sphere when
        # active. The exact count only bounds the switch total; landing on the
        # settle mode below guarantees we finish on Bubble regardless.
        return 6

    def _request_switch(self) -> None:
        self._pending_from_mode = self._active_mode()
        self._pending_since = time.monotonic()
        self._cycle_mode()

    def _tick_switching(self) -> None:
        current = self._active_mode()
        if current is not None:
            self._num_modes_seen.add(current)
        advanced = current is not None and current != self._pending_from_mode
        timed_out = (time.monotonic() - self._pending_since) > self._switch_timeout_s
        if not (advanced or timed_out):
            return
        if self._switches_remaining > 0:
            self._switches_remaining -= 1
            self._request_switch()
            return
        # Exposure complete: cycle until we settle on the hold mode (Bubble).
        if current != self._settle_mode:
            self._request_switch()
            return
        self._enter_hold(_Phase.HOLD_POST_SWITCH, "steady_B" if self._condition == "B" else "steady_C_preswitch")

    def _enter_hold(self, phase: _Phase, window_name: str) -> None:
        self._phase = phase
        self._begin_window(window_name)

    def _advance_hold_window(self, next_action: Callable[[], None]) -> None:
        now = time.monotonic()
        if not getattr(self, "_window_open", False):
            if now >= (self._window_deadline or 0.0):
                self._window_open = True
                self._window_deadline = now + self._hold_seconds
                self._mark(self._pending_window_phase, "start")
            return
        if now >= (self._window_deadline or 0.0):
            self._mark(self._pending_window_phase, "end")
            next_action()

    def _tick_hold_post_switch(self) -> None:
        if self._condition == "C":
            self._advance_hold_window(self._enter_recreate)
        else:
            self._advance_hold_window(self._finish)

    def _enter_recreate(self) -> None:
        self._phase = _Phase.RECREATE
        self._recreate_generation_before = self._runtime_generation()
        self._mark("recreate", "request")
        ok = bool(self._load_layout())
        logger.info("[ABC] recreate load_layout ok=%s", ok)
        self._recreate_since = time.monotonic()

    def _tick_recreate(self) -> None:
        # Wait until the runtime generation actually changes (real recreation).
        generation = self._runtime_generation()
        changed = (
            generation is not None
            and self._recreate_generation_before is not None
            and generation != self._recreate_generation_before
        )
        settled = self._active_mode() == self._settle_mode
        timed_out = (time.monotonic() - self._recreate_since) > self._switch_timeout_s
        if (changed and settled) or timed_out:
            self._mark("recreate", "generation=%s" % generation)
            self._enter_hold(_Phase.HOLD_POST_RECREATE, "steady_C_postrecreate")

    def _tick_hold_post_recreate(self) -> None:
        self._advance_hold_window(self._finish)

    def _tick_done(self) -> None:
        self.stop()

    def _finish(self) -> None:
        self._phase = _Phase.DONE
        self.stop()
        self._mark("driver", "complete")
        logger.info("[ABC] driver complete condition=%s", self._condition)
        if self._on_complete is not None:
            try:
                self._on_complete()
            except Exception:
                logger.exception("[ABC] on_complete callback failed")


def install_abc_driver_if_enabled(engine, app, *, layout_slot: str = "1"):
    """Install the driver when ``--abc-drive`` is set; return it or None.

    Uses the engine's real DisplayManager cycle-mode / load-layout seams. The
    ``on_complete`` callback quits the app so a harness can treat process exit as
    the run boundary. Kept defensive: any missing seam disables the driver.
    """
    from core.diagnostics.experiment_flags import abc_drive_condition

    condition = abc_drive_condition()
    if condition is None:
        return None

    # Read the DisplayManager lazily each call: RUN mode creates/recreates it
    # after this install, and condition C intentionally rebuilds it, so a stale
    # captured reference would break mid-experiment.
    def _dm():
        return getattr(engine, "display_manager", None)

    def _cycle_mode() -> None:
        display_manager = _dm()
        if display_manager is not None:
            display_manager._cycle_quick_visualizer_mode()

    def _active_mode() -> str | None:
        display_manager = _dm()
        if display_manager is None:
            return None
        owner = getattr(display_manager, "_quick_visualizer_owner", None)
        controller = getattr(owner, "controller", None) if owner is not None else None
        mode = getattr(controller, "mode_id", None)
        return None if mode is None else str(mode).strip().lower()

    def _load_layout() -> bool:
        display_manager = _dm()
        if display_manager is None:
            return False
        return bool(display_manager._load_layout_slot(str(layout_slot)))

    def _runtime_generation() -> int | None:
        display_manager = _dm()
        value = getattr(display_manager, "_runtime_generation", None)
        try:
            return None if value is None else int(value)
        except (TypeError, ValueError):
            return None

    def _on_complete() -> None:
        app.quit()

    driver = VisualizerSwitchAbcDriver(
        condition=condition,
        cycle_mode=_cycle_mode,
        active_mode=_active_mode,
        load_layout=_load_layout,
        runtime_generation=_runtime_generation,
        on_complete=_on_complete,
        parent=app,
    )
    driver.start()
    return driver


__all__ = ["VisualizerSwitchAbcDriver", "install_abc_driver_if_enabled"]

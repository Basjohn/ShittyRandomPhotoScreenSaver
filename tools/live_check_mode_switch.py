"""Visualizer mode switches inside the invisible live check (``tools/visualizer_live_check.py --mode-switch``).

At each requested time the runner makes the production cycle gesture, ``DisplayManager._cycle_quick_visualizer_mode``
(what a double-click or the context menu's cycle runs: the next enabled mode, through the Expanded Visualizer's
takeover when one is active), and records its completion where production persists it
(``DisplayManager._complete_quick_visualizer_mode_change``, called once the target is fully presented).

* **One at a time:** a switch due while the previous one is still in flight, or before the generation revealed, fires
  when that one completes (or at the reveal).
* **Recorded per switch:** the scheduled and fired times, the mode before, the mode the cycle should reach, the mode
  that completed and when (runner time and wall time, so the parent's external readings can align with it).
* **Fails the run** (``analyse_mode_switches``): a switch that never completed within ``COMPLETION_TIMEOUT_MS``, one
  that completed on an unexpected mode, or a process exit before the ``--exit-after`` deadline's terminal stop.

The runner writes ``mode_switch.json`` after every edge, so a run that dies still leaves it.
"""
from __future__ import annotations

import json
import time
import weakref
from functools import partial
from pathlib import Path

from tools.live_check_settings_roundtrip import EXIT_AFTER_REASON, parse_settings_roundtrip

COMPLETION_TIMEOUT_MS = 20_000


def parse_mode_switch(text: str) -> list[float]:
    """``AT[,AT...]`` seconds after the runner starts -> sorted, distinct, positive times."""
    try:
        return parse_settings_roundtrip(text)
    except ValueError as exc:
        raise ValueError(str(exc).replace("--settings-roundtrip", "--mode-switch")) from None


class ModeSwitchDriver:
    """Runner side: schedules the cycle gesture on the engine's display manager and records each completion."""

    def __init__(self, times, *, began: float, state_path: Path | None = None,
                 timeout_ms: int = COMPLETION_TIMEOUT_MS, memory_probe=None) -> None:
        self.times = list(times)
        # ``--roundtrip-memory`` with switches and no round trips: R-175's classification at each completed switch.
        self.memory_probe = memory_probe
        self.began = float(began)
        self.state_path = Path(state_path) if state_path is not None else None
        self.timeout_ms = int(timeout_ms)
        self.switches: list[dict] = []
        self.events: list[dict] = []
        self.exit: dict | None = None
        self._current: dict | None = None
        self._waiting: list[int] = []
        self._engine_ref = None
        self._revealed_generation = None

    def install(self, *, engine_class=None, manager_class=None, patch=setattr) -> None:
        """Wrap the engine's initialize/stop/reveal and the display manager's mode completion (production classes)."""
        if engine_class is None:
            from engine.screensaver_engine import ScreensaverEngine as engine_class
        if manager_class is None:
            from engine.display_manager import DisplayManager as manager_class
        driver = self

        initialize = engine_class.initialize

        def initialize_and_schedule(engine, *args, **kwargs):
            result = initialize(engine, *args, **kwargs)
            if result and driver._engine_ref is None:
                driver.attach(engine)
            return result

        stop = engine_class.stop

        def recorded_stop(engine, *args, **kwargs):
            try:
                return stop(engine, *args, **kwargs)
            finally:
                if kwargs.get("reason") == EXIT_AFTER_REASON:
                    driver._event("exit_after_stop")

        reveal = engine_class._freeze_revealed_generation

        def recorded_reveal(engine, *args, **kwargs):
            try:
                return reveal(engine, *args, **kwargs)
            finally:
                driver._on_reveal(engine)

        complete = manager_class._complete_quick_visualizer_mode_change

        def recorded_complete(manager, mode_id, *args, **kwargs):
            try:
                return complete(manager, mode_id, *args, **kwargs)
            finally:
                driver._on_complete(str(mode_id))

        for owner, name, value in (
            (engine_class, "initialize", initialize_and_schedule), (engine_class, "stop", recorded_stop),
            (engine_class, "_freeze_revealed_generation", recorded_reveal),
            (manager_class, "_complete_quick_visualizer_mode_change", recorded_complete),
        ):
            patch(owner, name, value)

    def attach(self, engine) -> None:
        """Arm one GUI-thread one-shot per switch (harness scheduling; the engine is the context)."""
        from PySide6.QtCore import QTimer

        self._engine_ref = weakref.ref(engine)
        now = time.monotonic()
        for index, at in enumerate(self.times):
            QTimer.singleShot(max(0, int(round((self.began + at - now) * 1000.0))), engine, partial(self.fire, index))
        self._event("armed", times=self.times)

    @staticmethod
    def _owner(engine):
        manager = getattr(engine, "display_manager", None)
        owner = getattr(manager, "_quick_visualizer_owner", None)
        if owner is None or getattr(owner, "is_retired", False):
            return manager, None
        return manager, owner

    def _admissible(self, engine) -> bool:
        state = getattr(engine._get_state(), "name", "")
        _manager, owner = self._owner(engine)
        return (state == "RUNNING" and owner is not None
                and self._revealed_generation == getattr(engine, "_runtime_generation", None)
                and not getattr(engine, "_settings_dialog_active", False))

    def fire(self, index: int) -> None:
        engine = self._engine_ref() if self._engine_ref is not None else None
        if engine is None:
            self._event("engine_gone", index=index)
            return
        if self._current is not None or not self._admissible(engine):
            if index not in self._waiting:
                self._waiting.append(index)
                self._event("deferred", index=index)
            return
        from rendering.quick.visualizer.double_click_admission import next_visualizer_mode_id

        manager, owner = self._owner(engine)
        controller = owner.controller
        before = str(controller.mode_id)
        mode_activation = getattr(getattr(controller, "settings_model", None), "mode_activation", None)
        record = {"index": index, "scheduled_at": self.times[index], "fired_at": self._now(), "fired_wall": time.time(),
                  "from_mode": before, "expected_mode": next_visualizer_mode_id(before, mode_activation),
                  "completed": False}
        self.switches.append(record)
        self._current = record
        self._flush()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(self.timeout_ms, engine, partial(self._timeout, record))
        manager._cycle_quick_visualizer_mode()
        record["request_returned_at"] = self._now()
        self._flush()

    def _timeout(self, record: dict) -> None:
        if record.get("completed") or self._current is not record:
            return
        record["timed_out"] = True
        self._event("timeout", index=record["index"])
        self._current = None
        self._next_waiting()

    def _on_complete(self, mode_id: str) -> None:
        record = self._current
        self._event("complete", mode=mode_id, index=record["index"] if record is not None else None)
        if record is None:
            return
        record.update(completed=True, completed_mode=mode_id, completed_at=self._now(), completed_wall=time.time())
        record["total_ms"] = round((record["completed_at"] - record["fired_at"]) * 1000.0, 1)
        self._current = None
        self._flush()
        engine = self._engine_ref() if self._engine_ref is not None else None
        if self.memory_probe is not None and engine is not None:
            # After the completion was timed and recorded: the census stalls the GUI turn it runs in.
            self.memory_probe.observe(engine, index=f"switch{record['index']}:{mode_id}")
        self._next_waiting()

    def _on_reveal(self, engine) -> None:
        self._revealed_generation = getattr(engine, "_runtime_generation", None)
        self._event("reveal", generation=self._revealed_generation)
        if self._current is None:
            self._next_waiting()

    def _next_waiting(self) -> None:
        engine = self._engine_ref() if self._engine_ref is not None else None
        if engine is None or not self._waiting:
            return
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, engine, partial(self.fire, self._waiting.pop(0)))   # after this handler returns

    def _now(self) -> float:
        return round(time.monotonic() - self.began, 3)

    def _event(self, name: str, **fields) -> None:
        self.events.append({"event": name, "at": self._now(), "wall": time.time(), **fields})
        self._flush()

    def finish(self) -> None:
        self.exit = {"at": self._now()}
        self._flush()

    def state(self) -> dict:
        return {"times": self.times, "switches": self.switches, "events": self.events, "exit": self.exit}

    def _flush(self) -> None:
        if self.state_path is not None:
            self.state_path.write_text(json.dumps(self.state(), indent=1), encoding="utf-8")


def analyse_mode_switches(state: dict | None, *, times: list[float], returncode: int | None) -> dict:
    failures: list[str] = []
    if returncode not in (0, None):
        failures.append(f"the saver process exited with code {returncode}")
    if state is None:
        failures.append("the runner left no mode_switch.json (it never armed the switches)")
        return {"switches": [], "failures": failures}
    by_index = {record["index"]: record for record in state.get("switches", [])}
    rows = []
    for index, at in enumerate(times):
        record = by_index.get(index)
        if record is None:
            failures.append(f"mode switch {index} at {at:g}s never fired")
            continue
        if not record.get("completed"):
            failures.append(f"mode switch {index} ({record['from_mode']} -> {record['expected_mode']}) never completed")
        elif record.get("completed_mode") != record.get("expected_mode"):
            failures.append(f"mode switch {index} completed on {record.get('completed_mode')}, "
                            f"expected {record.get('expected_mode')}")
        rows.append({"index": index, "at": at, "fired_at": record.get("fired_at"), "from": record.get("from_mode"),
                     "to": record.get("completed_mode"), "total_ms": record.get("total_ms")})
    if not any(event["event"] == "exit_after_stop" for event in state.get("events", [])):
        failures.append("the process ended without the --exit-after terminal stop (a process exit during the run)")
    return {"switches": rows, "failures": failures}


def print_mode_switches(summary: dict) -> None:
    for row in summary["switches"]:
        print(f"mode switch {row['index']} at {row['at']:g}s: {row['from']} -> {row['to']} in {row['total_ms']} ms")
    for failure in summary["failures"]:
        print(f"FAIL mode switch: {failure}")

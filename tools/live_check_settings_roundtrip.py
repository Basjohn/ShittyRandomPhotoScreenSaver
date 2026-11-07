"""Settings round trips inside the invisible live check (``tools/visualizer_live_check.py --settings-roundtrip``).

At each requested time the runner drives the engine's REAL Settings path, ``engine_handlers.on_settings_requested``:
the stop with reason ``settings``, the display teardown and its destruction barrier, the dialog generation (the real
``SettingsDialog``, built and torn down with its own barrier) and the replacement runtime up to its coordinated reveal.

* **Never visible:** ``SettingsDialog.exec`` is replaced in the runner process by a short dwell in a local event loop
  that never shows the dialog, and ``StyledPopup.exec`` answers "dismissed" without showing (any popup is recorded
  and fails the run). The saver itself stays invisible exactly as the live check already keeps it.
* **Recorded per round trip:** the stop (teardown) time, every destruction barrier that completed or timed out in
  it with its elapsed time, the runtime generation before and after, the dialog generation, RSS and private bytes
  before the request and at the replacement's reveal, and whether the retiring generation was thawed and the
  replacement re-frozen (``core/performance/gc_policy.py``: every reveal must re-freeze).
* **Fails the run** (``analyse_settings_roundtrips``): a barrier timeout, a reveal without a re-freeze, a round trip
  that never reached its reveal, a visible dialog or a popup, or any process exit before the ``--exit-after``
  deadline's own terminal stop.

The runner writes its state to ``settings_roundtrip.json`` after every edge, so a run that dies still leaves it.
"""
from __future__ import annotations

import json
import math
import time
import weakref
from functools import partial
from pathlib import Path

DIALOG_DWELL_MS = 1500          # the dialog's (invisible) life between construction and close
EXIT_AFTER_REASON = "cli_exit_after"


def parse_settings_roundtrip(text: str) -> list[float]:
    """``AT[,AT...]`` seconds after the runner starts -> sorted, distinct, positive times."""
    times: list[float] = []
    for part in str(text).split(","):
        at = float(part.strip())
        if not math.isfinite(at) or at <= 0.0:
            raise ValueError(f"--settings-roundtrip needs positive seconds, got {part!r}")
        times.append(at)
    times.sort()
    if len(set(times)) != len(times):
        raise ValueError("--settings-roundtrip times repeat")
    return times


def process_memory() -> dict:
    """This process's RSS and private bytes (Windows ``PrivateUsage``), in MB."""
    import psutil

    info = psutil.Process().memory_info()
    return {"rss_mb": round(info.rss / 2**20, 1), "private_mb": round(getattr(info, "private", 0) / 2**20, 1)}


class SettingsRoundTripDriver:
    """Runner side: schedules the round trips on the engine and records every lifecycle edge they cross."""

    def __init__(self, times, *, began: float, state_path: Path | None = None,
                 dwell_ms: int = DIALOG_DWELL_MS, memory=process_memory) -> None:
        self.times = list(times)
        self.began = float(began)
        self.state_path = Path(state_path) if state_path is not None else None
        self.dwell_ms = int(dwell_ms)
        self._memory = memory
        self.round_trips: list[dict] = []
        self.events: list[dict] = []
        self.exit: dict | None = None
        self._current: dict | None = None
        self._waiting: list[int] = []
        self._engine_ref = None
        self._revealed_generation = None
        self._dialog_patched = False
        self._patch = setattr

    # -- installation ----------------------------------------------------------------------------------------------

    def install(self, *, engine_class=None, policy_class=None, barrier_class=None, patch=setattr) -> None:
        """Wrap the engine, GC policy and barrier classes (production classes unless given)."""
        if engine_class is None:
            from engine.screensaver_engine import ScreensaverEngine as engine_class
        if policy_class is None:
            from core.performance.gc_policy import RuntimeGCPolicy as policy_class
        if barrier_class is None:
            from engine.runtime_destruction import RuntimeDestructionBarrier as barrier_class
        self._patch = patch
        driver = self

        initialize = engine_class.initialize

        def initialize_and_schedule(engine, *args, **kwargs):
            result = initialize(engine, *args, **kwargs)
            if result and driver._engine_ref is None:
                driver.attach(engine)
            return result

        stop = engine_class.stop

        def recorded_stop(engine, *args, **kwargs):
            reason = kwargs.get("reason")
            started = time.perf_counter()
            try:
                return stop(engine, *args, **kwargs)
            finally:
                if reason == EXIT_AFTER_REASON:
                    driver._event("exit_after_stop")
                elif reason == "settings" and driver._current is not None:
                    driver._current["stop_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
                    driver._current["generation_after_stop"] = getattr(engine, "_runtime_generation", None)
                    driver._flush()

        reveal = engine_class._freeze_revealed_generation

        def recorded_reveal(engine, *args, **kwargs):
            frozen_before = len(driver.events)
            try:
                return reveal(engine, *args, **kwargs)
            finally:
                refrozen = any(e["event"] == "freeze" and e["result"] for e in driver.events[frozen_before:])
                driver._on_reveal(engine, refrozen)

        freeze = policy_class.freeze_stable_generation

        def recorded_freeze(policy, *args, **kwargs):
            result = freeze(policy, *args, **kwargs)
            driver._event("freeze", result=bool(result))
            return result

        thaw = policy_class.thaw_for_runtime_retirement

        def recorded_thaw(policy, *args, **kwargs):
            result = thaw(policy, *args, **kwargs)
            driver._event("thaw", result=bool(result))
            if result and driver._current is not None:
                driver._current["thawed"] = True
            return result

        # Completion is recorded where the barrier hands over to its continuation (the replacement runs inside it).
        run_continuation = barrier_class._run_continuation

        def recorded_continuation(barrier, *args, **kwargs):
            if not getattr(barrier, "_live_check_recorded", False):
                barrier._live_check_recorded = True
                driver._barrier(barrier, "complete")
            return run_continuation(barrier, *args, **kwargs)

        on_timeout = barrier_class._on_timeout

        def recorded_timeout(barrier, *args, **kwargs):
            if not barrier._completed:
                barrier._live_check_recorded = True
                driver._barrier(barrier, "timeout")
            return on_timeout(barrier, *args, **kwargs)

        for owner, name, value in (
            (engine_class, "initialize", initialize_and_schedule), (engine_class, "stop", recorded_stop),
            (engine_class, "_freeze_revealed_generation", recorded_reveal),
            (policy_class, "freeze_stable_generation", recorded_freeze),
            (policy_class, "thaw_for_runtime_retirement", recorded_thaw),
            (barrier_class, "_run_continuation", recorded_continuation),
            (barrier_class, "_on_timeout", recorded_timeout),
        ):
            patch(owner, name, value)

    def install_dialog_patches(self) -> None:
        """``SettingsDialog.exec`` dwells invisibly and closes; ``StyledPopup.exec`` is answered unseen."""
        if self._dialog_patched:
            return
        from engine import engine_handlers
        from ui.styled_popup import StyledPopup

        settings_dialog = engine_handlers._settings_dialog_class()

        def dialog_exec(dialog) -> int:
            return self._dialog_exec(dialog)

        def popup_exec(popup) -> int:
            return self._popup_exec(popup)

        dialog_exec.settings_roundtrip_driver = popup_exec.settings_roundtrip_driver = self
        self._patch(settings_dialog, "exec", dialog_exec)
        self._patch(StyledPopup, "exec", popup_exec)
        self._dialog_patched = True

    def attach(self, engine) -> None:
        """Arm one GUI-thread one-shot per round trip (harness scheduling; the engine is the context)."""
        from PySide6.QtCore import QTimer

        self._engine_ref = weakref.ref(engine)
        now = time.monotonic()
        for index, at in enumerate(self.times):
            delay_ms = max(0, int(round((self.began + at - now) * 1000.0)))
            QTimer.singleShot(delay_ms, engine, partial(self.fire, index))
        self._event("armed", times=self.times)

    # -- the round trip --------------------------------------------------------------------------------------------

    def fire(self, index: int) -> None:
        engine = self._engine_ref() if self._engine_ref is not None else None
        if engine is None:
            self._event("engine_gone", index=index)
            return
        if self._current is not None or not self._admissible(engine, self._revealed_generation):
            if index not in self._waiting:
                self._waiting.append(index)          # fired at the next reveal
                self._event("deferred", index=index)
            return
        self.install_dialog_patches()
        record = {
            "index": index, "scheduled_at": self.times[index], "fired_at": self._now(),
            "generation_before": getattr(engine, "_runtime_generation", None),
            "memory_before": self._memory(), "thawed": False, "barriers": [], "popups": [],
        }
        self.round_trips.append(record)
        self._current = record
        self._flush()
        from engine import engine_handlers

        started = time.perf_counter()
        engine_handlers.on_settings_requested(engine)
        record["request_returned_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        self._flush()

    @staticmethod
    def _admissible(engine, revealed_generation) -> bool:
        """A RUNNING generation that has revealed (as the operator pressing S sees it); else wait for the reveal."""
        state = getattr(engine._get_state(), "name", "")
        return (state == "RUNNING" and revealed_generation == getattr(engine, "_runtime_generation", None)
                and not getattr(engine, "_settings_dialog_active", False)
                and getattr(engine, "_pending_runtime_destruction_barrier", None) is None)

    def _dialog_exec(self, dialog) -> int:
        from PySide6.QtCore import QEventLoop, QTimer

        record = self._current if self._current is not None else {}
        visible = bool(dialog.isVisible())
        started = time.perf_counter()
        loop = QEventLoop()
        QTimer.singleShot(self.dwell_ms, loop, loop.quit)
        loop.exec()
        record["dialog_generation"] = getattr(dialog, "_runtime_generation", None)
        record["dialog_visible"] = visible or bool(dialog.isVisible())
        record["dialog_exec_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        self._flush()
        return 0

    def _popup_exec(self, popup) -> int:
        entry = {"title": str(getattr(popup, "windowTitle", lambda: "")()), "at": self._now()}
        if self._current is not None:
            self._current["popups"].append(entry)
        self._event("popup", **entry)
        return 0

    def _on_reveal(self, engine, refrozen: bool) -> None:
        self._revealed_generation = getattr(engine, "_runtime_generation", None)
        self._event("reveal", generation=self._revealed_generation, refrozen=refrozen)
        record = self._current
        if record is not None and "dialog_generation" in record:
            record.update(
                revealed_at=self._now(), refrozen=refrozen,
                generation_after=getattr(engine, "_runtime_generation", None),
                memory_after=self._memory(), completed=True,
            )
            record["total_ms"] = round((record["revealed_at"] - record["fired_at"]) * 1000.0, 1)
            self._current = None
            self._flush()
        if self._current is None and self._waiting:
            from PySide6.QtCore import QTimer

            # After the reveal handler returns, never inside it.
            QTimer.singleShot(0, engine, partial(self.fire, self._waiting.pop(0)))

    def _barrier(self, barrier, outcome: str) -> None:
        created = getattr(barrier, "_created_ts", None)
        entry = {
            "outcome": outcome, "reason": str(getattr(barrier, "reason", "")),
            "retiring_generation": str(getattr(barrier, "retiring_generation", "")),
            "elapsed_ms": round((time.monotonic() - created) * 1000.0, 1) if created is not None else None,
        }
        if self._current is not None:
            self._current["barriers"].append(entry)
        self._event("barrier", **entry)

    # -- state -----------------------------------------------------------------------------------------------------

    def _now(self) -> float:
        return round(time.monotonic() - self.began, 3)

    def _event(self, name: str, **fields) -> None:
        self.events.append({"event": name, "at": self._now(), **fields})
        self._flush()

    def finish(self) -> None:
        """At interpreter exit: the process ended here (the parent judges whether that was the deadline)."""
        self.exit = {"at": self._now()}
        self._flush()

    def state(self) -> dict:
        return {"times": self.times, "dwell_ms": self.dwell_ms, "round_trips": self.round_trips,
                "events": self.events, "exit": self.exit}

    def _flush(self) -> None:
        if self.state_path is not None:
            self.state_path.write_text(json.dumps(self.state(), indent=1), encoding="utf-8")


# -- parent side ---------------------------------------------------------------------------------------------------

def gc_policy_lines(log_dir: Path) -> list[str]:
    """Every ``[GC_POLICY]`` line the run logged (main log and sidecars), in file order."""
    lines: list[str] = []
    for path in sorted(Path(log_dir).glob("*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "[GC_POLICY]" in line and line.strip() not in lines:
                lines.append(line.strip())
    return lines


def analyse_settings_roundtrips(state: dict | None, *, times: list[float], returncode: int | None,
                                gc_lines: list[str] = ()) -> dict:
    """Per round trip figures and the run's failures (any failure fails the live check)."""
    failures: list[str] = []
    if returncode not in (0, None):
        failures.append(f"the saver process exited with code {returncode}")
    if state is None:
        failures.append("the runner left no settings_roundtrip.json (it never armed the round trips)")
        return {"round_trips": [], "failures": failures, "gc_policy_lines": list(gc_lines)}
    events = state.get("events", [])
    by_index = {record["index"]: record for record in state.get("round_trips", [])}
    rows = []
    for index, at in enumerate(times):
        record = by_index.get(index)
        if record is None:
            failures.append(f"round trip {index} at {at:g}s never started (the process ended or never re-admitted it)")
            continue
        timeouts = [b for b in record.get("barriers", []) if b["outcome"] == "timeout"]
        for barrier in timeouts:
            failures.append(f"round trip {index}: barrier timeout reason={barrier['reason']} "
                            f"generation={barrier['retiring_generation']} after {barrier['elapsed_ms']} ms")
        if not record.get("completed"):
            stage = ("the replacement never revealed" if "dialog_generation" in record
                     else "the dialog never ran" if "stop_ms" in record else "the stop never returned")
            failures.append(f"round trip {index} at {at:g}s never completed: {stage}")
        elif not record.get("refrozen"):
            failures.append(f"round trip {index}: the replacement revealed without a GC re-freeze")
        if record.get("completed") and not record.get("thawed"):
            failures.append(f"round trip {index}: the retiring generation was never thawed")
        if record.get("dialog_visible"):
            failures.append(f"round trip {index}: the Settings dialog became visible")
        for popup in record.get("popups", []):
            failures.append(f"round trip {index}: a popup was raised ({popup['title']!r})")
        before, after = record.get("memory_before") or {}, record.get("memory_after") or {}
        rows.append({
            "index": index, "at": at, "fired_at": record.get("fired_at"), "stop_ms": record.get("stop_ms"),
            "barriers": [(b["reason"], b["outcome"], b["elapsed_ms"]) for b in record.get("barriers", [])],
            "dialog_exec_ms": record.get("dialog_exec_ms"), "total_ms": record.get("total_ms"),
            "generation": (record.get("generation_before"), record.get("generation_after")),
            "dialog_generation": record.get("dialog_generation"),
            "thawed": record.get("thawed"), "refrozen": record.get("refrozen"),
            "rss_mb": (before.get("rss_mb"), after.get("rss_mb")),
            "private_mb": (before.get("private_mb"), after.get("private_mb")),
        })
    in_round_trips = {(b["reason"], b["retiring_generation"]) for record in state.get("round_trips", [])
                      for b in record.get("barriers", []) if b["outcome"] == "timeout"}
    for event in events:
        if (event["event"] == "barrier" and event["outcome"] == "timeout"
                and (event["reason"], event["retiring_generation"]) not in in_round_trips):
            failures.append(f"barrier timeout outside a round trip reason={event['reason']} "
                            f"generation={event['retiring_generation']}")
    exit_after = any(event["event"] == "exit_after_stop" for event in events)
    if not exit_after:
        failures.append("the process ended without the --exit-after terminal stop (a process exit during the run)")
    froze = sum(1 for line in gc_lines if "[GC_POLICY] Froze " in line)
    completed = sum(1 for row in rows if row["refrozen"])
    if gc_lines and froze < completed + 1:
        failures.append(f"the log shows {froze} GC freezes for {completed + 1} reveals")
    return {"round_trips": rows, "failures": failures, "gc_policy_lines": list(gc_lines),
            "gc_freezes_logged": froze, "gc_thaws_logged": sum(1 for line in gc_lines if "[GC_POLICY] Thawed " in line)}


def print_settings_roundtrips(summary: dict) -> None:
    for row in summary["round_trips"]:
        print(f"settings round trip {row['index']} at {row['at']:g}s: stop {row['stop_ms']} ms, "
              f"barriers {row['barriers']}, dialog {row['dialog_exec_ms']} ms, reveal after {row['total_ms']} ms, "
              f"generation {row['generation'][0]}->{row['generation'][1]}, thawed={row['thawed']} "
              f"refrozen={row['refrozen']}, rss {row['rss_mb'][0]}->{row['rss_mb'][1]} MB, "
              f"private {row['private_mb'][0]}->{row['private_mb'][1]} MB")
    print(f"settings round trips: GC freezes logged {summary.get('gc_freezes_logged')}, "
          f"thaws logged {summary.get('gc_thaws_logged')}")
    for failure in summary["failures"]:
        print(f"FAIL settings round trip: {failure}")

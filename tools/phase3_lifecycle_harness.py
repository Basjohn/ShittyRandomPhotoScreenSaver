"""Deterministic 50/50/50 runtime-lifecycle churn harness.

This drives the production engine/display teardown seams with instrumented test
objects. It complements the real offscreen Qt/GL tests by making generation,
callback, timer, worker, and resource plateaus exactly assertable.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.display_manager import DisplayManager
from engine.engine_lifecycle import teardown_display_runtime
from engine.image_pipeline import _runtime_identity_is_current
from engine.screensaver_engine import EngineState, ScreensaverEngine


@dataclass
class _Ledger:
    resources: dict[str, tuple[int, int]] = field(default_factory=dict)
    timers: set[str] = field(default_factory=set)
    workers: set[str] = field(default_factory=set)
    callbacks: set[str] = field(default_factory=set)
    stale_rejections: int = 0
    stale_publications: int = 0
    cross_thread_gl_operations: int = 0
    context_current: int | None = None
    teardown_orders: list[tuple[str, ...]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "gl_resources": len(self.resources),
            "gl_bytes": sum(item[1] for item in self.resources.values()),
            "timers": len(self.timers),
            "workers": len(self.workers),
            "callbacks": len(self.callbacks),
        }


class _HarnessDisplay:
    def __init__(
        self,
        ledger: _Ledger,
        *,
        generation: int,
        context_id: int,
        mode: str,
        active_transition: bool,
        resolution: tuple[int, int],
    ) -> None:
        self._ledger = ledger
        self.generation = generation
        self.context_id = context_id
        self.mode = mode
        self.active_transition = active_transition
        self.resolution = resolution
        self.screen_index = 0
        self._runtime_cleanup_complete = False
        self._quiesced = False
        self._closed = False
        self._deleted = False
        self._order: list[str] = []

        prefix = f"g{generation}:c{context_id}"
        resource_sizes = {
            "program": 4096,
            "quad_vbo": 8192,
            "texture": resolution[0] * resolution[1] * 4,
            "pbo": resolution[0] * 4,
        }
        if active_transition:
            resource_sizes["transition"] = 2048
        if mode in {"spectrum", "bubble"}:
            resource_sizes[f"visualizer_{mode}"] = 16384
        for name, size in resource_sizes.items():
            ledger.resources[f"{prefix}:{name}"] = (generation, int(size))
        ledger.timers.update({f"{prefix}:rotation", f"{prefix}:visualizer"})
        ledger.workers.add(f"{prefix}:decode")
        ledger.callbacks.update({f"{prefix}:decode_done", f"{prefix}:warmup"})

    def describe_runtime_state(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "context_id": self.context_id,
            "mode": self.mode,
            "active_transition": self.active_transition,
            "resolution": list(self.resolution),
        }

    def quiesce_for_runtime_pause(self) -> None:
        self._order.append("quiesce")
        self._quiesced = True
        prefix = f"g{self.generation}:c{self.context_id}"
        self._ledger.timers = {
            item for item in self._ledger.timers if not item.startswith(prefix)
        }
        self._ledger.workers = {
            item for item in self._ledger.workers if not item.startswith(prefix)
        }
        self._ledger.callbacks = {
            item for item in self._ledger.callbacks if not item.startswith(prefix)
        }

    def clear(self) -> None:
        self._order.append("clear")
        if not self._quiesced:
            raise AssertionError("display clear occurred before producer quiesce")

    def cleanup_runtime(self, reason: str = "explicit") -> None:
        self._order.append("make_current")
        if not self._quiesced:
            raise AssertionError("GL cleanup occurred before producer quiesce")
        if threading.current_thread() is not threading.main_thread():
            self._ledger.cross_thread_gl_operations += 1
            raise AssertionError("cross-thread GL cleanup")
        self._ledger.context_current = self.context_id
        prefix = f"g{self.generation}:c{self.context_id}"
        self._ledger.resources = {
            key: value
            for key, value in self._ledger.resources.items()
            if not key.startswith(prefix)
        }
        self._order.append("delete_gl")
        self._ledger.context_current = None
        self._order.append("done_current")
        self._runtime_cleanup_complete = True

    def close(self) -> None:
        self._order.append("close")
        if not self._runtime_cleanup_complete:
            raise AssertionError("surface closed before GL cleanup")
        self._closed = True

    def deleteLater(self) -> None:
        self._order.append("delete_later")
        if not self._closed:
            raise AssertionError("QObject deletion scheduled before close")
        self._deleted = True
        self._ledger.teardown_orders.append(tuple(self._order))


class _HarnessManager:
    def __init__(self, display: _HarnessDisplay) -> None:
        self._runtime_generation = display.generation
        self.displays = [display]
        self.current_images: dict[int, str] = {0: "fixture.jpg"}
        self._image_accounting_publisher_ref = None
        self._display_image_accounting_by_id: dict[int, Any] = {}
        self._display_image_accounting_snapshot = None
        self._display_startup_generation = display.generation
        self._display_startup_ready_expected: set[int] = set()
        self._display_startup_ready_seen: set[int] = set()
        self._display_startup_ready_emitted_generation = -1
        self._authoritative_first_frame_screens: set[int] = set()
        self._authoritative_first_frame_emitted = False
        self._startup_reveal_screens: set[int] = set()
        self._startup_reveal_emitted = False
        self._deferred_reddit_urls: list[str] = []

    def get_display_count(self) -> int:
        return len(self.displays)

    def quiesce_all(self) -> None:
        DisplayManager.quiesce_all(self)

    def clear_all(self) -> None:
        DisplayManager.clear_all(self)

    def cleanup(self) -> None:
        DisplayManager.cleanup(self)

    def _publish_display_image_accounting(self) -> None:
        DisplayManager._publish_display_image_accounting(self)

    def flush_deferred_reddit_urls(self, *, ensure_widgets_dismissed: bool = False) -> None:
        self._deferred_reddit_urls.clear()


class _HarnessEngine:
    _advance_runtime_generation = ScreensaverEngine._advance_runtime_generation
    _capture_runtime_identity = ScreensaverEngine._capture_runtime_identity
    _is_runtime_identity_current = ScreensaverEngine._is_runtime_identity_current

    def __init__(self, ledger: _Ledger) -> None:
        self._ledger = ledger
        self._state_lock = threading.Lock()
        self._state = EngineState.RUNNING
        self._runtime_generation = 0
        self._lifecycle_rejected_callbacks = 0
        self.display_manager: _HarnessManager | None = None
        self._display_initialized = False
        self._display_initializing = False
        self._pending_displays_ready_generation = None
        self._loading_in_progress = False

    def _record_stale_runtime_callback(self, label: str, generation: int) -> None:
        self._lifecycle_rejected_callbacks += 1
        self._ledger.stale_rejections += 1


def _start_generation(
    engine: _HarnessEngine,
    ledger: _Ledger,
    *,
    context_id: int,
    mode: str,
    active_transition: bool,
    resolution: tuple[int, int],
) -> _HarnessManager:
    display = _HarnessDisplay(
        ledger,
        generation=engine._runtime_generation,
        context_id=context_id,
        mode=mode,
        active_transition=active_transition,
        resolution=resolution,
    )
    manager = _HarnessManager(display)
    engine.display_manager = manager
    engine._display_initialized = True
    engine._state = EngineState.RUNNING
    return manager


def run_harness(cycles: int = 50) -> dict[str, Any]:
    if cycles < 1:
        raise ValueError("cycles must be positive")

    ledger = _Ledger()
    engine = _HarnessEngine(ledger)
    scenario_results: list[dict[str, Any]] = []
    active_plateaus: set[tuple[int, int, int, int, int]] = set()
    context_id = 1000

    for scenario in ("settings", "edit", "mixed"):
        for cycle in range(cycles):
            mode = ("spectrum", "bubble", "spectrum")[cycle % 3]
            active_transition = True
            resolution = (1920, 1080) if cycle < cycles // 2 else (2560, 1440)
            manager = _start_generation(
                engine,
                ledger,
                context_id=context_id,
                mode=mode,
                active_transition=active_transition,
                resolution=resolution,
            )
            context_id += 1
            active_counts = ledger.counts()
            active_plateaus.add(tuple(active_counts.values()))

            callback_generation, callback_manager = engine._capture_runtime_identity()
            callback_publications = ledger.stale_publications

            engine._state = EngineState.STOPPING
            engine._advance_runtime_generation(f"harness_{scenario}")
            teardown_display_runtime(engine, reason=f"harness_{scenario}")

            if _runtime_identity_is_current(
                engine,
                callback_generation,
                callback_manager,
                label="harness_inflight_decode",
            ):
                ledger.stale_publications += 1

            stopped_counts = ledger.counts()
            errors: list[str] = []
            if any(stopped_counts.values()):
                errors.append(f"nonzero stopped counts: {stopped_counts}")
            if ledger.stale_publications != callback_publications:
                errors.append("stale decode callback published")
            if manager.displays:
                errors.append("old manager retained displays")

            scenario_results.append(
                {
                    "scenario": scenario,
                    "cycle": cycle + 1,
                    "old_generation": callback_generation,
                    "new_generation": engine._runtime_generation,
                    "context_id": context_id - 1,
                    "mode": mode,
                    "active_transition": active_transition,
                    "in_flight_decode": True,
                    "resolution": list(resolution),
                    "active_counts": active_counts,
                    "stopped_counts": stopped_counts,
                    "errors": errors,
                }
            )

    all_errors = [
        error
        for result in scenario_results
        for error in result["errors"]
    ]
    expected_order = (
        "quiesce",
        "clear",
        "quiesce",
        "clear",
        "make_current",
        "delete_gl",
        "done_current",
        "close",
        "delete_later",
    )
    invalid_orders = [
        list(order) for order in ledger.teardown_orders if order != expected_order
    ]
    if invalid_orders:
        all_errors.append(f"invalid teardown orders: {invalid_orders[:3]}")

    return {
        "schema_version": 1,
        "cycles_per_scenario": cycles,
        "total_cycles": len(scenario_results),
        "scenarios": {"settings": cycles, "edit": cycles, "mixed": cycles},
        "coverage": {
            "active_transition": True,
            "spectrum": True,
            "bubble": True,
            "in_flight_decode": True,
            "resolution_change": True,
            "sleep_wake": "unsupported_in_deterministic_headless_harness",
        },
        "pass_criteria": {
            "zero_cross_thread_gl": ledger.cross_thread_gl_operations == 0,
            "zero_stale_publications": ledger.stale_publications == 0,
            "all_stale_callbacks_rejected": ledger.stale_rejections == len(scenario_results),
            "zero_old_generation_resources": all(
                not any(result["stopped_counts"].values())
                for result in scenario_results
            ),
            "no_timer_worker_callback_growth": all(
                result["stopped_counts"][name] == 0
                for result in scenario_results
                for name in ("timers", "workers", "callbacks")
            ),
            "valid_teardown_order": not invalid_orders,
        },
        "active_plateaus": [list(item) for item in sorted(active_plateaus)],
        "stale_rejections": ledger.stale_rejections,
        "errors": all_errors,
        "cycles": scenario_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_harness(args.cycles)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")

    passed = not report["errors"] and all(report["pass_criteria"].values())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

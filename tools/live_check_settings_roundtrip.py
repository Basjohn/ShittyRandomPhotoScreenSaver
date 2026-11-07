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

**Memory classification (opt-in, ``--roundtrip-memory census[,collect][,tracemalloc][,map]``):** at every
coordinated reveal, just before the reveal's GC freeze, ``RoundTripMemoryProbe`` records what one round trip left
behind, by category: the tracked Python heap by type, live QObject wrappers by class (with shiboken validity) and the
native QObject trees, the render host's GL accounting, threads/handles/GDI/USER, and which objects of earlier
(retired) generations are still alive (weakrefs and ``destroyed`` edges on each generation's retirement roots and on
each Settings dialog). ``collect`` adds one ``gc.collect()`` there, with its garbage classified (``DEBUG_SAVEALL``)
and the RSS/private drop it causes; ``tracemalloc`` starts tracemalloc at the runner's start and records the top
allocation-site diffs between reveals; ``map`` adds the process's native memory map by category
(``tools/win_memory_map.py``, ~10 s in process). Each level stalls the reveal it observes, so a run classifies; it does
not time. Without the option nothing here runs; with it, it runs in the runner only (``settings_roundtrip_memory.json``).
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


MEMORY_LEVELS = ("census", "collect", "tracemalloc", "map")


def parse_roundtrip_memory(text: str) -> tuple[str, ...]:
    """``census[,collect][,tracemalloc][,map]`` -> the admitted levels (``census`` is implied by the others)."""
    levels = {part.strip() for part in str(text).split(",") if part.strip()}
    unknown = levels - set(MEMORY_LEVELS)
    if unknown or not levels:
        raise ValueError(f"--roundtrip-memory takes {','.join(MEMORY_LEVELS)}, got {text!r}")
    return tuple(level for level in MEMORY_LEVELS if level in levels or level == "census")


def _type_name(obj) -> str:
    kind = type(obj)
    return f"{getattr(kind, '__module__', '?')}.{kind.__qualname__}"


def _top_deltas(now: dict, before: dict, top: int) -> list:
    keys = set(now) | set(before)
    deltas = [(key, now.get(key, 0) - before.get(key, 0)) for key in keys]
    return [(key, delta) for key, delta in sorted(deltas, key=lambda kv: -abs(kv[1])) if delta][:top]


class RoundTripMemoryProbe:
    """Runner-only classification of what each Settings round trip leaves behind (see the module docstring)."""

    TOP = 25

    def __init__(self, levels, *, out_dir: Path | None = None) -> None:
        self.levels = tuple(levels)
        self.collect = "collect" in self.levels
        self.tracemalloc = "tracemalloc" in self.levels
        self.out_dir = Path(out_dir) if out_dir is not None else None
        self.observations: list[dict] = []
        self._previous: dict | None = None
        self._previous_snapshot = None
        self._previous_map = None
        # generation label -> {"python": [(label, weakref)], "native": {token: label}}
        self._generations: dict[str, dict] = {}

    @staticmethod
    def start_tracing(levels) -> None:
        """At the runner's start, before the application imports (so every allocation site is attributed)."""
        if "tracemalloc" in tuple(levels):
            import tracemalloc

            tracemalloc.start(1)     # one frame: a snapshot of the whole heap stays seconds, not a minute

    # -- retired generations ---------------------------------------------------------------------------------------

    def watch_generation(self, label: str, qobjects=(), python_owners=()) -> None:
        """Weakrefs (and native ``destroyed`` edges) on one generation's owners; survivors are counted later."""
        entry = self._generations.setdefault(str(label), {"python": [], "native": {}, "qobject_wrappers": []})
        for owner in python_owners:
            try:
                entry["python"].append((_type_name(owner), weakref.ref(owner)))
            except TypeError:
                pass
        for obj in qobjects:
            token = id(obj)
            if token in entry["native"]:
                continue
            try:
                entry["native"][token] = type(obj).__name__
                entry["qobject_wrappers"].append((type(obj).__name__, weakref.ref(obj)))
                obj.destroyed.connect(partial(self._native_destroyed, str(label), token))
            except (RuntimeError, TypeError):
                entry["native"].pop(token, None)

    def _native_destroyed(self, label: str, token: int, *_args) -> None:
        entry = self._generations.get(label)
        if entry is not None:
            entry["native"].pop(token, None)

    def watch_engine_generation(self, engine) -> None:
        manager = getattr(engine, "display_manager", None)
        label = f"display:{getattr(engine, '_runtime_generation', '?')}"
        if manager is None or label in self._generations:
            return
        try:
            qobjects, python_owners = manager.collect_runtime_retirement_roots()
        except Exception as exc:  # observation only
            self._generations[label] = {"python": [], "native": {}, "qobject_wrappers": [], "error": repr(exc)}
            return
        self.watch_generation(label, qobjects, [manager, *python_owners])

    def _survivors(self, current: str) -> dict:
        from collections import Counter

        report = {}
        for label, entry in self._generations.items():
            if label == current:
                continue
            python = Counter(name for name, ref in entry["python"] if ref() is not None)
            wrappers = Counter(name for name, ref in entry["qobject_wrappers"] if ref() is not None)
            native = Counter(entry["native"].values())
            if python or wrappers or native:
                report[label] = {"python_owners": dict(python), "qobject_wrappers_alive": dict(wrappers),
                                 "native_qobjects_alive": dict(native.most_common(self.TOP)),
                                 "native_total": sum(native.values())}
        return report

    # -- the observation -------------------------------------------------------------------------------------------

    def observe(self, engine, *, index, memory=process_memory) -> dict:
        import gc
        import sys
        from collections import Counter

        started = time.perf_counter()
        self.watch_engine_generation(engine)
        current = f"display:{getattr(engine, '_runtime_generation', '?')}"
        row: dict = {"index": index, "generation": getattr(engine, "_runtime_generation", None),
                     "memory": memory(), "allocated_blocks": sys.getallocatedblocks(),
                     "gc_counts": gc.get_count(), "gc_freeze_count": gc.get_freeze_count()}

        objects = gc.get_objects()
        types = Counter(_type_name(obj) for obj in objects)
        row["tracked"] = len(objects)
        qt = self._qt_census(objects)
        del objects
        row["qt"] = qt
        row["native_qt"] = self._native_qt_census()
        row["gl"] = self._gl_accounting(engine)
        row["os"] = self._os_counts()
        row["retired_survivors"] = self._survivors(current)
        if self.collect:
            row["collect"] = self._collect(memory)
        if self.tracemalloc:
            row["tracemalloc"] = self._tracemalloc_diff()
        if "map" in self.levels:
            row["memory_map"] = self._memory_map(index)
        previous = self._previous
        if previous is not None:
            row["delta"] = {
                "rss_mb": round(row["memory"]["rss_mb"] - previous["memory"]["rss_mb"], 1),
                "private_mb": round(row["memory"]["private_mb"] - previous["memory"]["private_mb"], 1),
                "tracked": row["tracked"] - previous["tracked"],
                "allocated_blocks": row["allocated_blocks"] - previous["allocated_blocks"],
                "types": _top_deltas(types, previous["_types"], self.TOP),
                "qobject_wrappers": _top_deltas(qt["by_class"], previous["qt"]["by_class"], self.TOP),
                "native_qt": {key: row["native_qt"].get(key, 0) - previous["native_qt"].get(key, 0)
                              for key in row["native_qt"] if isinstance(row["native_qt"].get(key), int)},
                "native_qobject_classes": _top_deltas(row["native_qt"]["children_by_class"],
                                                      previous["native_qt"]["children_by_class"], self.TOP),
                "os": {key: row["os"][key] - previous["os"].get(key, 0) for key in row["os"]},
                "gl": {key: value - previous["gl"].get(key, 0) for key, value in row["gl"].items()
                       if isinstance(value, int) and isinstance(previous["gl"].get(key), int)},
            }
        row["top_types"] = types.most_common(self.TOP)
        row["probe_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
        self._previous = dict(row, _types=types)
        self.observations.append(row)
        self._flush()
        return row

    @staticmethod
    def _qt_census(objects) -> dict:
        from collections import Counter

        from PySide6.QtCore import QObject

        try:
            from shiboken6 import isValid
        except ImportError:  # pragma: no cover
            isValid = lambda _obj: True  # noqa: E731
        try:
            from PySide6.QtQml import QQmlComponent, QQmlEngine
            from PySide6.QtQuick import QQuickItem, QQuickWindow
        except ImportError:  # pragma: no cover
            QQmlComponent = QQmlEngine = QQuickItem = QQuickWindow = ()
        by_class, invalid = Counter(), Counter()
        kinds = Counter()
        for obj in objects:
            if not isinstance(obj, QObject):
                continue
            name = type(obj).__name__
            if not isValid(obj):
                invalid[name] += 1
                continue
            by_class[name] += 1
            for kind, cls in (("QQmlEngine", QQmlEngine), ("QQmlComponent", QQmlComponent),
                              ("QQuickItem", QQuickItem), ("QQuickWindow", QQuickWindow)):
                if cls and isinstance(obj, cls):
                    kinds[kind] += 1
        return {"wrappers_valid": sum(by_class.values()), "wrappers_invalid": sum(invalid.values()),
                "by_class": dict(by_class), "invalid_by_class": dict(invalid.most_common(15)), "kinds": dict(kinds)}

    @staticmethod
    def _native_qt_census() -> dict:
        """Native QObject trees reachable from the application, its windows and widgets (no Python wrapper needed)."""
        from collections import Counter

        from PySide6.QtCore import QCoreApplication, QObject
        from PySide6.QtGui import QGuiApplication

        app = QCoreApplication.instance()
        windows = list(QGuiApplication.allWindows()) if isinstance(app, QGuiApplication) else []
        widgets = []
        try:
            from PySide6.QtWidgets import QApplication

            if isinstance(app, QApplication):
                widgets = list(QApplication.topLevelWidgets())
                all_widgets = len(QApplication.allWidgets())
            else:
                all_widgets = 0
        except ImportError:  # pragma: no cover
            all_widgets = 0
        children = Counter()
        seen = set()
        for root in [app, *windows, *widgets]:
            if root is None:
                continue
            try:
                for child in root.findChildren(QObject):
                    key = id(child)
                    if key not in seen:
                        seen.add(key)
                        children[type(child).__name__] += 1
            except RuntimeError:
                continue
        engines = 0
        try:
            from PySide6.QtQml import QQmlEngine

            engines = sum(1 for window in windows for _ in window.findChildren(QQmlEngine))
        except Exception:
            pass
        return {"windows": len(windows), "top_level_widgets": len(widgets), "all_widgets": all_widgets,
                "app_tree_qobjects": sum(children.values()), "qml_engines_under_windows": engines,
                "children_by_class": dict(children)}

    @staticmethod
    def _gl_accounting(engine) -> dict:
        try:
            from core.performance.resource_metrics import collect_resource_accounting

            return dict(collect_resource_accounting(engine).aggregate_fields())
        except Exception as exc:  # observation only
            return {"error": repr(exc)}

    @staticmethod
    def _os_counts() -> dict:
        import ctypes
        import threading

        import psutil

        process = psutil.Process()
        counts = {"threads": process.num_threads(), "python_threads": threading.active_count()}
        try:
            counts["handles"] = process.num_handles()
            user32 = ctypes.WinDLL("user32")
            current = ctypes.WinDLL("kernel32").GetCurrentProcess()
            counts["gdi"] = int(user32.GetGuiResources(current, 0))
            counts["user"] = int(user32.GetGuiResources(current, 1))
        except (AttributeError, OSError):
            pass
        return counts

    def _collect(self, memory) -> dict:
        """One collection with its garbage classified, and what freeing it returned to the OS."""
        import gc
        from collections import Counter

        before = memory()
        started = time.perf_counter()
        gc.set_debug(gc.DEBUG_SAVEALL)
        try:
            found = gc.collect()
            garbage = list(gc.garbage)
            gc.garbage.clear()
        finally:
            gc.set_debug(0)
        kinds = Counter(_type_name(obj) for obj in garbage)
        qobjects = Counter(type(obj).__name__ for obj in garbage if _is_qobject(obj))
        buffers = Counter()      # the bulk a cycle can pin: arrays and images it reaches one hop away
        for obj in garbage:
            for value in (obj.values() if isinstance(obj, dict) else (obj,)):
                size = _buffer_bytes(value)
                if size:
                    buffers[_type_name(value)] += size
        del garbage
        freed = gc.collect()
        after = memory()
        return {"unreachable": found, "freed_second_pass": freed, "ms": round((time.perf_counter() - started) * 1e3, 1),
                "garbage_types": kinds.most_common(self.TOP), "garbage_qobjects": dict(qobjects),
                "garbage_buffers_mb": {key: round(value / 2**20, 2) for key, value in buffers.most_common(10)},
                "rss_drop_mb": round(before["rss_mb"] - after["rss_mb"], 1),
                "private_drop_mb": round(before["private_mb"] - after["private_mb"], 1),
                "memory_before": before, "memory_after": after}

    def _tracemalloc_diff(self) -> dict:
        import tracemalloc

        if not tracemalloc.is_tracing():
            return {"error": "tracemalloc was not started"}
        snapshot = tracemalloc.take_snapshot().filter_traces(
            (tracemalloc.Filter(False, tracemalloc.__file__), tracemalloc.Filter(False, "<frozen importlib._bootstrap>")))
        current, peak = tracemalloc.get_traced_memory()
        result: dict = {"traced_mb": round(current / 2**20, 2), "peak_mb": round(peak / 2**20, 2)}
        previous, self._previous_snapshot = self._previous_snapshot, snapshot
        if previous is not None:
            def rows(group):
                return [{"site": str(stat.traceback), "size_kb": round(stat.size_diff / 1024, 1),
                         "count": stat.count_diff} for stat in snapshot.compare_to(previous, group)[: self.TOP]]
            result["by_line"] = rows("lineno")
            result["by_file"] = rows("filename")
        return result

    def _memory_map(self, index) -> dict:
        import os
        from collections import defaultdict

        try:
            from tools import win_memory_map
        except ImportError:  # pragma: no cover
            return {}
        try:
            snap = win_memory_map.snapshot(os.getpid())
        except (OSError, SystemExit) as exc:
            return {"error": repr(exc)}
        totals: dict = defaultdict(lambda: [0, 0])
        for alloc in snap["allocations"]:
            totals[alloc["category"]][0] += alloc["commit"]
            totals[alloc["category"]][1] += alloc["resident_private"]
        result = {"commit_mb": {k: round(v[0] / 2**20, 1) for k, v in totals.items()},
                  "resident_private_mb": {k: round(v[1] / 2**20, 1) for k, v in totals.items()},
                  "threads": len(snap["threads"]), "elapsed_ms": snap["elapsed_ms"]}
        if self.out_dir is not None:
            path = self.out_dir / f"memory_map_{index}.json"
            path.write_text(json.dumps(snap), encoding="utf-8")
            result["file"] = path.name
        if self._previous_map is not None:
            result["diff_vs_previous"] = win_memory_map.diff(self._previous_map, snap, top=12)
        self._previous_map = snap
        return result

    def _flush(self) -> None:
        if self.out_dir is not None:
            (self.out_dir / "settings_roundtrip_memory.json").write_text(
                json.dumps({"levels": self.levels, "observations": self.observations}, indent=1, default=str),
                encoding="utf-8")


def _buffer_bytes(value) -> int:
    """Bytes of a numpy array, ``bytes``/``bytearray`` or QImage (0 for anything else); attribute probes only."""
    if isinstance(value, (bytes, bytearray)):
        return len(value) if len(value) >= 65536 else 0
    nbytes = getattr(type(value), "nbytes", None)
    if nbytes is not None and type(value).__module__ == "numpy":
        try:
            return int(value.nbytes) if value.base is None else 0     # views do not own their buffer
        except Exception:
            return 0
    if type(value).__name__ == "QImage":
        try:
            return int(value.sizeInBytes())
        except Exception:
            return 0
    return 0


def _is_qobject(obj) -> bool:
    try:
        from PySide6.QtCore import QObject

        return isinstance(obj, QObject)
    except Exception:  # pragma: no cover
        return False


class SettingsRoundTripDriver:
    """Runner side: schedules the round trips on the engine and records every lifecycle edge they cross."""

    def __init__(self, times, *, began: float, state_path: Path | None = None,
                 dwell_ms: int = DIALOG_DWELL_MS, memory=process_memory,
                 memory_probe: RoundTripMemoryProbe | None = None) -> None:
        self.times = list(times)
        self.memory_probe = memory_probe
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
            if driver.memory_probe is not None and getattr(engine._get_state(), "name", "") == "RUNNING":
                # Before the reveal's freeze: a collection here still reaches the retired generation's cycles.
                record = driver._current
                driver.memory_probe.observe(engine, index=record["index"] if record is not None else "startup",
                                            memory=driver._memory)
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
        if self.memory_probe is not None:
            from PySide6.QtCore import QObject

            self.memory_probe.watch_generation(
                f"dialog:{getattr(dialog, '_runtime_generation', '?')}", [dialog, *dialog.findChildren(QObject)], [])
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

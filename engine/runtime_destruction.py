"""Non-reentrant destruction barrier for retired display generations.

Explicit producer/GL cleanup remains synchronous and authoritative.  This
module only proves that Qt has processed the resulting ``deleteLater()`` work
before a replacement runtime is constructed.  It never pumps the event loop,
performs garbage collection, or participates in first-frame/reveal decisions.
"""

from __future__ import annotations

from collections import Counter
from functools import partial
import time
from typing import Callable
import weakref

from PySide6.QtCore import QCoreApplication, QObject, QTimer
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger

try:
    from shiboken6 import isValid as _is_valid_qobject
except ImportError:  # pragma: no cover - PySide supplies shiboken in production
    _is_valid_qobject = None


logger = get_logger(__name__)

_DEFAULT_TIMEOUT_MS = 8000
_RESOURCE_RECHECK_MS = 25


def _qobject_is_valid(obj: QObject) -> bool:
    if _is_valid_qobject is None:
        return True
    try:
        return bool(_is_valid_qobject(obj))
    except RuntimeError:
        return False


def _safe_class_name(value: object) -> str:
    try:
        return type(value).__name__
    except Exception:
        return "unknown"


def _runtime_event(reason: str) -> str:
    reason = str(reason or "runtime")
    if "setting" in reason:
        return "settings"
    if "custom" in reason or "edit" in reason:
        return "custom_edit"
    if "monitor" in reason:
        return "monitor_topology"
    if "dialog" in reason:
        return "settings_dialog"
    return "runtime"


def qt_replacement_may_run(engine: object | None) -> bool:
    """Return whether replacement code may safely create Qt objects."""

    app = QCoreApplication.instance()
    if app is None or QCoreApplication.closingDown():
        return False
    if engine is None or bool(
        getattr(engine, "_terminal_shutdown_requested", False)
    ):
        return False
    get_state = getattr(engine, "_get_state", None)
    if callable(get_state):
        try:
            if getattr(get_state(), "name", "") == "SHUTTING_DOWN":
                return False
        except Exception:
            return False
    return True


def collect_runtime_roots(manager: object) -> tuple[list[QObject], list[object]]:
    """Collect runtime roots through the display orchestrator's contract."""

    collect = getattr(manager, "collect_runtime_retirement_roots", None)
    if not callable(collect):
        raise RuntimeError(
            "Display manager has no collect_runtime_retirement_roots() contract"
        )
    qobjects, python_owners = collect()
    return list(qobjects), list(python_owners)


class RuntimeDestructionBarrier:
    """One-shot proof that a retiring generation has no live runtime roots."""

    def __init__(
        self,
        engine: object,
        *,
        reason: str,
        retiring_generation: int | None,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        purpose: str = "replacement",
    ) -> None:
        app = QCoreApplication.instance()
        if app is None or QCoreApplication.closingDown():
            raise RuntimeError(
                "Cannot create a runtime destruction barrier without a live Qt event loop"
            )
        # "replacement" proves a retiring generation drained before a replacement
        # runtime is constructed; "terminal" proves the same drain during
        # application exit and must NOT self-cancel merely because terminal
        # shutdown was requested (that request is precisely why it exists). The
        # two purposes share observation; they differ only in the completion
        # gate and what completion is allowed to run.
        self._purpose = str(purpose or "replacement")
        self._is_terminal = self._purpose == "terminal"
        # The barrier is deliberately a plain Python owner.  In particular it
        # must not parent QTimers: constructing a QTimer under a Python QObject
        # during PySide lifecycle churn can enter a native-invalid parent path.
        try:
            self._engine_ref = weakref.ref(engine)
        except TypeError:
            self._engine_ref = lambda: engine
        self.reason = str(reason or "runtime")
        self.event = _runtime_event(self.reason)
        self.retiring_generation = retiring_generation
        self._created_ts = time.monotonic()
        self._timeout_ms = max(100, int(timeout_ms))
        self._sealed = False
        self._completed = False
        self._completion_scheduled = False
        self._had_qobjects = False
        self._continuation: Callable[[], None] | None = None
        self._qobject_labels: dict[int, str] = {}
        self._qobject_refs: dict[int, weakref.ReferenceType[QObject]] = {}
        self._qobject_callbacks: dict[int, Callable[..., None]] = {}
        self._python_labels: dict[int, str] = {}
        self._python_refs: dict[int, weakref.ReferenceType[object]] = {}

        self._timeout_timer: QTimer | None = None
        self._resource_recheck_timer: QTimer | None = None
        self._completion_timer: QTimer | None = None
        try:
            self._timeout_timer = QTimer()
            self._timeout_timer.setSingleShot(True)
            self._timeout_timer.timeout.connect(self._on_timeout)
            self._resource_recheck_timer = QTimer()
            self._resource_recheck_timer.setSingleShot(True)
            self._resource_recheck_timer.timeout.connect(self._maybe_complete)
            self._completion_timer = QTimer()
            self._completion_timer.setSingleShot(True)
            self._completion_timer.timeout.connect(self._complete)
        except Exception:
            self._dispose_timers()
            raise

    def _dispose_timers(self) -> None:
        closing_down = QCoreApplication.closingDown()
        for attribute in (
            "_timeout_timer",
            "_resource_recheck_timer",
            "_completion_timer",
        ):
            timer = getattr(self, attribute, None)
            if timer is None:
                continue
            try:
                timer.stop()
                timer.timeout.disconnect()
            except (RuntimeError, TypeError):
                pass
            if not closing_down:
                try:
                    timer.deleteLater()
                except RuntimeError:
                    pass
            setattr(self, attribute, None)

    def cancel_for_terminal_shutdown(self) -> None:
        """Disarm replacement-only work before the Qt application exits."""

        if self._completed:
            return
        self._continuation = None
        self._completed = True
        self._completion_scheduled = False
        self._dispose_timers()

        for token, callback in tuple(self._qobject_callbacks.items()):
            ref = self._qobject_refs.get(token)
            obj = ref() if ref is not None else None
            if obj is None or not _qobject_is_valid(obj):
                continue
            try:
                obj.destroyed.disconnect(callback)
            except (RuntimeError, TypeError):
                pass

        self._qobject_labels.clear()
        self._qobject_refs.clear()
        self._qobject_callbacks.clear()
        self._python_labels.clear()
        self._python_refs.clear()
        engine = self._engine_ref()
        if engine is not None and getattr(
            engine, "_pending_runtime_destruction_barrier", None
        ) is self:
            engine._pending_runtime_destruction_barrier = None

    @property
    def is_complete(self) -> bool:
        return self._completed

    def watch_qobject(self, obj: QObject, *, label: str | None = None) -> None:
        if self._sealed:
            raise RuntimeError("Cannot add roots after destruction barrier is sealed")
        if not _qobject_is_valid(obj):
            return
        token = id(obj)
        if token in self._qobject_labels:
            return
        self._had_qobjects = True
        self._qobject_labels[token] = label or _safe_class_name(obj)
        try:
            self._qobject_refs[token] = weakref.ref(obj)
        except TypeError:
            pass
        callback = partial(self._on_qobject_destroyed, token)
        self._qobject_callbacks[token] = callback
        obj.destroyed.connect(callback)

    def watch_python_owner(self, owner: object, *, label: str | None = None) -> None:
        if self._sealed:
            raise RuntimeError("Cannot add owners after destruction barrier is sealed")
        if isinstance(owner, QObject):
            self.watch_qobject(owner, label=label)
            return
        token = id(owner)
        if token in self._python_labels:
            return
        try:
            ref = weakref.ref(
                owner,
                partial(self._on_python_owner_released, token),
            )
        except TypeError:
            logger.debug(
                "[LIFECYCLE_BARRIER] Owner is not weak-referenceable class=%s id=%s",
                _safe_class_name(owner),
                token,
            )
            return
        self._python_labels[token] = label or _safe_class_name(owner)
        self._python_refs[token] = ref

    def seal(self) -> None:
        if self._sealed:
            return
        self._sealed = True
        if self._timeout_timer is None:
            raise RuntimeError("Runtime destruction barrier timers were disposed")
        self._timeout_timer.start(self._timeout_ms)
        logger.info(
            "[LIFECYCLE_BARRIER] armed reason=%s retiring_generation=%s "
            "qobjects=%d python_owners=%d python_owner_classes=%s",
            self.reason,
            self.retiring_generation,
            len(self._qobject_labels),
            len(self._python_labels),
            dict(Counter(self._python_labels.values())),
        )
        self._maybe_complete()

    def then(self, continuation: Callable[[], None]) -> None:
        if self._continuation is not None:
            raise RuntimeError("Runtime destruction barrier already has a continuation")
        self._continuation = continuation
        if self._completed:
            self._run_continuation()

    def describe(self) -> dict[str, object]:
        return {
            "reason": self.reason,
            "retiring_generation": self.retiring_generation,
            "qobjects_pending": len(self._qobject_labels),
            "qobjects_by_class": dict(Counter(self._qobject_labels.values())),
            "python_owners_pending": len(self._python_labels),
            "python_owners_by_class": dict(Counter(self._python_labels.values())),
            "resources_pending": len(self._remaining_generation_resources()),
            "thread_work_pending": len(self._remaining_thread_work()),
            "global_subscriptions_pending": len(
                self._remaining_global_subscriptions()
            ),
            "elapsed_ms": max(0.0, (time.monotonic() - self._created_ts) * 1000.0),
            "sealed": self._sealed,
            "complete": self._completed,
        }

    def _on_qobject_destroyed(self, token: int, *_args: object) -> None:
        label = self._qobject_labels.pop(token, "unknown")
        self._qobject_refs.pop(token, None)
        self._qobject_callbacks.pop(token, None)
        logger.debug(
            "[LIFECYCLE_BARRIER] destroyed class=%s id=%s generation=%s",
            label,
            token,
            self.retiring_generation,
        )
        self._maybe_complete()

    def _on_python_owner_released(
        self,
        token: int,
        _ref: weakref.ReferenceType[object],
    ) -> None:
        self._python_labels.pop(token, None)
        self._python_refs.pop(token, None)
        self._maybe_complete()

    def _remaining_generation_resources(self) -> tuple[object, ...]:
        if self.retiring_generation is None:
            return ()
        engine = self._engine_ref()
        manager = getattr(engine, "resource_manager", None) if engine is not None else None
        getter = getattr(manager, "get_resources_by_runtime_generation", None)
        if not callable(getter):
            return ()
        try:
            return tuple(getter(self.retiring_generation))
        except Exception:
            logger.debug(
                "[LIFECYCLE_BARRIER] Generation resource query failed",
                exc_info=True,
            )
            return ()

    def _remaining_thread_work(self) -> tuple[object, ...]:
        if self.retiring_generation is None:
            return ()
        engine = self._engine_ref()
        thread_manager = getattr(engine, "thread_manager", None) if engine is not None else None
        getter = getattr(thread_manager, "get_lifecycle_ownership_snapshot", None)
        if not callable(getter):
            return ()
        try:
            snapshot = getter()
            work: list[object] = [
                task
                for task in snapshot.get("active_tasks", ())
                if task.get("runtime_generation") == self.retiring_generation
            ]
            ui = snapshot.get("ui", {})
            generation_key = str(self.retiring_generation)
            scheduled = int(
                ui.get("scheduled_single_shots_by_generation", {}).get(
                    generation_key,
                    0,
                )
            )
            if scheduled:
                work.append(
                    {
                        "kind": "scheduled_single_shot",
                        "runtime_generation": self.retiring_generation,
                        "count": scheduled,
                    }
                )
            queued = int(
                ui.get("queued_by_generation", {}).get(generation_key, 0)
            )
            if queued:
                work.append(
                    {
                        "kind": "queued_ui_callback",
                        "runtime_generation": self.retiring_generation,
                        "count": queued,
                    }
                )
            return tuple(work)
        except Exception:
            logger.debug(
                "[LIFECYCLE_BARRIER] Thread ownership query failed",
                exc_info=True,
            )
            return ()

    def _remaining_global_subscriptions(self) -> tuple[object, ...]:
        if self.retiring_generation is None:
            return ()
        try:
            from widgets.clock_ticker import GlobalClockTicker

            ticker = GlobalClockTicker._instance
            if ticker is None:
                return ()
            snapshot = ticker.get_lifecycle_ownership_snapshot()
            count = int(
                snapshot.get("subscribers_by_generation", {}).get(
                    str(self.retiring_generation),
                    0,
                )
            )
            if count <= 0:
                return ()
            return (
                {
                    "kind": "clock_subscription",
                    "runtime_generation": self.retiring_generation,
                    "count": count,
                },
            )
        except Exception:
            logger.debug(
                "[LIFECYCLE_BARRIER] Global subscription query failed",
                exc_info=True,
            )
            return ()

    def _maybe_complete(self) -> None:
        if not self._sealed or self._completed or self._completion_scheduled:
            return
        if not self._is_terminal:
            if not qt_replacement_may_run(self._engine_ref()):
                self.cancel_for_terminal_shutdown()
                return
        else:
            # Terminal observation must survive the terminal-shutdown request;
            # it only stops if the Qt loop itself is already gone, in which case
            # there is nothing left to observe and terminal finalization runs.
            app = QCoreApplication.instance()
            if app is None or QCoreApplication.closingDown():
                self._completion_scheduled = True
                self._complete()
                return
        if self._qobject_labels or self._python_labels:
            return
        resources = self._remaining_generation_resources()
        thread_work = self._remaining_thread_work()
        global_subscriptions = self._remaining_global_subscriptions()
        if resources or thread_work or global_subscriptions:
            timer = self._resource_recheck_timer
            if timer is not None and not timer.isActive():
                timer.start(_RESOURCE_RECHECK_MS)
            return
        self._completion_scheduled = True
        # If there were no roots (unit-test/fallback shape), preserve the
        # existing synchronous behavior.  Real Qt roots complete on a later
        # event-loop turn and receive one additional queued boundary so no
        # replacement is constructed inside a QObject.destroyed emission.
        if not self._had_qobjects:
            self._complete()
        else:
            timer = self._completion_timer
            if timer is None:
                raise RuntimeError("Runtime destruction completion timer was disposed")
            timer.start(0)

    def _complete(self) -> None:
        if self._completed:
            return
        self._completion_scheduled = False
        if (
            self._qobject_labels
            or self._python_labels
            or self._remaining_generation_resources()
            or self._remaining_thread_work()
            or self._remaining_global_subscriptions()
        ):
            self._maybe_complete()
            return
        self._completed = True
        self._dispose_timers()
        engine = self._engine_ref()
        elapsed_ms = max(0.0, (time.monotonic() - self._created_ts) * 1000.0)
        logger.info(
            "[LIFECYCLE_BARRIER] complete reason=%s retiring_generation=%s elapsed_ms=%.1f",
            self.reason,
            self.retiring_generation,
            elapsed_ms,
        )
        # Every watched runtime root has now been released.  Weakref callbacks
        # are no longer needed and must not leave a barrier self-cycle behind.
        self._python_labels.clear()
        self._python_refs.clear()
        if engine is not None:
            try:
                from core.performance.resource_metrics import (
                    log_lifecycle_resource_snapshot,
                )

                log_lifecycle_resource_snapshot(
                    engine,
                    event=self.event,
                    stage="after_roots_destroyed",
                )
            except Exception:
                logger.debug(
                    "[LIFECYCLE_BARRIER] Completion snapshot failed",
                    exc_info=True,
                )
        if engine is not None and getattr(
            engine, "_pending_runtime_destruction_barrier", None
        ) is self:
            engine._pending_runtime_destruction_barrier = None
        self._run_continuation()

    def _run_continuation(self) -> None:
        continuation, self._continuation = self._continuation, None
        if continuation is None:
            return
        # A replacement continuation must never run during terminal shutdown; a
        # terminal continuation is the terminal finalization itself and must run
        # even though qt_replacement_may_run() is (correctly) False.
        if not self._is_terminal and not qt_replacement_may_run(self._engine_ref()):
            self.cancel_for_terminal_shutdown()
            return
        try:
            continuation()
        except Exception:
            logger.critical(
                "[LIFECYCLE_BARRIER] %s continuation failed reason=%s",
                "Terminal" if self._is_terminal else "Replacement",
                self.reason,
                exc_info=True,
            )
            if self._is_terminal:
                try:
                    QApplication.quit()
                except Exception:
                    logger.error(
                        "[LIFECYCLE_BARRIER] Terminal finalization quit failed",
                        exc_info=True,
                    )
            else:
                QApplication.exit(1)

    def _on_timeout(self) -> None:
        if self._completed:
            return
        pending_python_owner_refs = tuple(
            (
                token,
                label,
                self._python_refs.get(token),
            )
            for token, label in self._python_labels.items()
            if self._python_refs.get(token) is not None
        )
        resources = self._remaining_generation_resources()
        thread_work = self._remaining_thread_work()
        global_subscriptions = self._remaining_global_subscriptions()
        qobject_classes = dict(Counter(self._qobject_labels.values()))
        python_owner_classes = dict(Counter(self._python_labels.values()))
        resource_labels = [
            {
                "id": entry.get("resource_id"),
                "type": entry.get("resource_type"),
                "class": entry.get("resource_class"),
                "valid": entry.get("qobject_valid"),
                "site": entry.get("creation_site"),
            }
            for entry in resources[:24]
        ]
        logger.critical(
            "[LIFECYCLE_BARRIER] timeout reason=%s retiring_generation=%s "
            "qobjects=%s python_owners=%s resources=%s thread_work=%s "
            "global_subscriptions=%s",
            self.reason,
            self.retiring_generation,
            qobject_classes,
            python_owner_classes,
            resource_labels,
            list(thread_work[:24]),
            list(global_subscriptions[:24]),
        )
        # Preserve the ordinary timeout report/exit ordering, but commit the
        # existing fail-closed policy before any diagnostic graph query.
        # QApplication.exit() takes effect after this callback returns;
        # attribution cannot permit a replacement runtime or change the
        # lifecycle decision.
        if self._is_terminal:
            # Terminal drain timed out: the critical log above is the loud
            # failure record. Still run terminal finalization (clean worker/
            # process shutdown + quit) so the process terminates rather than
            # hanging; never force-kill, and never claim a clean success.
            self._completed = True
            self._completion_scheduled = False
            self._dispose_timers()
            self._run_continuation()
        else:
            self.cancel_for_terminal_shutdown()
            QApplication.exit(1)
        diagnostic_owner_referrers, diagnostic_trace_metadata = (
            self._capture_diagnostic_python_owner_referrers(
                pending_python_owner_refs
            )
        )
        if diagnostic_trace_metadata:
            logger.critical(
                "[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS_SUMMARY] "
                "reason=%s retiring_generation=%s summary=%s",
                self.reason,
                self.retiring_generation,
                diagnostic_trace_metadata,
            )
        for token, label, snapshot in diagnostic_owner_referrers:
            logger.critical(
                "[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS] "
                "reason=%s retiring_generation=%s class=%s id=%s snapshot=%s",
                self.reason,
                self.retiring_generation,
                label,
                token,
                snapshot,
            )

    def _capture_diagnostic_python_owner_referrers(
        self,
        pending_owner_refs: tuple[tuple[int, str, object], ...] | None = None,
    ) -> tuple[tuple[tuple[int, str, str], ...], dict[str, object]]:
        """Attribute survivors only in the explicit diagnostic product.

        The snapshot is taken after the barrier has already failed.  It is
        observational only: no garbage collection, owner release, retry, or
        continuation decision is performed here.
        """

        try:
            from core.build_profile import is_diagnostic_build

            if not is_diagnostic_build():
                return (), {}
            from core.logging.ownership_trace import (
                capture_weak_owner_referrer_snapshots,
            )
        except Exception:
            logger.debug(
                "[LIFECYCLE_BARRIER] Diagnostic ownership tracer unavailable",
                exc_info=True,
            )
            return (), {}

        if pending_owner_refs is None:
            pending_owner_refs = tuple(
                (
                    token,
                    label,
                    self._python_refs.get(token),
                )
                for token, label in self._python_labels.items()
                if self._python_refs.get(token) is not None
            )
        try:
            return capture_weak_owner_referrer_snapshots(pending_owner_refs)
        except Exception:
            logger.debug(
                "[LIFECYCLE_BARRIER] Diagnostic ownership capture failed",
                exc_info=True,
            )
            return (), {}


def create_runtime_destruction_barrier(
    engine: object,
    manager: object,
    *,
    reason: str,
    retiring_generation: int | None,
    purpose: str = "replacement",
) -> RuntimeDestructionBarrier:
    barrier = RuntimeDestructionBarrier(
        engine,
        reason=reason,
        retiring_generation=retiring_generation,
        purpose=purpose,
    )
    try:
        qobjects, python_owners = collect_runtime_roots(manager)
        for obj in qobjects:
            barrier.watch_qobject(obj)
        for owner in python_owners:
            barrier.watch_python_owner(owner)
    except Exception:
        barrier.cancel_for_terminal_shutdown()
        raise
    return barrier


def continue_after_runtime_destruction(
    engine: object,
    continuation: Callable[[], None],
) -> None:
    """Run after the engine's current retiring-generation barrier, if any."""

    if not qt_replacement_may_run(engine):
        logger.info(
            "[LIFECYCLE_BARRIER] Replacement continuation discarded during terminal shutdown"
        )
        return

    barrier = getattr(engine, "_pending_runtime_destruction_barrier", None)
    if isinstance(barrier, RuntimeDestructionBarrier):
        barrier.then(continuation)
        return
    continuation()

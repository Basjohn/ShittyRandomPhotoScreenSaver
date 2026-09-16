"""One GUI/Quick visualizer presentation synchronization owner (H).

The authored logical step publishes an immutable ``VisualizerLogicalFrame`` into
the controller's latest-state mailbox; Quick rendering consumes a
``VisualizerRenderSnapshot`` from the controller's ``VisualizerSnapshotBridge``.
A bound-but-empty bridge is not a complete destination edge: something must
perform the middle operation on the GUI/Quick synchronization side.

``QuickVisualizerPresentationSync`` is that single owner. On each GUI-side pull it:

1. takes the freshest logical publication with latest-wins semantics (no FIFO,
   no catch-up backlog);
2. rejects stale runtime-generation / engine-generation / activation / mode
   identity against the controller's current render identity;
3. resolves the complete current ``ResolvedVisualizerPresentation`` through the
   injected resolver (the display owner owns geometry/scale/fade/style);
4. composes + publishes one immutable ``VisualizerRenderSnapshot`` through the
   controller's existing render bridge (``publish_render_snapshot``);
5. on successful publication, commits that exact resolved presentation to the
   retained presentation owner, then optionally requests retained Quick
   presentation.

It owns no clock, cadence, timer, queue or paint acknowledgement: it takes the
latest state and returns. It never reads QWidget/QObject presentation state or
invokes a second presentation owner.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from core.performance.frame_trace import (
    FrameTraceEvent,
    current_frame_trace,
    logical_timestamp_ns,
)
from widgets.spotify_visualizer.reactivity_diagnostics import (
    maybe_log_snapshot_publication,
)
from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation

logger = get_logger(__name__)

PresentationResolver = Callable[[], Optional[ResolvedVisualizerPresentation]]
PresentationCommitter = Callable[[ResolvedVisualizerPresentation], None]
ScreenIndexResolver = Callable[[], int]




class QuickVisualizerPublicationWake(QObject):
    """Coalesced logical-publication wakeup onto the Qt GUI thread.

    ``request()`` is safe to call from the visualizer logical thread. Qt owns
    the cross-thread event delivery; no polling timer, ThreadManager callback,
    or Python logging sits on this edge. Mailbox coalescing guarantees at most
    one queued wake while an unread latest-state publication exists.
    """

    _wake = Signal()

    def __init__(self, callback: Callable[[], bool]) -> None:
        super().__init__()
        if not callable(callback):
            raise TypeError("visualizer publication wake callback must be callable")
        self._callback: Callable[[], bool] | None = callback
        self._closed = False
        self._pending = False
        self._pending_lock = threading.Lock()
        self._wake.connect(self._deliver, Qt.ConnectionType.QueuedConnection)

    def request(self) -> None:
        # The mailbox already emits only on empty -> populated, but transfer /
        # rebind edges may request the same Qt wake again while delivery is still
        # queued. Bound the cross-thread Qt edge itself to one pending event.
        with self._pending_lock:
            if self._closed or self._pending:
                return
            self._pending = True
        self._wake.emit()

    @Slot()
    def _deliver(self) -> None:
        # Clear before invoking the callback. If the callback drains the mailbox
        # and a producer publishes a newer state while delivery is still running,
        # that empty -> populated edge must be able to queue exactly one successor.
        with self._pending_lock:
            self._pending = False
            callback = self._callback
            closed = self._closed
        if closed or callback is None:
            return
        callback()

    def close(self) -> None:
        with self._pending_lock:
            if self._closed:
                return
            self._closed = True
            self._pending = False
            self._callback = None
        try:
            self._wake.disconnect(self._deliver)
        except (RuntimeError, TypeError):
            pass

    @property
    def pending(self) -> bool:
        """Focused lifecycle/test visibility; never a production polling API."""

        with self._pending_lock:
            return bool(self._pending)

class QuickVisualizerPresentationSync:
    """Drain latest logical state, resolve presentation, publish one snapshot."""

    def __init__(
        self,
        controller: Any,
        *,
        resolve_presentation: PresentationResolver,
        commit_presentation: Optional[PresentationCommitter] = None,
        request_present: Optional[Callable[[], None]] = None,
        resolve_screen_index: Optional[ScreenIndexResolver] = None,
    ) -> None:
        if not callable(resolve_presentation):
            raise TypeError("resolve_presentation must be callable")
        if commit_presentation is not None and not callable(commit_presentation):
            raise TypeError("commit_presentation must be callable or None")
        if request_present is not None and not callable(request_present):
            raise TypeError("request_present must be callable or None")
        if resolve_screen_index is not None and not callable(resolve_screen_index):
            raise TypeError("resolve_screen_index must be callable or None")
        self._controller = controller
        self._resolve_presentation = resolve_presentation
        self._commit_presentation = commit_presentation
        self._request_present = request_present
        self._resolve_screen_index = resolve_screen_index
        self._frame_trace = current_frame_trace()

    def _screen_index(self) -> int:
        resolver = self._resolve_screen_index
        if resolver is None:
            return -1
        try:
            return int(resolver())
        except (RuntimeError, TypeError, ValueError):
            return -1

    def _identity_is_current(self, logical: Any) -> bool:
        identity = self._controller.render_identity
        if identity is None:
            return False
        return (
            int(getattr(logical, "runtime_generation", -1))
            == identity.runtime_generation
            and int(getattr(logical, "engine_generation", -1))
            == identity.engine_generation
            and int(getattr(logical, "activation_id", -1))
            == identity.activation_id
            and str(getattr(logical, "mode_id", "")) == identity.mode_id
        )

    def sync_latest(self) -> bool:
        """Publish the freshest current logical frame as one Quick snapshot."""

        publication = self._controller.logical_mailbox.take()
        if publication is None:
            return False
        logical = publication.state
        if logical is None or not self._identity_is_current(logical):
            return False
        trace = self._frame_trace
        if trace is not None:
            trace.record(
                FrameTraceEvent.GUI_WAKE_DELIVER,
                screen_index=self._screen_index(),
                revision=publication.revision,
                logical_timestamp_ns=logical_timestamp_ns(
                    getattr(logical, "logical_timestamp", 0.0)
                ),
                auxiliary=int(getattr(logical, "runtime_generation", -1)),
            )
        presentation = self._resolve_presentation()
        if presentation is None:
            return False
        published = bool(
            self._controller.publish_render_snapshot(
                logical,
                presentation,
                logical_revision=publication.revision,
            )
        )
        if not published:
            return False
        if trace is not None:
            trace.record(
                FrameTraceEvent.GUI_SNAPSHOT_PUBLISH,
                screen_index=self._screen_index(),
                revision=publication.revision,
                logical_timestamp_ns=logical_timestamp_ns(
                    getattr(logical, "logical_timestamp", 0.0)
                ),
                auxiliary=int(getattr(logical, "runtime_generation", -1)),
            )
        if is_viz_diagnostics_enabled():
            maybe_log_snapshot_publication(
                self._controller,
                logger,
                now_ts=time.time(),
                logical=logical,
                revision=publication.revision,
            )
        if self._commit_presentation is not None:
            # Commit the SAME record embedded in the just-published snapshot.
            # Do not independently resolve presentation again.
            self._commit_presentation(presentation)
        if trace is not None:
            trace.record(
                FrameTraceEvent.GUI_PRESENTATION_COMMIT_READY,
                screen_index=self._screen_index(),
                revision=publication.revision,
                logical_timestamp_ns=logical_timestamp_ns(
                    getattr(logical, "logical_timestamp", 0.0)
                ),
                auxiliary=int(getattr(logical, "runtime_generation", -1)),
            )
        if self._request_present is not None:
            self._request_present()
        if trace is not None:
            trace.record(
                FrameTraceEvent.GUI_PRESENT_REQUEST_READY,
                screen_index=self._screen_index(),
                revision=publication.revision,
                logical_timestamp_ns=logical_timestamp_ns(
                    getattr(logical, "logical_timestamp", 0.0)
                ),
                auxiliary=int(getattr(logical, "runtime_generation", -1)),
            )
        return True


__all__ = [
    "QuickVisualizerPresentationSync",
    "QuickVisualizerPublicationWake",
    "PresentationCommitter",
    "PresentationResolver",
    "ScreenIndexResolver",
]

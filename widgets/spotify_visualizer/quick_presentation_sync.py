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
5. optionally requests retained Quick presentation.

It owns no clock, cadence, timer, queue or paint acknowledgement: it takes the
latest state and returns. It never reads QWidget/QObject presentation state and
never calls the legacy ``present_tick``.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation

# A resolver returns the current complete immutable presentation, or None when
# the destination is not ready to present (admission closed, no geometry yet).
PresentationResolver = Callable[[], Optional[ResolvedVisualizerPresentation]]


class QuickVisualizerPresentationSync:
    """Drain latest logical state, resolve presentation, publish one snapshot."""

    def __init__(
        self,
        controller: Any,
        *,
        resolve_presentation: PresentationResolver,
        request_present: Optional[Callable[[], None]] = None,
    ) -> None:
        if not callable(resolve_presentation):
            raise TypeError("resolve_presentation must be callable")
        if request_present is not None and not callable(request_present):
            raise TypeError("request_present must be callable or None")
        self._controller = controller
        self._resolve_presentation = resolve_presentation
        self._request_present = request_present

    def _identity_is_current(self, logical: Any) -> bool:
        identity = self._controller.render_identity
        if identity is None:
            # Admission is closed (retired / mode change awaiting commit); a
            # publication for no active identity must never be presented.
            return False
        return (
            int(getattr(logical, "runtime_generation", -1)) == identity.runtime_generation
            and int(getattr(logical, "engine_generation", -1)) == identity.engine_generation
            and int(getattr(logical, "activation_id", -1)) == identity.activation_id
            and str(getattr(logical, "mode_id", "")) == identity.mode_id
        )

    def sync_latest(self) -> bool:
        """Publish the freshest current logical frame as one Quick snapshot.

        Returns True iff a fresh, identity-current frame was resolved and
        admitted into the render bridge. A stale frame, a closed admission, an
        empty mailbox or a mode/policy mismatch is a benign no-publication result.
        """

        publication = self._controller.logical_mailbox.take()
        if publication is None:
            return False
        logical = publication.state
        if logical is None or not self._identity_is_current(logical):
            return False
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
        if published and self._request_present is not None:
            self._request_present()
        return published


__all__ = ["QuickVisualizerPresentationSync", "PresentationResolver"]

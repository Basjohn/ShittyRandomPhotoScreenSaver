"""N0.4 in the worker, box 3: the framed view costs nothing per frame; it is resolved and sent at its edges only.

The worker tick's camera cost itself is measured outside the suite (``Current_Plan.md``, the N0.4 box).
"""
from __future__ import annotations

import pytest

from tests.test_framed_view_record import _drawn, pcm  # noqa: F401  (pcm is a fixture)


@pytest.mark.qt
@pytest.mark.parametrize("keyed", (True, False), ids=("keyed", "pre_fix"))
def test_the_framed_view_is_sent_once_per_edge_and_never_across_steady_frames(qt_app, pcm, monkeypatch, keyed):
    # Across steady frames the scene resolves no framed view and the owner sends no view carrying a new one; an
    # Expanded enter and exit, instant or through the fade-through, are one resolve and one send each (a fade changes
    # the drawn record every frame, never its geometry); moving the ordinary card's origin (no camera change) resolves
    # once and sends nothing. Counted on the real owner behind the supervisor stand-in.
    # Negative control: without the scene's geometry key every faded frame resolves the view again.
    from core.process.types import MessageType
    from rendering.quick.visualizer import framed_view as framed_view_module
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    resolves = []
    resolve = framed_view_module.resolve_framed_view
    monkeypatch.setattr(framed_view_module, "resolve_framed_view",
                        lambda presentation: resolves.append(presentation) or resolve(presentation))
    if not keyed:
        monkeypatch.setattr(framed_view_module, "framed_view_geometry_key", lambda _presentation: object())
    engine_worker_link.reset_run_state_for_testing()
    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("waveform_ribbon", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        _pump(rig, 0.4, until=lambda: _drawn(owner) is not None)
        rig.settle()

        def views() -> list:
            return [payload.get("framed_view") for msg, payload in stand_in.sent if msg == MessageType.VIS_SET_VIEW]

        def framed_sends(since: int) -> int:
            """How many views sent since the ``since``-th carried a framed view other than the one before it."""
            sent = views()
            return sum(1 for before, view in zip(sent[since - 1:], sent[since:]) if view != before)

        assert views() and owner.controller.framed_view is not None
        fade = 2.0 * owner.expanded_display_fade_half_s + 0.4
        counts = {}
        for edge in ("steady", "expand", "steady_expanded", "collapse", "origin", "expand_faded", "collapse_faded"):
            sent, resolved, published = len(views()), len(resolves), len(rig.published)
            if edge in ("expand", "collapse", "expand_faded", "collapse_faded"):
                assert owner.set_expanded_display(edge.startswith("expand"), animate=edge.endswith("faded"))
            elif edge == "origin":
                x, y, _w, _h = _drawn(owner).outer_rect
                assert owner.set_authored_outer_origin(x + 17.0, y + 9.0)
            _pump(rig, fade if edge.endswith("faded") else 0.6)
            rig.settle()
            assert len(rig.published) > published + 10, edge          # frames were presented meanwhile
            counts[edge] = (framed_sends(sent), len(resolves) - resolved)
        sends = {edge: count[0] for edge, count in counts.items()}
        assert sends == {"steady": 0, "expand": 1, "steady_expanded": 0, "collapse": 1, "origin": 0,
                         "expand_faded": 1, "collapse_faded": 1}, counts
        resolved = {edge: count[1] for edge, count in counts.items()}
        if keyed:
            assert resolved == {"steady": 0, "expand": 1, "steady_expanded": 0, "collapse": 1, "origin": 1,
                                "expand_faded": 1, "collapse_faded": 1}, counts
        else:
            assert resolved["expand_faded"] > 3 and resolved["collapse_faded"] > 3, counts
    finally:
        rig.close()
        stand_in.close()
        engine_worker_link.reset_run_state_for_testing()

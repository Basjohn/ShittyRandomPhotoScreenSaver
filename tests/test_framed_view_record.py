"""N0.4 in the worker, box 1: ``VIS_SET_VIEW`` carries the drawn card's exact framed view.

The renderer of a framed 3D mode builds its camera from the card's device-pixel rect (``item_pixel_rect`` of its
oriented render frame) and the presentation's ``framed_aperture_scale``. The GUI side resolves the same numbers from
the record the scene draws (``rendering.quick.visualizer.framed_view``), the scene publishes them to the runtime
controller at its geometry edges, and the engine worker's session receives them in ``VIS_SET_VIEW`` (version
``core.framed_view.VIEW_MESSAGE_VERSION``). The oracle is the render node's own frame: Qt's float32
``projectionMatrix() * matrix()`` for the item at the drawn card in its window, through the renderers' calls.
"""
from __future__ import annotations

import math
import pickle
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from core.framed_view import VIEW_MESSAGE_VERSION, FramedView
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from widgets.spotify_visualizer.presentation_geometry import (
    framed_aperture_scale,
    resize_visualizer_presentation,
    resolve_card_drawn_rect,
    resolve_expanded_visualizer_presentation,
    resolve_visualizer_presentation,
)

DPRS = (1.0, 1.25, 1.5)
DISPLAY_DEVICE = (2560, 1440)
BASELINE = (420.0, 280.0)


@dataclass(frozen=True)
class _Snapshot:
    presentation: Any


def _card(mode: str, dpr: float, *, origin=(37.3, 61.7), scale=1.0, extent=None, border=2.0, inset=0.0,
          quarters=0):
    display = (DISPLAY_DEVICE[0] / dpr, DISPLAY_DEVICE[1] / dpr)
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode), display_size=display, outer_origin=origin, dpr=dpr,
        uniform_visual_scale=scale, viewport_extent=extent, content_rotation_quarters=quarters,
        border_width=border, corner_radius=8.0, content_inset=inset, background_color=(0, 0, 0, 255),
        border_color=(255, 255, 255, 255), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))


def _cards(mode: str, dpr: float) -> list[tuple[str, Any, tuple[float, float]]]:
    """(label, the drawn record, the layout extent the worker holds for it today): card sizes, CUSTOM stages (edge
    resize: extent; corner: uniform scale; both), a quarter-turn and Expanded (the worker holds the ordinary
    card's extent: the display-wide record never reaches the controller's metrics)."""
    display = (DISPLAY_DEVICE[0] / dpr, DISPLAY_DEVICE[1] / dpr)
    base = _card(mode, dpr)
    cards = [("canonical", base),
             ("scaled", _card(mode, dpr, scale=1.37, origin=(101.4, 33.9))),
             ("thick_border_inset", _card(mode, dpr, scale=0.83, border=3.0, inset=4.0, origin=(12.1, 7.6)))]
    for label, extent, relative in (("edge_wide", (630.0, 280.0), 1.0), ("edge_tall", (420.0, 517.5), 1.0),
                                    ("edge_both_scaled", (1282.5, 1005.0), 0.71), ("corner", None, 1.613),
                                    ("edge_narrow", (233.3, 280.0), 1.29)):
        cards.append((f"custom_{label}", resize_visualizer_presentation(
            base, display_size=display, outer_origin=(55.55, 44.44), relative_scale=relative,
            viewport_extent=extent)))
    cards.append(("custom_quarter_turn", resize_visualizer_presentation(
        base, display_size=display, outer_origin=(70.2, 90.9), relative_scale=1.1, viewport_extent=(630.0, 280.0),
        content_rotation_quarters=1)))
    cards = [(label, card, card.logical_viewport_extent) for label, card in cards]
    cards.append(("expanded", resolve_expanded_visualizer_presentation(base, display_size=display),
                  base.logical_viewport_extent))
    # The display styles (1D.2): the pixel aspect and the aperture follow each style's extent.
    for style in ("borders_to_edge", "hide_borders"):
        cards.append((f"expanded_{style}", resolve_expanded_visualizer_presentation(
            base, display_size=display, display_style=style), base.logical_viewport_extent))
    return cards


def render_frame(presentation, display_device=DISPLAY_DEVICE):
    """The render node's frame for this record, oriented as the framed renderers orient it: the item at the drawn
    card in a window covering a display of ``display_device`` pixels, Qt's float32 matrix."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QMatrix4x4

    from rendering.quick.scene3d.frame import orient_visualizer_scene_frame
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame

    dpr = float(presentation.dpr)
    viewport = (0, 0, *display_device)
    projection = QMatrix4x4()
    projection.ortho(QRectF(0.0, 0.0, display_device[0] / dpr, display_device[1] / dpr))
    model = QMatrix4x4()
    x, y, _w, _h = resolve_card_drawn_rect(presentation)       # where the scene places the card (R-191)
    model.translate(x, y)
    matrix = tuple(float(v) for v in (projection * model).data())
    frame = QuickVisualizerRenderFrame(snapshot=_Snapshot(presentation), viewport=viewport,
                                       logical_size=(float(presentation.outer_rect[2]),
                                                     float(presentation.outer_rect[3])),
                                       matrix_values=matrix, quad_vao=1)
    return orient_visualizer_scene_frame(frame)


def renderer_view(presentation, display_device=DISPLAY_DEVICE) -> FramedView:
    """What the framed renderers read from the render node's frame for this record (the oracle)."""
    from rendering.quick.scene3d.frame import item_pixel_rect

    frame = render_frame(presentation, display_device)
    _x, _y, width, height = item_pixel_rect(frame)
    oriented = frame.snapshot.presentation
    return FramedView(width / height, framed_aperture_scale(oriented, content=True), framed_aperture_scale(oriented))


def todays_view(extent) -> FramedView:
    """What the worker could build from today's record (the layout extent): ``card_span``'s approximation."""
    return FramedView(extent[0] / extent[1], extent[1] / BASELINE[1], extent[1] / BASELINE[1])


class _Session:
    """The worker session's ``set_view`` (the real method) on a real runtime controller."""

    def __init__(self) -> None:
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

        self._controller = VisualizerRuntimeController(runtime_generation=1, initial_mode="waveform_ribbon")

    def set_view(self, **payload) -> None:
        from core.visualizer_engine.engine_worker import EngineSession

        EngineSession.set_view(self, **payload)


def _send_through_the_link(qt_app, view: FramedView | None, link_patch=None):
    """GUI controller -> ``EngineWorkerLink.send_view`` -> pickled payload -> the worker session's ``set_view``: the
    session controller's framed view."""
    from core.process.types import MessageType, WorkerResponse
    from tests.test_visualizer_owner_engine_worker_liveness import _ManualSupervisor
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    main = VisualizerRuntimeController(runtime_generation=1, initial_mode="waveform_ribbon")
    main.set_framed_view(view)
    supervisor = _ManualSupervisor()
    link = EngineWorkerLink(supervisor, on_lost=lambda _link, _reason: None)
    session = _Session()
    try:
        link.set_view_source(lambda: (main.layout_metrics_snapshot, {}))
        assert link.send_view()
        message, correlation = supervisor.sent[-1]
        assert message == MessageType.VIS_SET_VIEW
        payload = pickle.loads(pickle.dumps(supervisor.payloads[-1]))
        if link_patch is not None:
            payload = link_patch(payload)
        session.set_view(**payload)
        supervisor.callbacks[correlation](WorkerResponse(msg_type=message, seq_no=0, correlation_id=correlation,
                                                         success=True))
    finally:
        link.close()
    return session._controller.framed_view


@pytest.mark.qt
@pytest.mark.parametrize("mode", ("waveform_ribbon", "extruded_bubble"))
@pytest.mark.parametrize("dpr", DPRS)
def test_the_worker_receives_the_renderers_framed_view(qt_app, mode, dpr):
    from rendering.quick.visualizer.framed_view import resolve_framed_view

    discriminating = []
    for label, card, worker_extent in _cards(mode, dpr):
        expected = renderer_view(card)
        resolved = resolve_framed_view(card)
        assert resolved == expected, (label, resolved, expected)
        received = _send_through_the_link(qt_app, resolved)
        assert received == expected and type(received) is FramedView, (label, received, expected)
        # Bit for bit, not close: the floats are the renderer's own.
        assert all(a.hex() == b.hex() for a, b in zip(received, expected)), label
        if todays_view(worker_extent)[:2] != expected[:2]:
            discriminating.append(label)
    # Negative control: today's record (the layout extent, and its height over the canonical one) misses the
    # renderer's aspect or aperture on edge-resized CUSTOM stages and Expanded, so the comparison above discriminates.
    assert {"custom_edge_tall", "custom_edge_both_scaled", "custom_quarter_turn", "expanded",
            "expanded_borders_to_edge", "expanded_hide_borders"} <= set(discriminating), discriminating
    # A switch to a margin-0 style changes the view (its extent is the whole display's, not the inset card's), so the
    # worker follows it; the two margin-0 styles share one extent and so one view (the frame is not the world).
    views = {label: resolve_framed_view(card) for label, card, _extent in _cards(mode, dpr) if label.startswith("expanded")}
    assert views["expanded"] != views["expanded_borders_to_edge"] == views["expanded_hide_borders"], views


@pytest.mark.qt
def test_the_view_message_carries_its_version_and_a_stale_shape_is_refused(qt_app):
    # Negative control: the message as it was before N0.4 (no version, no framed view) is refused by the session,
    # which keeps what it holds; an unknown version too.
    from rendering.quick.visualizer.framed_view import resolve_framed_view

    view = resolve_framed_view(_card("waveform_ribbon", 1.25, extent=(630.0, 280.0)))
    session = _Session()
    with pytest.raises(TypeError):
        session.set_view(extent=(630.0, 280.0), rotations={})                      # today's shape
    with pytest.raises(ValueError):
        session.set_view(version=VIEW_MESSAGE_VERSION - 1, extent=(630.0, 280.0), rotations={}, framed_view=view)
    assert session._controller.framed_view is None
    assert session._controller.committed_viewport_extent == BASELINE           # nothing applied
    assert _send_through_the_link(qt_app, view) == view
    assert _send_through_the_link(qt_app, None) is None


@pytest.mark.qt
def test_a_framed_view_without_the_field_never_reaches_the_worker(qt_app):
    # Negative control for the link: a payload without the framed view (today's record) leaves the worker with none.
    from rendering.quick.visualizer.framed_view import resolve_framed_view

    view = resolve_framed_view(_card("waveform_ribbon", 1.5, extent=(1282.5, 1005.0), scale=0.7))
    stripped = _send_through_the_link(qt_app, view, link_patch=lambda payload: {
        key: value for key, value in payload.items() if key != "framed_view"})
    assert stripped is None and view is not None


@pytest.fixture(scope="module")
def pcm():
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    return paced_pcm(3.0)


def _drawn(owner):
    """The record the owner's scene item draws now."""
    return owner.presentation_runtime.scene_controller.visualizer_item.presentation


@pytest.mark.qt
@pytest.mark.parametrize("bound", (True, False), ids=("bound", "pre_fix"))
def test_the_real_owners_session_holds_the_drawn_cards_framed_view(qt_app, pcm, monkeypatch, bound):
    # End to end on the real owner (the host binding's construct, an unshown runtime, the session in this process
    # behind the supervisor stand-in): the session's framed view is the renderer's view of the card the scene draws,
    # and follows an Expanded enter and exit. Negative control (the owner's binding before N0.4, no framed-view sink):
    # the session never holds one.
    from rendering.quick.runtime import QuickDisplayRuntime
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link

    if not bound:
        bind = QuickDisplayRuntime.bind_visualizer_viewport_config
        monkeypatch.setattr(QuickDisplayRuntime, "bind_visualizer_viewport_config",
                            lambda self, sink, **_kwargs: bind(self, sink))
    engine_worker_link.reset_run_state_for_testing()
    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("waveform_ribbon", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        _pump(rig, 0.4, until=lambda: _drawn(owner) is not None)
        rig.settle()
        session = stand_in.worker._session._controller
        _x, _y, width, height = owner.presentation_runtime.display_identity.geometry
        dpr = float(_drawn(owner).dpr)
        display_device = (round(width * dpr), round(height * dpr))      # the unshown window's render target
        seen = []
        for expanded in (True, False):
            drawn = _drawn(owner)
            seen.append(session.framed_view == renderer_view(drawn, display_device) == owner.controller.framed_view)
            assert owner.set_expanded_display(expanded)
            _pump(rig, 0.3)
            rig.settle()
            assert _drawn(owner) != drawn
        seen.append(session.framed_view == renderer_view(_drawn(owner), display_device))
        # 1D.2: a display style switch while expanded (a fade-through) lands the new style's view in the worker.
        assert owner.set_expanded_display(True)
        _pump(rig, 0.3)
        rig.settle()
        default_view = session.framed_view
        assert owner.set_expanded_display_style("hide_borders")
        _pump(rig, 1.5)
        rig.settle()
        assert _drawn(owner).display_style == "hide_borders" and _drawn(owner).scene_fade == 1.0
        # The unshown window publishes no visible rect, so the whole-display card is resolved on Qt's whole-logical
        # screen size here (half a device pixel past a 1706.67-wide monitor): the oracle is the scene's own
        # resolution of the card it draws (the renderer's view for every card inside the window, test above).
        from rendering.quick.visualizer.framed_view import resolve_framed_view

        expected = resolve_framed_view(_drawn(owner))
        assert expected != default_view, (expected, default_view)
        seen.append(session.framed_view == expected)
        assert seen == ([True] * 4 if bound else [False] * 4), seen
    finally:
        rig.close()
        stand_in.close()
        engine_worker_link.reset_run_state_for_testing()


def test_a_framed_view_is_three_finite_positive_numbers():
    from core.framed_view import admit_framed_view

    assert admit_framed_view(None) is None
    assert admit_framed_view((1.5, 1.0, 1.0)) == FramedView(1.5, 1.0, 1.0)
    for bad in ((1.0, 1.0), (1.0, 0.0, 1.0), (1.0, math.inf, 1.0), (1.0, -1.0, 1.0), "abc", 3.0):
        with pytest.raises(ValueError):
            admit_framed_view(bad)


@pytest.mark.qt
def test_the_scene_publishes_the_framed_view_at_geometry_edges_only(qt_app):
    # The scene resolves the framed view once per geometry edge of the record its item draws and publishes it to the
    # bound sink; a fade (the same geometry) publishes nothing; binding publishes the current one.
    from dataclasses import replace

    from rendering.quick.scene_controller import QuickSceneController

    published = []
    scene = SimpleNamespace(_visualizer_framed_view_sink=None, _visualizer_framed_view_key=None,
                            _visualizer_framed_view=None, _visualizer_viewport_config_sink=None,
                            _custom_layout_session=None, _custom_layout_fullscreen=False)
    for name in ("_publish_visualizer_framed_view", "_resolve_visualizer_framed_view",
                 "set_visualizer_viewport_config_sink", "_publish_visualizer_viewport_config"):
        setattr(scene, name, getattr(QuickSceneController, name).__get__(scene))
    card = _card("waveform_ribbon", 1.25)
    scene._resolve_visualizer_framed_view(card)
    scene.set_visualizer_viewport_config_sink(lambda *_args: None, framed_view_sink=published.append)
    assert published == [renderer_view(card)]
    scene._resolve_visualizer_framed_view(replace(card, content_fade=0.4))
    scene._resolve_visualizer_framed_view(replace(card, scene_fade=0.7))
    assert len(published) == 1
    wider = resize_visualizer_presentation(card, display_size=(2048.0, 1152.0), outer_origin=(10.0, 10.0),
                                           relative_scale=1.0, viewport_extent=(630.0, 280.0))
    scene._resolve_visualizer_framed_view(wider)
    assert published == [renderer_view(card), renderer_view(wider)]
    scene.set_visualizer_viewport_config_sink(None)
    scene._resolve_visualizer_framed_view(card)
    assert len(published) == 2                                    # unbound: nothing more reaches the old sink

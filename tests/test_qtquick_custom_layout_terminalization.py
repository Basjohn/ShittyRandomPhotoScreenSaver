"""Regressions for atomic CUSTOM closure after retained-Qt corruption.

The 2026-09-05 stress run proved that one deleted ordinary ``QQuickItem`` could
throw halfway through ``QuickCustomLayoutOwner._finish()``, leaving one display
out of Edit while another still owned the shared session.  These tests protect
the recovery contract without making reconstruction the healthy Save path.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect

from rendering.custom_layout_session import CustomLayoutSession
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    RetainedOverlayWidget,
)


class _Settings:
    def __init__(self) -> None:
        self.widgets = {}
        self.saved = 0

    def get_widgets_map(self):
        return self.widgets

    def set_widgets_map(self, widgets, *, emit_change=True):
        del emit_change
        self.widgets = widgets

    def save(self):
        self.saved += 1


class _Scene:
    def __init__(self, *, result=(), error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def clear_custom_layout_session(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class _Coordinator:
    def __init__(self) -> None:
        self.retired = 0

    def retire(self) -> None:
        self.retired += 1


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _DeadItem:
    """Non-QObject stand-in: sufficient to exercise the destroyed-edge ledger."""

    def __init__(self) -> None:
        self.destroyed = _Signal()


def _owner(*, reloads=None) -> QuickCustomLayoutOwner:
    target = [] if reloads is None else reloads
    return QuickCustomLayoutOwner(
        settings_manager=_Settings(),
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=target.append,
    )


def _binding(identity: str, scene: _Scene) -> _DisplayBinding:
    return _DisplayBinding(
        identity=identity,
        monitor_route=identity,
        unit=SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene)),
        screen=object(),
        geometry=QRect(0, 0, 800, 600),
    )


def test_finish_closes_every_display_and_shared_owner_when_one_scene_cleanup_throws() -> None:
    owner = _owner()
    first = _Scene(error=RuntimeError("dead retained item"))
    second = _Scene(result=("ordinary:media",))
    coordinator = _Coordinator()
    owner._active = True
    owner._session = CustomLayoutSession()
    owner._bindings = {
        "display:0": _binding("display:0", first),
        "display:1": _binding("display:1", second),
    }
    owner._descriptors = {object(): object()}
    owner._resize_origins = {object(): object()}
    owner._visualizer_pixels_per_world = {object(): 1.0}
    owner._visualizer_move_transfer_latch = {object()}
    owner._coordinator = coordinator

    corruption = owner._finish()

    assert first.calls == 1
    assert second.calls == 1
    assert coordinator.retired == 1
    assert "display:0:scene_cleanup:RuntimeError" in corruption
    assert "display:1:ordinary:media" in corruption
    assert owner.is_active is False
    assert owner.session is None
    assert owner._bindings == {}
    assert owner._descriptors == {}
    assert owner._resize_origins == {}
    assert owner._visualizer_pixels_per_world == {}
    assert owner._visualizer_move_transfer_latch == set()


def test_healthy_live_save_does_not_request_runtime_reload() -> None:
    reloads: list[str] = []
    owner = _owner(reloads=reloads)
    owner._active = True
    owner._session = CustomLayoutSession()
    owner._live_commit_topology_reason = lambda: None
    owner._promote_live_geometry_commit = lambda: None
    owner._finish = lambda: ()

    assert owner.save() is True
    assert reloads == []


def test_save_requests_one_reconstruction_only_after_cleanup_reports_corruption() -> None:
    reloads: list[str] = []
    owner = _owner(reloads=reloads)
    owner._active = True
    owner._session = CustomLayoutSession()
    owner._live_commit_topology_reason = lambda: None
    owner._promote_live_geometry_commit = lambda: None
    owner._finish = lambda: ("display:1:ordinary:gmail",)

    assert owner.save() is True
    assert reloads == ["save_corrupt_retained_runtime"]


def test_cancel_closes_session_and_requests_reconstruction_when_baseline_projection_fails() -> None:
    reloads: list[str] = []
    owner = _owner(reloads=reloads)

    class _BrokenSession:
        def restore_baseline(self):
            raise RuntimeError("deleted QQuickItem")

    owner._active = True
    owner._session = _BrokenSession()
    finishes = []
    owner._finish = lambda: finishes.append(True) or ()

    assert owner.cancel() is True
    assert finishes == [True]
    assert reloads == ["cancel_corrupt_retained_runtime"]


def test_unexpected_qt_destruction_drops_wrapper_and_records_identity_without_polling() -> None:
    host = OrdinaryWidgetPresentationHost(
        host_item=object(),
        context=object(),
        create_overlay_item=lambda _initial, _context: None,
    )
    widget = RetainedOverlayWidget(_DeadItem(), model_identity="gmail")
    widget._host = host
    host._live.append(widget)
    host._by_model_identity["gmail"] = widget

    widget._on_item_destroyed()

    assert host.presentation_for_model_identity("gmail") is None
    assert host.live_count == 0
    assert host.consume_unexpected_qt_deaths() == ("gmail",)
    assert host.consume_unexpected_qt_deaths() == ()

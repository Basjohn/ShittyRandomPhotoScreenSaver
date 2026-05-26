"""Regression tests for GLCompositorWidget transition lifecycle safety.

These tests focus on ensuring that compositor transitions can start and tear
down without raising, even when the GL pipeline is unavailable (our CI
environment). They guard against missing helper hooks when adding new
instrumentation around transition cancellation.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget

from core.animation import AnimationManager, EasingCurve
from core.animation.frame_interpolator import FrameState
from rendering.gl_compositor import GLCompositorWidget
from transitions.base_transition import WipeDirection
from tests._gl_test_utils import solid_pixmap


class DummySettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key]
        if "." in key:
            cur = self._data
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return default
            return cur
        return default


def _setup_compositor(monkeypatch) -> tuple[QWidget, GLCompositorWidget]:
    """Create a GLCompositorWidget with frame pacing patched out."""
    parent = QWidget()
    parent.resize(64, 64)
    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()

    def _fake_start_frame_pacing(duration_sec: float) -> FrameState:
        comp._frame_state = FrameState(duration=duration_sec)
        return comp._frame_state

    monkeypatch.setattr(comp, "_start_frame_pacing", _fake_start_frame_pacing)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_release_transition_textures", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_start_render_timer", lambda *a, **k: None)
    monkeypatch.setattr(comp, "_stop_render_timer", lambda *a, **k: None)
    comp._desync_delay_ms = 0
    return parent, comp


@pytest.mark.qt_no_exception_capture
def test_clear_all_transitions_cancels_active_animation(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841 - parent keeps widget alive
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    anim_id = comp.start_slide(
        old_pm,
        new_pm,
        old_start=QPoint(0, 0),
        old_end=QPoint(64, 64),
        new_start=QPoint(0, 0),
        new_end=QPoint(64, 64),
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    comp._clear_all_transitions()

    assert anim_mgr.get_active_count() == 0
    assert comp._current_anim_id is None

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_gl_prewarm_initializes_shared_compositor(qtbot):
    """GL prewarm should create a shared compositor that can make the GL context current."""
    from rendering.display_widget import DisplayWidget
    from rendering.display_modes import DisplayMode

    settings = DummySettings(
        {
            "display.hw_accel": True,
            "widgets": {"clock": {"enabled": False}},
        }
    )

    widget = DisplayWidget(screen_index=0, display_mode=DisplayMode.FILL, settings_manager=settings)
    qtbot.addWidget(widget)

    widget.show_on_screen()
    qtbot.wait(800)

    comp = getattr(widget, "_gl_compositor", None)
    assert isinstance(comp, GLCompositorWidget), "GL compositor should exist after prewarm"

    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip("GL context not available for GLCompositorWidget prewarm")
    finally:
        widget.close()


@pytest.mark.qt_no_exception_capture
def test_cancel_current_transition_snaps_to_new_pixmap(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.green)
    comp.set_base_pixmap(old_pm)

    anim_id = comp.start_slide(
        old_pm,
        new_pm,
        old_start=QPoint(0, 0),
        old_end=QPoint(64, 64),
        new_start=QPoint(0, 0),
        new_end=QPoint(64, 64),
        duration_ms=200,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    comp.cancel_current_transition(snap_to_new=True)

    assert anim_mgr.get_active_count() == 0
    assert comp._current_anim_id is None
    assert comp._base_pixmap is not None
    assert comp._base_pixmap.cacheKey() == new_pm.cacheKey()

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_transition_start_ensures_program_ready_on_first_use(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    ensured: list[object] = []
    monkeypatch.setattr(comp, "_ensure_transition_program_ready", lambda identity: ensured.append(identity) or True)

    anim_id = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is not None
    assert "wipe" in ensured

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_non_crossfade_transition_uses_shared_desync_start(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    anim_mgr = AnimationManager(fps=60)
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    monkeypatch.setattr(comp, "_apply_desync_strategy", lambda duration_ms: (75, duration_ms + 75))
    scheduled: list[int] = []
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.transitions.QTimer.singleShot",
        lambda delay, callback: scheduled.append(delay),
    )

    start_calls: list[int] = []
    monkeypatch.setattr(comp, "_clear_all_transitions", lambda: start_calls.append(-1))
    monkeypatch.setattr(comp, "_prepare_wipe_textures", lambda: True)
    monkeypatch.setattr(comp, "_pre_upload_textures", lambda prep_fn: prep_fn())
    monkeypatch.setattr(
        comp,
        "_start_transition_animation",
        lambda duration_ms, *args, **kwargs: start_calls.append(duration_ms) or "anim-1",
    )

    anim_id = comp.start_wipe(
        old_pm,
        new_pm,
        direction=WipeDirection.LEFT_TO_RIGHT,
        duration_ms=120,
        easing=EasingCurve.LINEAR,
        animation_manager=anim_mgr,
        on_finished=None,
    )

    assert anim_id is None
    assert scheduled == [75]
    assert start_calls == []

    anim_mgr.cancel_all()
    anim_mgr.stop()


@pytest.mark.qt_no_exception_capture
def test_warm_transition_resources_uses_single_current_context_cycle(qt_app, monkeypatch):
    parent, comp = _setup_compositor(monkeypatch)  # noqa: F841
    old_pm = solid_pixmap(64, 64, Qt.GlobalColor.red)
    new_pm = solid_pixmap(64, 64, Qt.GlobalColor.blue)

    comp._gl_disabled_for_session = False
    comp._gl_pipeline = type("_Pipeline", (), {"initialized": True})()

    calls: list[str] = []
    monkeypatch.setattr(comp, "_ensure_gl_pipeline_ready", lambda: True)
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.gl_lifecycle.bind_transition_program_for_current_context",
        lambda widget, identity: calls.append(f"bind:{identity}") or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_pixmap_textures_in_current_context",
        lambda old_pixmap, new_pixmap: calls.append("textures") or True,
    )
    monkeypatch.setattr(
        comp,
        "_warm_transition_state_in_current_context",
        lambda transition_name, old_pixmap, new_pixmap: calls.append(f"state:{transition_name}") or True,
    )

    make_current_calls = {"count": 0}
    done_current_calls = {"count": 0}

    monkeypatch.setattr(
        comp,
        "makeCurrent",
        lambda: make_current_calls.__setitem__("count", make_current_calls["count"] + 1),
    )
    monkeypatch.setattr(
        comp,
        "doneCurrent",
        lambda: done_current_calls.__setitem__("count", done_current_calls["count"] + 1),
    )

    assert comp.warm_transition_resources("GLCompositorSlideTransition", old_pm, new_pm) is True
    assert calls == ["bind:GLCompositorSlideTransition", "textures", "state:GLCompositorSlideTransition"]
    assert make_current_calls["count"] == 1
    assert done_current_calls["count"] == 1

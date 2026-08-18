"""Presentation liveness reasons for the single-surface display compositor.

Before P2-SINGLE-SURFACE the compositor presented only while a transition was
running, because the visualizer had its own surface and its own update stream.
With one accelerated surface per display, the compositor must also stay live
while a visualizer is visibly active — and the two reasons are independent:

* transition completion must not stop visualizer presentation;
* a visualizer hiding must not stop an active transition.

There is still exactly ONE render strategy instance per display. These bars
exist so a future change cannot quietly reintroduce a second timer, or make one
reason cancel the other.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

from rendering.gl_compositor import GLCompositorWidget


TRANSITION = GLCompositorWidget.PRESENTATION_TRANSITION_ACTIVE
VISUALIZER = GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE


class _Compositor:
    """Minimal stand-in exercising the real reason-model methods."""

    PRESENTATION_TRANSITION_ACTIVE = TRANSITION
    PRESENTATION_VISUALIZER_ACTIVE = VISUALIZER

    def __init__(self) -> None:
        self._presentation_reasons: set[str] = set()
        self.starts = 0
        self.pauses = 0

    def _start_render_timer(self) -> None:
        self.starts += 1

    def _pause_render_timer(self) -> None:
        self.pauses += 1

    acquire_presentation_reason = GLCompositorWidget.acquire_presentation_reason
    release_presentation_reason = GLCompositorWidget.release_presentation_reason
    has_presentation_reason = GLCompositorWidget.has_presentation_reason


class TestReasonModel:
    def test_first_reason_starts_presentation(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(TRANSITION)
        assert comp.starts == 1
        assert comp.pauses == 0
        assert comp.has_presentation_reason(TRANSITION)

    def test_second_reason_does_not_start_a_second_timer(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(TRANSITION)
        comp.acquire_presentation_reason(VISUALIZER)
        assert comp.starts == 1, "one render strategy owns display presentation"

    def test_reacquiring_the_same_reason_is_idempotent(self):
        comp = _Compositor()
        for _ in range(5):
            comp.acquire_presentation_reason(VISUALIZER)
        assert comp.starts == 1
        assert comp._presentation_reasons == {VISUALIZER}

    def test_presentation_pauses_only_when_the_last_reason_releases(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(TRANSITION)
        comp.acquire_presentation_reason(VISUALIZER)

        comp.release_presentation_reason(TRANSITION)
        assert comp.pauses == 0, "visualizer still needs presentation"

        comp.release_presentation_reason(VISUALIZER)
        assert comp.pauses == 1

    def test_releasing_an_unheld_reason_is_a_no_op(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(VISUALIZER)
        comp.release_presentation_reason(TRANSITION)
        assert comp.pauses == 0
        assert comp.has_presentation_reason(VISUALIZER)

    def test_transition_completion_does_not_stop_a_visible_visualizer(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(VISUALIZER)
        comp.acquire_presentation_reason(TRANSITION)
        comp.release_presentation_reason(TRANSITION)
        assert comp.pauses == 0
        assert comp.has_presentation_reason(VISUALIZER)

    def test_visualizer_hiding_does_not_stop_an_active_transition(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(TRANSITION)
        comp.acquire_presentation_reason(VISUALIZER)
        comp.release_presentation_reason(VISUALIZER)
        assert comp.pauses == 0
        assert comp.has_presentation_reason(TRANSITION)

    def test_idle_returns_after_both_release(self):
        comp = _Compositor()
        comp.acquire_presentation_reason(TRANSITION)
        comp.acquire_presentation_reason(VISUALIZER)
        comp.release_presentation_reason(VISUALIZER)
        comp.release_presentation_reason(TRANSITION)
        assert comp._presentation_reasons == set()
        assert comp.pauses == 1


class TestRenderTickHonoursBothReasons:
    def _tick(self, *, transition_live: bool, visualizer_reason: bool):
        updates: list[str] = []
        accepted: list[bool] = []
        frame_state = (
            SimpleNamespace(started=True, completed=False) if transition_live else None
        )
        comp = SimpleNamespace(
            _frame_state=frame_state,
            _presentation_reasons={VISUALIZER} if visualizer_reason else set(),
            PRESENTATION_VISUALIZER_ACTIVE=VISUALIZER,
            update=lambda: updates.append("update"),
            _record_render_timer_tick=lambda **kw: accepted.append(
                bool(kw.get("accepted_update"))
            ),
        )
        GLCompositorWidget._on_render_tick(comp)
        return updates, accepted

    def test_transition_only_presents(self):
        updates, accepted = self._tick(transition_live=True, visualizer_reason=False)
        assert updates == ["update"]
        assert accepted == [True]

    def test_visualizer_only_presents(self):
        """The regression this whole architecture exists to fix."""
        updates, accepted = self._tick(transition_live=False, visualizer_reason=True)
        assert updates == ["update"], (
            "a visible visualizer with no transition must still be presented"
        )
        assert accepted == [True]

    def test_both_present_once(self):
        updates, _ = self._tick(transition_live=True, visualizer_reason=True)
        assert updates == ["update"], "one presentation per tick, not one per reason"

    def test_neither_does_not_present(self):
        updates, accepted = self._tick(transition_live=False, visualizer_reason=False)
        assert updates == []
        assert accepted == [False]


class TestSingleOwner:
    def test_transition_lifecycle_uses_the_reason_model(self):
        """Frame pacing must not call the timer directly any more."""
        for name in ("_start_frame_pacing", "_stop_frame_pacing"):
            source = textwrap.dedent(
                inspect.getsource(getattr(GLCompositorWidget, name))
            )
            called = {
                node.func.attr
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            assert "_start_render_timer" not in called
            assert "_pause_render_timer" not in called
            assert called & {
                "acquire_presentation_reason",
                "release_presentation_reason",
            }, f"{name} must go through the reason model"

    def test_only_the_reason_model_drives_the_render_timer(self):
        """Exactly one owner may start/pause presentation."""
        source = inspect.getsource(GLCompositorWidget)
        tree = ast.parse(textwrap.dedent(source))

        callers: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr in {"_start_render_timer", "_pause_render_timer"}
                ):
                    callers.setdefault(sub.func.attr, set()).add(node.name)

        assert callers.get("_start_render_timer", set()) <= {
            "acquire_presentation_reason"
        }, callers
        assert callers.get("_pause_render_timer", set()) <= {
            "release_presentation_reason"
        }, callers

    def test_teardown_clears_every_reason(self):
        source = textwrap.dedent(inspect.getsource(GLCompositorWidget.cleanup))
        assert "_presentation_reasons.clear()" in source

    def test_no_second_timer_type_was_introduced(self):
        source = inspect.getsource(GLCompositorWidget)
        tree = ast.parse(textwrap.dedent(source))
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "QTimer" not in constructed, "presentation has one timer owner"

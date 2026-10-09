"""Test-owned timings: multi-display spacing, duration and first-image liveness."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QImage, QColor

from core.constants.timing import FIRST_IMAGE_STAGGER_MS, TRANSITION_STAGGER_MS
from engine.display_manager import DisplayManager
from engine.image_pipeline import _image_batch_display_stagger_ms
from rendering.quick.display_image_route import presentation_image_from_processed_qimage
from rendering.quick.transitions.request_resolution import ResolvedQuickTransitionSpec


def _image(name: str):
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(QColor("#334455"))
    return presentation_image_from_processed_qimage(image, image_path=name)


def test_first_image_and_normal_transition_have_separate_admission_spacing():
    assert FIRST_IMAGE_STAGGER_MS == 200
    assert TRANSITION_STAGGER_MS == 400
    assert _image_batch_display_stagger_ms(SimpleNamespace(has_presented_image=lambda: False)) == FIRST_IMAGE_STAGGER_MS
    assert _image_batch_display_stagger_ms(SimpleNamespace(has_presented_image=lambda: True)) == TRANSITION_STAGGER_MS


def test_secondary_transition_extends_duration_without_mutating_batch_spec():
    spec = ResolvedQuickTransitionSpec(
        transition_id="crossfade", requested_name="Crossfade", selected_from_random=False,
        duration_ms=2400, direction=None, parameters={},
    )
    outputs = []
    manager = SimpleNamespace(
        _transition_work_pending=True,
        _quick_batch_expected_screens={0, 1},
        _quick_batch_published_screens=set(),
        _quick_transition_paths={},
        _startup_desktop_seed_screens=set(),
        _runtime_generation=9,
        _resolve_quick_transition_batch_spec=lambda: spec,
    )
    source = _image("source")
    for screen in (0, 1):
        target = SimpleNamespace(
            screen_index=screen,
            current_image=lambda: source,
            present_captured_image=lambda image: None,
            start_transition=lambda req: outputs.append((screen, req)),
            has_running_transition=lambda: False,
        )
        assert DisplayManager._present_quick_captured_image(
            manager, target, _image(f"new-{screen}"), f"new-{screen}",
        ) == "transition_started"
    assert [request.duration_ms for _, request in outputs] == [2400, 2400 + TRANSITION_STAGGER_MS]
    assert spec.duration_ms == 2400
    assert outputs[0][1].transition_id == outputs[1][1].transition_id
    assert outputs[0][1].parameters == outputs[1][1].parameters


def test_single_display_retains_exact_authored_duration():
    spec = ResolvedQuickTransitionSpec(
        transition_id="crossfade", requested_name="Crossfade", selected_from_random=False,
        duration_ms=1500, direction=None, parameters={},
    )
    started = []
    manager = SimpleNamespace(
        _transition_work_pending=True, _quick_batch_expected_screens={0},
        _quick_batch_published_screens=set(), _quick_transition_paths={},
        _startup_desktop_seed_screens=set(), _runtime_generation=4,
        _resolve_quick_transition_batch_spec=lambda: spec,
    )
    target = SimpleNamespace(
        screen_index=0, current_image=lambda: _image("before"),
        present_captured_image=lambda img: None,
        start_transition=started.append, has_running_transition=lambda: False,
    )
    DisplayManager._present_quick_captured_image(manager, target, _image("after"), "after")
    assert len(started) == 1 and started[0].duration_ms == 1500

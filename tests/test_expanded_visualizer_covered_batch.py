"""Expanded Visualizer M4: a covered display leaves image batches at admission (plan 01 E0,
``Docs/Future_Work/Expanded_Visualizer/02_E0_Covered_Display_Admission.md``).

The real batch accounting of ``DisplayManager`` (open, per-screen omission, publish, close) runs on a stand-in owner;
the real image pipeline admits the batch and publishes the worker's result. A covered display that already shows an
image takes no queue advance, no work and no publication, keeps its image and its history entry, and the batch still
closes; a covered display with no image yet is still a destination; a fully covered setup moves nothing."""
from __future__ import annotations

import types
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage

import engine.image_pipeline as pipeline
from engine.display_manager import DisplayManager
from engine.screensaver_engine import ScreensaverEngine
from rendering.display_modes import DisplayMode
from rendering.quick.display_image_route import presentation_image_from_processed_qimage
from rendering.quick.display_processing import DisplayProcessingDescriptor

_BOUND = (
    "_selected_destination_screen_indices", "_reset_quick_transition_batch", "_begin_quick_transition_batch",
    "_finish_quick_transition_batch_if_complete", "set_transition_work_pending",
    "covered_image_destination_screens", "has_admitted_image_destination",
)


def _manager(screens=(0, 1), *, current=None, covered=None):
    """The real batch methods on a stand-in owner; publication installs the image and closes like a finalization."""
    idle, presented = [], []
    manager = SimpleNamespace(
        displays=[SimpleNamespace(screen_index=screen) for screen in screens],
        current_images=dict(current or {}),
        _transition_work_pending=False, _quick_transition_batch_spec=None, _quick_transition_spec_resolved=False,
        _quick_transition_paths={}, _quick_batch_expected_screens=set(), _quick_batch_published_screens=set(),
        _expanded_display_coordinator=SimpleNamespace(
            covered_unit=None if covered is None else SimpleNamespace(screen_index=covered)),
        _cancel_idle_transition_warmup=lambda: None, has_running_transition=lambda: False,
        transition_batch_idle=SimpleNamespace(emit=lambda: idle.append(True)),
        idle=idle, presented=presented,
    )
    for name in _BOUND:
        setattr(manager, name, types.MethodType(getattr(DisplayManager, name), manager))
    manager.has_transition_work_pending = lambda: manager._transition_work_pending
    manager.has_presented_image = lambda: bool(manager.current_images)

    def present(screen_index, image, path):
        presented.append(screen_index)
        manager._quick_batch_published_screens.add(screen_index)
        manager.current_images[screen_index] = path
        manager._finish_quick_transition_batch_if_complete()
        return "transition_started"

    manager.present_processed_presentation_image = present

    def targets():
        return tuple(
            DisplayProcessingDescriptor(screen_index=screen, target_size=QSize(4, 4), logical_size=QSize(4, 4),
                                        display_mode=DisplayMode.FILL, device_pixel_ratio=1.0)
            for screen in screens)

    manager.snapshot_processing_descriptors = targets
    return manager


def _meta(name):
    return SimpleNamespace(local_path=f"C:\\wall\\{name}.jpg", url=None, name=name)


def _engine(manager, *, same_image, queue):
    class _Threads:
        def __init__(self):
            self.tasks = []

        def submit_compute_task(self, task, *, callback, category):
            self.tasks.append((task, callback))

        def run_on_ui_thread(self, callback):
            callback()

    pulled = []

    def next_meta():
        meta = queue.pop(0) if queue else None
        pulled.append(meta)
        return meta

    return SimpleNamespace(
        thread_manager=_Threads(), display_manager=manager,
        settings_manager=SimpleNamespace(get_bool=lambda key: same_image if key == "display.same_image_all_monitors"
                                         else False),
        image_queue=SimpleNamespace(next=next_meta), pulled=pulled,
        _process_supervisor=SimpleNamespace(is_running=lambda _worker: True),
        _runtime_generation=1, _shutting_down=False, _loading_in_progress=True,
        _display_image_history=[], image_changed=SimpleNamespace(emit=lambda _path: None),
    )


def _image(name):
    image = QImage(4, 4, QImage.Format.Format_ARGB32)
    image.fill(QColor("#336699"))
    return presentation_image_from_processed_qimage(image, image_path=name)


@pytest.fixture
def worker(monkeypatch):
    """The worker's processing, recorded: which targets it was handed and with which metas."""
    seen = []

    def per_display(engine, display, index, meta, *_args, **_kwargs):
        seen.append((int(display.screen_index), meta.name))
        return SimpleNamespace(presentation_image=_image(meta.name), path=meta.local_path), meta

    def same(engine, displays, meta, *_args, **_kwargs):
        seen.extend((int(display.screen_index), meta.name) for display in displays)
        return ({index: SimpleNamespace(presentation_image=_image(meta.name), path=meta.local_path)
                 for index, _display in enumerate(displays)}, meta)

    monkeypatch.setattr(pipeline, "_process_display_with_replacements", per_display)
    monkeypatch.setattr(pipeline, "_process_same_image_with_replacements", same)
    monkeypatch.setattr(pipeline, "_get_display_quality_settings", lambda _engine: ("lanczos", False))
    monkeypatch.setattr(pipeline, "schedule_prefetch", lambda _engine: None)
    monkeypatch.setattr(pipeline, "image_processing_authority_available", lambda _engine: True)
    return seen


def _run(engine, first):
    manager = engine.display_manager
    manager.set_transition_work_pending(True)        # the engine's claim (``_try_begin_image_change_work``)
    assert pipeline.load_and_display_image_async(engine, first) is True
    (task, callback), = engine.thread_manager.tasks
    callback(SimpleNamespace(success=True, result=task()))


@pytest.mark.parametrize("same_image", (False, True))
def test_a_covered_display_with_an_image_keeps_it_and_the_batch_still_closes(worker, same_image):
    manager = _manager(current={0: "a", 1: "b"}, covered=1)
    engine = _engine(manager, same_image=same_image, queue=[_meta("next1"), _meta("next2")])
    engine._display_image_history.append([_meta("a"), _meta("b")])
    _run(engine, _meta("next0"))

    assert {screen for screen, _ in worker} == {0}                 # no work for the covered display
    assert engine.pulled == []                                      # no image taken from the queue for it
    assert manager.presented == [0] and manager.current_images[1] == "b"
    assert manager.idle == [True] and not manager._transition_work_pending   # the batch closed
    assert [meta.name for meta in engine._display_image_history[-1]] == ["next0", "b"]   # it keeps its entry


@pytest.mark.parametrize("same_image", (False, True))
def test_without_a_cover_every_display_is_a_destination(worker, same_image):
    # The negative control of the test above: same setup, nothing covered.
    manager = _manager(current={0: "a", 1: "b"})
    engine = _engine(manager, same_image=same_image, queue=[_meta("next1")])
    manager.set_transition_work_pending(True)
    assert pipeline.load_and_display_image_async(engine, _meta("next0")) is True
    (task, _callback), = engine.thread_manager.tasks
    task()
    assert {screen for screen, _ in worker} == {0, 1}
    assert manager._quick_batch_expected_screens == {0, 1}
    assert len(engine.pulled) == (0 if same_image else 1)


def test_a_covered_display_without_an_image_is_still_a_destination(worker):
    manager = _manager(current={}, covered=1)                     # first image: nothing would sit under the card
    assert manager.covered_image_destination_screens() == frozenset()
    engine = _engine(manager, same_image=True, queue=[])
    manager.set_transition_work_pending(True)
    assert pipeline.load_and_display_image_async(engine, _meta("first")) is True
    (task, _callback), = engine.thread_manager.tasks
    task()
    assert {screen for screen, _ in worker} == {0, 1}


def test_coverage_is_read_once_at_admission():
    # Uncovered at admission: both are destinations even if one is covered before the worker returns (its
    # transition then runs under the card and finishes intact); covered at admission: it stays out after an uncover.
    manager = _manager(current={0: "a", 1: "b"})
    targets, covered = pipeline._leave_out_covered_destinations(manager, manager.snapshot_processing_descriptors())
    manager._expanded_display_coordinator.covered_unit = SimpleNamespace(screen_index=1)
    assert [t.screen_index for t in targets] == [0, 1] and covered == frozenset()

    manager = _manager(current={0: "a", 1: "b"}, covered=1)
    manager.set_transition_work_pending(True)
    targets, covered = pipeline._leave_out_covered_destinations(manager, manager.snapshot_processing_descriptors())
    manager._expanded_display_coordinator.covered_unit = None
    assert [t.screen_index for t in targets] == [0] and covered == {1}
    assert manager._quick_batch_expected_screens == {0}


def test_every_display_covered_moves_nothing_before_the_queue():
    manager = _manager(screens=(0,), current={0: "a"}, covered=0)
    assert manager.has_admitted_image_destination() is False
    pulled = []
    engine = SimpleNamespace(
        display_manager=manager, image_queue=SimpleNamespace(next=lambda: pulled.append(True)),
        _display_selection_suspended=lambda: False, _rss_startup_image_pending=lambda: False,
        _display_image_history=[["a"]],
    )
    assert ScreensaverEngine._show_next_image(engine, origin="timer") is False
    engine.image_queue.previous = lambda: pulled.append(True)
    ScreensaverEngine._on_previous_requested(engine)
    assert pulled == [] and engine._display_image_history == [["a"]] and not manager._transition_work_pending
    manager._expanded_display_coordinator.covered_unit = None
    assert manager.has_admitted_image_destination() is True    # a collapse re-admits it at the next edge


def test_previous_image_moves_only_uncovered_displays(worker, monkeypatch):
    previous_seen = []

    def previous(engine, targets, metas, *_args):
        previous_seen.extend((int(t.screen_index), m.name) for t, m in zip(targets, metas))
        return {}

    monkeypatch.setattr(pipeline, "_process_previous_images_with_exact_reuse", previous)
    manager = _manager(current={0: "a", 1: "b"}, covered=1)
    engine = _engine(manager, same_image=False, queue=[])
    manager.set_transition_work_pending(True)
    pipeline.load_and_display_image_async_with_metas(engine, [_meta("old0"), _meta("old1")])
    (task, _callback), = engine.thread_manager.tasks
    task()
    assert previous_seen == [(0, "old0")]
    assert manager._quick_batch_expected_screens == {0}

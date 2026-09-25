"""Replacement first image: one admission owner, never a replay + retry pair.

The 2026-09-25 double-wake evidence showed every monitor rebuild submitting two
foreground image batches into the fresh generation: the current-image replay
(unclaimed) and, 180 ms later, the startup first-image retry, which saw no
loading work, advanced the queue twice and claimed a second batch.

These bars drive the real ``ScreensaverEngine`` admission code with the real Qt
timer loop. The display owner and the image submission are recording stand-ins:
they prove the engine's admission contract, not native Windows hotplug.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from engine.screensaver_engine import EngineState, ScreensaverEngine
from sources.base_provider import ImageMetadata, ImageSourceType


class _DisplayOwner:
    """Batch owner with the DisplayManager admission contract."""

    def __init__(self) -> None:
        self.pending = False
        self.presented = False
        self.pending_edges: list[bool] = []

    def has_transition_work_pending(self) -> bool:
        return self.pending

    def set_transition_work_pending(self, pending: bool, *, screen_index=None) -> None:
        self.pending_edges.append(bool(pending))
        if screen_index is None:
            self.pending = bool(pending)

    def has_presented_image(self) -> bool:
        return self.presented

    def has_admissible_transition_for_open_batch(self) -> bool:
        return True

    def show_error(self, _message: str) -> None:
        pass


class _Queue:
    def __init__(self) -> None:
        self.next_calls = 0

    def next(self):
        self.next_calls += 1
        return _meta(f"queued_{self.next_calls}.jpg")


class _Supervisor:
    def is_running(self, _worker_type) -> bool:
        return True


def _meta(name: str) -> ImageMetadata:
    return ImageMetadata(
        source_type=ImageSourceType.FOLDER,
        source_id="test",
        image_id=name,
        local_path=Path(name),
    )


# Each engine takes a generation no earlier test in this process retired:
# ThreadManager rejects delayed callbacks of any cancelled generation.
_GENERATIONS = itertools.count(7001)


@pytest.fixture
def replacement_engine(qt_app, monkeypatch):
    engine = ScreensaverEngine()
    engine._runtime_generation = next(_GENERATIONS)
    owner = _DisplayOwner()
    queue = _Queue()
    submissions: list[str] = []

    def _submit(image_meta, retry_count=0, *, perf_trace=None):
        submissions.append(str(image_meta.local_path))
        return True

    engine.display_manager = owner
    engine.image_queue = queue
    engine.thread_manager = object()
    engine._process_supervisor = _Supervisor()
    engine._state = EngineState.STOPPED
    monkeypatch.setattr(engine, "_load_and_display_image_async", _submit)
    monkeypatch.setattr(engine, "_prepare_random_transition_if_needed", lambda: None)
    yield engine, owner, queue, submissions
    engine._state = EngineState.SHUTTING_DOWN


def test_topology_replay_is_the_only_first_image_admission(replacement_engine, qtbot):
    engine, owner, queue, submissions = replacement_engine
    engine._pending_monitor_replay_image = _meta("current.jpg")

    assert engine.start(show_first_image=False) is True
    engine._on_displays_ready(1, owner, engine._runtime_generation)

    # Longer than the 180 ms startup retry: a scheduled retry would have fired
    # while the replay is still processing (nothing presented yet).
    qtbot.wait(450)

    assert submissions == ["current.jpg"]
    assert queue.next_calls == 0
    assert engine._loading_in_progress is True
    assert owner.pending is True

    # The rotation timer coalesces behind the claimed replay instead of
    # admitting a parallel batch into the fresh generation.
    engine._on_rotation_timer()
    assert submissions == ["current.jpg"]
    assert queue.next_calls == 0


def test_rejected_replay_admission_hands_first_image_to_bounded_retry(
    replacement_engine,
    qtbot,
    monkeypatch,
):
    engine, owner, queue, submissions = replacement_engine
    engine._pending_monitor_replay_image = _meta("current.jpg")
    attempts: list[str] = []

    def _reject_first(image_meta, retry_count=0, *, perf_trace=None):
        attempts.append(str(image_meta.local_path))
        if len(attempts) == 1:
            return False
        submissions.append(str(image_meta.local_path))
        return True

    monkeypatch.setattr(engine, "_load_and_display_image_async", _reject_first)

    assert engine.start(show_first_image=False) is True
    engine._on_displays_ready(1, owner, engine._runtime_generation)

    # The rejected replay released its claim; the retry then admits exactly one
    # queue image through the ordinary owner.
    assert engine._loading_in_progress is False
    qtbot.waitUntil(lambda: bool(submissions), timeout=2000)
    qtbot.wait(450)
    assert attempts[0] == "current.jpg"
    assert submissions == ["queued_1.jpg"]
    assert engine._loading_in_progress is True


def test_replay_is_rejected_while_another_batch_owns_the_generation(
    replacement_engine,
    qtbot,
):
    engine, owner, queue, submissions = replacement_engine
    engine._pending_monitor_replay_image = _meta("current.jpg")
    owner.pending = True  # a batch already owns the destination

    assert engine._admit_monitor_replay_image(_meta("current.jpg")) is False
    assert submissions == []
    assert queue.next_calls == 0
    assert engine._loading_in_progress is False

"""Studio analysed clips: one bounded store per mode, and the worker's output parsed off the GUI thread (AC-06).

* Every adapter with its own clip worker (Waveform, Extruded Bubble, Bubble, Sphere) keeps its analysed clips in
  ``engine_answers``' bounded per-mode store: ``ANALYSED_LIMIT + 5`` distinct analyses keep only the newest
  ``ANALYSED_LIMIT`` (the oldest analyse again; the newest come from the store). The former class-level dicts kept
  every analysis for the process (one per Audio Analysis edit, about 0.66 MB each for Extruded Bubble).
* ``ClipLoadJob._on_finished`` (the QProcess.finished slot, GUI thread) never parses the worker's JSON: the parse
  and conversion run on the app-shared ThreadManager's IO pool and the inputs come back on the GUI thread, fenced
  on ``cancel``.
No worker process is started (the adapters' job is a stub; the parse tests never start their QProcess).
"""
from __future__ import annotations

import threading
import time
import uuid

import pytest

ADAPTERS = (
    ("ui.studio.waveform_adapter", "WaveformStudioAdapter"),
    ("ui.studio.extruded_bubble_adapter", "ExtrudedBubbleStudioAdapter"),
    ("ui.studio.bubble_adapter", "BubbleStudioAdapter"),
    ("ui.studio.sphere_adapter", "SphereStudioAdapter"),
)


@pytest.mark.parametrize("module_name,class_name", ADAPTERS, ids=[a[1] for a in ADAPTERS])
def test_each_adapter_keeps_only_the_newest_analysed_clips(qt_app, monkeypatch, module_name, class_name):
    import importlib
    import ui.studio.waveform_recorded_inputs as wri
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.engine_answers import ANALYSED_LIMIT
    started = []

    class StubJob:
        """The worker, landing at once: one distinct result per analysis."""
        def __init__(self, clip, settings, finished, **_kwargs):
            started.append(clip.description)
            finished(("inputs", clip.description), "")

        def cancel(self):
            pass

    monkeypatch.setattr(wri, "ClipLoadJob", StubJob)
    adapter = getattr(importlib.import_module(module_name), class_name)()
    run = uuid.uuid4().hex
    clips = [StudioFixture(f"clip:probe{i}", f"Probe {i}", RECORDED, 1.0, f"probe-{run}-{i}")
             for i in range(ANALYSED_LIMIT + 5)]
    for clip in clips:
        adapter.start_clip_load(clip, {}, lambda *_a: None)
    assert len(started) == len(clips)

    landed = []
    for clip in clips[-ANALYSED_LIMIT:]:                    # the newest: from the store, no new analysis
        assert adapter.start_clip_load(clip, {}, lambda r, e="": landed.append(r)) is None
    assert landed == [("inputs", c.description) for c in clips[-ANALYSED_LIMIT:]]
    assert len(started) == len(clips)

    for clip in clips[:5]:                                  # the oldest were evicted: analysed again
        adapter.start_clip_load(clip, {}, lambda *_a: None)
    assert started[len(clips):] == [c.description for c in clips[:5]], \
        f"{class_name}: the oldest analyses are still held past ANALYSED_LIMIT"


# ------------------------------------------------------------------------------------------- off-thread parse
@pytest.fixture
def app_threads(qt_app):
    from core.threading.manager import ThreadManager
    previous = ThreadManager.get_app_shared()
    manager = ThreadManager.create_helper_manager()
    ThreadManager.set_app_shared(manager)
    yield manager
    ThreadManager.set_app_shared(previous)
    manager.shutdown(wait=True)


@pytest.fixture
def unstarted_job(qt_app, monkeypatch):
    """A real ``ClipLoadJob`` whose QProcess never starts; its worker's output written by the test."""
    import json as real_json
    from PySide6.QtCore import QProcess
    import ui.studio.waveform_recorded_inputs as wri
    from ui.studio.adapter import RECORDED, StudioFixture
    monkeypatch.setattr(QProcess, "start", lambda self, *_a, **_k: None)
    parsed_on = []

    class RecordingJson:
        dumps = staticmethod(real_json.dumps)

        @staticmethod
        def loads(text, *a, **k):
            parsed_on.append(threading.get_ident())
            return real_json.loads(text, *a, **k)

    monkeypatch.setattr(wri, "json", RecordingJson)
    jobs = []

    def make(convert, finished):
        clip = StudioFixture("clip:probe", "Probe", RECORDED, 1.0, "probe")
        job = wri.ClipLoadJob(clip, {}, finished, convert=convert)
        job._output_path.write_text(real_json.dumps({"duration": 2.0}), encoding="utf-8")
        jobs.append(job)
        return job
    yield make, parsed_on
    for job in jobs:
        job._directory.cleanup()


def _pump_until(condition, seconds: float = 10.0) -> bool:
    from PySide6.QtCore import QCoreApplication
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    return condition()


def test_the_finished_slot_parses_nothing_on_the_gui_thread(app_threads, unstarted_job):
    make, parsed_on = unstarted_job
    gui = threading.get_ident()
    delivered = []
    job = make(lambda data, fixture: ("inputs", data["duration"], fixture.duration),
               lambda result, error="": delivered.append((result, error, threading.get_ident())))
    job._on_finished(0, None)                               # the QProcess.finished slot, on the GUI thread
    assert gui not in parsed_on, "the worker's JSON was parsed on the GUI thread inside QProcess.finished"
    assert _pump_until(lambda: bool(delivered))
    assert delivered == [(("inputs", 2.0, 2.0), "", gui)]  # converted off thread, delivered on the GUI thread
    assert parsed_on and gui not in parsed_on


def test_a_job_cancelled_while_its_output_is_parsed_delivers_nothing(app_threads, unstarted_job):
    import ui.studio.waveform_recorded_inputs as wri
    make, _parsed_on = unstarted_job
    release = threading.Event()
    delivered = []

    def slow_convert(data, fixture):
        release.wait(5.0)
        return ("inputs",)
    job = make(slow_convert, lambda *a: delivered.append(a))
    job._on_finished(0, None)
    job.cancel()                                            # the user moved on while the parse ran
    release.set()
    assert _pump_until(lambda: job not in getattr(wri, "_HELD", ()))
    assert _pump_until(lambda: job not in wri._CANCELLED)
    assert delivered == []

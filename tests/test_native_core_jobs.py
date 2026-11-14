"""N3.8, D9's job service: its latch and cancellation, GPU-free (``native/core/src/job_service.h``).

Two parts:

- On the built module (``release/native_module``; the module is compiled only on GitHub, so without it these skip and
  say so): ``job_service_self_test`` runs the product's ``JobService`` (its own thread, queue, park, latch,
  cancellation, release and teardown) over a scripted backend whose "GPU wait" the script holds and releases and whose
  next upload or set-up it can fail. Each case has its twin that differs in the one step the case is about (a job not
  cancelled publishes; a job cancelled while queued never runs, one cancelled while running drops its output, one
  cancelled after it published hands it back; a failed job keeps its pixels, a published one drops them; a job wakes
  the parked thread, rest does not).
- Without the module: the Python face's reading of the counts the destruction barrier waits for
  (``NativeCore.pending_native_work``), over a stand-in module.

The drawn proof is ``native/core/python/job_service_check.py`` (real photos, the hidden host, both backends).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()

needs_module = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd",
)


@pytest.fixture(scope="module")
def core():
    return loader.load(MODULE_DIR)


def _run(core, steps: list[dict]) -> dict:
    result = core.job_service_self_test(steps)
    assert "error" not in result, result
    return result


def _step(result: dict, index: int) -> dict:
    return result["steps"][index]


def _final(result: dict) -> dict:
    return result["steps"][-1]


# --------------------------------------------------------------------------------------------- on the built module


@needs_module
def test_a_job_publishes_once_and_its_output_is_released_on_the_job_thread(core):
    result = _run(core, [
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "release", "name": "a"},
        {"op": "wait_idle"},
    ])
    published, released = _step(result, 1), _step(result, 3)
    assert published["idle"] is True
    assert published["jobs"]["a"]["state"] == "done"
    assert published["jobs"]["a"]["pixels_held"] is False          # the job dropped the core's copy once recorded
    assert published["notified"] == 1                               # the latch's edge, once
    assert published["service"]["images"] == 1 and published["counts"]["job_images"] == 1
    assert released["service"]["images"] == 0 and released["service"]["destroyed"] == 1
    assert released["counts"]["job_images"] == 0 and released["counts"]["job_releases_pending"] == 0
    # The service's own thread did the work, never with a Python thread state.
    assert released["service"]["thread_calls"] > 0
    assert released["service"]["thread_calls_with_python_thread_state"] == 0
    assert released["service"]["thread_calls_on_gui_thread"] == 0


@needs_module
def test_a_job_cancelled_while_queued_never_runs(core):
    result = _run(core, [
        {"op": "hold"},
        {"op": "submit", "name": "a"},
        {"op": "wait_entered", "count": 1},
        {"op": "submit", "name": "b"},
        {"op": "cancel", "name": "b"},
        {"op": "go"},
        {"op": "wait_idle"},
    ])
    assert _step(result, 2)["entered"] is True
    assert _step(result, 4)["result"] == "pending"
    end = _final(result)
    assert end["jobs"]["a"]["state"] == "done"                      # its twin, not cancelled, published
    assert end["jobs"]["b"]["state"] == "cancelled"
    assert end["jobs"]["b"]["pixels_held"] is False                 # a cancelled queued job's copy goes at once
    assert end["service"]["backend"]["uploads"] == 1                # b never ran
    assert end["service"]["cancelled"] == 1 and end["notified"] == 1


@needs_module
def test_a_job_cancelled_while_running_drops_its_output_on_its_own_thread(core):
    result = _run(core, [
        {"op": "hold"},
        {"op": "submit", "name": "a"},
        {"op": "wait_entered", "count": 1},
        {"op": "cancel", "name": "a"},
        {"op": "go"},
        {"op": "wait_idle"},
    ])
    assert _step(result, 3)["result"] == "pending"
    end = _final(result)
    assert end["jobs"]["a"]["state"] == "cancelled"
    assert end["service"]["backend"]["uploads"] == 1                # it ran (its "GPU work" completed)
    assert end["service"]["images"] == 0 and end["service"]["destroyed"] == 1
    assert end["service"]["published"] == 0 and end["notified"] == 0   # never published, the item never asked
    assert end["counts"]["job_images"] == 0


@needs_module
def test_a_job_cancelled_after_it_published_hands_its_output_back(core):
    result = _run(core, [
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "cancel", "name": "a"},                              # the consumer then releases it (never sampled)
        {"op": "wait_idle"},
    ])
    assert _step(result, 2)["result"] == "published"
    end = _final(result)
    assert end["jobs"]["a"]["state"] == "done"
    assert end["service"]["images"] == 0 and end["service"]["destroyed"] == 1
    # Control: the same job not handed back keeps its output.
    kept = _run(core, [{"op": "submit", "name": "a"}, {"op": "wait_idle"}])
    assert _final(kept)["service"]["images"] == 1


@needs_module
def test_a_failed_job_keeps_its_pixels_for_the_in_frame_form(core):
    result = _run(core, [
        {"op": "fail_next"},
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "take_pixels", "name": "a"},
        {"op": "submit", "name": "b"},
        {"op": "wait_idle"},
        {"op": "take_pixels", "name": "b"},
    ])
    failed = _step(result, 2)
    assert failed["jobs"]["a"]["state"] == "failed" and failed["jobs"]["a"]["error"]
    assert failed["notified"] == 1                                  # a failure is an edge too: the item commits
    assert _step(result, 3)["pixels"] is True                       # the in-frame form has what it needs
    assert _step(result, 5)["jobs"]["b"]["state"] == "done"        # the service itself did not fail
    assert _step(result, 6)["pixels"] is False                      # control: a published job dropped them


@needs_module
def test_a_service_that_cannot_be_set_up_fails_closed(core):
    result = _run(core, [
        {"op": "fail_setup"},
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "submit", "name": "b"},
    ])
    after = _step(result, 2)
    assert after["jobs"]["a"]["state"] == "failed"
    assert after["service"]["failed"] is True
    assert _step(result, 3)["submitted"] is False                   # every later job runs in the frame


@needs_module
def test_a_device_lost_during_an_upload_fails_the_job_and_the_service_closed(core):
    # Audit N38 L1: the upload's completion edge found the device lost. The job never publishes (Qt would import an
    # image whose upload never completed) and every later job runs in the frame.
    result = _run(core, [
        {"op": "lose_device"},
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "submit", "name": "b"},
    ])
    lost = _step(result, 2)
    assert lost["jobs"]["a"]["state"] == "failed" and "lost" in lost["jobs"]["a"]["error"]
    assert lost["service"]["published"] == 0 and lost["counts"]["job_images"] == 0
    assert lost["service"]["failed"] is True
    assert _step(result, 3)["submitted"] is False
    # Control: an ordinary upload failure fails the job only (the service goes on: the failed-job case above).


@needs_module
def test_a_job_thread_that_cannot_start_fails_the_service_closed(core):
    # Audit N38 L3: Qt only warns when a thread does not start. Nothing may stay queued that no thread runs: the job is
    # refused (its consumer runs the in-frame form) and so is every later one.
    result = _run(core, [
        {"op": "fail_thread_start"},
        {"op": "submit", "name": "a"},
        {"op": "submit", "name": "b"},
        {"op": "release", "name": "a"},
    ])
    assert _step(result, 1)["submitted"] is False and _step(result, 2)["submitted"] is False
    end = _final(result)
    assert end["service"]["failed"] is True
    assert end["counts"]["jobs_queued"] == 0 and end["counts"]["job_releases_pending"] == 0
    assert end["service"]["set_up_error"]
    # Control: without the failed start the same job is queued and runs.
    ran = _run(core, [{"op": "submit", "name": "a"}, {"op": "wait_idle"}])
    assert _step(ran, 0)["submitted"] is True and _final(ran)["jobs"]["a"]["state"] == "done"


@needs_module
def test_the_state_reads_only_the_running_jobs_constant_fields(core):
    # Audit N38 L2: while the job thread may be writing a job's error, times and output, another thread's state reads
    # its constant fields and its atomic state only.
    result = _run(core, [
        {"op": "hold"},
        {"op": "submit", "name": "a"},
        {"op": "wait_entered", "count": 1},
        {"op": "running_state"},
        {"op": "go"},
        {"op": "wait_idle"},
    ])
    assert sorted(_step(result, 3)["running_keys"]) == ["generation", "mips", "name", "size", "state"]
    assert _final(result)["jobs"]["a"]["state"] == "done"


@needs_module
def test_a_windows_frame_is_counted_once_whatever_number_of_drivers_sees_it(core):
    # Audit N38 M1: two drivers on one window (a second host, or one detached and not yet released) counted each frame
    # twice, and a retired image was released a frame early ([1, 2, 3, 4] before the fix).
    result = json.loads(core.module.window_edges_self_test())
    assert result == {"edges": [1, 1, 2, 2], "total": 2}


@needs_module
def test_the_lost_texture_listener_goes_with_the_owners_retire(core, qt_app):
    # Audit N38 L4: no lost edge reaches a retired owner, and the core holds no reference to it after its retire.
    from PySide6.QtQuick import QQuickItem

    parent = QQuickItem()
    mode = core.mode(parent)
    try:
        mode.on_textures_lost(lambda names: None)
        assert mode.state()["textures_lost_listener"] is True          # the control: set until the retire
        mode.retire()
        assert mode.state()["textures_lost_listener"] is False
    finally:
        mode.composite.destroy()


@needs_module
def test_stop_abandons_the_job_in_flight_and_the_queue_and_joins(core):
    result = _run(core, [
        {"op": "hold"},
        {"op": "submit", "name": "a"},
        {"op": "wait_entered", "count": 1},
        {"op": "submit", "name": "b"},
        {"op": "stop"},
    ])
    end = _final(result)
    assert end["jobs"]["a"]["state"] == "abandoned"                 # its "GPU wait" ended after the stop: dropped
    assert end["jobs"]["b"]["state"] == "abandoned"
    assert end["stop"]["abandoned"] == 2 and end["stop"]["images_left"] == 0
    assert end["stop"]["published"] == 0 and end["notified"] == 0
    assert end["submit_after_stop"] is False
    assert end["service"]["backend"]["torn_down"] is True
    after = result["counts_after"]
    assert after["job_threads"] == 0 and after["job_images"] == 0 and after["jobs_queued"] == 0
    assert after["jobs_running"] == 0 and after["job_services"] == 0


@needs_module
def test_the_parked_thread_never_wakes_at_rest(core):
    result = _run(core, [
        {"op": "submit", "name": "a"},
        {"op": "wait_idle"},
        {"op": "rest", "ms": 300},
        {"op": "submit", "name": "b"},
        {"op": "wait_idle"},
    ])
    assert _step(result, 2)["wakeups_during_rest"] == 0
    # Control: a job wakes it.
    assert _final(result)["service"]["wakeups"] > _step(result, 2)["service"]["wakeups"]


@needs_module
def test_a_service_with_no_job_starts_no_thread(core):
    result = _run(core, [{"op": "state"}])
    assert _final(result)["service"]["started"] is False
    assert _final(result)["counts"]["job_threads"] == 0
    assert result["final_stop"]["thread_started"] is False


@needs_module
def test_the_face_reads_the_job_counts(core):
    counts = core.job_counts()
    for key in ("job_services", "job_threads", "jobs_queued", "jobs_running", "job_images", "job_image_bytes",
                "job_releases_pending", "job_wakeups", "job_images_retiring"):
        assert key in counts, key
    assert core.pending_native_work() == []                         # nothing native in this process


# --------------------------------------------------------------------------------------------- the face, GPU-free


class _StandInModule:
    def __init__(self, jobs: dict, live: dict) -> None:
        self._jobs, self._live = jobs, live

    def job_counts(self) -> str:
        return json.dumps(self._jobs)

    def composite_live(self) -> str:
        return json.dumps(self._live)


def test_the_mode_face_passes_the_in_frame_control_and_the_lost_listener():
    from rendering.native.composite import CompositeItem
    from rendering.native.mode import NativeMode

    calls = []

    class Module:
        def __getattr__(self, name):
            def call(*args):
                calls.append((name, args))
            return call

    module = Module()
    mode = NativeMode(module, CompositeItem(module, 9))
    mode.texture("new", b"\0" * 16, (2, 2), mips=True)
    mode.texture("new", b"\0" * 16, (2, 2), in_frame=True)

    def listener(names):
        return names

    mode.on_textures_lost(listener)
    mode.on_textures_lost(None)
    assert [name for name, _args in calls] == ["composite_mode_texture", "composite_mode_texture",
                                               "composite_mode_on_lost", "composite_mode_on_lost"]
    default, control = calls[0][1], calls[1][1]
    assert default == (9, "new", (2, 2), b"\0" * 16, True)          # the device's own route: no control sent
    assert control == (9, "new", (2, 2), b"\0" * 16, False, True)   # the harness control, last
    assert calls[2][1] == (9, listener) and calls[3][1] == (9, None)


def test_pending_native_work_names_only_the_work_in_flight():
    jobs = {"jobs_queued": 1, "jobs_running": 1, "job_releases_pending": 2, "job_images": 3, "job_images_retiring": 1,
            "job_services": 1, "job_threads": 1, "job_wakeups": 40}
    live = {"mode_textures": 2, "mode_texture_images": 1, "items": 1}
    core = loader.NativeCore(_StandInModule(jobs, live), {})
    pending = {entry["kind"]: entry["count"] for entry in core.pending_native_work()}
    assert pending == {"native_jobs_queued": 1, "native_jobs_running": 1, "native_job_releases_pending": 2,
                       "native_job_images_retiring": 1}
    # Audit N38 M3: what live items hold (their textures, an output shown as a front, a copy not yet uploaded) is
    # process-wide and never ends by itself while those items live (another display's background layer): it does not
    # hold a retiring generation's barrier. (Before M3 these kinds were counted: the barrier timed out on them.)
    shown = loader.NativeCore(_StandInModule({"job_images": 3, "job_services": 1}, live), {})
    assert shown.pending_native_work() == []
    # A device's parked service and thread are not work: they go with the window's device.
    idle = loader.NativeCore(_StandInModule({"job_services": 1, "job_threads": 1, "job_wakeups": 9}, {"items": 0}), {})
    assert idle.pending_native_work() == []

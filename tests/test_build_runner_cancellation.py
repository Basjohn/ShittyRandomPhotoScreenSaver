"""Focused lifecycle bars for Build Foundry's owned build process tree."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from typing import Any

from tools import build_runner


class _FakeProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.pid = 4242
        self._handle = 8181
        self.returncode = returncode
        self.wait_calls = 0
        self.kill_calls = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        return self.returncode

    def kill(self) -> None:
        self.kill_calls += 1


class _FakeJob:
    def __init__(self) -> None:
        self.assigned: list[_FakeProcess] = []
        self.terminate_calls = 0
        self.close_calls = 0

    def assign(self, process: _FakeProcess) -> None:
        self.assigned.append(process)

    def terminate(self) -> None:
        self.terminate_calls += 1

    def close(self) -> None:
        self.close_calls += 1


def _fake_owner(process: _FakeProcess, job: _FakeJob) -> build_runner.BuildProcessOwner:
    return build_runner.BuildProcessOwner(
        popen_factory=lambda *_args, **_kwargs: process,
        windows=True,
        job_factory=lambda: job,
        resume_windows_process=lambda _pid: None,
    )


def _fixture_job(tmp_path: Path) -> build_runner.Job:
    script = tmp_path / "build.ps1"
    script.write_text("Write-Host fixture", encoding="utf-8")
    return build_runner.Job(
        "fixture",
        "Fixture",
        "powershell",
        script,
        tmp_path / "release",
        tmp_path / "release" / "artifact.scr",
    )


def test_owner_retires_normal_and_failure_processes_once() -> None:
    for returncode in (0, 9):
        process, job = _FakeProcess(returncode), _FakeJob()
        owner = _fake_owner(process, job)

        active = owner.start(["fixture"])
        assert active is process
        assert process.wait() == returncode
        assert owner.retire(process) is False
        assert owner.retire(process) is False
        assert job.assigned == [process]
        assert job.terminate_calls == 0
        assert job.close_calls == 1


def test_cancel_and_shutdown_terminate_only_the_active_owned_tree_once() -> None:
    process, job = _FakeProcess(), _FakeJob()
    owner = _fake_owner(process, job)
    owner.start(["fixture"])

    assert owner.cancel() is True
    assert owner.cancel() is False
    assert owner.shutdown() is False
    assert job.terminate_calls == 1
    assert owner.retire(process) is True
    assert job.close_calls == 1


def test_cancel_cannot_terminate_a_job_handle_after_completion_retires_it() -> None:
    class _BlockingJob(_FakeJob):
        def __init__(self) -> None:
            super().__init__()
            self.terminate_entered = threading.Event()
            self.allow_terminate = threading.Event()

        def terminate(self) -> None:
            self.terminate_entered.set()
            assert self.allow_terminate.wait(timeout=2), "test did not release cancellation"
            assert self.close_calls == 0, "completion closed the Job while cancellation used it"
            super().terminate()

    process, job = _FakeProcess(), _BlockingJob()
    owner = _fake_owner(process, job)
    owner.start(["fixture"])
    errors: list[BaseException] = []

    def cancel() -> None:
        try:
            assert owner.cancel() is True
        except BaseException as exc:  # pragma: no cover - assertion handoff
            errors.append(exc)

    def retire() -> None:
        try:
            assert owner.retire(process) is True
        except BaseException as exc:  # pragma: no cover - assertion handoff
            errors.append(exc)

    cancelling = threading.Thread(target=cancel)
    cancelling.start()
    assert job.terminate_entered.wait(timeout=2)
    retiring = threading.Thread(target=retire)
    retiring.start()
    time.sleep(0.05)
    assert job.close_calls == 0
    job.allow_terminate.set()
    cancelling.join(timeout=2)
    retiring.join(timeout=2)

    assert not cancelling.is_alive()
    assert not retiring.is_alive()
    assert errors == []
    assert job.terminate_calls == 1
    assert job.close_calls == 1


def test_event_polling_stops_before_rescheduling_after_destroy() -> None:
    class _Root:
        def __init__(self) -> None:
            self.after_calls = 0

        def after(self, _delay: int, _callback) -> None:  # noqa: ANN001
            self.after_calls += 1

    class _PollingHarness:
        def __init__(self) -> None:
            self._destroyed = False
            self._events: queue.Queue[tuple[str]] = queue.Queue()
            self._root = _Root()

        def _dispatch_event(self, _event: tuple[str]) -> None:
            self._destroyed = True

    harness = _PollingHarness()
    harness._events.put(("pipeline_done",))

    build_runner.BuildRunnerApp._poll_events(harness)

    assert harness._root.after_calls == 0


def test_windows_launch_is_suspended_before_assignment_and_closes_unlaunched_job() -> None:
    process, job = _FakeProcess(), _FakeJob()
    captured: dict[str, object] = {}

    def launch(command, **kwargs):  # noqa: ANN001
        captured["command"] = command
        captured.update(kwargs)
        return process

    owner = build_runner.BuildProcessOwner(
        popen_factory=launch,
        windows=True,
        job_factory=lambda: job,
        resume_windows_process=lambda _pid: None,
    )
    owner.start(["fixture"])
    assert int(captured["creationflags"]) & 0x00000004
    assert job.assigned == [process]
    owner.retire(process)

    failed_job = _FakeJob()
    failed_owner = build_runner.BuildProcessOwner(
        popen_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("launch failed")),
        windows=True,
        job_factory=lambda: failed_job,
        resume_windows_process=lambda _pid: None,
    )
    try:
        failed_owner.start(["fixture"])
    except OSError as exc:
        assert "launch failed" in str(exc)
    else:
        raise AssertionError("launch failure must reach the caller")
    assert failed_job.close_calls == 1


def test_aborted_job_result_is_distinct_and_prevents_later_launch(tmp_path: Path) -> None:
    process, job = _FakeProcess(returncode=1), _FakeJob()
    owner = _fake_owner(process, job)
    fixture = _fixture_job(tmp_path)
    launches: list[tuple[object, dict[str, object]]] = []

    def launch(command, **kwargs):  # noqa: ANN001
        launches.append((command, kwargs))
        return process

    owner._popen_factory = launch

    def aborting_wait(timeout: float | None = None) -> int:
        owner.cancel()
        return 1

    process.wait = aborting_wait  # type: ignore[method-assign]
    result = build_runner.run_job(
        fixture,
        build_runner.PreflightResult(pwsh=Path("pwsh.exe")),
        tmp_path / "logs",
        process_owner=owner,
    )

    assert result.aborted is True
    assert result.returncode == 130
    assert result.detail == "Aborted by operator"
    assert len(launches) == 1
    assert owner.cancellation_requested is True

    later = build_runner.run_job(
        fixture,
        build_runner.PreflightResult(pwsh=Path("pwsh.exe")),
        tmp_path / "logs",
        process_owner=owner,
    )
    assert later.aborted is True
    assert len(launches) == 1


def test_pipeline_cancellation_completes_one_job_and_a_fresh_owner_can_rerun(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first = _fixture_job(tmp_path)
    second = build_runner.Job(
        "queued",
        "Queued",
        "powershell",
        tmp_path / "queued.ps1",
        tmp_path / "release",
        tmp_path / "release" / "queued.scr",
    )
    second.script.write_text("Write-Host queued", encoding="utf-8")
    owner = _fake_owner(_FakeProcess(), _FakeJob())

    class _PipelineHarness:
        def __init__(self) -> None:
            self._events: queue.Queue[tuple] = queue.Queue()

    harness = _PipelineHarness()
    launched: list[str] = []
    real_run_job = build_runner.run_job

    def cancel_after_first(
        job: build_runner.Job,
        _preflight: build_runner.PreflightResult,
        *,
        process_owner: build_runner.BuildProcessOwner,
    ) -> build_runner.JobResult:
        launched.append(job.key)
        assert job is first
        assert process_owner.cancel() is False
        return build_runner.JobResult(
            130,
            "Aborted by operator",
            tmp_path / "first.log",
            job.output_dir,
            aborted=True,
        )

    monkeypatch.setattr(
        build_runner,
        "write_curated_visualizer_preset_manifest",
        lambda _root: (),
    )
    monkeypatch.setattr(
        build_runner,
        "helper_build_status",
        lambda _mode: build_runner.HelperBuildStatus(False, "fixture", "fingerprint", 0),
    )
    monkeypatch.setattr(build_runner, "run_job", cancel_after_first)

    build_runner.BuildRunnerApp._pipeline_worker(
        harness,
        "venv",
        (first, second),
        {first.key, second.key},
        build_runner.PreflightResult(pwsh=Path("pwsh.exe")),
        owner,
    )

    events: list[tuple] = []
    while not harness._events.empty():
        events.append(harness._events.get_nowait())
    assert launched == [first.key]
    completed = [event for event in events if event[0] == "job_done"]
    assert len(completed) == 1
    assert completed[0][1] == first.key
    assert completed[0][2].aborted is True
    assert ("job_cancelled", second.key) in events
    assert events[-1] == (
        "pipeline_done",
        False,
        "Pipeline aborted by operator. Remaining selected jobs did not start.",
        True,
    )

    first.expected_artifact.parent.mkdir(parents=True, exist_ok=True)
    first.expected_artifact.write_bytes(b"fresh-success")
    fresh_process, fresh_job = _FakeProcess(), _FakeJob()
    fresh_owner = _fake_owner(fresh_process, fresh_job)
    result = real_run_job(
        first,
        build_runner.PreflightResult(pwsh=Path("pwsh.exe")),
        tmp_path / "fresh-logs",
        process_owner=fresh_owner,
    )

    assert result.returncode == 0
    assert result.aborted is False
    assert fresh_job.assigned == [fresh_process]
    assert fresh_job.close_calls == 1


def _pid_is_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: the PID has already exited.
            return False
        raise ctypes.WinError(error)
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return exit_code.value == still_active
    finally:
        if not kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


def test_cancel_terminates_only_bounded_disposable_parent_and_grandchild(tmp_path: Path) -> None:
    pid_path = tmp_path / "build_tree_pids.json"
    script = """
import json
from pathlib import Path
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path(sys.argv[1]).write_text(json.dumps([child.pid]), encoding="utf-8")
time.sleep(60)
"""
    owner = build_runner.BuildProcessOwner()
    process: Any | None = None
    try:
        process = owner.start(
            [sys.executable, "-c", script, str(pid_path)],
            cwd=str(tmp_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5.0
        while not pid_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pid_path.is_file(), "disposable child did not publish its pid"
        child_pid = int(json.loads(pid_path.read_text(encoding="utf-8"))[0])
        assert _pid_is_alive(child_pid), "disposable child exited before cancellation"

        assert owner.cancel() is True
        process.wait(timeout=10)
        assert owner.retire(process) is True
        deadline = time.monotonic() + 5.0
        while _pid_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not _pid_is_alive(child_pid)
    finally:
        owner.shutdown()
        if process is not None and process.poll() is None:
            process.wait(timeout=10)
            owner.retire(process)

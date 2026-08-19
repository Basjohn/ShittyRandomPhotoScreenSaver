"""Tests for the [SOURCE_HEAD] local-Git-HEAD startup diagnostic.

The subprocess boundary is mocked, so these never require Git, a network, or a
particular checked-out commit.
"""

from __future__ import annotations

import logging
import subprocess
from types import SimpleNamespace

import pytest

from core import source_head

_SHA = "a" * 40  # a valid 40-char hex sha


class _FakeRun:
    def __init__(self, *, returncode=0, stdout=b"", raises=None):
        self.calls: list = []
        self._returncode = returncode
        self._stdout = stdout
        self._raises = raises

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(returncode=self._returncode, stdout=self._stdout)


@pytest.fixture
def env(monkeypatch):
    """Reset the one-shot guard and capture emitted log lines."""
    source_head._LOOKUP_DONE = False
    lines: list[str] = []
    monkeypatch.setattr(
        source_head,
        "logger",
        SimpleNamespace(info=lambda msg, *a: lines.append(msg % a if a else msg)),
    )
    return lines


def _configure(monkeypatch, *, debug: bool, compiled: bool):
    monkeypatch.setattr(source_head, "is_compiled_runtime", lambda: compiled)
    monkeypatch.setattr(source_head, "_debug_logging_active", lambda: debug)


def test_debug_script_run_performs_one_lookup_and_logs_the_sha(env, monkeypatch):
    fake = _FakeRun(returncode=0, stdout=(_SHA + "\n").encode())
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()

    assert len(fake.calls) == 1, "debug+script did not perform exactly one lookup"
    assert env == [f"[SOURCE_HEAD] {_SHA}"]

    cmd, kwargs = fake.calls[0]
    # Local-only, no network, no shell, deterministic cwd, bounded, stderr hidden.
    assert cmd == ["git", "rev-parse", "--verify", "HEAD"]
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == str(source_head._REPO_ROOT)
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["timeout"] == source_head._GIT_TIMEOUT_S


def test_non_debug_performs_zero_git_lookup(env, monkeypatch):
    fake = _FakeRun(returncode=0, stdout=(_SHA + "\n").encode())
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=False, compiled=False)

    source_head.log_source_head()

    assert fake.calls == [], "a non-debug run touched Git"
    assert env == []


def test_compiled_build_performs_zero_git_lookup(env, monkeypatch):
    fake = _FakeRun(returncode=0, stdout=(_SHA + "\n").encode())
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=True)

    source_head.log_source_head()

    assert fake.calls == [], "a compiled/frozen build touched Git"
    assert env == []


def test_git_failure_does_not_affect_startup(env, monkeypatch):
    fake = _FakeRun(returncode=128, stdout=b"")
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()  # must not raise

    assert len(fake.calls) == 1
    assert env == ["[SOURCE_HEAD] unavailable"]


def test_git_exception_does_not_affect_startup(env, monkeypatch):
    fake = _FakeRun(raises=OSError("git not found"))
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()  # must not raise

    assert env == ["[SOURCE_HEAD] unavailable"]


def test_timeout_does_not_affect_startup(env, monkeypatch):
    fake = _FakeRun(raises=subprocess.TimeoutExpired(cmd="git", timeout=1.0))
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()  # must not raise

    assert env == ["[SOURCE_HEAD] unavailable"]


def test_repeated_calls_spawn_git_at_most_once(env, monkeypatch):
    fake = _FakeRun(returncode=0, stdout=(_SHA + "\n").encode())
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()
    source_head.log_source_head()
    source_head.log_source_head()

    assert len(fake.calls) == 1, "repeated calls re-spawned Git within one process"
    assert env == [f"[SOURCE_HEAD] {_SHA}"]


def test_a_failed_lookup_is_not_retried(env, monkeypatch):
    fake = _FakeRun(returncode=128, stdout=b"")
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()
    source_head.log_source_head()

    assert len(fake.calls) == 1, "a failed lookup was retried"


def test_malformed_output_is_unavailable(env, monkeypatch):
    fake = _FakeRun(returncode=0, stdout=b"not-a-sha\n")
    monkeypatch.setattr(source_head.subprocess, "run", fake)
    _configure(monkeypatch, debug=True, compiled=False)

    source_head.log_source_head()

    assert env == ["[SOURCE_HEAD] unavailable"]


def test_debug_active_reflects_the_root_logger_level():
    root = logging.getLogger()
    previous = root.level
    try:
        root.setLevel(logging.DEBUG)
        assert source_head._debug_logging_active() is True
        root.setLevel(logging.INFO)
        assert source_head._debug_logging_active() is False
    finally:
        root.setLevel(previous)


def test_repo_root_contains_the_git_metadata_dir():
    # The resolved root is the repository root (holds .git), not the cwd.
    assert (source_head._REPO_ROOT / ".git").exists()

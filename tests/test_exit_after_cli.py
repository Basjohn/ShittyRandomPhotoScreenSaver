"""RUN-only self-termination CLI for bounded physical/diagnostic sessions."""
from __future__ import annotations

import inspect

import pytest

import main


def test_exit_after_parses_separate_and_equals_forms() -> None:
    assert main._parse_exit_after_seconds(["main.py", "--exit-after", "15", "/s"]) == 15.0
    assert main._parse_exit_after_seconds(["main.py", "--exit-after=60.5", "/s"]) == 60.5
    assert main._parse_exit_after_seconds(["main.py", "/s"]) is None


@pytest.mark.parametrize(
    "argv",
    [
        ["main.py", "--exit-after"],
        ["main.py", "--exit-after", "0", "/s"],
        ["main.py", "--exit-after=-1", "/s"],
        ["main.py", "--exit-after=nan", "/s"],
        ["main.py", "--exit-after=inf", "/s"],
        ["main.py", "--exit-after=1", "--exit-after=2", "/s"],
    ],
)
def test_exit_after_rejects_missing_nonpositive_nonfinite_or_duplicate_values(argv) -> None:
    with pytest.raises(ValueError):
        main._parse_exit_after_seconds(argv)


def test_exit_after_value_does_not_leak_into_windows_mode_parsing(monkeypatch) -> None:
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--exit-after", "15", "/s"])
    mode, preview_hwnd = main.parse_screensaver_args()
    assert mode is main.ScreensaverMode.RUN
    assert preview_hwnd is None

    monkeypatch.setattr(main.sys, "argv", ["main.py", "--exit-after=15", "/c"])
    mode, preview_hwnd = main.parse_screensaver_args()
    assert mode is main.ScreensaverMode.CONFIG
    assert preview_hwnd is None


def test_exit_after_is_dormant_without_the_cli_switch(monkeypatch) -> None:
    class _Timer:
        @staticmethod
        def singleShot(*_args):  # pragma: no cover - must remain untouched
            raise AssertionError("no Qt timer may be created without --exit-after")

    monkeypatch.setattr(main, "QTimer", _Timer)
    assert main._arm_cli_exit_after(object(), None) is False


def test_exit_after_arms_one_qt_oneshot_and_uses_normal_terminal_stop(monkeypatch) -> None:
    scheduled: list[tuple[int, object]] = []

    class _Timer:
        @staticmethod
        def singleShot(milliseconds, callback):
            scheduled.append((milliseconds, callback))

    class _Engine:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def stop(self, *args, **kwargs) -> None:
            self.calls.append((args, kwargs))

    monkeypatch.setattr(main, "QTimer", _Timer)
    engine = _Engine()

    assert main._arm_cli_exit_after(engine, 15.0) is True
    assert len(scheduled) == 1
    assert scheduled[0][0] == 15_000
    assert engine.calls == []

    callback = scheduled[0][1]
    callback()
    assert engine.calls == [((), {"reason": "cli_exit_after"})]


def test_exit_after_uses_no_threadmanager_or_recurring_scheduler() -> None:
    source = inspect.getsource(main._arm_cli_exit_after)
    assert "QTimer.singleShot" in source
    assert "thread_manager" not in source.lower()
    assert "schedule_recurring" not in source

"""Build Foundry UX contracts (Foundry UX audit quick wins): close confirm, clocks, Start gate, failure detail, CLI.

Tk windows cannot be shown here, so the app methods run unbound against small harness objects.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_runner

ROOT = Path(__file__).resolve().parents[1]
App = build_runner.BuildRunnerApp


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.options: dict = {}

    def configure(self, **kwargs) -> None:
        self.calls.append(("configure", kwargs))
        self.options.update(kwargs)

    def state(self, spec) -> None:  # noqa: ANN001
        self.calls.append(("state", {"spec": list(spec)}))
        self.options["state"] = list(spec)


# --- B1: close while running -------------------------------------------------------------------------------

def _close_harness(*, running: bool, answer: bool) -> SimpleNamespace:
    owner = SimpleNamespace(shutdowns=0)
    owner.shutdown = lambda: setattr(owner, "shutdowns", owner.shutdowns + 1)
    harness = SimpleNamespace(
        _running=running,
        _shutdown_requested=False,
        _process_owner=owner,
        _footer_status=_Recorder(),
        asked=0,
        destroyed=0,
    )

    def confirm() -> bool:
        harness.asked += 1
        return answer

    harness._confirm_stop_and_close = confirm
    harness._cancel_auto_close = lambda: None
    harness._destroy_root = lambda: setattr(harness, "destroyed", harness.destroyed + 1)
    return harness


def test_close_while_building_asks_and_keeping_the_build_stops_nothing() -> None:
    harness = _close_harness(running=True, answer=False)
    App._request_close(harness)
    assert harness.asked == 1
    assert harness._process_owner.shutdowns == 0
    assert not harness._shutdown_requested
    assert harness.destroyed == 0


def test_close_while_building_confirmed_stops_and_cancels() -> None:
    harness = _close_harness(running=True, answer=True)
    App._request_close(harness)
    assert harness._process_owner.shutdowns == 1
    assert harness._shutdown_requested


def test_second_close_while_stopping_does_not_ask_again() -> None:
    harness = _close_harness(running=True, answer=True)
    App._request_close(harness)
    App._request_close(harness)
    assert harness.asked == 1


def test_close_when_idle_closes_without_asking() -> None:
    harness = _close_harness(running=False, answer=False)
    App._request_close(harness)
    assert harness.asked == 0
    assert harness.destroyed == 1


def test_confirmation_dialog_defaults_to_no(monkeypatch) -> None:
    captured: dict = {}

    def fake_askyesno(*args, **kwargs):  # noqa: ANN002, ANN003
        captured.update(kwargs)
        return False

    monkeypatch.setattr(build_runner.messagebox, "askyesno", fake_askyesno)
    assert App._confirm_stop_and_close(SimpleNamespace(_root=None)) is False
    assert captured["default"] == "no"


# --- B3: per-row clock ---------------------------------------------------------------------------------------

def test_elapsed_format() -> None:
    assert build_runner.format_elapsed(0) == "00:00"
    assert build_runner.format_elapsed(75.9) == "01:15"
    assert build_runner.format_elapsed(3725) == "1:02:05"
    assert build_runner.format_elapsed(-4) == "00:00"


def _clock_harness(keys=("standard",)) -> SimpleNamespace:
    widgets = {key: SimpleNamespace(status=_Recorder(), tip=None) for key in keys}
    return SimpleNamespace(
        _job_widgets=widgets, _job_started={}, _job_base_text={}, _job_shown_text={},
    )


def test_row_clock_starts_once_and_ticks_from_the_poll() -> None:
    h = _clock_harness()
    App._set_job_status(h, "standard", "Queued", now=100.0)
    App._set_job_status(h, "standard", "Building", now=130.0)  # a later status must not restart the clock
    assert h._job_started["standard"] == 100.0
    assert h._job_widgets["standard"].status.options["text"] == "Building  00:30"
    App._tick_job_clocks(h, now=165.0)
    assert h._job_widgets["standard"].status.options["text"] == "Building  01:05"


def test_tick_touches_a_label_only_when_its_text_changes() -> None:
    h = _clock_harness()
    App._set_job_status(h, "standard", "Building", now=0.0)
    before = len(h._job_widgets["standard"].status.calls)
    App._tick_job_clocks(h, now=0.4)
    App._tick_job_clocks(h, now=0.9)
    assert len(h._job_widgets["standard"].status.calls) == before
    App._tick_job_clocks(h, now=1.0)
    assert len(h._job_widgets["standard"].status.calls) == before + 1


def test_finished_job_stops_its_clock() -> None:
    h = _clock_harness()
    App._set_job_status(h, "standard", "Building", now=0.0)
    App._end_job_clock(h, "standard")
    calls = len(h._job_widgets["standard"].status.calls)
    App._tick_job_clocks(h, now=50.0)
    assert len(h._job_widgets["standard"].status.calls) == calls


def test_poll_drives_the_clock_without_a_new_timer() -> None:
    import queue

    ticks: list[int] = []

    class _Root:
        def __init__(self) -> None:
            self.after_delays: list[int] = []

        def after(self, delay: int, _callback) -> None:  # noqa: ANN001
            self.after_delays.append(delay)

    h = SimpleNamespace(_destroyed=False, _events=queue.Queue(), _root=_Root(),
                        _tick_job_clocks=lambda: ticks.append(1), _dispatch_event=lambda _e: None,
                        _poll_events=lambda: None)
    App._poll_events(h)
    assert ticks == [1]
    assert h._root.after_delays == [100]


# --- M4: Start gate ---------------------------------------------------------------------------------------------

def test_errors_block_start_with_the_first_error_as_reason_and_warnings_do_not() -> None:
    errors = build_runner.PreflightResult(errors=["first problem", "second"], warnings=["w"])
    assert build_runner.start_blocked_reason(errors) == "first problem"
    assert build_runner.start_blocked_reason(build_runner.PreflightResult(warnings=["w"])) == ""
    assert build_runner.start_blocked_reason(build_runner.PreflightResult()) == ""


def _preflight_harness(mode: str = "github") -> SimpleNamespace:
    return SimpleNamespace(
        _mode_var=SimpleNamespace(get=lambda: mode),
        _running=False,
        _preflight=None,
        _preflight_label=_Recorder(),
        _preflight_detail=_Recorder(),
        _jobs=(),
        _job_widgets={},
        _start_button=_Recorder(),
        _footer_status=_Recorder(),
    )


def test_preflight_errors_disable_start_and_show_the_reason() -> None:
    h = _preflight_harness()
    result = build_runner.PreflightResult(errors=["Defaults authority audit failed"])
    App._dispatch_event(h, ("preflight", "github", result))
    assert h._start_button.options["state"] == ["disabled"]
    assert "Defaults authority audit failed" in h._footer_status.options["text"]


def test_preflight_with_only_warnings_leaves_start_enabled() -> None:
    h = _preflight_harness()
    App._dispatch_event(h, ("preflight", "github", build_runner.PreflightResult(warnings=["dirty tree"])))
    assert h._start_button.options["state"] == ["!disabled"]


def test_reenabling_controls_after_a_run_keeps_start_off_while_errors_stand() -> None:
    buttons = {name: _Recorder() for name in ("_start_button", "_select_all_button", "_select_none_button",
                                              "_auto_close_checkbox", "_emergency_stop_button")}
    h = SimpleNamespace(_job_widgets={}, _mode_buttons=[], _preflight=build_runner.PreflightResult(errors=["bad"]),
                        **buttons)
    App._set_controls_enabled(h, True)
    assert h._start_button.options["state"] == ["disabled"]
    assert h._select_all_button.options["state"] == ["!disabled"]
    h._preflight = build_runner.PreflightResult()
    App._set_controls_enabled(h, True)
    assert h._start_button.options["state"] == ["!disabled"]


# --- M1: failed job detail --------------------------------------------------------------------------------------------

def _result(returncode: int, detail: str, aborted: bool = False) -> build_runner.JobResult:
    return build_runner.JobResult(returncode, detail, Path("log.txt"), Path("no_such_output_dir"), aborted=aborted)


def test_failure_note_is_the_readable_reason_and_only_for_real_failures() -> None:
    assert build_runner.job_failure_note("Standard", _result(1, "GitHub run failure: https://x/1")) == (
        "Standard: GitHub run failure: https://x/1")
    assert build_runner.job_failure_note("Standard", _result(1, "  ")) == "Standard: exit code 1"
    assert build_runner.job_failure_note("Standard", _result(0, "ok")) is None
    assert build_runner.job_failure_note("Standard", _result(1, "stopped", aborted=True)) is None


class _Link(_Recorder):
    _command = None

    def pack(self, **_kwargs) -> None:
        pass


def _done_harness() -> SimpleNamespace:
    tip = SimpleNamespace(text="", set_text=lambda text: setattr(tip, "text", text))
    widgets = SimpleNamespace(status=_Recorder(), log_link=_Link(), evidence_link=_Link(), output_link=_Link(),
                              run_link=_Link(), tip=tip)
    return SimpleNamespace(
        _job_widgets={"standard": widgets},
        _jobs=(SimpleNamespace(key="standard", name="Standard"),),
        _job_started={}, _job_base_text={}, _job_shown_text={},
        _failure_notes=[], _progress_completed=0, _progress_total=1,
        _progress_bar=SimpleNamespace(stop=lambda: None, configure=lambda **_k: None),
        _progress_detail=_Recorder(), _footer_status=_Recorder(),
        _end_job_clock=lambda _key: None,
    )




def test_failed_job_detail_reaches_the_footer_and_the_row_tooltip() -> None:
    h = _done_harness()
    App._dispatch_event(h, ("job_done", "standard", _result(1, "GitHub run failure: https://x/1")))
    assert "GitHub run failure: https://x/1" in h._footer_status.options["text"]
    assert h._job_widgets["standard"].tip.text == "GitHub run failure: https://x/1"
    assert h._job_widgets["standard"].status.options["text"].startswith("Failed")


def test_successful_job_leaves_footer_and_tooltip_alone() -> None:
    h = _done_harness()
    App._dispatch_event(h, ("job_done", "standard", _result(0, "ok")))
    assert h._footer_status.calls == []
    assert h._job_widgets["standard"].tip.text == ""


def test_pipeline_done_footer_keeps_the_failure_reasons() -> None:
    text = build_runner.footer_with_failures("Pipeline completed with one or more failures.", ["Standard: boom"])
    assert text.startswith("Pipeline completed") and "Standard: boom" in text
    assert build_runner.footer_with_failures("All good.", []) == "All good."


# --- CLI --------------------------------------------------------------------------------------------------------

def test_run_implies_github_mode_and_the_explicit_spelling_still_works() -> None:
    assert build_runner.parse_args(["--run"]).mode == "github"
    assert build_runner.parse_args(["--mode", "github", "--run"]).mode == "github"
    assert build_runner.parse_args(["--mode", "venv"]).mode == "venv"
    assert build_runner.parse_args([]).mode is None


def test_main_run_without_mode_runs_the_github_pipeline(monkeypatch) -> None:
    called: dict = {}
    monkeypatch.setattr(build_runner, "run_headless", lambda select, iscc_override=None: called.setdefault("ok", 0))
    monkeypatch.setattr(build_runner, "load_preferences", lambda: SimpleNamespace(mode="normal"))
    assert build_runner.main(["--run", "--select", "standard"]) == 0
    assert "ok" in called


def test_main_run_with_a_conflicting_mode_is_still_refused(monkeypatch) -> None:
    monkeypatch.setattr(build_runner, "load_preferences", lambda: SimpleNamespace(mode="normal"))
    assert build_runner.main(["--mode", "venv", "--run"]) == 2


# --- Casing (M6) ----------------------------------------------------------------------------------------------------

def test_build_foundry_buttons_are_title_case() -> None:
    tree = ast.parse((ROOT / "tools" / "build_runner.py").read_text(encoding="utf-8"))
    labels: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in {"Button", "Radiobutton"}:
                for kw in node.keywords:
                    if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                        labels.append(kw.value.value)
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            for item in node.iter.elts:  # the mode buttons: (label, mode) pairs
                if isinstance(item, ast.Tuple) and item.elts and isinstance(item.elts[0], ast.Constant) \
                        and isinstance(item.elts[0].value, str):
                    labels.append(item.elts[0].value)
    assert len(labels) >= 5
    shouting = [t for t in labels if any(
        len([c for c in w if c.isalpha()]) > 3 and w.upper() == w for w in re.split(r"\s+", t))]
    assert not shouting, shouting

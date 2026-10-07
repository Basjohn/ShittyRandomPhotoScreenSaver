from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import run_matrix as harness
from tools.run_matrix import MatrixError, RunCase, load_matrix, run_matrix


def _main_markers() -> str:
    return ("Starting screensaver in RUN mode\n"
            "[AUTO_EXIT] Armed normal terminal shutdown after 1.000 s\n"
            "[AUTO_EXIT] Deadline reached after 1.000 s; requesting normal terminal shutdown\n")


def _qml_markers(session: str = "newrun") -> str:
    return (f"[QT_CAPTURE] event=session_start session={session}\n"
            f"[QT_CAPTURE] event=session_end session={session}\n")


def _write_matrix(path: Path, cases: list[dict]) -> None:
    path.write_text(json.dumps({"schema_version": 1, "cases": cases}), encoding="utf-8")


def _case(name: str, *, entrypoint: str = "main.py", argv: list[str] | None = None,
          duration: float = 1) -> dict:
    return {
        "name": name,
        "entrypoint": entrypoint,
        "argv": ["/s", *(argv or [])],
        "exit_after_seconds": duration,
    }


@pytest.mark.parametrize(
    "bad_case",
    [
        ["--debug"],
        ["/s", "--exit-after", "9"],
        ["/s", "--gui-stall-stacks"],
        ["/s", "--arbitrary"],
    ],
)
def test_rejects_unadmitted_arguments(tmp_path: Path, bad_case: list[str]) -> None:
    matrix_path = tmp_path / "matrix.json"
    item = _case("unsafe")
    item["argv"] = bad_case
    _write_matrix(matrix_path, [item])

    with pytest.raises(MatrixError):
        load_matrix(matrix_path)


@pytest.mark.parametrize("entrypoint", ["main_diagnostic.py", "../main.py", "tools/run_matrix.py"])
def test_rejects_noncanonical_entrypoints(tmp_path: Path, entrypoint: str) -> None:
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path, [_case("unsafe", entrypoint=entrypoint)])

    with pytest.raises(MatrixError):
        load_matrix(matrix_path)


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), 3601])
def test_rejects_invalid_exit_after_duration(tmp_path: Path, duration: float) -> None:
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path, [_case("invalid-duration", duration=duration)])

    with pytest.raises(MatrixError):
        load_matrix(matrix_path)


def test_runs_sequentially_snapshots_logs_and_reports_distinct_failures(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path, [
        _case("clean", argv=["--debug"], duration=1.25),
        _case("fault", argv=["--perf"]),
        _case("nonzero"),
    ])
    cases = load_matrix(matrix_path)
    output_dir = tmp_path / "evidence"
    logs_dir = tmp_path / "product-logs"
    logs_dir.mkdir()
    (logs_dir / "screensaver.log").write_text(
        "Windows fatal exception: older unrelated run\n", encoding="utf-8"
    )
    seen_commands: list[list[str]] = []

    def fake_runner(command: list[str], cwd: Path, stdout_path: Path, stderr_path: Path) -> int:
        run_index = len(seen_commands)
        if run_index:
            first_log = output_dir / "001_clean" / "logs" / "screensaver.log"
            assert first_log.read_text(encoding="utf-8") == (
                "Windows fatal exception: older unrelated run\nrun 1\n" + _main_markers()
            )
        seen_commands.append(list(command))
        assert cwd.name == "ShittyRandomPhotoScreenSaver"
        stdout_path.write_bytes(f"stdout {run_index}\n".encode())
        stderr_path.write_bytes(f"stderr {run_index}\n".encode())
        text = "Windows fatal exception: current run\n" if run_index == 1 else f"run {run_index + 1}\n"
        with (logs_dir / "screensaver.log").open("a", encoding="utf-8") as handle:
            handle.write(text + _main_markers())
        with (logs_dir / "screensaver_qml.log").open("a", encoding="utf-8") as handle:
            handle.write(_qml_markers(f"case{run_index}"))
        return 3 if run_index == 2 else 0

    report = run_matrix(
        cases,
        output_dir,
        runner=fake_runner,
        python_executable="python-test",
        log_dir=logs_dir,
    )

    assert report["status"] == "failed"
    results = report["results"]
    assert [item["status"] for item in results] == ["passed", "failed", "failed"]
    assert [item["exit_code"] for item in results] == [0, 0, 3]
    assert results[1]["faults"][0]["artifact"] == "screensaver.log"
    assert results[1]["faults"][0]["line"] == 6
    assert results[0]["artifacts"][0]["present"] is True
    assert Path(results[0]["artifacts"][0]["path"]).read_text(encoding="utf-8") == (
        "Windows fatal exception: older unrelated run\nrun 1\n" + _main_markers()
    )
    assert seen_commands[0][:3] == ["python-test", str(Path(__file__).resolve().parents[1] / "main.py"), "/s"]
    assert seen_commands[0][-2:] == ["--exit-after", "1.25"]
    assert Path(str(report["report_path"])).is_file()


def test_refuses_existing_artifact_directory_before_launch(tmp_path: Path) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    launches = 0

    def fake_runner(*_args) -> int:
        nonlocal launches
        launches += 1
        return 0

    with pytest.raises(MatrixError, match="already exists"):
        run_matrix([RunCase("one", "main.py", ("/s",), 1)], output_dir, runner=fake_runner)
    assert launches == 0


@pytest.mark.parametrize("entrypoint", [None, "main_mc.py", "main.py"])
def test_admits_canonical_launchers_and_explicit_diagnostic_flags(tmp_path: Path, entrypoint) -> None:
    item = _case("run", argv=["--fresh", "--set"])
    if entrypoint is None:
        del item["entrypoint"]
    else:
        item["entrypoint"] = entrypoint
    path = tmp_path / "matrix.json"
    _write_matrix(path, [item])
    case = load_matrix(path)[0]
    assert case.entrypoint == (entrypoint or "main_mc.py")
    assert case.argv == ("/s", "--fresh", "--set")


@pytest.mark.parametrize("cases", [
    [], [RunCase("x", "../main.py", ("/s",), 1)],
    [RunCase("x", "main.py", ("/s", "--exit-after", "1"), 1)],
    [RunCase("x", "main.py", ("/s",), float("nan"))],
    [RunCase("x", "main.py", ("/s",), True)],
    [RunCase("x", "main.py", ("/s",), 1)] * 101,
    [RunCase("x", "main.py", ("/s",), 1)] * 2,
    [RunCase("..", "main.py", ("/s",), 1), RunCase("_", "main.py", ("/s",), 1)],
])
def test_public_seam_validates_before_creating_artifacts(tmp_path: Path, cases) -> None:
    out = tmp_path / "evidence"
    with pytest.raises(MatrixError):
        run_matrix(cases, out, runner=lambda *_: pytest.fail("must not launch"))
    assert not out.exists()


@pytest.mark.parametrize("mode,expected", [
    ("clean_rotation", "passed"), ("fault_rotation", "failed"),
    ("truncated", "unavailable"), ("missing", "unavailable"),
    ("fresh", "passed"), ("mismatched_session", "unavailable"),
])
def test_current_run_evidence_across_rotation_reset_and_missing_logs(tmp_path: Path, mode, expected) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    old = "Windows fatal exception: stale run\nold tail\n"
    (logs / "screensaver.log").write_text(old)
    (logs / "screensaver_qml.log").write_text(_qml_markers("oldrun"))

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"out\n")
        stderr.write_bytes(b"")
        if mode == "missing":
            return 0
        if "rotation" in mode:
            (logs / "screensaver.log.1").write_bytes((logs / "screensaver.log").read_bytes())
            if mode == "fault_rotation":
                with (logs / "screensaver.log.1").open("a") as stream:
                    stream.write("BufferError: current RUN\n")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(
            _qml_markers("newrun") if mode == "fresh" else _qml_markers("oldrun") +
            (_qml_markers("newrun").replace("session_end session=newrun", "session_end session=other")
             if mode == "mismatched_session" else _qml_markers("newrun")))
        if mode == "mismatched_session":
            (logs / "screensaver.log").write_text(old + _main_markers())
        (logs / "screensaver_settings.log").write_text("settings trace\n")
        (logs / "screensaver_frame_trace.bin.3").write_bytes(b"trace")
        return 0

    argv = ("/s", "--fresh") if mode == "fresh" else ("/s",)
    report = run_matrix([RunCase("one", "main_mc.py", argv, 1)], tmp_path / "out",
                        runner=runner, log_dir=logs)
    result = report["results"][0]
    assert report["status"] == expected
    assert result["status"] == expected
    if expected == "passed":
        assert result["faults"] == []
    if mode == "fault_rotation":
        assert result["faults"][0]["artifact"] == "screensaver.log.1"
        assert result["faults"][0]["line"] == 3
    assert result["source_attribution"]["revision"]
    assert len(result["source_sha256"]) == 64
    if mode != "missing":
        present = {a["name"] for a in result["artifacts"] if a["present"]}
        assert {"screensaver_settings.log", "screensaver_frame_trace.bin.3"} <= present


def test_allows_new_evidence_subdirectory_inside_log_root(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers())
        return 0

    report = run_matrix([RunCase("one", "main_mc.py", ("/s", "--fresh"), 1)],
                        logs / "run_matrix" / "new", runner=runner, log_dir=logs)
    assert report["status"] == "passed"


def test_missing_provenance_is_explicit_unavailable(tmp_path: Path, monkeypatch) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(harness, "_source_attribution", lambda: {"unavailable": ["git unavailable"]})

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers())
        return 0

    report = run_matrix([RunCase("one", "main_mc.py", ("/s",), 1)], tmp_path / "out",
                        runner=runner, log_dir=logs)
    assert report["status"] == "unavailable"
    assert report["results"][0]["source_attribution"] == {"unavailable": ["git unavailable"]}


def test_child_uses_only_product_owned_exit_and_captured_process_output(tmp_path: Path, monkeypatch) -> None:
    def launch(command, **kwargs):
        assert command == ["python", "main_mc.py", "/s", "--exit-after", "1"]
        assert set(kwargs) == {"cwd", "stdout", "stderr", "check"}
        kwargs["stdout"].write(b"stdout")
        kwargs["stderr"].write(b"stderr")
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(harness.subprocess, "run", launch)
    out, err = tmp_path / "stdout.bin", tmp_path / "stderr.bin"
    assert harness._run_child(["python", "main_mc.py", "/s", "--exit-after", "1"], tmp_path, out, err) == 0
    assert out.read_bytes() == b"stdout"
    assert err.read_bytes() == b"stderr"


def test_fresh_runs_preserve_prior_evidence_inside_product_logs(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    out = logs / "run_matrix" / "fresh-pair"
    calls = 0

    def runner(command, cwd, stdout, stderr):
        nonlocal calls
        if calls:
            assert (out / "001_first" / "logs" / "screensaver.log").read_text() == _main_markers()
        for path in logs.iterdir():
            if path.is_file():
                path.write_bytes(b"")  # Model canonical startup log clearing without filesystem deletion.
        calls += 1
        stdout.write_bytes(b"out")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers(f"case{calls}"))
        return 0

    cases = [RunCase(name, "main_mc.py", ("/s", "--fresh"), 1) for name in ("first", "second")]
    report = run_matrix(cases, out, runner=runner, log_dir=logs)
    assert [r["status"] for r in report["results"]] == ["passed", "passed"]


def test_snapshot_failure_is_explicit_unavailable(tmp_path: Path, monkeypatch) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers())
        return 0

    def denied(*_args):
        raise PermissionError("snapshot denied")

    monkeypatch.setattr(harness.shutil, "copy2", denied)
    report = run_matrix([RunCase("one", "main_mc.py", ("/s",), 1)], tmp_path / "out",
                        runner=runner, log_dir=logs)
    assert report["status"] == "unavailable"
    assert any("snapshot denied" in reason for reason in report["results"][0]["evidence"]["unavailable"])


def test_selected_handle_attribution_scopes_canonical_session_reset(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "screensaver_handles.log").write_text(
        '{"event":"session_start","target_pid":1,"utc":"old"}\n'
        'Windows fatal exception: stale\n')

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers())
        (logs / "screensaver_handles.log").write_text(
            '{"event":"session_start","target_pid":2,"utc":"new"}\n')
        return 0

    report = run_matrix([RunCase("one", "main_mc.py", ("/s", "--handle-attribution"), 1)],
                        tmp_path / "out", runner=runner, log_dir=logs)
    assert report["status"] == "passed"


def test_fresh_unchanged_fault_log_reports_ambiguous_scope_without_old_fault_failure(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "native_faults.log").write_text("Windows fatal exception: stale\n")

    def runner(command, cwd, stdout, stderr):
        stdout.write_bytes(b"")
        stderr.write_bytes(b"")
        (logs / "screensaver.log").write_text(_main_markers())
        (logs / "screensaver_qml.log").write_text(_qml_markers())
        return 0

    report = run_matrix([RunCase("one", "main_mc.py", ("/s", "--fresh"), 1)],
                        tmp_path / "out", runner=runner, log_dir=logs)
    assert report["status"] == "unavailable"
    assert report["results"][0]["faults"] == []


def test_dirty_preset_json_changes_source_digest_without_revision_change(tmp_path: Path, monkeypatch) -> None:
    preset = tmp_path / "appearance.json"
    preset.write_text('{"roughness":0.2}\n')
    original = preset.read_bytes()

    def git_metadata(command, **kwargs):
        args = command[3:]
        if args[0] == "rev-parse":
            output = b"0123456789abcdef\n"
        elif args[0] == "status":
            output = b"" if preset.read_bytes() == original else b" M appearance.json\0"
        else:
            assert args[0] == "ls-files"
            output = b"appearance.json\0"
        return type("Completed", (), {"stdout": output})()

    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness.subprocess, "run", git_metadata)
    before = harness._source_attribution()
    preset.write_text('{"roughness":0.8}\n')
    after = harness._source_attribution()
    assert before["unavailable"] == after["unavailable"] == []
    assert before["revision"] == after["revision"]
    assert before["dirty"] is False and after["dirty"] is True
    assert before["source_tree_sha256"] != after["source_tree_sha256"]
    assert after["source_file_count"] == 1

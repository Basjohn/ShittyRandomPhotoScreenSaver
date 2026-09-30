"""Focused contracts for the one Build Foundry QRC prerequisite."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_runner, regen_qrc


def _qrc_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    assets = tmp_path / "assets"
    assets.mkdir(parents=True)
    (assets / "mark.svg").write_text("<svg/>", encoding="utf-8")
    qrc = tmp_path / "assets.qrc"
    qrc.write_text(
        "<RCC><qresource prefix=\"/srpss\"><file alias=\"ui/mark.svg\">"
        "assets/mark.svg</file></qresource></RCC>",
        encoding="utf-8",
    )
    output = tmp_path / "assets_rc.py"
    return qrc, output, assets / "mark.svg"


def test_qrc_status_tracks_manifest_sources_and_rejects_missing_files(tmp_path: Path) -> None:
    qrc, output, source = _qrc_fixture(tmp_path)

    missing = regen_qrc.qrc_status(qrc, output)
    assert missing.current is False
    assert "missing" in missing.reason.lower()
    assert missing.input_paths == (qrc, source.resolve())

    output.write_text("generated", encoding="utf-8")
    newest_input = max(qrc.stat().st_mtime_ns, source.stat().st_mtime_ns)
    os.utime(output, ns=(source.stat().st_atime_ns, newest_input + 1))
    assert regen_qrc.qrc_status(qrc, output).current is False  # a recent timestamp is not provenance

    source.unlink()
    with pytest.raises(regen_qrc.QrcRegenerationError, match="source asset is missing"):
        regen_qrc.qrc_status(qrc, output)


def test_regeneration_uses_only_selected_python_and_publishes_atomically(tmp_path: Path) -> None:
    qrc, output, _source = _qrc_fixture(tmp_path)
    python = Path(sys.executable)
    rcc = tmp_path / "rcc.exe"
    rcc.write_bytes(b"fixture")
    calls: list[tuple[list[str], dict]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append((command, kwargs))
        if command[1] == "-c":
            return subprocess.CompletedProcess(
                command,
                0,
                "PySide6=6.11.2;PySide6_Addons=6.11.2;PySide6_Essentials=6.11.2;"
                f"shiboken6=6.11.2;Qt=6.11.2;rcc={rcc}",
                "",
            )
        temporary = Path(command[-1])
        temporary.write_text("new generated module", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    status = regen_qrc.ensure_qrc_current(
        python_executable=python,
        qrc_path=qrc,
        output_path=output,
        run=fake_run,
    )

    assert status.current is True
    assert output.read_text(encoding="utf-8").endswith("new generated module")
    assert len(calls) == 2
    command, kwargs = calls[1]
    assert command[:4] == [str(rcc), "-g", "python", str(qrc)]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert not list(tmp_path.glob(".*.qrc.tmp"))

    unchanged = regen_qrc.ensure_qrc_current(
        python_executable=python,
        qrc_path=qrc,
        output_path=output,
        run=fake_run,
    )
    assert unchanged.current is True
    assert len(calls) == 3


def test_failed_regeneration_keeps_prior_generated_module(tmp_path: Path) -> None:
    qrc, output, source = _qrc_fixture(tmp_path)
    rcc = tmp_path / "rcc.exe"
    rcc.write_bytes(b"fixture")
    output.write_text("known good", encoding="utf-8")
    os.utime(output, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns - 1))

    with pytest.raises(regen_qrc.QrcRegenerationError, match="exit 9"):
        regen_qrc.ensure_qrc_current(
            python_executable=Path(sys.executable),
            qrc_path=qrc,
            output_path=output,
            run=lambda command, **_kwargs: subprocess.CompletedProcess(
                command,
                0 if command[1] == "-c" else 9,
                (
                    "PySide6=6.11.2;PySide6_Addons=6.11.2;PySide6_Essentials=6.11.2;"
                    f"shiboken6=6.11.2;Qt=6.11.2;rcc={rcc}"
                    if command[1] == "-c"
                    else ""
                ),
                "bad manifest",
            ),
        )
    assert output.read_text(encoding="utf-8") == "known good"


def test_two_target_compile_failure_preserves_every_prior_generated_module(tmp_path: Path) -> None:
    first_qrc, first_output, _first_source = _qrc_fixture(tmp_path / "first")
    second_qrc, second_output, _second_source = _qrc_fixture(tmp_path / "second")
    first_output.write_text("first known good", encoding="utf-8")
    second_output.write_text("second known good", encoding="utf-8")
    rcc = tmp_path / "rcc.exe"
    rcc.write_bytes(b"fixture")

    def fail_second_target(command, **_kwargs):  # noqa: ANN001
        if command[1] == "-c":
            return subprocess.CompletedProcess(
                command,
                0,
                "PySide6=6.11.2;PySide6_Addons=6.11.2;PySide6_Essentials=6.11.2;"
                f"shiboken6=6.11.2;Qt=6.11.2;rcc={rcc}",
                "",
            )
        if Path(command[3]) == second_qrc:
            return subprocess.CompletedProcess(command, 9, "", "second failed")
        Path(command[-1]).write_text("first replacement", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(regen_qrc.QrcRegenerationError, match="exit 9"):
        regen_qrc.ensure_qrc_targets_current(
            python_executable=Path(sys.executable),
            targets=(
                regen_qrc.QrcTarget(first_qrc, first_output),
                regen_qrc.QrcTarget(second_qrc, second_output),
            ),
            run=fail_second_target,
        )
    assert first_output.read_text(encoding="utf-8") == "first known good"
    assert second_output.read_text(encoding="utf-8") == "second known good"


def test_input_change_during_generation_prevents_any_publish(tmp_path: Path) -> None:
    qrc, output, source = _qrc_fixture(tmp_path)
    output.write_text("known good", encoding="utf-8")
    rcc = tmp_path / "rcc.exe"
    rcc.write_bytes(b"fixture")

    def mutate_input_after_compile(command, **_kwargs):  # noqa: ANN001
        if command[1] == "-c":
            return subprocess.CompletedProcess(
                command,
                0,
                "PySide6=6.11.2;PySide6_Addons=6.11.2;PySide6_Essentials=6.11.2;"
                f"shiboken6=6.11.2;Qt=6.11.2;rcc={rcc}",
                "",
            )
        Path(command[-1]).write_text("replacement", encoding="utf-8")
        source.write_text("<svg changed='true'/>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    with pytest.raises(regen_qrc.QrcRegenerationError, match="changed during regeneration"):
        regen_qrc.ensure_qrc_current(
            python_executable=Path(sys.executable),
            qrc_path=qrc,
            output_path=output,
            run=mutate_input_after_compile,
        )
    assert output.read_text(encoding="utf-8") == "known good"


def test_selected_pyside_rcc_compiles_a_tiny_fixture(tmp_path: Path) -> None:
    """The real 6.11 sidecar works without invoking a build script or GUI."""
    qrc, output, source = _qrc_fixture(tmp_path)
    status = regen_qrc.ensure_qrc_current(
        python_executable=Path(sys.executable),
        qrc_path=qrc,
        output_path=output,
    )

    assert status.current is True
    assert "SRPSS-QRC-PROVENANCE" in output.read_text(encoding="utf-8")
    generated_mtime = output.stat().st_mtime_ns
    os.utime(source, ns=(generated_mtime + 1, generated_mtime + 1))
    assert regen_qrc.ensure_qrc_current(
        python_executable=Path(sys.executable), qrc_path=qrc, output_path=output,
    ).current
    assert output.stat().st_mtime_ns == generated_mtime  # touching unchanged input must not rebuild
    toolchain = regen_qrc._selected_toolchain_identity(Path(sys.executable), subprocess.run)
    assert not regen_qrc.qrc_status(qrc, output, toolchain_identity="changed").current
    original_stat = source.stat()
    source.write_bytes(b"<bad/>")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert not regen_qrc.qrc_status(qrc, output, toolchain_identity=toolchain.identity).current
    source.write_bytes(b"<svg/>")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    with output.open("ab") as stream:
        stream.write(b"# modified generated body\n")
    assert not regen_qrc.qrc_status(qrc, output, toolchain_identity=toolchain.identity).current


def test_mismatched_selected_qt_toolchain_cannot_rewrite_resources(tmp_path: Path) -> None:
    qrc, output, _source = _qrc_fixture(tmp_path)
    calls: list[list[str]] = []

    def stale_toolchain(command, **_kwargs):  # noqa: ANN001
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            "PySide6=6.9.1;PySide6_Addons=6.9.1;PySide6_Essentials=6.9.1;shiboken6=6.9.1;Qt=6.9.1",
            "",
        )

    with pytest.raises(regen_qrc.QrcRegenerationError, match="pinned Qt 6.11.2"):
        regen_qrc.ensure_qrc_current(
            python_executable=Path(sys.executable),
            qrc_path=qrc,
            output_path=output,
            run=stale_toolchain,
        )
    assert calls and calls[0][1] == "-c"
    assert not output.exists()


def test_foundry_runs_one_qrc_prerequisite_only_for_selected_runtime_products(monkeypatch, tmp_path: Path) -> None:
    class _Owner:
        cancellation_requested = False

        def shutdown(self) -> bool:
            return False

    class _Harness:
        def __init__(self) -> None:
            import queue

            self._events: queue.Queue[tuple] = queue.Queue()

    standard = build_runner.Job(
        "standard", "Standard", "powershell", tmp_path / "standard.ps1", tmp_path, tmp_path / "SRPSS.scr"
    )
    installer = build_runner.Job(
        "standard_installer", "Installer", "inno", tmp_path / "setup.iss", tmp_path, tmp_path / "setup.exe"
    )
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(build_runner, "write_curated_visualizer_preset_manifest", lambda _root: ())
    monkeypatch.setattr(
        build_runner,
        "ensure_selected_qrc_current",
        lambda mode, owner: calls.append((mode, owner))
        or (
            regen_qrc.QrcStatus(
                True,
                "QRC generated module is current",
                (Path("assets.qrc"), Path("asset.svg")),
            ),
        ),
    )
    monkeypatch.setattr(
        build_runner,
        "helper_build_status",
        lambda _mode: build_runner.HelperBuildStatus(False, "fixture", "fingerprint", 0),
    )
    monkeypatch.setattr(
        build_runner,
        "run_job",
        lambda job, _preflight, *, process_owner: build_runner.JobResult(
            0, "Completed", tmp_path / f"{job.key}.log", tmp_path
        ),
    )

    harness = _Harness()
    owner = _Owner()
    build_runner.BuildRunnerApp._pipeline_worker(
        harness,
        "venv",
        (standard, installer),
        {standard.key, installer.key},
        build_runner.PreflightResult(),
        owner,
    )
    assert calls == [("venv", owner)]

    calls.clear()
    second_harness = _Harness()
    build_runner.BuildRunnerApp._pipeline_worker(
        second_harness,
        "venv",
        (installer,),
        {installer.key},
        build_runner.PreflightResult(),
        owner,
    )
    assert calls == []

    diagnostic = build_runner.Job(
        "diagnostic", "Diagnostic", "powershell", tmp_path / "diagnostic.ps1",
        tmp_path, tmp_path / "Diagnostic.scr",
    )
    build_runner.BuildRunnerApp._pipeline_worker(
        _Harness(), "normal", (diagnostic,), {diagnostic.key},
        build_runner.PreflightResult(), owner,
    )
    assert calls == [("venv", owner)]


def test_foundry_does_not_launch_product_jobs_after_qrc_prerequisite_failure(monkeypatch, tmp_path: Path) -> None:
    class _Owner:
        cancellation_requested = False

        def shutdown(self) -> bool:
            return False

    class _Harness:
        def __init__(self) -> None:
            import queue

            self._events: queue.Queue[tuple] = queue.Queue()

    job = build_runner.Job(
        "standard", "Standard", "powershell", tmp_path / "standard.ps1", tmp_path, tmp_path / "SRPSS.scr"
    )
    launched: list[str] = []
    monkeypatch.setattr(build_runner, "write_curated_visualizer_preset_manifest", lambda _root: ())
    monkeypatch.setattr(
        build_runner,
        "ensure_selected_qrc_current",
        lambda *_args: (_ for _ in ()).throw(regen_qrc.QrcRegenerationError("rcc failed")),
    )
    monkeypatch.setattr(
        build_runner,
        "run_job",
        lambda called_job, *_args, **_kwargs: launched.append(called_job.key),
    )

    harness = _Harness()
    build_runner.BuildRunnerApp._pipeline_worker(
        harness,
        "venv",
        (job,),
        {job.key},
        build_runner.PreflightResult(),
        _Owner(),
    )
    events: list[tuple] = []
    while not harness._events.empty():
        events.append(harness._events.get_nowait())
    assert launched == []
    assert events[-1] == ("pipeline_done", False, "Pipeline failed: rcc failed", False)


def test_foundry_marks_selected_jobs_cancelled_when_qrc_sidecar_is_aborted(monkeypatch, tmp_path: Path) -> None:
    class _Owner:
        cancellation_requested = True

        def shutdown(self) -> bool:
            return False

    class _Harness:
        def __init__(self) -> None:
            import queue

            self._events: queue.Queue[tuple] = queue.Queue()

    job = build_runner.Job(
        "standard", "Standard", "powershell", tmp_path / "standard.ps1", tmp_path, tmp_path / "SRPSS.scr"
    )
    monkeypatch.setattr(build_runner, "write_curated_visualizer_preset_manifest", lambda _root: ())
    monkeypatch.setattr(
        build_runner,
        "ensure_selected_qrc_current",
        lambda *_args: (_ for _ in ()).throw(build_runner.BuildPipelineCancelled("cancelled")),
    )

    harness = _Harness()
    build_runner.BuildRunnerApp._pipeline_worker(
        harness,
        "venv",
        (job,),
        {job.key},
        build_runner.PreflightResult(),
        _Owner(),
    )
    events: list[tuple] = []
    while not harness._events.empty():
        events.append(harness._events.get_nowait())
    assert ("job_cancelled", job.key) in events
    assert events[-1] == (
        "pipeline_done",
        False,
        "Pipeline aborted by operator. Selected jobs did not start.",
        True,
    )


def test_foundry_qrc_sidecar_uses_the_active_owner_and_cancellation(monkeypatch, tmp_path: Path) -> None:
    qrc, output, _source = _qrc_fixture(tmp_path)
    python = tmp_path / "python.exe"
    python.write_bytes(b"fixture")
    rcc = tmp_path / "rcc.exe"
    rcc.write_bytes(b"fixture")
    captured: dict[str, object] = {}
    launched: list[list[str]] = []

    class _Process:
        returncode = 0

        def communicate(self):
            command = captured["command"]  # type: ignore[assignment]
            if "-PrepareEnvironmentOnly" in command:
                return ("environment ready", "")
            if command[1] == "-c":  # type: ignore[index]
                return (
                    "PySide6=6.11.2;PySide6_Addons=6.11.2;PySide6_Essentials=6.11.2;"
                    f"shiboken6=6.11.2;Qt=6.11.2;rcc={rcc}",
                    "",
                )
            Path(command[-1]).write_text("generated", encoding="utf-8")  # type: ignore[index]
            return ("", "")

    class _Owner:
        cancellation_requested = False

        def start(self, command, **kwargs):  # noqa: ANN001
            launched.append(list(command))
            captured["command"] = command
            captured["kwargs"] = kwargs
            return _Process()

        def retire(self, _process):  # noqa: ANN001
            return False

    monkeypatch.setattr(build_runner, "qrc_python_for_mode", lambda _mode, _root: python)
    monkeypatch.setattr(build_runner, "_find_pwsh", lambda: Path("pwsh.exe"))
    monkeypatch.setattr(
        build_runner,
        "resource_targets",
        lambda _root: (regen_qrc.QrcTarget(qrc, output),),
    )
    statuses = build_runner.ensure_selected_qrc_current("venv", _Owner(), tmp_path)

    assert statuses[0].current is True
    assert "-PrepareEnvironmentOnly" in launched[0]
    assert launched[1][1] == "-c"
    assert captured["command"][:4] == [str(rcc), "-g", "python", str(qrc)]  # type: ignore[index]
    assert captured["kwargs"]["stdout"] is subprocess.PIPE  # type: ignore[index]


def test_venv_preparation_stops_before_build_mutation_and_normal_does_not_bootstrap(monkeypatch):
    source = (build_runner.REPO_ROOT / "scripts/venv/build_nuitka.ps1").read_text(encoding="utf-8")
    bootstrap = source.index("$VenvPython = Ensure-ProjectVenv")
    stop = source.index("if ($PrepareEnvironmentOnly)", bootstrap)
    assert bootstrap < stop < source.index("$BuildRoot =", stop)
    assert "return" in source[stop:source.index("$BuildRoot =", stop)]
    monkeypatch.setattr(build_runner, "_find_pwsh", lambda: pytest.fail("Normal mode must not bootstrap venv"))
    build_runner.prepare_qrc_environment("normal", object())

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from core import build_profile
from core.logging import crash_capture
from core.logging import logger as logging_config


ROOT = Path(__file__).resolve().parents[1]


def test_compiled_runtime_detection_is_authoritative_and_product_neutral(
    monkeypatch,
) -> None:
    monkeypatch.setattr(build_profile.sys, "frozen", False, raising=False)
    monkeypatch.delattr(build_profile, "__compiled__", raising=False)
    monkeypatch.delattr("builtins.__compiled__", raising=False)
    monkeypatch.setitem(build_profile.sys.modules, "__main__", SimpleNamespace())

    assert build_profile.is_compiled_runtime() is False

    monkeypatch.setattr(build_profile, "__compiled__", object(), raising=False)
    assert build_profile.is_compiled_runtime() is True

    monkeypatch.delattr(build_profile, "__compiled__", raising=False)
    monkeypatch.setattr(build_profile.sys, "frozen", True, raising=False)
    assert build_profile.is_compiled_runtime() is True


def test_diagnostic_build_profile_is_explicit_and_idempotent(monkeypatch) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)

    assert build_profile.is_diagnostic_build() is False
    assert build_profile.get_build_flavour() == "release"

    build_profile.activate_diagnostic_build()
    build_profile.activate_diagnostic_build()

    assert build_profile.is_diagnostic_build() is True
    assert build_profile.get_build_flavour() == "diagnostic"


def test_only_the_published_diagnostic_file_name_selects_the_flavour(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)
    monkeypatch.setattr(build_profile, "is_compiled_runtime", lambda: True)
    for name in ("SRPSS.scr", "SRPSS_Diagnostic_old.scr", "My SRPSS_Diagnostic.scr", "SRPSS Diagnostic.scr", ""):
        assert build_profile.activate_flavour_for_artifact(rf"C:\Apps\{name}") is False, name
    assert build_profile.is_diagnostic_build() is False
    # Windows stores screensavers by their 8.3 short path; the long name still selects it.
    published = tmp_path / "a long folder name" / "SRPSS_Diagnostic.scr"
    published.parent.mkdir()
    published.write_bytes(b"binary")
    short = published
    if sys.platform == "win32":
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(published), buffer, 1024):
            short = Path(buffer.value)
    assert build_profile.activate_flavour_for_artifact(str(short)) is True
    assert build_profile.is_diagnostic_build() is True


def test_source_runs_never_select_the_flavour_by_name(monkeypatch) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)
    monkeypatch.setattr(build_profile, "is_compiled_runtime", lambda: False)
    assert build_profile.activate_flavour_for_artifact(r"C:\Apps\SRPSS_Diagnostic.scr") is False
    assert build_profile.is_diagnostic_build() is False


def test_the_standard_build_publishes_the_diagnostic_file_from_its_own_binary() -> None:
    worker = (ROOT / "scripts" / "venv" / "build_nuitka.ps1").read_text(encoding="utf-8")

    assert not (ROOT / "scripts" / "venv" / "build_nuitka_diagnostic.ps1").exists()
    assert not (ROOT / "scripts" / "SRPSS_Diagnostic_Installer.iss").exists()
    assert '[string]$DiagnosticArtifactName = "SRPSS_Diagnostic"' in worker
    assert f'"{build_profile.DIAGNOSTIC_ARTIFACT_STEM}"' in worker
    assert "Copy-Item -LiteralPath $primaryArtifact.FullName" in worker
    # The copy is checked byte-for-byte against the compiled binary, and a console build
    # (-Console) never publishes one: the diagnostic file has no forced terminal.
    assert "differs from the compiled binary" in worker
    assert "(-not $Console)" in worker
    assert '$consoleArg = "--windows-console-mode=disable"' in worker


def test_the_diagnostic_terminal_opens_only_with_debug() -> None:
    from core.windows.debug_console import debug_console_requested

    assert debug_console_requested(["SRPSS_Diagnostic.scr"]) is False
    assert debug_console_requested(["SRPSS_Diagnostic.scr", "/s"]) is False
    assert debug_console_requested(["SRPSS_Diagnostic.scr", "/p", "123"]) is False
    assert debug_console_requested(["SRPSS_Diagnostic.scr", "--debug"]) is True
    assert debug_console_requested(["--debug"]) is False           # argv[0] is never an option
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "if debug_console_requested(sys.argv):\n            open_debug_console()" in source


def test_diagnostic_crash_capture_is_inert_for_release(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)

    assert crash_capture.enable_diagnostic_crash_capture(tmp_path) is None
    crash_capture.record_diagnostic_stage("must_not_exist")
    assert list(tmp_path.iterdir()) == []


def test_diagnostic_crash_capture_writes_flushed_bounded_companion(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", True)
    crash_capture.close_diagnostic_crash_capture()

    path = crash_capture.enable_diagnostic_crash_capture(tmp_path)
    assert path == tmp_path / "diagnostic_crash.log"
    crash_capture.record_diagnostic_stage("settings_dialog_exec_begin", generation=7)
    text = path.read_text(encoding="utf-8")
    assert "stage=crash_capture_enabled" in text
    assert "stage=settings_dialog_exec_begin" in text
    assert "generation=7" in text

    crash_capture.close_diagnostic_crash_capture()
    assert "stage=orderly_process_exit" in path.read_text(encoding="utf-8")


def test_diagnostic_crash_capture_rotates_during_a_long_session(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", True)
    monkeypatch.setattr(crash_capture, "CRASH_LOG_MAX_BYTES", 512)
    monkeypatch.setattr(crash_capture, "CRASH_LOG_BACKUP_COUNT", 2)
    crash_capture.close_diagnostic_crash_capture()

    path = crash_capture.enable_diagnostic_crash_capture(tmp_path)
    for index in range(24):
        crash_capture.record_diagnostic_stage(
            "settings_boundary",
            index=index,
            detail="x" * 180,
        )

    files = sorted(tmp_path.glob("diagnostic_crash.log*"))
    assert path in files
    assert len(files) == 3
    assert all(file.stat().st_size <= 512 for file in files)
    assert any("index=23" in file.read_text(encoding="utf-8") for file in files)

    crash_capture.close_diagnostic_crash_capture()


def test_diagnostic_crash_capture_trims_raw_fatal_output_before_retaining_backup(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", True)
    monkeypatch.setattr(crash_capture, "CRASH_LOG_MAX_BYTES", 512)
    monkeypatch.setattr(crash_capture, "CRASH_LOG_BACKUP_COUNT", 2)
    crash_capture.close_diagnostic_crash_capture()
    path = tmp_path / "diagnostic_crash.log"
    path.write_bytes(b"old-stage\n" + (b"fatal-frame\n" * 200))

    crash_capture.enable_diagnostic_crash_capture(tmp_path)

    retained = tmp_path / "diagnostic_crash.log.1"
    assert retained.is_file()
    assert retained.stat().st_size <= 512
    assert b"fatal-frame" in retained.read_bytes()
    crash_capture.close_diagnostic_crash_capture()


def test_a_direct_diagnostic_launch_runs_without_overriding_an_explicit_mode(
    monkeypatch,
) -> None:
    import main

    monkeypatch.setattr(main.sys, "argv", ["SRPSS_Diagnostic.scr", "--debug"])
    main.default_diagnostic_launch_to_run()
    assert main.sys.argv == ["SRPSS_Diagnostic.scr", "/s", "--debug"]

    monkeypatch.setattr(main.sys, "argv", ["SRPSS_Diagnostic.scr", "/c:1234"])
    main.default_diagnostic_launch_to_run()
    assert main.sys.argv == ["SRPSS_Diagnostic.scr", "/c:1234"]

    source = (ROOT / "main_diagnostic.py").read_text(encoding="utf-8")
    assert "rendering.display_widget" not in source
    assert "DisplayWidget" not in source


def test_source_diagnostic_reuses_normal_source_log_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(logging_config, "_BASE_DIR", tmp_path)
    monkeypatch.setattr(logging_config, "_ACTIVE_LOG_DIR", None)

    chosen = logging_config._select_diagnostic_log_dir(None)

    assert chosen == tmp_path / "logs"


def test_frozen_diagnostic_prefers_its_adjacent_log_directory(tmp_path, monkeypatch) -> None:
    exe = tmp_path / "diagnostic" / "SRPSS_Diagnostic.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(logging_config, "_ACTIVE_LOG_DIR", None)

    chosen = logging_config._select_diagnostic_log_dir(exe)

    assert chosen == exe.parent / "logs"

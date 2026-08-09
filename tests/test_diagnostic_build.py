from __future__ import annotations

import sys
from types import SimpleNamespace

from core import build_profile
from core.logging import crash_capture


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


def test_diagnostic_identity_is_not_inferred_from_executable_name(monkeypatch) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)
    monkeypatch.setattr(
        build_profile.sys,
        "executable",
        r"C:\Program Files\SRPSS Diagnostic\SRPSS_Diagnostic.exe",
    )

    assert build_profile.is_diagnostic_build() is False


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


def test_diagnostic_entrypoint_defaults_to_run_without_overriding_explicit_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(build_profile, "_DIAGNOSTIC_BUILD", False)
    sys.modules.pop("main_diagnostic", None)
    import main_diagnostic

    monkeypatch.setattr(main_diagnostic.sys, "argv", ["SRPSS_Diagnostic.exe", "--perf"])
    main_diagnostic._inject_run_mode_arg()
    assert main_diagnostic.sys.argv[-1] == "/s"

    monkeypatch.setattr(main_diagnostic.sys, "argv", ["SRPSS_Diagnostic.exe", "/c:1234"])
    main_diagnostic._inject_run_mode_arg()
    assert main_diagnostic.sys.argv == ["SRPSS_Diagnostic.exe", "/c:1234"]

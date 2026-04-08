from __future__ import annotations

from pathlib import Path

import main
from core.logging import logger as logger_mod


def test_clear_logs_for_fresh_start_preserves_worker_logs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    preserved = log_dir / "worker_media.log"
    preserved.write_text("keep", encoding="utf-8")
    (log_dir / "screensaver.log").write_text("main", encoding="utf-8")
    (log_dir / "screensaver.log.1").write_text("rotated", encoding="utf-8")
    (log_dir / "screensaver_spotify_vis.log").write_text("viz", encoding="utf-8")
    (log_dir / "notes.txt").write_text("misc", encoding="utf-8")

    monkeypatch.setattr(logger_mod, "_BASE_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)

    resolved_dir, deleted_count = logger_mod.clear_logs_for_fresh_start()

    assert resolved_dir == log_dir
    assert deleted_count == 4
    assert preserved.exists()
    assert sorted(path.name for path in log_dir.iterdir()) == ["worker_media.log"]


def test_parse_screensaver_args_ignores_fresh_flag(monkeypatch) -> None:
    monkeypatch.setattr(main.sys, "argv", ["main.py", "--fresh", "/c"])

    mode, preview_hwnd = main.parse_screensaver_args()

    assert mode is main.ScreensaverMode.CONFIG
    assert preview_hwnd is None


def test_is_frozen_build_detects_srpss_executable_without_sys_frozen(monkeypatch) -> None:
    monkeypatch.setattr(main.sys, "frozen", False, raising=False)
    monkeypatch.setattr(main.sys, "executable", r"C:\Windows\System32\SRPSS.scr")
    monkeypatch.setattr(main.sys, "argv", [r"C:\Windows\System32\SRPSS.scr", "/s"])
    if main._builtins is not None:
        monkeypatch.setattr(main._builtins, "__compiled__", False, raising=False)

    assert main._is_frozen_build() is True
    assert main.is_script_mode() is False

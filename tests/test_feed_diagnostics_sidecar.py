"""FEEDS diagnostics stay opt-in and isolated from general logs."""
from __future__ import annotations

import logging

from core.logging import logger as logger_mod


def _reset(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    for name in (
        "_PERF_METRICS_ENABLED", "_USAGE_LOGGING_ENABLED", "_VIZ_LOGGING_ENABLED",
        "_VIZ_DIAGNOSTICS_ENABLED", "_GEOMETRY_LOGGING_ENABLED",
        "_SETTINGS_LOGGING_ENABLED", "_LIFECYCLE_LOGGING_ENABLED",
        "_CACHE_LOGGING_ENABLED", "_STEAM_LOGGING_ENABLED", "_FEEDS_LOGGING_ENABLED",
    ):
        monkeypatch.setattr(logger_mod, name, False)


def test_feeds_sidecar_is_absent_without_explicit_flag(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path)
    logger_mod.setup_logging(debug=True, verbose=True, feeds_trace=False)
    # Product warnings remain visible; optional FEEDS diagnostic summaries are
    # emitted by their producer only when is_feeds_logging_enabled() is true.
    logging.getLogger("core.feeds.source").warning("feed warning")
    logger_mod.flush_and_close_logging()
    assert not (tmp_path / "screensaver_feeds.log").exists()
    assert "feed warning" in (tmp_path / "screensaver.log").read_text(encoding="utf-8")


def test_feeds_sidecar_owns_info_diagnostics_when_enabled(tmp_path, monkeypatch):
    _reset(monkeypatch, tmp_path)
    logger_mod.setup_logging(debug=True, verbose=True, feeds_trace=True)
    logging.getLogger("core.feeds.artwork").info("[FEEDS][ARTWORK] candidate summary")
    logging.getLogger("core.feeds.source").warning("feed warning remains general")
    logger_mod.flush_and_close_logging()
    sidecar = (tmp_path / "screensaver_feeds.log").read_text(encoding="utf-8")
    main = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    verbose = (tmp_path / "screensaver_verbose.log").read_text(encoding="utf-8")
    assert "candidate summary" in sidecar
    assert "candidate summary" not in main
    assert "candidate summary" not in verbose
    assert "feed warning remains general" in main
    assert "feed warning remains general" in sidecar

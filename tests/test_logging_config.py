import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from core.logging import logger as logger_mod
from core.logging.tags import (
    LOG_FAMILY_CACHE,
    LOG_FAMILY_FIELD,
    LOG_FAMILY_PERF,
)


@pytest.fixture(autouse=True)
def _close_process_logging_after_test(monkeypatch):
    yield
    logger_mod.flush_and_close_logging()


def test_setup_logging_cli_families_enable_sidecar_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    monkeypatch.setattr(logger_mod, "_PERF_METRICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GPU_TIMING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_USAGE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_DIAGNOSTICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GEOMETRY_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_SETTINGS_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_LIFECYCLE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_CACHE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_STEAM_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VERBOSE", False)

    logger_mod.setup_logging(
        debug=False,
        verbose=False,
        perf=True,
        gpu_timing=True,
        usage=True,
        viz=True,
        geo=True,
        settings_trace=True,
        lifecycle=True,
        cache_trace=True,
        steam_trace=True,
    )

    logging.getLogger("rendering.custom_layout_manager").info("[CUSTOM_LAYOUT] geometry trace")
    logging.getLogger("SettingsManager").info("[SETTINGS] write trace")
    logging.getLogger("widgets.spotify_visualizer_widget").info("[SPOTIFY_VIS] mode trace")
    logging.getLogger("engine.screensaver").info("[PERF] timing trace")
    logging.getLogger("widgets.media_widget").warning(
        "[PERF_WIDGET] warning visibility trace"
    )
    logging.getLogger("core.performance.usage_sampler").info("[USAGE] sample seq=1")
    logging.getLogger("core.process.supervisor").info("ProcessSupervisor initialized")
    logging.getLogger("engine.image_pipeline").info("[CACHE] cache authority trace")
    logging.getLogger("transitions.texture_manager").info(
        "[GL CACHE] retained texture trace"
    )
    logging.getLogger("transitions.texture_manager").warning(
        "[GL CACHE] upload warning trace"
    )
    logging.getLogger("utils.image_cache").info("[CACHE] Cache hit: image-a.jpg")
    logging.getLogger("engine.engine_lifecycle").info(
        "[PERF] [CACHE] ImageCacheFlow: raw_hits=1 raw_misses=0"
    )
    logging.getLogger("utils.image_cache").warning(
        "[CACHE] [FALLBACK] Cache entry recovery failed"
    )
    logging.getLogger("core.steam.backend").info("[STEAM] provider trace")
    logging.getLogger("unrelated.structured.cache").info(
        "structured cache info",
        extra={LOG_FAMILY_FIELD: (LOG_FAMILY_CACHE,)},
    )
    logging.getLogger("unrelated.structured.cache").warning(
        "structured cache warning",
        extra={LOG_FAMILY_FIELD: (LOG_FAMILY_CACHE,)},
    )
    logging.getLogger("unrelated.structured.multi").info(
        "structured perf cache info",
        extra={
            LOG_FAMILY_FIELD: (
                LOG_FAMILY_PERF,
                LOG_FAMILY_CACHE,
            )
        },
    )
    logging.getLogger("third.party.unknown").info(
        "unknown structured family remains general",
        extra={LOG_FAMILY_FIELD: ("future_external_family",)},
    )

    metrics = logger_mod.flush_and_close_logging()
    assert metrics["flush_timed_out"] is False

    assert logger_mod.is_perf_metrics_enabled() is True
    assert logger_mod.is_gpu_timing_enabled() is True
    assert logger_mod.is_usage_logging_enabled() is True
    assert logger_mod.is_viz_logging_enabled() is True
    assert logger_mod.is_viz_diagnostics_enabled() is True
    assert logger_mod.is_geometry_logging_enabled() is True
    assert logger_mod.is_settings_logging_enabled() is True
    assert logger_mod.is_lifecycle_logging_enabled() is True
    assert logger_mod.is_cache_logging_enabled() is True
    assert logger_mod.is_steam_logging_enabled() is True

    main_log = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    assert "[CUSTOM_LAYOUT] geometry trace" not in main_log
    assert "[SETTINGS] write trace" not in main_log
    assert "[SPOTIFY_VIS] mode trace" not in main_log
    assert "[PERF] timing trace" not in main_log
    assert "[PERF_WIDGET] warning visibility trace" in main_log
    assert "[USAGE] sample seq=1" not in main_log
    assert "ProcessSupervisor initialized" not in main_log
    assert "[CACHE] cache authority trace" not in main_log
    assert "[GL CACHE] retained texture trace" not in main_log
    assert "[GL CACHE] upload warning trace" in main_log
    assert "[CACHE] Cache hit: image-a.jpg" not in main_log
    assert "[PERF] [CACHE] ImageCacheFlow: raw_hits=1 raw_misses=0" not in main_log
    assert "[CACHE] [FALLBACK] Cache entry recovery failed" in main_log
    assert "[STEAM] provider trace" not in main_log
    assert "structured cache info" not in main_log
    assert "structured cache warning" in main_log
    assert "structured perf cache info" not in main_log
    assert "unknown structured family remains general" in main_log
    assert "Specific logs available:" in main_log
    assert "Specific logs active:" in main_log
    assert "[LOG_QUEUE] final" in main_log

    assert "[CUSTOM_LAYOUT] geometry trace" in (tmp_path / "screensaver_geometry.log").read_text(encoding="utf-8")
    assert "[SETTINGS] write trace" in (tmp_path / "screensaver_settings.log").read_text(encoding="utf-8")
    assert "[SPOTIFY_VIS] mode trace" in (tmp_path / "screensaver_spotify_vis.log").read_text(encoding="utf-8")
    assert "[PERF] timing trace" in (tmp_path / "screensaver_perf.log").read_text(encoding="utf-8")
    assert "[PERF_WIDGET] warning visibility trace" in (
        tmp_path / "perf_widgets.log"
    ).read_text(encoding="utf-8")
    assert "[USAGE] sample seq=1" in (tmp_path / "screensaver_usage.log").read_text(encoding="utf-8")
    assert "ProcessSupervisor initialized" in (tmp_path / "screensaver_lifecycle.log").read_text(encoding="utf-8")
    assert "[CACHE] cache authority trace" in (tmp_path / "screensaver_cache.log").read_text(encoding="utf-8")
    cache_log = (tmp_path / "screensaver_cache.log").read_text(encoding="utf-8")
    assert "[GL CACHE] retained texture trace" in cache_log
    assert "[GL CACHE] upload warning trace" in cache_log
    assert "[CACHE] Cache hit: image-a.jpg" in cache_log
    assert "[PERF] [CACHE] ImageCacheFlow: raw_hits=1 raw_misses=0" in cache_log
    assert "[CACHE] [FALLBACK] Cache entry recovery failed" in cache_log
    assert "structured cache info" in cache_log
    assert "structured cache warning" in cache_log
    assert "structured perf cache info" in cache_log
    assert "[PERF] [CACHE] ImageCacheFlow: raw_hits=1 raw_misses=0" in (
        tmp_path / "screensaver_perf.log"
    ).read_text(encoding="utf-8")
    assert "structured perf cache info" in (
        tmp_path / "screensaver_perf.log"
    ).read_text(encoding="utf-8")
    assert "[STEAM] provider trace" in (tmp_path / "screensaver_steam.log").read_text(encoding="utf-8")


def test_dedicated_family_suppress_filter_keeps_warning_in_main_log():
    family_filter = logger_mod.GeometryLogFilter()
    suppress_filter = logger_mod.DedicatedFamilySuppressFilter(family_filter, lambda: True)

    info_record = logging.LogRecord(
        "rendering.custom_layout_manager",
        logging.INFO,
        __file__,
        1,
        "[CUSTOM_LAYOUT] info",
        args=(),
        exc_info=None,
    )
    warning_record = logging.LogRecord(
        "rendering.custom_layout_manager",
        logging.WARNING,
        __file__,
        1,
        "[CUSTOM_LAYOUT] warning",
        args=(),
        exc_info=None,
    )

    assert suppress_filter.filter(info_record) is False
    assert suppress_filter.filter(warning_record) is True


def test_lifecycle_filter_matches_lifecycle_and_supervisor_records():
    lifecycle_filter = logger_mod.LifecycleLogFilter()

    widget_record = logging.LogRecord(
        "widgets.media_widget",
        logging.INFO,
        __file__,
        1,
        "[LIFECYCLE] MediaWidget activated",
        args=(),
        exc_info=None,
    )
    supervisor_record = logging.LogRecord(
        "core.process.supervisor",
        logging.INFO,
        __file__,
        1,
        "ProcessSupervisor initialized",
        args=(),
        exc_info=None,
    )
    unrelated_record = logging.LogRecord(
        "widgets.example_widget",
        logging.INFO,
        __file__,
        1,
        "regular widget paint",
        args=(),
        exc_info=None,
    )

    assert lifecycle_filter.filter(widget_record) is True
    assert lifecycle_filter.filter(supervisor_record) is True
    assert lifecycle_filter.filter(unrelated_record) is False


def test_old_logging_env_toggles_no_longer_enable_families(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    monkeypatch.setattr(logger_mod, "_PERF_METRICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GPU_TIMING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_USAGE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_DIAGNOSTICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GEOMETRY_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_SETTINGS_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_LIFECYCLE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_CACHE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_STEAM_LOGGING_ENABLED", False)
    monkeypatch.setenv("SRPSS_PERF_METRICS", "1")
    monkeypatch.setenv("SRPSS_VIZ_LOGGING", "1")
    monkeypatch.setenv("SRPSS_VIZ_DIAGNOSTICS", "1")
    monkeypatch.setenv("SRPSS_GEOMETRY_LOGGING", "1")
    monkeypatch.setenv("SRPSS_SETTINGS_LOGGING", "1")

    logger_mod.setup_logging(debug=False, verbose=False)
    logger_mod.flush_and_close_logging()

    assert logger_mod.is_perf_metrics_enabled() is False
    assert logger_mod.is_usage_logging_enabled() is False
    assert logger_mod.is_viz_logging_enabled() is False
    assert logger_mod.is_viz_diagnostics_enabled() is False
    assert logger_mod.is_geometry_logging_enabled() is False
    assert logger_mod.is_settings_logging_enabled() is False
    assert logger_mod.is_cache_logging_enabled() is False
    assert logger_mod.is_steam_logging_enabled() is False


def test_diagnostic_build_enables_every_family_beside_frozen_executable(
    tmp_path,
    monkeypatch,
):
    executable = tmp_path / "installed" / "SRPSS_Diagnostic.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"fixture")
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(logger_mod.sys, "executable", str(executable))
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", True)
    monkeypatch.setattr(logger_mod, "_PERF_METRICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_USAGE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_DIAGNOSTICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GEOMETRY_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_SETTINGS_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_LIFECYCLE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_CACHE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_STEAM_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_WIDGET_PERF_VERBOSE", False)

    logger_mod.setup_logging(diagnostic_build=True)
    logging.getLogger("SettingsManager").info("[SETTINGS] diagnostic settings")
    logging.getLogger("engine.engine_lifecycle").info("[LIFECYCLE] diagnostic lifecycle")

    expected = executable.parent / "logs"
    assert logger_mod.get_log_dir() == expected
    rotating = [
        handler
        for handler in logger_mod.get_logging_output_handlers()
        if isinstance(handler, RotatingFileHandler)
    ]
    assert rotating

    # Production + Logging_Guide contract: all rotating logs use 2 MiB chunks.
    # Diagnostic extends bounded history for the main/usage/lifecycle spines;
    # it does not globally force every family down to <=5 backups.
    expected_backup_counts = {
        "screensaver.log": 11,
        "screensaver_verbose.log": 3,
        "screensaver_perf.log": 5,
        "perf_widgets.log": 5,
        "screensaver_usage.log": 11,
        "screensaver_spotify_vis.log": 5,
        "screensaver_spotify_vol.log": 5,
        "screensaver_geometry.log": 5,
        "screensaver_settings.log": 5,
        "screensaver_lifecycle.log": 11,
        "screensaver_cache.log": 5,
        "screensaver_steam.log": 5,
    }
    rotating_by_name = {
        Path(handler.baseFilename).name: handler
        for handler in rotating
    }
    assert set(rotating_by_name) == set(expected_backup_counts)
    assert all(handler.maxBytes == 2 * 1024 * 1024 for handler in rotating)
    assert {
        name: handler.backupCount
        for name, handler in rotating_by_name.items()
    } == expected_backup_counts

    assert logger_mod.is_verbose_logging() is True
    assert logger_mod.is_perf_metrics_enabled() is True
    assert logger_mod.is_gpu_timing_enabled() is True
    assert logger_mod.is_usage_logging_enabled() is True
    assert logger_mod.is_widget_perf_verbose() is True
    assert logger_mod.is_viz_logging_enabled() is True
    assert logger_mod.is_viz_diagnostics_enabled() is True
    assert logger_mod.is_geometry_logging_enabled() is True
    assert logger_mod.is_settings_logging_enabled() is True
    assert logger_mod.is_lifecycle_logging_enabled() is True
    assert logger_mod.is_cache_logging_enabled() is True
    assert logger_mod.is_steam_logging_enabled() is True
    assert {
        "screensaver.log",
        "screensaver_verbose.log",
        "screensaver_perf.log",
        "perf_widgets.log",
        "screensaver_usage.log",
        "screensaver_spotify_vis.log",
        "screensaver_spotify_vol.log",
        "screensaver_geometry.log",
        "screensaver_settings.log",
        "screensaver_lifecycle.log",
        "screensaver_cache.log",
        "screensaver_steam.log",
    } <= {Path(handler.baseFilename).name for handler in rotating}

    logger_mod.flush_and_close_logging()
    assert "diagnostic settings" in (expected / "screensaver_settings.log").read_text(
        encoding="utf-8"
    )
    assert "diagnostic lifecycle" in (expected / "screensaver_lifecycle.log").read_text(
        encoding="utf-8"
    )


def test_diagnostic_log_dir_falls_back_localappdata_then_temp(tmp_path, monkeypatch):
    executable = tmp_path / "install" / "SRPSS_Diagnostic.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"fixture")
    local_root = tmp_path / "local"
    temp_root = tmp_path / "temp"
    monkeypatch.setenv("LOCALAPPDATA", str(local_root))
    monkeypatch.setattr(logger_mod.tempfile, "gettempdir", lambda: str(temp_root))
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(logger_mod.sys, "executable", str(executable))
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)

    real_try = logger_mod._try_writable_log_dir
    monkeypatch.setattr(
        logger_mod,
        "_try_writable_log_dir",
        lambda path: None if path == executable.parent / "logs" else real_try(path),
    )
    expected_local = local_root / "SRPSS" / "Diagnostic" / "logs"
    assert logger_mod._resolve_runtime_log_dir(diagnostic_build=True) == expected_local

    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(
        logger_mod,
        "_try_writable_log_dir",
        lambda path: (
            None
            if path in (executable.parent / "logs", expected_local)
            else real_try(path)
        ),
    )
    assert logger_mod._resolve_runtime_log_dir(diagnostic_build=True) == (
        temp_root / "SRPSS" / "Diagnostic" / "logs"
    )


def test_diagnostic_fresh_clear_and_get_use_exact_same_resolved_dir(
    tmp_path,
    monkeypatch,
):
    executable = tmp_path / "installed" / "SRPSS_Diagnostic.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"fixture")
    log_dir = executable.parent / "logs"
    log_dir.mkdir()
    (log_dir / "stale.log").write_text("old", encoding="utf-8")
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(logger_mod.sys, "executable", str(executable))
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)

    resolved, deleted = logger_mod.clear_logs_for_fresh_start(diagnostic_build=True)

    assert resolved == log_dir
    assert deleted == 1
    assert logger_mod.get_log_dir() == log_dir


def test_logging_bootstrap_profile_keeps_normal_collectors_off_without_flags():
    normal = logger_mod.resolve_logging_bootstrap_profile((), diagnostic_build=False)
    diagnostic = logger_mod.resolve_logging_bootstrap_profile((), diagnostic_build=True)

    assert not any(vars(normal).values())
    assert all(vars(diagnostic).values())


def test_gpu_timing_is_explicit_and_implies_perf_logging():
    ordinary_perf = logger_mod.resolve_logging_bootstrap_profile(
        ("--perf",),
        diagnostic_build=False,
    )
    gpu_timing = logger_mod.resolve_logging_bootstrap_profile(
        ("--gpu-timing",),
        diagnostic_build=False,
    )

    assert ordinary_perf.perf is True
    assert ordinary_perf.gpu_timing is False
    assert gpu_timing.perf is True
    assert gpu_timing.gpu_timing is True


def test_setup_logging_can_return_from_gpu_timing_to_ordinary_perf(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: False)
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    monkeypatch.setattr(logger_mod, "_PERF_METRICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GPU_TIMING_ENABLED", False)

    logger_mod.setup_logging(perf=True, gpu_timing=True)
    assert logger_mod.is_gpu_timing_enabled() is True

    logger_mod.setup_logging(perf=True, gpu_timing=False)
    assert logger_mod.is_perf_metrics_enabled() is True
    assert logger_mod.is_gpu_timing_enabled() is False


def test_normal_frozen_build_remains_logging_disabled(tmp_path, monkeypatch):
    executable = tmp_path / "SRPSS.scr"
    executable.write_bytes(b"fixture")
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(logger_mod.sys, "executable", str(executable))
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", True)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    for name in (
        "_PERF_METRICS_ENABLED",
        "_GPU_TIMING_ENABLED",
        "_USAGE_LOGGING_ENABLED",
        "_VIZ_LOGGING_ENABLED",
        "_VIZ_DIAGNOSTICS_ENABLED",
        "_GEOMETRY_LOGGING_ENABLED",
        "_SETTINGS_LOGGING_ENABLED",
        "_LIFECYCLE_LOGGING_ENABLED",
        "_CACHE_LOGGING_ENABLED",
        "_STEAM_LOGGING_ENABLED",
    ):
        monkeypatch.setattr(logger_mod, name, False)

    logger_mod.setup_logging()

    assert all(
        isinstance(handler, logging.NullHandler)
        for handler in logging.getLogger().handlers
    )
    assert not (tmp_path / "logs").exists()
    assert logger_mod.is_perf_metrics_enabled() is False
    assert logger_mod.is_gpu_timing_enabled() is False
    assert logger_mod.is_usage_logging_enabled() is False


def test_script_mode_retains_main_log_only_without_diagnostic_flags(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(logger_mod, "is_compiled_runtime", lambda: False)
    monkeypatch.setattr(logger_mod, "_BASE_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    for name in (
        "_PERF_METRICS_ENABLED",
        "_GPU_TIMING_ENABLED",
        "_USAGE_LOGGING_ENABLED",
        "_VIZ_LOGGING_ENABLED",
        "_VIZ_DIAGNOSTICS_ENABLED",
        "_GEOMETRY_LOGGING_ENABLED",
        "_SETTINGS_LOGGING_ENABLED",
        "_LIFECYCLE_LOGGING_ENABLED",
        "_CACHE_LOGGING_ENABLED",
        "_STEAM_LOGGING_ENABLED",
    ):
        monkeypatch.setattr(logger_mod, name, False)

    logger_mod.setup_logging()
    handlers = [
        handler
        for handler in logger_mod.get_logging_output_handlers()
        if isinstance(handler, RotatingFileHandler)
    ]

    assert {Path(handler.baseFilename).name for handler in handlers} == {
        "screensaver.log"
    }
    assert logger_mod.is_perf_metrics_enabled() is False
    assert logger_mod.is_gpu_timing_enabled() is False
    assert logger_mod.is_usage_logging_enabled() is False

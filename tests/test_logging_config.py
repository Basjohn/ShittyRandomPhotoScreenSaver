import logging
from core.logging import logger as logger_mod


def test_setup_logging_cli_families_enable_sidecar_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    monkeypatch.setattr(logger_mod, "_PERF_METRICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_DIAGNOSTICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GEOMETRY_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_SETTINGS_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_LIFECYCLE_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VERBOSE", False)

    logger_mod.setup_logging(
        debug=False,
        verbose=False,
        perf=True,
        viz=True,
        geo=True,
        settings_trace=True,
        lifecycle=True,
    )

    logging.getLogger("rendering.custom_layout_manager").info("[CUSTOM_LAYOUT] geometry trace")
    logging.getLogger("SettingsManager").info("[SETTINGS] write trace")
    logging.getLogger("widgets.spotify_visualizer_widget").info("[SPOTIFY_VIS] mode trace")
    logging.getLogger("engine.screensaver").info("[PERF] timing trace")
    logging.getLogger("core.process.supervisor").info("ProcessSupervisor initialized")

    logging.shutdown()

    assert logger_mod.is_perf_metrics_enabled() is True
    assert logger_mod.is_viz_logging_enabled() is True
    assert logger_mod.is_viz_diagnostics_enabled() is True
    assert logger_mod.is_geometry_logging_enabled() is True
    assert logger_mod.is_settings_logging_enabled() is True
    assert logger_mod.is_lifecycle_logging_enabled() is True

    main_log = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    assert "[CUSTOM_LAYOUT] geometry trace" not in main_log
    assert "[SETTINGS] write trace" not in main_log
    assert "[SPOTIFY_VIS] mode trace" not in main_log
    assert "[PERF] timing trace" not in main_log
    assert "ProcessSupervisor initialized" not in main_log
    assert "Specific logs available:" in main_log
    assert "Specific logs active:" in main_log

    assert "[CUSTOM_LAYOUT] geometry trace" in (tmp_path / "screensaver_geometry.log").read_text(encoding="utf-8")
    assert "[SETTINGS] write trace" in (tmp_path / "screensaver_settings.log").read_text(encoding="utf-8")
    assert "[SPOTIFY_VIS] mode trace" in (tmp_path / "screensaver_spotify_vis.log").read_text(encoding="utf-8")
    assert "[PERF] timing trace" in (tmp_path / "screensaver_perf.log").read_text(encoding="utf-8")
    assert "ProcessSupervisor initialized" in (tmp_path / "screensaver_lifecycle.log").read_text(encoding="utf-8")


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
        "widgets.clock_widget",
        logging.INFO,
        __file__,
        1,
        "[LIFECYCLE] ClockWidget activated",
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
        "widgets.reddit_widget",
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
    monkeypatch.setattr(logger_mod, "_VIZ_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_VIZ_DIAGNOSTICS_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_GEOMETRY_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_SETTINGS_LOGGING_ENABLED", False)
    monkeypatch.setattr(logger_mod, "_LIFECYCLE_LOGGING_ENABLED", False)
    monkeypatch.setenv("SRPSS_PERF_METRICS", "1")
    monkeypatch.setenv("SRPSS_VIZ_LOGGING", "1")
    monkeypatch.setenv("SRPSS_VIZ_DIAGNOSTICS", "1")
    monkeypatch.setenv("SRPSS_GEOMETRY_LOGGING", "1")
    monkeypatch.setenv("SRPSS_SETTINGS_LOGGING", "1")

    logger_mod.setup_logging(debug=False, verbose=False)
    logging.shutdown()

    assert logger_mod.is_perf_metrics_enabled() is False
    assert logger_mod.is_viz_logging_enabled() is False
    assert logger_mod.is_viz_diagnostics_enabled() is False
    assert logger_mod.is_geometry_logging_enabled() is False
    assert logger_mod.is_settings_logging_enabled() is False

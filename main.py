"""
ShittyRandomPhotoScreenSaver - Main Entry Point

Windows screensaver application that displays photos with transitions.
"""
import sys
import os
import gc
import shutil
import ctypes
import time
from pathlib import Path
from enum import Enum
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QImageReader, QIcon
from core.logging.logger import (
    clear_logs_for_fresh_start,
    flush_and_close_logging,
    flush_logging,
    setup_logging,
    get_logger,
    get_log_dir,
    is_perf_metrics_enabled,
    resolve_logging_bootstrap_profile,
)
from core.build_profile import (
    activate_diagnostic_build,
    get_build_flavour,
    is_compiled_runtime,
    is_diagnostic_build,
)
from core.settings.settings_manager import SettingsManager
from core.settings.persistence import flush_and_close_settings_persistence
from core.animation import AnimationManager
from engine.screensaver_engine import ScreensaverEngine
from ui.settings_dialog import SettingsDialog
from rendering.gl_format import build_surface_format
from ui.system_tray import ScreensaverTrayIcon
from versioning import APP_VERSION, APP_EXE_NAME

logger = get_logger(__name__)

# Windows timer resolution management for smoother animations.
# Default Windows timer resolution is ~15.6ms which causes timer coalescing
# and frame timing jitter. We request 1ms resolution for the duration of
# the screensaver to ensure smooth 60fps+ animations.
_winmm = None
_timer_resolution_set = False

def _set_windows_timer_resolution(resolution_ms: int = 1) -> bool:
    """Request higher timer resolution on Windows for smoother animations.
    
    Args:
        resolution_ms: Desired timer resolution in milliseconds (1-15)
    
    Returns:
        True if resolution was set successfully
    """
    global _winmm, _timer_resolution_set
    if sys.platform != 'win32':
        return False
    if _timer_resolution_set:
        return True
    try:
        _winmm = ctypes.windll.winmm
        result = _winmm.timeBeginPeriod(resolution_ms)
        if result == 0:  # TIMERR_NOERROR
            _timer_resolution_set = True
            return True
    except Exception as e:
        logger.debug("[MAIN] Exception suppressed: %s", e)
    return False

def _restore_windows_timer_resolution(resolution_ms: int = 1) -> None:
    """Restore default Windows timer resolution."""
    global _winmm, _timer_resolution_set
    if not _timer_resolution_set or _winmm is None:
        return
    try:
        _winmm.timeEndPeriod(resolution_ms)
        _timer_resolution_set = False
    except Exception as e:
        logger.debug("[MAIN] Exception suppressed: %s", e)

class ScreensaverMode(Enum):
    """Screensaver execution modes based on Windows arguments."""
    RUN = "run"          # /s - Run screensaver
    CONFIG = "config"    # /c - Configuration dialog
    PREVIEW = "preview"  # /p <hwnd> - Preview in settings window


def _is_frozen_build() -> bool:
    """Compatibility wrapper around the authoritative runtime check."""
    return is_compiled_runtime()


def parse_screensaver_args() -> tuple[ScreensaverMode, int | None]:
    """
    Parse Windows screensaver command-line arguments.
    
    Windows screensaver arguments:
    - /s - Run the screensaver
    - /c - Show configuration dialog
    - /p <hwnd> - Preview mode (show in window with handle <hwnd>)
    
    Debug flags (ignored here, handled earlier):
    - --debug, -d - Enable debug logging
    - --verbose, -v - Enable full verbose log stream
    - --perf - Enable performance logging
    - --gpu-timing - Enable sampled owner-context GL timer queries (implies --perf)
    - --usage - Enable low-cadence CPU/GPU/memory/thread usage logging
    - --viz - Enable visualizer logging and diagnostics
    - --geo - Enable geometry/z-order/edit-layout diagnostics
    - --set - Enable settings mutation/import/schema diagnostics
    - --life - Enable widget/worker/engine lifecycle diagnostics
    - --cache - Enable image-cache/prefetch/cache-authority diagnostics
    - --steam - Enable Steam widget family diagnostics
    - --noupdates - Disable automatic Gmail/Reddit/Weather retrievals; manual refresh still works
    - --viz-diagnostics (or --viz-diag) - Legacy alias for extra Spotify visualizer diagnostics
    - --devcurve - Legacy no-op flag kept for compatibility
    - --devsteam - Show unfinished Steam Journey, Abandonment Issues, and Friend Pulse cards
    
    Returns:
        tuple: (ScreensaverMode, preview_window_handle)
    """
    # Filter out debug/viz/dev-gate flags
    _filtered = {
        "--debug", "-d", "--verbose", "-v", "--perf", "--gpu-timing", "--diag-pair-warm-finish", "--diag-p4-stages", "--usage", "--viz", "--geo", "--set", "--life", "--cache", "--steam",
        "--noupdates",
        "--viz-diagnostics", "--viz-diag",
        "--fresh", "--devcurve", "--devsteam",
    }
    args = [arg for arg in sys.argv if arg not in _filtered]
    
    logger.debug(f"Command-line arguments: {sys.argv}")
    logger.debug(f"Filtered arguments: {args}")

    # Detect whether we are running as a frozen executable (.exe/.scr)
    # or as a plain Python script.
    is_frozen = _is_frozen_build()

    # Default mode depends on environment:
    #  - Script runs (python main.py) default to RUN for convenience.
    #  - Frozen builds (SRPSS.exe/SRPSS.scr) default to CONFIG to avoid
    #    surprising full-screen runs when selected in the Windows dialog
    #    or double-clicked.
    if len(args) == 1:
        if is_frozen:
            logger.info("No arguments provided in frozen build, defaulting to CONFIG mode")
            return ScreensaverMode.CONFIG, None
        logger.info("No arguments provided in script mode, defaulting to RUN mode")
        return ScreensaverMode.RUN, None
    
    # Get the first argument (after program name)
    raw_arg = args[1]
    arg = raw_arg.lower().strip()

    # Run screensaver (Windows /s only). For convenience, -s/--s open settings.
    if arg == '/s':
        logger.info("RUN mode selected")
        return ScreensaverMode.RUN, None
    
    # Configuration dialog. Windows may pass "/c" or "/c:####" (with a
    # parent window handle); treat any "/c*" pattern as CONFIG mode so the
    # Screen Saver Settings "Settings" button never accidentally runs the
    # saver full-screen.
    elif arg.startswith('/c') or arg in ('-c', '-s', '--s'):
        logger.info("CONFIG mode selected")
        return ScreensaverMode.CONFIG, None
    
    # Preview mode
    elif arg == '/p' or arg == '-p':
        if len(args) > 2:
            try:
                hwnd = int(args[2])
                logger.info(f"PREVIEW mode selected with window handle: {hwnd}")
                return ScreensaverMode.PREVIEW, hwnd
            except ValueError:
                logger.error(f"Invalid window handle: {args[2]}")
                return ScreensaverMode.PREVIEW, None
        else:
            logger.warning("PREVIEW mode selected but no window handle provided")
            return ScreensaverMode.PREVIEW, None
    
    # Unknown argument – default mode depends on environment so we never
    # "surprise run" a frozen build while keeping script usage simple.
    else:
        if is_frozen:
            logger.warning(f"Unknown argument: {arg}, defaulting to CONFIG mode (frozen)")
            return ScreensaverMode.CONFIG, None
        logger.warning(f"Unknown argument: {arg}, defaulting to RUN mode (script)")
        return ScreensaverMode.RUN, None


def is_script_mode() -> bool:
    """
    Check if running as a script (not compiled executable).
    
    Returns:
        True if running as .py script, False if compiled .exe/.scr
    """
    # PyInstaller and similar bundlers set sys.frozen on the runtime
    # executable; treat any such environment as non-script.
    if _is_frozen_build():
        return False

    # Check if running from a .py file or if __file__ exists
    return hasattr(sys, 'ps1') or (
        hasattr(sys.modules['__main__'], '__file__') and
        sys.modules['__main__'].__file__.endswith('.py')
    )


def cleanup_pycache(root_path: Path) -> int:
    """
    Recursively delete all __pycache__ directories.
    
    Args:
        root_path: Root directory to start cleanup from
    
    Returns:
        Number of directories removed
    """
    removed_count = 0
    
    try:
        for dirpath, dirnames, _ in os.walk(root_path):
            # Look for __pycache__ directories
            if '__pycache__' in dirnames:
                pycache_path = Path(dirpath) / '__pycache__'
                try:
                    shutil.rmtree(pycache_path)
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove pycache {pycache_path}: {e}")
    except Exception as e:
        logger.warning(f"Error during pycache cleanup: {e}")
    
    return removed_count


def _schedule_runtime_reddit_helper_session(engine) -> bool:
    """Keep a saver-session ticket fresh and request task-owned helper launch.

    The saver does not spawn the helper directly anymore. It only refreshes a
    benign ProgramData ticket and asks Windows Task Scheduler to start the
    already-registered interactive helper task when needed.
    """
    if is_diagnostic_build():
        logger.info(
            "[REDDIT-HELPER] Session helper skipped for isolated diagnostic runtime"
        )
        return False
    try:
        from core.mc import is_mc_build
        from core.windows.reddit_helper_installer import _log_helper_event
        from core.windows import reddit_helper_runtime

        script_mode = bool(is_script_mode())
        mc_mode = bool(is_mc_build())
        if script_mode or mc_mode:
            _log_helper_event(
                "session helper skipped "
                f"script={int(script_mode)} mc={int(mc_mode)} "
                f"argv0={Path(str(getattr(sys, 'argv', [''])[0] or '')).name} "
                f"exe={Path(str(getattr(sys, 'executable', '') or '')).name}"
            )
            return False
    except Exception:
        logger.debug("[REDDIT-HELPER] Failed to resolve session-helper environment", exc_info=True)
        return False

    timer = getattr(engine, "_reddit_helper_session_timer", None)
    if timer is not None:
        try:
            timer.stop()
            timer.deleteLater()
        except Exception:
            logger.debug("[REDDIT-HELPER] Failed to reset previous session timer", exc_info=True)

    thread_manager = getattr(engine, "thread_manager", None)
    if thread_manager is None:
        _log_helper_event("session helper skipped no-thread-manager")
        logger.info("[REDDIT-HELPER] Session helper skipped because ThreadManager is unavailable")
        return False

    if not reddit_helper_runtime.refresh_session_ticket(source="run_session_start"):
        _log_helper_event("session helper ticket-refresh-failed source=run_session_start")

    launched = reddit_helper_runtime.ensure_helper_runtime(
        source="run_session_start",
        persistent=False,
        allow_system=True,
    )
    _log_helper_event(
        "session helper start "
        f"launched={int(bool(launched))}"
    )

    interval_ms = int(max(1000, reddit_helper_runtime.SESSION_TICKET_REFRESH_SECONDS * 1000.0))

    def _session_tick() -> None:
        try:
            if not bool(getattr(engine, "_running", False)):
                reddit_helper_runtime.clear_session_ticket(source="run_session_stop")
                timer_ref = getattr(engine, "_reddit_helper_session_timer", None)
                if timer_ref is not None:
                    try:
                        timer_ref.stop()
                        timer_ref.deleteLater()
                    except Exception:
                        logger.debug("[REDDIT-HELPER] Failed to stop session timer", exc_info=True)
                    finally:
                        engine._reddit_helper_session_timer = None
                _log_helper_event("session helper stopped engine-not-running")
                return

            reddit_helper_runtime.refresh_session_ticket(source="run_session_keepalive")
            if not reddit_helper_runtime.is_helper_healthy():
                relaunched = reddit_helper_runtime.ensure_helper_runtime(
                    source="run_session_keepalive",
                    persistent=False,
                    allow_system=True,
                )
                _log_helper_event(f"session helper keepalive launch={int(bool(relaunched))}")
        except Exception as exc:
            try:
                from core.windows.reddit_helper_installer import _log_helper_event as _fallback_log_helper_event
                _fallback_log_helper_event(f"session helper callback exception: {exc!r}")
            except Exception:
                pass
            logger.debug("[REDDIT-HELPER] Session helper keepalive failed", exc_info=True)

    timer = thread_manager.schedule_recurring(
        interval_ms,
        _session_tick,
        description="Reddit helper session keepalive",
    )
    engine._reddit_helper_session_timer = timer
    logger.info("[REDDIT-HELPER] Scheduled session ticket keepalive every %sms", interval_ms)
    return True


def run_screensaver(app: QApplication, *, usage_enabled: bool = False) -> int:
    """
    Run the screensaver.
    
    Args:
        app: Qt application instance
        usage_enabled: Start opt-in low-cadence resource telemetry.
    
    Returns:
        Exit code
    """
    logger.info("Initializing screensaver engine")

    # Create settings manager
    settings = SettingsManager()

    # Determine whether Interaction Mode is enabled so we can optionally
    # expose a small system tray for Settings/Exit while the saver runs.
    interaction_mode_enabled = False
    try:
        raw_interaction_mode = settings.get('input.interaction_mode', False)
        if hasattr(SettingsManager, "to_bool"):
            interaction_mode_enabled = SettingsManager.to_bool(raw_interaction_mode, False)
        else:
            interaction_mode_enabled = bool(raw_interaction_mode)
    except Exception as e:
        logger.debug("[MAIN] Exception suppressed: %s", e)
        interaction_mode_enabled = False
    
    # Check if sources are configured (using dot notation)
    folders = settings.get('sources.folders', [])
    rss_feeds = settings.get('sources.rss_feeds', [])
    
    if not folders and not rss_feeds:
        logger.warning("No image sources configured - opening settings dialog")
        msg = QMessageBox(
            QMessageBox.Icon.Information,
            "No Sources Configured",
            "No image sources have been configured.\n\n"
            "Please add folders or RSS feeds in the settings dialog.\n\n"
            "This dialog will close automatically in 10 seconds.",
        )
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.raise_()
        msg.activateWindow()
        # Auto-close after 10 seconds — uses QTimer.singleShot (static, no
        # compositor active at this point so no performance concern).
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10_000, msg.accept)
        msg.exec()
        return run_config(app)
    # Create and start screensaver engine
    try:
        engine = ScreensaverEngine()
        if not engine.initialize():
            logger.error("Failed to initialize screensaver engine")
            logger.warning("Opening settings dialog to configure sources")
            msg2 = QMessageBox(
                QMessageBox.Icon.Warning,
                "Configuration Required",
                "Failed to initialize screensaver.\n\n"
                "Please configure image sources in the settings dialog.\n\n"
                "This dialog will close automatically in 10 seconds.",
            )
            msg2.setWindowFlags(msg2.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            msg2.raise_()
            msg2.activateWindow()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10_000, msg2.accept)
            msg2.exec()
            return run_config(app)
        
        if not engine.start():
            logger.error("Failed to start screensaver engine")
            logger.warning("Opening settings dialog")
            msg3 = QMessageBox(
                QMessageBox.Icon.Warning,
                "Startup Failed",
                "Failed to start screensaver.\n\n"
                "Please check your configuration.\n\n"
                "This dialog will close automatically in 10 seconds.",
            )
            msg3.setWindowFlags(msg3.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            msg3.raise_()
            msg3.activateWindow()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10_000, msg3.accept)
            msg3.exec()
            return run_config(app)

        # RUN lifetime is owned by explicit engine/tray/error exit routes, not
        # by the current top-level-window count.  Settings/Edit recreation now
        # deliberately has a destruction-barrier interval after its last old
        # window closes and before replacement construction.  Qt's default
        # auto-quit would terminate that healthy interval before the barrier's
        # queued completion callback can run.
        app.setQuitOnLastWindowClosed(False)

        event_loop_recorder = None
        if is_perf_metrics_enabled():
            try:
                from core.performance.event_loop_recorder import EventLoopStallRecorder

                event_loop_recorder = EventLoopStallRecorder(parent=app)
                event_loop_recorder.start()
            except Exception:
                event_loop_recorder = None
                logger.exception("[PERF] Failed to start event-loop lateness recorder")

        if usage_enabled:
            try:
                from core.performance.usage_sampler import UsageTelemetryService
                from core.performance.resource_metrics import collect_resource_accounting

                if engine.thread_manager is None:
                    raise RuntimeError("ThreadManager unavailable after engine start")

                def _usage_resource_snapshot() -> dict[str, object]:
                    fields: dict[str, object] = dict(
                        collect_resource_accounting(
                            engine,
                            worker_safe=True,
                        ).aggregate_fields()
                    )
                    supervisor = getattr(engine, "_process_supervisor", None)
                    if supervisor is not None:
                        fields.update(supervisor.get_image_worker_usage_snapshot())
                    return fields

                engine._usage_telemetry = UsageTelemetryService(
                    engine.thread_manager,
                    resource_snapshot_provider=_usage_resource_snapshot,
                )
                if not engine._usage_telemetry.start():
                    raise RuntimeError("usage telemetry declined startup")
            except Exception:
                logger.exception("[USAGE] Failed to start whole-process telemetry")
        
        # Optional system tray presence in Interaction Mode.
        tray_icon = None
        if interaction_mode_enabled:
            try:
                tray_icon = ScreensaverTrayIcon(app, app.windowIcon())
            except Exception:
                logger.debug("Failed to create system tray icon", exc_info=True)

            if tray_icon is not None:
                # Delegate to the engine's existing S-key workflow so tray
                # Settings behaves identically to pressing S.
                def _on_tray_settings() -> None:
                    try:
                        # _on_settings_requested performs a full stop →
                        # settings dialog → restart cycle.
                        engine._on_settings_requested()  # type: ignore[attr-defined]
                    except Exception:
                        logger.exception("Failed to open settings from system tray")

                def _on_tray_exit() -> None:
                    try:
                        engine.stop()
                    except Exception:
                        logger.exception("Failed to stop engine from system tray")
                    app.quit()

                tray_icon.settings_requested.connect(_on_tray_settings)
                tray_icon.exit_requested.connect(_on_tray_exit)

        logger.info("Screensaver engine started - entering event loop")
        _schedule_runtime_reddit_helper_session(engine)
        try:
            return app.exec()
        finally:
            if event_loop_recorder is not None:
                try:
                    event_loop_recorder.stop()
                except Exception:
                    logger.debug("[PERF] Event-loop recorder stop failed", exc_info=True)
        
    except Exception as e:
        logger.exception(f"Failed to start screensaver engine: {e}")
        QMessageBox.critical(
            None,
            "Screensaver Error",
            f"Failed to start screensaver:\n{e}"
        )
        return 1


def run_config(app: QApplication) -> int:
    """
    Run configuration dialog.
    
    Args:
        app: Qt application instance
    
    Returns:
        Exit code
    """
    logger.info("Opening configuration dialog")
    
    # Create settings manager
    settings = SettingsManager()
    
    # Create animation manager
    animations = AnimationManager(owner="settings:config")
    
    # Create and show settings dialog
    try:
        dialog = SettingsDialog(settings, animations)
        dialog.show()
        
        logger.info("Configuration dialog opened - entering event loop")
        return app.exec()
        
    except Exception as e:
        logger.exception(f"Failed to open configuration dialog: {e}")
        QMessageBox.critical(
            None,
            "Configuration Error",
            f"Failed to open settings:\n{e}"
        )
        return 1


def main(*, entrypoint: str = "main"):
    """Main entry point for the screensaver application."""
    entrypoint_token = str(entrypoint).strip().lower()
    if entrypoint_token == "main_diagnostic":
        activate_diagnostic_build()
    diagnostic_build = is_diagnostic_build()

    fresh_mode = '--fresh' in sys.argv
    fresh_result: tuple[Path, int] | None = None
    if fresh_mode:
        fresh_result = clear_logs_for_fresh_start(
            diagnostic_build=diagnostic_build,
        )

    logging_profile = resolve_logging_bootstrap_profile(
        sys.argv[1:],
        diagnostic_build=diagnostic_build,
    )
    debug_mode = logging_profile.debug
    verbose_mode = logging_profile.verbose
    perf_mode = logging_profile.perf
    usage_mode = logging_profile.usage
    setup_logging(
        debug=debug_mode,
        verbose=verbose_mode,
        perf=perf_mode,
        gpu_timing=logging_profile.gpu_timing,
        usage=usage_mode,
        viz=logging_profile.viz,
        viz_diag=logging_profile.viz_diag,
        geo=logging_profile.geo,
        settings_trace=logging_profile.settings_trace,
        lifecycle=logging_profile.lifecycle,
        cache_trace=logging_profile.cache_trace,
        steam_trace=logging_profile.steam_trace,
        diagnostic_build=diagnostic_build,
    )
    diagnostic_record = None
    diagnostic_close = None
    if diagnostic_build:
        from core.logging.crash_capture import (
            close_diagnostic_crash_capture,
            enable_diagnostic_crash_capture,
            record_diagnostic_stage,
        )

        diagnostic_record = record_diagnostic_stage
        diagnostic_close = close_diagnostic_crash_capture
        crash_path = enable_diagnostic_crash_capture(get_log_dir())
        logger.info(
            "[DIAGNOSTIC] Bounded logs active at %s crash_capture=%s",
            get_log_dir(),
            crash_path or "unavailable",
        )
        diagnostic_record("main_logging_ready")
    if fresh_result is not None:
        fresh_log_dir, fresh_deleted = fresh_result
        logger.info(
            "[FRESH] Cleared %s log files from %s before startup",
            fresh_deleted,
            fresh_log_dir,
        )
    
    # GC tracking for performance debugging
    if perf_mode:
        _gc_start_time = [0.0]
        def _gc_callback(phase: str, info: dict) -> None:
            if phase == 'start':
                _gc_start_time[0] = time.time()
            elif phase == 'stop':
                elapsed_ms = (time.time() - _gc_start_time[0]) * 1000.0
                if elapsed_ms > 10.0:
                    logger.warning("[PERF] [GC] Collection took %.2fms (gen=%s, collected=%s)",
                                   elapsed_ms, info.get('generation', '?'), info.get('collected', '?'))
        gc.callbacks.append(_gc_callback)
        logger.info("[PERF] GC tracking enabled")
    
    logger.info("=" * 60)
    logger.info("ShittyRandomPhotoScreenSaver Starting")
    logger.info("=" * 60)
    
    # Startup should not pay the recursive pycache-cleanup cost in script mode.
    # Exit cleanup is still retained for local developer hygiene.
    
    # Parse command-line arguments
    mode, preview_hwnd = parse_screensaver_args()
    if entrypoint_token == "main_mc":
        entrypoint_name = "main_mc"
    elif entrypoint_token == "main_diagnostic":
        entrypoint_name = "main_diagnostic"
    else:
        entrypoint_name = "main"
    logger.info(
        "[STARTUP] entrypoint=%s mode=%s frozen=%s executable=%s build_flavour=%s",
        entrypoint_name,
        mode.value,
        _is_frozen_build(),
        Path(getattr(sys, "executable", "") or "").name or "<unknown>",
        get_build_flavour(),
    )
    if diagnostic_record is not None:
        diagnostic_record(
            "main_mode_parsed",
            entrypoint=entrypoint_name,
            mode=mode.value,
        )
    
    # Enable High DPI scaling BEFORE creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Configure OpenGL globally BEFORE creating QApplication
    try:
        # Prefer desktop OpenGL and share contexts across widgets
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

        fmt, prefs = build_surface_format(reason="startup")
        QSurfaceFormat.setDefaultFormat(fmt)
        logger.info(
            "Global QSurfaceFormat configured (swap=%s, interval=%s, depth=%s, stencil=%s)",
            fmt.swapBehavior(),
            fmt.swapInterval(),
            fmt.depthBufferSize(),
            fmt.stencilBufferSize(),
        )
    except Exception as e:
        logger.warning(f"Failed to configure global OpenGL format: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_EXE_NAME)
    app.setOrganizationName("ShittyRandomPhotoScreenSaver")
    try:
        app.setApplicationVersion(APP_VERSION)
    except Exception:
        logger.debug("[MAIN] Failed to set application version")

    # Apply application icon from SRPSS.ico when available so the
    # taskbar/systray and dialogs share a consistent identity.
    icon_path = Path(__file__).with_name("SRPSS.ico")
    if icon_path.exists():
        try:
            app.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            logger.debug("Failed to set application icon from SRPSS.ico", exc_info=True)

    # Increase Qt image allocation limit from 256MB to 1GB for high-res images
    # This is per-image when loaded, not total memory for all images
    # Images are loaded on-demand, not all at startup (ImageQueue stores metadata only)
    QImageReader.setAllocationLimit(1024)  # 1GB in MB
    logger.info("Qt image allocation limit: 1GB (supports 8K+ images, per-image on-demand)")
    
    logger.info("Qt Application created: %s", app.applicationName())
    if diagnostic_record is not None:
        diagnostic_record("qapplication_created")
    logger.debug("High DPI scaling enabled")

    # Register bundled custom fonts before any widgets are created
    from ui.tabs.shared_styles import ensure_custom_fonts
    ensure_custom_fonts()
    logger.debug("Custom fonts registered")

    # Route to appropriate mode
    exit_code = 0
    
    # Set Windows timer resolution for smoother animations (RUN mode only)
    timer_res_set = False
    
    try:
        if mode == ScreensaverMode.RUN:
            logger.info("Starting screensaver in RUN mode")
            # Request 1ms timer resolution for smooth 60fps+ animations
            timer_res_set = _set_windows_timer_resolution(1)
            if timer_res_set:
                logger.info("Windows timer resolution set to 1ms for smooth animations")
            else:
                logger.debug("Could not set Windows timer resolution (non-Windows or failed)")
            profile_flag = os.getenv("SRPSS_PROFILE_CPU", "").strip().lower()
            if profile_flag in ("1", "true", "on", "yes"):
                import cProfile

                profiler = cProfile.Profile()
                profiler.enable()
                exit_code = run_screensaver(app, usage_enabled=usage_mode)
                profiler.disable()
                try:
                    profile_path = get_log_dir() / "screensaver_run.pstats"
                    profiler.dump_stats(str(profile_path))
                    logger.info("[PERF] [CPU] cProfile stats written to %s", profile_path)
                except Exception:
                    logger.debug("[PERF] [CPU] Failed to write cProfile stats", exc_info=True)
            else:
                exit_code = run_screensaver(app, usage_enabled=usage_mode)
            
        elif mode == ScreensaverMode.CONFIG:
            logger.info("Starting configuration dialog")
            profile_flag = os.getenv("SRPSS_PROFILE_CPU", "").strip().lower()
            if profile_flag in ("1", "true", "on", "yes"):
                import cProfile

                profiler = cProfile.Profile()
                profiler.enable()
                exit_code = run_config(app)
                profiler.disable()
                try:
                    profile_path = get_log_dir() / "screensaver_config.pstats"
                    profiler.dump_stats(str(profile_path))
                    logger.info("[PERF] [CPU] cProfile stats written to %s", profile_path)
                except Exception:
                    logger.debug("[PERF] [CPU] Failed to write cProfile stats", exc_info=True)
            else:
                exit_code = run_config(app)
            
        elif mode == ScreensaverMode.PREVIEW:
            logger.info(f"Starting preview mode (hwnd={preview_hwnd})")
            # FEATURE BACKLOG: Preview mode shows thumbnail in Windows Screen Saver dialog.
            # Currently not implemented - would embed into host window via hwnd.
            # No window shown to avoid surprising users in dialog preview.
            logger.warning("PREVIEW mode not yet implemented (no window shown)")
        
    except Exception as e:
        logger.exception(f"Fatal error in main: {e}")
        exit_code = 1
    finally:
        # Restore Windows timer resolution if we changed it
        if timer_res_set:
            _restore_windows_timer_resolution(1)
            logger.debug("Windows timer resolution restored to default")
    
    settings_persistence = flush_and_close_settings_persistence(timeout=5.0)
    logger.info(
        "[SETTINGS_PERSIST] enqueued=%d coalesced=%d writes=%d failed=%d "
        "high_water=%d lag_avg_ms=%.3f lag_max_ms=%.3f write_avg_ms=%.3f "
        "write_max_ms=%.3f flush_max_ms=%.3f close_ms=%.3f timed_out=%s",
        int(settings_persistence.get("enqueued", 0)),
        int(settings_persistence.get("coalesced", 0)),
        int(settings_persistence.get("writes_completed", 0)),
        int(settings_persistence.get("writes_failed", 0)),
        int(settings_persistence.get("queue_high_water", 0)),
        float(settings_persistence.get("writer_lag_avg_ms", 0.0)),
        float(settings_persistence.get("writer_lag_max_ms", 0.0)),
        float(settings_persistence.get("write_avg_ms", 0.0)),
        float(settings_persistence.get("write_max_ms", 0.0)),
        float(settings_persistence.get("flush_max_ms", 0.0)),
        float(settings_persistence.get("close_duration_ms", 0.0)),
        bool(settings_persistence.get("close_timed_out", False)),
    )
    if (
        settings_persistence.get("close_timed_out")
        or int(settings_persistence.get("writes_failed", 0)) > 0
    ):
        logger.warning(
            "[SETTINGS_PERSIST] Terminal durability boundary was not clean: %r",
            settings_persistence,
        )
        if diagnostic_record is not None:
            diagnostic_record(
                "settings_persistence_close_failure",
                queue_depth=settings_persistence.get("queue_depth", 0),
                writes_failed=settings_persistence.get("writes_failed", 0),
                close_timed_out=settings_persistence.get("close_timed_out", False),
            )

    # Cleanup pycache on exit (script mode only)
    if is_script_mode():
        logger.info("Cleaning pycache on exit")
        project_root = Path(__file__).parent
        removed = cleanup_pycache(project_root)
        if removed > 0:
            logger.info(f"Removed {removed} __pycache__ directories")
    
    logger.info("=" * 60)
    logger.info(f"ShittyRandomPhotoScreenSaver Exiting (code={exit_code})")
    logger.info("=" * 60)
    if diagnostic_record is not None:
        diagnostic_record("main_return", exit_code=exit_code)

    logging_flushed_for_parser = flush_logging()
    if not logging_flushed_for_parser and diagnostic_record is not None:
        diagnostic_record(
            "ordinary_logging_pre_parser_flush_timeout",
        )

    # When PERF metrics are enabled for this run, automatically invoke the
    # PERF helper to summarise recent Spotify visualiser and Slide metrics
    # from the dedicated screensaver_perf.log. This is a best-effort helper
    # and failures are logged at DEBUG only so normal runs are unaffected.
    try:
        if perf_mode and logging_flushed_for_parser:
            try:
                from scripts import spotify_vis_metrics_parser as _sv  # type: ignore[import]
                _sv.main()
            except Exception:
                logger.debug(
                    "[PERF] spotify_vis_metrics_parser auto-run failed",
                    exc_info=True,
                )
    except Exception:
        logger.debug(
            "[PERF] spotify_vis_metrics_parser auto-run guard failed",
            exc_info=True,
        )

    logging_metrics = flush_and_close_logging()
    if logging_metrics.get("flush_timed_out") and diagnostic_record is not None:
        diagnostic_record(
            "ordinary_logging_flush_timeout",
            queue_depth=logging_metrics.get("queue_depth", 0),
            writer_alive=logging_metrics.get("writer_alive", False),
        )
    
    if diagnostic_close is not None:
        diagnostic_close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

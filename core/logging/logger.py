"""
Centralized logging configuration for screensaver application.

Uses rotating file handler with logs stored in logs/ directory.
Includes colored console output for debug mode.
"""
import logging
import os
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Detect frozen/Nuitka builds up-front so we can default to silent logging
# unless explicitly re-enabled.
try:
    import builtins as _builtins  # type: ignore
except Exception:  # pragma: no cover - fallback during exotic import failures
    _builtins = None


def _detect_frozen_environment() -> bool:
    """Best-effort detection of compiled/frozen runtime."""
    if bool(getattr(sys, "frozen", False)):
        return True

    if globals().get("__compiled__", False):
        return True

    if _builtins is not None and bool(getattr(_builtins, "__compiled__", False)):
        return True

    main_mod = sys.modules.get("__main__")
    if main_mod is not None and bool(getattr(main_mod, "__compiled__", False)):
        return True

    exe_path = Path(getattr(sys, "executable", "") or "")
    exe_name = exe_path.name.lower()
    if exe_name and exe_name not in ("python.exe", "pythonw.exe"):
        if exe_name.startswith("srpss"):
            return True
    return False


_IS_FROZEN: bool = _detect_frozen_environment()

_VERBOSE: bool = False
# PERF metrics default to False for production builds. Script mode (development)
# can enable via SRPSS_PERF_METRICS=1 env var; Nuitka builds use .perf.cfg files.
_PERF_METRICS_ENABLED: bool = False
# Logging defaults to disabled for frozen builds unless explicitly enabled via
# env vars or .logging.cfg files next to the executable.
_LOGGING_DISABLED: bool = _IS_FROZEN
# Base directory for logs and related artefacts. This is initialised to the
# project root by default and updated by setup_logging() for frozen builds so
# helpers like get_log_dir() always point at the effective runtime location.
_BASE_DIR: Path = Path(__file__).parent.parent.parent
_FORCED_LOG_DIR: Path | None = None
_ACTIVE_LOG_DIR: Path | None = None

def _parse_bool_token(value: Optional[str]) -> Optional[bool]:
    """Parse a string token into a boolean or None if indeterminate."""
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "on", "yes", "enable", "enabled"}:
        return True
    if lowered in {"0", "false", "off", "no", "disable", "disabled"}:
        return False
    return None


def _read_bool_flag_file(path: Path) -> Optional[bool]:
    """Read a boolean flag from the given path."""
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8").strip()
        return _parse_bool_token(raw)
    except Exception:
        return None


_env_perf = os.getenv("SRPSS_PERF_METRICS")
if _env_perf is not None:
    try:
        if str(_env_perf).strip().lower() in ("0", "false", "off", "no"):
            _PERF_METRICS_ENABLED = False
        elif str(_env_perf).strip().lower() in ("1", "true", "on", "yes"):
            _PERF_METRICS_ENABLED = True
    except Exception:
        pass  # Keep default (False) on parse failure

_env_log_dir = os.getenv("SRPSS_FORCE_LOG_DIR")
if _env_log_dir:
    try:
        candidate = Path(_env_log_dir).expanduser()
        if not candidate.is_absolute():
            candidate = candidate.resolve()
        _FORCED_LOG_DIR = candidate
    except Exception:
        _FORCED_LOG_DIR = None


def _determine_logging_disabled(exe_path: Path | None) -> bool:
    """Decide whether logging should be disabled for this runtime."""
    logging_disabled = _LOGGING_DISABLED

    if exe_path:
        if not logging_disabled:
            # Frozen builds default to logging disabled unless explicitly re-enabled.
            logging_disabled = True
        logging_cfg = exe_path.parent / f"{exe_path.stem}.logging.cfg"
        cfg_value = _read_bool_flag_file(logging_cfg)
        if cfg_value is not None:
            # File stores "1" to enable logging, "0" to disable.
            logging_disabled = not cfg_value

    env_disable = _parse_bool_token(os.getenv("SRPSS_DISABLE_LOGS"))
    if env_disable is True:
        logging_disabled = True
    elif env_disable is False:
        logging_disabled = False

    env_force = _parse_bool_token(os.getenv("SRPSS_FORCE_LOGS"))
    if env_force is True:
        logging_disabled = False

    return logging_disabled


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',       # Cyan
        'INFO': '\033[32m',        # Green
        'WARNING': '\033[33m',     # Yellow
        'ERROR': '\033[31m',       # Red
        'CRITICAL': '\033[35m',    # Magenta
    }
    FALLBACK_COLOR = '\033[38;5;208m'
    PREWARM_COLOR = '\033[38;5;135m'   # Purple for prewarm/flicker diagnostics
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg

        msg_text = str(record.msg)
        # Check if this is a fallback or prewarm/flicker-related message
        is_fallback = '[FALLBACK]' in msg_text
        is_prewarm = ('[PREWARM]' in msg_text
                      or 'flicker' in msg_text.lower()
                      or 'Seed pixmap' in msg_text)
        
        # Color the entire line
        color = None
        if is_fallback:
            # Highlight any fallback path in a distinct bright color so they
            # stand out regardless of level.
            color = self.FALLBACK_COLOR
        elif is_prewarm:
            # Use dedicated purple for prewarm/flicker diagnostics
            color = self.PREWARM_COLOR
        elif record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]

        if color is not None:
            # Color the level name in bold
            record.levelname = f"{self.BOLD}{color}{record.levelname}{self.RESET}"
            # Format the message
            message = super().format(record)
            # Color the entire formatted message
            colored_message = f"{color}{message}{self.RESET}"
            # Restore original values
            record.levelname = original_levelname
            record.msg = original_msg
            return colored_message
        
        # Restore original values for non-colored output
        record.levelname = original_levelname
        record.msg = original_msg
        return super().format(record)


class DeduplicatingRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that suppresses consecutive duplicate log lines.
    
    Thread-safe line-by-line deduplication for file logs. When consecutive
    identical messages are detected, they are collapsed with a count:
    "[N duplicates suppressed]"
    
    This significantly reduces log file size without losing information.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self._last_message: str | None = None
        self._suppress_count: int = 0
        self._last_record: logging.LogRecord | None = None
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record with deduplication."""
        try:
            # Get the formatted message
            msg_text = record.getMessage()
            
            with self._lock:
                # Always emit WARNING+ immediately
                if record.levelno >= logging.WARNING:
                    self._flush_suppression()
                    super().emit(record)
                    self._last_message = None
                    self._suppress_count = 0
                    self._last_record = None
                    return
                
                # First message or different from last
                if self._last_message is None or msg_text != self._last_message:
                    self._flush_suppression()
                    super().emit(record)
                    self._last_message = msg_text
                    self._suppress_count = 0
                    self._last_record = record
                else:
                    # Duplicate detected - increment counter
                    self._suppress_count += 1
                    if self._last_record is None:
                        self._last_record = record
        except Exception:
            self.handleError(record)
    
    def _flush_suppression(self) -> None:
        """Flush any pending suppression count."""
        if self._suppress_count > 0 and self._last_record is not None:
            # Create a summary record
            msg = f"[{self._suppress_count} duplicates suppressed]"
            summary = logging.LogRecord(
                self._last_record.name,
                self._last_record.levelno,
                self._last_record.pathname,
                self._last_record.lineno,
                msg,
                args=None,
                exc_info=None,
            )
            summary.created = self._last_record.created
            summary.msecs = self._last_record.msecs
            summary.relativeCreated = self._last_record.relativeCreated
            summary.thread = self._last_record.thread
            summary.threadName = self._last_record.threadName
            summary.process = self._last_record.process
            summary.processName = self._last_record.processName
            
            # Emit the suppression summary
            super().emit(summary)
            
            self._suppress_count = 0
            self._last_record = None
    
    def close(self) -> None:
        """Close handler and flush any pending suppression."""
        try:
            with self._lock:
                self._flush_suppression()
        finally:
            super().close()


class SuppressingStreamHandler(logging.StreamHandler):
    """Stream handler that suppresses consecutive duplicate sources.

    Repeated DEBUG/INFO lines from the same logger/level are collapsed into a
    single summary line like "[N Suppressed: CHECK screensaver_verbose.log]"
    while file logs remain unaffected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_name: str | None = None
        self._last_level: int | None = None
        self._last_message: str | None = None
        self._suppress_count: int = 0
        self._last_record: logging.LogRecord | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit_with_suppression(record)
        except Exception:
            self.handleError(record)

    def _emit_with_suppression(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.WARNING:
            self._flush_summary()
            self._emit_record(record)
            self._last_name = None
            self._last_level = None
            self._last_message = None
            self._suppress_count = 0
            self._last_record = None
            return

        name = record.name
        level = record.levelno
        try:
            msg_text = record.getMessage()
        except Exception:
            msg_text = str(record.msg)

        if "🔴" in msg_text or "Initializing Screensaver Engine" in msg_text:
            self._flush_summary()
            self._emit_record(record)
            self._last_name = name
            self._last_level = level
            self._suppress_count = 0
            self._last_record = record
            return

        if self._last_name is None:
            self._emit_record(record)
            self._last_name = name
            self._last_level = level
            self._last_message = msg_text
            self._suppress_count = 0
            self._last_record = record
            return

        if name == self._last_name and level == self._last_level and msg_text == self._last_message:
            self._suppress_count += 1
            if self._last_record is None:
                self._last_record = record
            return

        self._flush_summary()
        self._emit_record(record)
        self._last_name = name
        self._last_level = level
        self._last_message = msg_text
        self._suppress_count = 0
        self._last_record = record

    def _emit_record(self, record: logging.LogRecord) -> None:
        """Emit a single record to the underlying stream with Unicode-safe fallback.

        File handlers always receive the original record; this handler is only
        responsible for console output. When the console encoding cannot represent
        some characters (e.g. Windows cp1252 vs arrows/emoji), we degrade the
        console line using replacement characters instead of raising a logging
        error while keeping file logs intact.
        """

        try:
            msg = self.format(record)
            stream = self.stream
            if stream is None:
                return
            text = msg + self.terminator
            try:
                stream.write(text)
            except UnicodeEncodeError:
                try:
                    encoding = getattr(stream, "encoding", None) or "ascii"
                    safe_text = text.encode(encoding, errors="replace").decode(
                        encoding, errors="replace"
                    )
                    stream.write(safe_text)
                except Exception:
                    # As a last resort, drop the console write; file logs still
                    # contain the full Unicode record.
                    return
            try:
                stream.flush()
            except Exception:
                # Ignore flush errors for console output.
                pass
        except Exception:
            self.handleError(record)

    def _flush_summary(self) -> None:
        if self._suppress_count <= 0 or self._last_record is None:
            self._suppress_count = 0
            self._last_record = None
            self._last_message = None
            return

        last = self._last_record
        # Build a compact summary. For PERF lines that already contain
        # metrics like "avg_fps=78.5" we try to surface that token so
        # grouped telemetry is still somewhat informative in the console.
        avg_suffix = ""
        try:
            text = last.getMessage()
        except Exception:
            text = str(last.msg)
        if "[PERF]" in text and "avg_fps=" in text:
            try:
                idx = text.find("avg_fps=")
                if idx != -1:
                    # Take the avg_fps token up to the next comma or end.
                    tail = text[idx:].split(",", 1)[0].strip()
                    if tail:
                        avg_suffix = f", {tail}"
            except Exception:
                avg_suffix = ""

        msg = f"[{self._suppress_count} Suppressed: CHECK screensaver_verbose.log{avg_suffix}]"
        summary = logging.LogRecord(
            last.name,
            last.levelno,
            last.pathname,
            last.lineno,
            msg,
            args=None,
            exc_info=None,
        )
        summary.created = last.created
        summary.msecs = last.msecs
        summary.relativeCreated = last.relativeCreated
        summary.thread = last.thread
        summary.threadName = last.threadName
        summary.process = last.process
        summary.processName = last.processName
        super().emit(summary)

        self._suppress_count = 0
        self._last_record = None
        self._last_message = None

    def close(self) -> None:
        try:
            self._flush_summary()
        finally:
            super().close()


class NonPerfFilter(logging.Filter):
    """Filter that drops PERF-tagged records from the main log file.

    Detailed performance telemetry is already written to a dedicated
    ``screensaver_perf.log`` via PerfLogFilter, so the primary
    ``screensaver.log`` can omit those high-volume lines to keep logs
    smaller and more focused while preserving all metrics.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF]" not in msg


class NonSpotifyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[SPOTIFY_VIS]" not in msg and "[SPOTIFY_VOL]" not in msg


class VerboseLogFilter(logging.Filter):
    """Filter for verbose debug log - accepts DEBUG and INFO, excludes PERF.
    
    This log captures everything that would be suppressed in console output,
    providing a complete debug trail without the noise of PERF metrics.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Only DEBUG and INFO levels (not WARNING+)
        if record.levelno > logging.INFO:
            return False
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        # Exclude PERF records (they have their own log)
        return "[PERF]" not in msg


class PerfLogFilter(logging.Filter):
    """Filter that accepts only PERF metric records.

    Records are matched purely on the presence of "[PERF]" in the formatted
    message so existing call sites do not need to change.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF]" in msg


class WidgetPerfLogFilter(logging.Filter):
    """Filter that accepts only widget PERF instrumentation records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF_WIDGET]" in msg


class SpotifyVisLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "[SPOTIFY_VIS]" in msg:
            return True
        name = str(getattr(record, "name", ""))
        return (
            "spotify_visualizer" in name
            or "spotify_bars_gl_overlay" in name
            or name.endswith("widgets.beat_engine")
            or name.endswith("widgets.spotify_visualizer_widget")
        )


class SpotifyVolLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "[SPOTIFY_VOL]" in msg:
            return True
        name = str(getattr(record, "name", ""))
        return "spotify_volume" in name


def get_log_dir() -> Path:
    """Return the directory used for log files.
    
    setup_logging() should be called once at startup so that _BASE_DIR is
    updated for frozen builds and the returned path matches the location used
    by the active RotatingFileHandler.
    """
    if _ACTIVE_LOG_DIR is not None:
        return _ACTIVE_LOG_DIR
    if _FORCED_LOG_DIR is not None:
        return _FORCED_LOG_DIR
    return _BASE_DIR / "logs"


def _candidate_programdata_dir() -> Path | None:
    program_data = os.getenv("PROGRAMDATA")
    if not program_data:
        return None
    return Path(program_data) / "SRPSS" / "logs"


def _select_log_dir(
    forced_dir: Path | None,
    base_dir: Path,
) -> Path:
    """
    Determine a writable log directory, falling back to ProgramData or temp.
    """
    global _ACTIVE_LOG_DIR

    def _try_path(path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".srpss_log_probe"
            with probe.open("w", encoding="utf-8") as handle:
                handle.write("ok")
            probe.unlink(missing_ok=True)
            return path
        except Exception:
            return None

    candidates: list[Path | None] = []
    candidates.append(forced_dir)
    candidates.append(base_dir / "logs")
    candidates.append(_candidate_programdata_dir())
    candidates.append(Path(tempfile.gettempdir()) / "SRPSS" / "logs")

    for candidate in candidates:
        chosen = _try_path(candidate)
        if chosen is not None:
            _ACTIVE_LOG_DIR = chosen
            return chosen

    # As a last resort, use current working directory logs/ without validation.
    fallback = Path.cwd() / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    _ACTIVE_LOG_DIR = fallback
    return fallback


def setup_logging(debug: bool = False, verbose: bool = False) -> None:
    """
    Configure application logging with file rotation.
    
    Args:
        debug: If True, set log level to DEBUG and enable console output.
        verbose: When True, enables additional high-volume debug logs in
            selected modules (media widget polling, raw settings dumps,
            etc.). Verbose mode also implies debug-level logging.
    """
    global _VERBOSE, _PERF_METRICS_ENABLED, _BASE_DIR, _FORCED_LOG_DIR, _ACTIVE_LOG_DIR

    debug_enabled = debug or verbose
    # Create logs directory. In frozen builds (Nuitka/PyInstaller) we prefer
    # a logs/ directory next to the executable so users can easily find it.

    base_dir = _BASE_DIR
    forced_dir = _FORCED_LOG_DIR
    _ACTIVE_LOG_DIR = None
    try:
        import sys as _sys
        import builtins as _builtins

        frozen = bool(getattr(_sys, "frozen", False))  # type: ignore[attr-defined]
        # Nuitka sets a module-level __compiled__ flag rather than sys.frozen.
        nuitka_compiled = bool(getattr(_builtins, "__compiled__", False))

        exe_path = Path(getattr(_sys, "executable", "") or "")
        exe_path_valid: Path | None = exe_path if exe_path.exists() else None

        if frozen or nuitka_compiled:
            if exe_path_valid is not None:
                base_dir = exe_path_valid.parent
                try:
                    cfg_name = exe_path_valid.stem + ".perf.cfg"
                    cfg_path = exe_path_valid.parent / cfg_name
                    cfg_value = _read_bool_flag_file(cfg_path)
                    if cfg_value is not None:
                        _PERF_METRICS_ENABLED = cfg_value
                except Exception:
                    # On any failure, keep existing _PERF_METRICS_ENABLED value.
                    pass
                try:
                    if forced_dir is None:
                        log_cfg_name = exe_path_valid.stem + ".logdir.cfg"
                        log_cfg_path = exe_path_valid.parent / log_cfg_name
                        if log_cfg_path.exists():
                            raw_dir = log_cfg_path.read_text(encoding="utf-8").strip()
                            if raw_dir:
                                candidate = Path(raw_dir).expanduser()
                                if not candidate.is_absolute():
                                    candidate = candidate.resolve()
                                forced_dir = candidate
                except Exception:
                    forced_dir = forced_dir
        else:
            exe_path_valid = None
    except Exception:
        exe_path_valid = None

    logging_disabled = _determine_logging_disabled(exe_path_valid)
    global _LOGGING_DISABLED
    _LOGGING_DISABLED = logging_disabled

    # Persist the resolved base_dir so helpers like get_log_dir() can return
    # a consistent location for logs and profiling artefacts.
    _BASE_DIR = base_dir
    if forced_dir is not None:
        _FORCED_LOG_DIR = forced_dir
    else:
        _FORCED_LOG_DIR = None

    if logging_disabled and not debug_enabled:
        _ACTIVE_LOG_DIR = None
        root = logging.getLogger()
        for handler in list(root.handlers):
            try:
                handler.close()
            except Exception:
                pass
            root.removeHandler(handler)
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 10)
        return

    log_dir = _select_log_dir(forced_dir, base_dir)
    
    log_file = log_dir / "screensaver.log"
    
    # Root logger must be DEBUG in debug/verbose modes so the verbose handler
    # can capture full traces. Individual handlers decide what they write.
    root_level = logging.DEBUG if debug_enabled else logging.INFO
    main_level = logging.INFO
    
    # Create formatter with aligned columns for logger name and level
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation and deduplication (1MB cap with line-by-line
    # duplicate suppression keeps logs small and readable).
    main_handler = DeduplicatingRotatingFileHandler(
        log_file,
        maxBytes=1 * 1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setFormatter(formatter)
    main_handler.setLevel(main_level)
    
    # PERF-tagged records are redirected to the dedicated PERF log, so we
    # drop them from the main screensaver.log to reduce noise and keep
    # per-run logs smaller and easier to inspect.
    main_handler.addFilter(NonPerfFilter())
    main_handler.addFilter(NonSpotifyFilter())
    
    console_handler = SuppressingStreamHandler(sys.stdout)
    if debug_enabled and sys.stdout.isatty():
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
            datefmt='%H:%M:%S',
        )
        console_handler.setFormatter(colored_formatter)
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
            datefmt='%H:%M:%S',
        )
        console_handler.setFormatter(console_formatter)
    console_handler.setLevel(main_level)
    console_handler.addFilter(NonPerfFilter())
    console_handler.addFilter(NonSpotifyFilter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)
    root_logger.addHandler(main_handler)
    
    if debug_enabled:
        root_logger.addHandler(console_handler)

    # Dedicated PERF metrics log capturing any record whose message contains
    # the "[PERF]" tag. This keeps performance summaries readable even when
    # the main log is busy with other diagnostics.
    perf_log_file = log_dir / "screensaver_perf.log"
    perf_handler = DeduplicatingRotatingFileHandler(
        perf_log_file,
        maxBytes=1 * 1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8',
    )
    perf_handler.setFormatter(formatter)
    perf_handler.setLevel(logging.INFO)
    perf_handler.addFilter(PerfLogFilter())
    root_logger.addHandler(perf_handler)

    if _PERF_METRICS_ENABLED:
        widget_perf_log_file = log_dir / "perf_widgets.log"
        widget_perf_handler = DeduplicatingRotatingFileHandler(
            widget_perf_log_file,
            maxBytes=1 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        widget_perf_handler.setFormatter(formatter)
        widget_perf_handler.setLevel(logging.INFO)
        widget_perf_handler.addFilter(WidgetPerfLogFilter())
        root_logger.addHandler(widget_perf_handler)

    spotify_vis_log_file = log_dir / "screensaver_spotify_vis.log"
    spotify_vis_handler = DeduplicatingRotatingFileHandler(
        spotify_vis_log_file,
        maxBytes=1 * 1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8',
    )
    spotify_vis_handler.setFormatter(formatter)
    spotify_vis_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    spotify_vis_handler.addFilter(SpotifyVisLogFilter())
    root_logger.addHandler(spotify_vis_handler)

    spotify_vol_log_file = log_dir / "screensaver_spotify_vol.log"
    spotify_vol_handler = DeduplicatingRotatingFileHandler(
        spotify_vol_log_file,
        maxBytes=1 * 1024 * 1024,  # 1MB
        backupCount=5,
        encoding='utf-8',
    )
    spotify_vol_handler.setFormatter(formatter)
    spotify_vol_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    spotify_vol_handler.addFilter(SpotifyVolLogFilter())
    root_logger.addHandler(spotify_vol_handler)
    
    # Verbose debug log - captures ALL DEBUG/INFO with deduplication.
    # This is the "messy" log for deep debugging when console suppression
    # hides important details. Now with 1MB limit and deduplication.
    # Log types summary:
    #   1. screensaver.log - Main log (INFO+, no PERF, no Spotify)
    #   2. screensaver_verbose.log - Full DEBUG/INFO with deduplication
    #   3. screensaver_perf.log - PERF metrics only
    #   4. screensaver_spotify_vis.log - Spotify visualizer logs
    #   5. screensaver_spotify_vol.log - Spotify volume logs
    if debug_enabled:
        verbose_log_file = log_dir / "screensaver_verbose.log"
        verbose_handler = DeduplicatingRotatingFileHandler(
            verbose_log_file,
            maxBytes=1 * 1024 * 1024,  # 1MB with deduplication
            backupCount=3,
            encoding='utf-8',
        )
        verbose_handler.setFormatter(formatter)
        verbose_handler.setLevel(logging.DEBUG)
        verbose_handler.addFilter(VerboseLogFilter())
        root_logger.addHandler(verbose_handler)

    # Tame particularly noisy third-party libraries so their DEBUG-level
    # chatter (HTTP connection pools, asyncio internals, etc.) only shows
    # up when explicit verbose logging is requested.
    noisy_level = logging.DEBUG if verbose else logging.INFO
    for name in ("urllib3", "urllib3.connectionpool", "asyncio"):
        logging.getLogger(name).setLevel(noisy_level)
    
    # NOISE REDUCTION: Silence high-frequency internal modules at DEBUG level
    # These modules produce excessive logs during normal operation that make
    # debugging other issues nearly impossible. They only log at INFO+ unless
    # --verbose is explicitly requested.
    NOISY_INTERNAL_MODULES = (
        # Animation system - logs every frame tick
        "core.animation.animator",
        "core.animation",
        # Rendering system - logs every paint/update
        "rendering.display",
        "rendering.display_widget", 
        "rendering.gl_format",
        "rendering.input_handler",
        "rendering.widget_manager",
        # Transitions - logs every frame during transitions
        "transitions.base_transition",
        "transitions.gl_crossfade_transition",
        "transitions.gl_slide_transition",
        "transitions.gl_wipe_transition",
        "transitions.gl_diffuse_transition",
        "transitions.gl_xfade",
        "transitions.gl_slide",
        "transitions.gl_wipe",
        "transitions.gl_diffuse",
        "transitions.gl_blockflip",
        "transitions.gl_blinds",
        "transitions.gl_compositor",
        "transitions.gl_compositor_crumble_transition",
        # Settings manager - logs on every widget interaction
        "SettingsManager",
        # Image queue - logs every image selection
        "engine.image_queue",
        # Widget spam
        "widgets.reddit_widget",
        "widgets.media_widget",
        "widgets.clock_widget",
        "widgets.weather_widget",
        # Windows diagnostics - very noisy during cleanup
        "win_diag",
        # GUI settings tabs - noisy during settings dialog
        "gui.tabs",
        "gui.settings_dialog",
        "gui.main_window",
        # Resource manager - logs on every registration/cleanup
        "resources.manager",
        "core.resources.manager",
        # Multi-monitor coordinator - logs halo owner on every check
        "rendering.multi_monitor_coordinator",
        # RSS source - logs every feed parse
        "sources.rss_source",
        # Gmail modules - logs on every fetch/auth
        "core.auth.gmail_oauth",
        "core.gmail.gmail_client",
        "widgets.gmail_widget",
    )
    internal_noisy_level = logging.DEBUG if verbose else logging.INFO
    for name in NOISY_INTERNAL_MODULES:
        logging.getLogger(name).setLevel(internal_noisy_level)
    
    # Log startup
    _VERBOSE = bool(verbose)

    root_logger.info("=" * 60)
    root_logger.info(
        "Screensaver logging initialized (debug=%s, verbose=%s)",
        debug_enabled,
        _VERBOSE,
    )
    root_logger.info("=" * 60)


_SHORT_NAME_OVERRIDES = {
    "core.resources.manager": "resources.manager",
    "engine.screensaver_engine": "engine.screensaver",
    "engine.display_manager": "engine.display",
    "rendering.display_widget": "rendering.display",
    "rendering.gl_format": "rendering.gl_format",
    "transitions.gl_crossfade_transition": "transitions.gl_xfade",
    "transitions.gl_slide_transition": "transitions.gl_slide",
    "transitions.gl_wipe_transition": "transitions.gl_wipe",
    "transitions.gl_diffuse_transition": "transitions.gl_diffuse",
    "transitions.gl_block_puzzle_flip_transition": "transitions.gl_blockflip",
    "transitions.gl_blinds": "transitions.gl_blinds",
}


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with optional short-name overrides for noisy modules."""
    actual = _SHORT_NAME_OVERRIDES.get(name, name)
    return logging.getLogger(actual)


class ThrottledLogger:
    """Rate-limited logger for high-frequency log points.
    
    Wraps a standard logger and limits how often messages are emitted.
    Useful for hot paths like animation frames, visualizer ticks, etc.
    
    Usage:
        throttled = ThrottledLogger(logger, max_per_second=1.0)
        # In hot loop:
        throttled.debug("Frame %d", frame_num)  # Only logs ~1/second
    
    Features:
        - Per-message rate limiting (based on message template)
        - Configurable rate (messages per second)
        - Optional sampling mode (log 1 in N messages)
        - Thread-safe
        - Tracks suppressed count for diagnostics
    """
    
    def __init__(
        self,
        logger: logging.Logger,
        max_per_second: float = 1.0,
        sample_rate: int = 0,
    ):
        """Initialize throttled logger.
        
        Args:
            logger: Underlying logger to wrap
            max_per_second: Maximum messages per second (0 = unlimited)
            sample_rate: If > 0, log 1 in N messages instead of rate limiting
        """
        self._logger = logger
        self._max_per_second = max(0.0, float(max_per_second))
        self._sample_rate = max(0, int(sample_rate))
        self._lock = threading.Lock()
        # Track last emit time per message template
        self._last_emit: dict[str, float] = {}
        # Track call count for sampling mode
        self._call_count: dict[str, int] = {}
        # Track suppressed messages for diagnostics
        self._suppressed_count: int = 0
        self._emitted_count: int = 0
    
    def _should_emit(self, msg: str) -> bool:
        """Check if message should be emitted based on throttling rules."""
        import time
        
        with self._lock:
            # Sampling mode: log 1 in N
            if self._sample_rate > 0:
                count = self._call_count.get(msg, 0) + 1
                self._call_count[msg] = count
                if count % self._sample_rate == 1:
                    self._emitted_count += 1
                    return True
                self._suppressed_count += 1
                return False
            
            # Rate limiting mode
            if self._max_per_second <= 0:
                self._emitted_count += 1
                return True  # Unlimited
            
            now = time.monotonic()
            min_interval = 1.0 / self._max_per_second
            last = self._last_emit.get(msg, 0.0)
            
            if now - last >= min_interval:
                self._last_emit[msg] = now
                self._emitted_count += 1
                return True
            
            self._suppressed_count += 1
            return False
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message with throttling."""
        if self._should_emit(msg):
            self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message with throttling."""
        if self._should_emit(msg):
            self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message (never throttled)."""
        self._emitted_count += 1
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message (never throttled)."""
        self._emitted_count += 1
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message (never throttled)."""
        self._emitted_count += 1
        self._logger.critical(msg, *args, **kwargs)
    
    @property
    def suppressed_count(self) -> int:
        """Get count of suppressed messages."""
        with self._lock:
            return self._suppressed_count
    
    @property
    def emitted_count(self) -> int:
        """Get count of emitted messages."""
        with self._lock:
            return self._emitted_count
    
    def reset_counts(self) -> None:
        """Reset suppressed and emitted counts."""
        with self._lock:
            self._suppressed_count = 0
            self._emitted_count = 0
            self._call_count.clear()


def get_throttled_logger(
    name: str,
    max_per_second: float = 1.0,
    sample_rate: int = 0,
) -> ThrottledLogger:
    """Get a throttled logger instance.
    
    Args:
        name: Logger name (same as get_logger)
        max_per_second: Maximum messages per second per unique message
        sample_rate: If > 0, log 1 in N messages instead of rate limiting
    
    Returns:
        ThrottledLogger wrapping the named logger
    """
    return ThrottledLogger(get_logger(name), max_per_second, sample_rate)


def is_verbose_logging() -> bool:
    """Return True when verbose debug logging is enabled globally."""

    return _VERBOSE


def is_perf_metrics_enabled() -> bool:
    """Return True when PERF metrics/telemetry are enabled globally."""

    return _PERF_METRICS_ENABLED

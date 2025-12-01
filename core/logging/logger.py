"""
Centralized logging configuration for screensaver application.

Uses rotating file handler with logs stored in logs/ directory.
Includes colored console output for debug mode.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_VERBOSE: bool = False
_PERF_METRICS_ENABLED: bool = True
# Base directory for logs and related artefacts. This is initialised to the
# project root by default and updated by setup_logging() for frozen builds so
# helpers like get_log_dir() always point at the effective runtime location.
_BASE_DIR: Path = Path(__file__).parent.parent.parent

_env_perf = os.getenv("SRPSS_PERF_METRICS")
if _env_perf is not None:
    try:
        if str(_env_perf).strip().lower() in ("0", "false", "off", "no"):
            _PERF_METRICS_ENABLED = False
        elif str(_env_perf).strip().lower() in ("1", "true", "on", "yes"):
            _PERF_METRICS_ENABLED = True
    except Exception:
        _PERF_METRICS_ENABLED = True


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


class SuppressingStreamHandler(logging.StreamHandler):
    """Stream handler that suppresses consecutive duplicate sources.

    Repeated DEBUG/INFO lines from the same logger/level are collapsed into a
    single summary line like "[N Suppressed: CHECK LOG]" while file logs
    remain unaffected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_name: str | None = None
        self._last_level: int | None = None
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
            self._suppress_count = 0
            self._last_record = record
            return

        if name == self._last_name and level == self._last_level:
            self._suppress_count += 1
            if self._last_record is None:
                self._last_record = record
            return

        self._flush_summary()
        self._emit_record(record)
        self._last_name = name
        self._last_level = level
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

        msg = f"[{self._suppress_count} Suppressed: CHECK LOG{avg_suffix}]"
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

    def close(self) -> None:
        try:
            self._flush_summary()
        finally:
            super().close()


def get_log_dir() -> Path:
    """Return the directory used for log files.

    setup_logging() should be called once at startup so that _BASE_DIR is
    updated for frozen builds and the returned path matches the location used
    by the active RotatingFileHandler.
    """

    return _BASE_DIR / "logs"


def setup_logging(debug: bool = False, verbose: bool = False) -> None:
    """
    Configure application logging with file rotation.
    
    Args:
        debug: If True, set log level to DEBUG and enable console output.
        verbose: When True, enables additional high-volume debug logs in
            selected modules (media widget polling, raw settings dumps,
            etc.). Verbose mode also implies debug-level logging.
    """
    global _VERBOSE, _PERF_METRICS_ENABLED

    debug_enabled = debug or verbose
    # Create logs directory. In frozen builds (Nuitka/PyInstaller) we prefer
    # a logs/ directory next to the executable so users can easily find it.
    global _VERBOSE, _PERF_METRICS_ENABLED, _BASE_DIR

    base_dir = _BASE_DIR
    try:
        import sys as _sys
        import builtins as _builtins

        frozen = bool(getattr(_sys, "frozen", False))  # type: ignore[attr-defined]
        # Nuitka sets a module-level __compiled__ flag rather than sys.frozen.
        nuitka_compiled = bool(getattr(_builtins, "__compiled__", False))

        if frozen or nuitka_compiled:
            exe_path = Path(getattr(_sys, "executable", "") or "")
            if exe_path.exists():
                base_dir = exe_path.parent
                try:
                    cfg_name = exe_path.stem + ".perf.cfg"
                    cfg_path = exe_path.parent / cfg_name
                    if cfg_path.exists():
                        raw = cfg_path.read_text(encoding="utf-8").strip().lower()
                        if raw in ("0", "false", "off", "no"):
                            _PERF_METRICS_ENABLED = False
                        elif raw in ("1", "true", "on", "yes"):
                            _PERF_METRICS_ENABLED = True
                except Exception:
                    # On any failure, keep existing _PERF_METRICS_ENABLED value.
                    pass
    except Exception:
        pass

    # Persist the resolved base_dir so helpers like get_log_dir() can return
    # a consistent location for logs and profiling artefacts.
    _BASE_DIR = base_dir

    log_dir = get_log_dir()
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "screensaver.log"
    
    # Configure root logger
    level = logging.DEBUG if debug_enabled else logging.INFO
    
    # Create formatter with aligned columns for logger name and level
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (1MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
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
    console_handler.setLevel(level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    
    if debug_enabled:
        root_logger.addHandler(console_handler)

    # Tame particularly noisy third-party libraries so their DEBUG-level
    # chatter (HTTP connection pools, asyncio internals, etc.) only shows
    # up when explicit verbose logging is requested.
    noisy_level = logging.DEBUG if verbose else logging.INFO
    for name in ("urllib3", "urllib3.connectionpool", "asyncio"):
        logging.getLogger(name).setLevel(noisy_level)
    
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


def is_verbose_logging() -> bool:
    """Return True when verbose debug logging is enabled globally."""

    return _VERBOSE


def is_perf_metrics_enabled() -> bool:
    """Return True when PERF metrics/telemetry are enabled globally."""

    return _PERF_METRICS_ENABLED

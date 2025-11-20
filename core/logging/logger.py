"""
Centralized logging configuration for screensaver application.

Uses rotating file handler with logs stored in logs/ directory.
Includes colored console output for debug mode.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_VERBOSE: bool = False


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
    FALLBACK_COLOR = '\033[38;5;208m'   # Orange for fallback warnings
    PREWARM_COLOR = '\033[38;5;135m'    # Purple for prewarm/flicker diagnostics
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
        if record.levelname in self.COLORS:
            if is_fallback and record.levelname == 'WARNING':
                # Use orange for fallback warnings instead of regular yellow
                color = self.FALLBACK_COLOR
            elif is_prewarm:
                # Use dedicated purple for prewarm/flicker diagnostics
                color = self.PREWARM_COLOR
            else:
                color = self.COLORS[record.levelname]
            
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


def setup_logging(debug: bool = False, verbose: bool = False) -> None:
    """
    Configure application logging with file rotation.
    
    Args:
        debug: If True, set log level to DEBUG and enable console output.
        verbose: When True, enables additional high-volume debug logs in
            selected modules (media widget polling, raw settings dumps,
            etc.). Verbose mode also implies debug-level logging.
    """
    global _VERBOSE

    debug_enabled = debug or verbose
    # Create logs directory
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "screensaver.log"
    
    # Configure root logger
    level = logging.DEBUG if debug_enabled else logging.INFO
    
    # Create formatter with aligned columns for logger name and level
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Console handler (for development) - with colors in debug mode
    console_handler = logging.StreamHandler(sys.stdout)
    if debug_enabled and sys.stdout.isatty():
        # Use colored formatter for terminal output
        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(colored_formatter)
    else:
        console_handler.setFormatter(formatter)
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

"""Thin pytest runner with logging.

Usage (PowerShell, from project root):

    python pytest.py
    python pytest.py tests/test_widgets_media_integration.py -vv

This exists because terminal output is often truncated; use the
log files under `logs/` to inspect full results.
"""

from __future__ import annotations

import sys
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import importlib


def _setup_pytest_logging() -> logging.Logger:
    root = Path(__file__).resolve().parent
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "pytest.log"

    logger = logging.getLogger("pytest_runner")
    logger.setLevel(logging.DEBUG)

    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    logger = _setup_pytest_logging()
    logger.info("pytest.py starting with args: %r", argv)

    # Import the real pytest library, not this script. Because this file is
    # named pytest.py, a normal `import pytest` would resolve back to this
    # module and recurse. To avoid that, temporarily remove the project root
    # from sys.path while importing the package.
    root = Path(__file__).resolve().parent
    orig_sys_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if Path(p).resolve() != root]
        real_pytest = importlib.import_module("pytest")
    finally:
        sys.path = orig_sys_path

    try:
        # Delegate to the real pytest library. This returns an exit code int.
        code = real_pytest.main(argv)
        logger.info("pytest finished with exit code %s", code)
        return int(code)
    except SystemExit as exc:
        code = int(getattr(exc, "code", 1) or 1)
        logger.info("pytest SystemExit with code %s", code)
        return code
    except Exception:
        logger.exception("pytest run failed with unexpected error")
        return 1


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())

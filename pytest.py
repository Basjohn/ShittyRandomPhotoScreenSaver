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
import contextlib
import io
import time


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


def _open_pytest_output_stream() -> io.TextIOBase:
    root = Path(__file__).resolve().parent
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)

    out_file = log_dir / "pytest_output.log"
    handler = RotatingFileHandler(
        out_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    stream = io.StringIO()

    def _flush_to_handler() -> None:
        try:
            value = stream.getvalue()
        except Exception:
            return
        if not value:
            return
        try:
            record = logging.LogRecord(
                name="pytest_output",
                level=logging.INFO,
                pathname=str(out_file),
                lineno=0,
                msg=value,
                args=(),
                exc_info=None,
            )
            handler.emit(record)
        finally:
            try:
                stream.seek(0)
                stream.truncate(0)
            except Exception:
                pass

    class _FlushOnWrite(io.TextIOBase):
        def write(self, s: str) -> int:  # type: ignore[override]
            n = stream.write(s)
            if "\n" in s:
                _flush_to_handler()
            return n

        def flush(self) -> None:  # type: ignore[override]
            _flush_to_handler()

    wrapper = _FlushOnWrite()

    header = f"\n===== pytest run {time.strftime('%Y-%m-%d %H:%M:%S')} args={sys.argv[1:]} =====\n"
    try:
        wrapper.write(header)
        wrapper.flush()
    except Exception:
        pass
    return wrapper


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

    out_stream = _open_pytest_output_stream()
    try:
        # Delegate to the real pytest library. This returns an exit code int.
        with contextlib.redirect_stdout(out_stream), contextlib.redirect_stderr(out_stream):
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
    finally:
        try:
            out_stream.flush()
        except Exception:
            pass


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())

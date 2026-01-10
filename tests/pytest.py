"""Thin pytest runner with logging.

Usage (PowerShell, from project root):

    python tests/pytest.py
    python tests/pytest.py tests/test_widgets_media_integration.py -vv

This exists because terminal output is often truncated; use the
log files under `logs/` to inspect full results.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import time


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _tests_dir() -> Path:
    return Path(__file__).resolve().parent


def _logs_dir() -> Path:
    logs_dir = _root_dir() / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def _setup_pytest_logging() -> logging.Logger:
    log_dir = _logs_dir()
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
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def _open_pytest_output_stream() -> io.TextIOBase:
    log_dir = _logs_dir()
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


def _with_default_config(args: list[str]) -> list[str]:
    if any(arg == "-c" or arg.startswith("-c") for arg in args):
        return args
    config_path = Path(__file__).with_name("pytest.ini")
    return ["-c", str(config_path)] + args


def _import_real_pytest():
    tests_dir = _tests_dir()
    orig_sys_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if Path(p).resolve() != tests_dir]
        return importlib.import_module("pytest")
    finally:
        sys.path = orig_sys_path


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _with_default_config(list(argv))

    logger = _setup_pytest_logging()
    logger.info("tests/pytest.py starting with args: %r", argv)

    real_pytest = _import_real_pytest()

    out_stream = _open_pytest_output_stream()
    try:
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

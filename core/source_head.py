"""One-line diagnostic that names the local Git HEAD a script/dev run came from.

Purely diagnostic. It runs at most one local ``git rev-parse --verify HEAD`` per
process, and only when the process is a normal Python/script run (never a
compiled/frozen build) with debug logging enabled. It never touches the network,
never writes the repository, and can never delay or derail startup: any failure
(no Git, no ``.git``, timeout, unresolved HEAD) simply emits ``unavailable`` and
continues.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from core.build_profile import is_compiled_runtime
from core.logging.logger import get_logger

logger = get_logger(__name__)

# Deterministic repository root from this source file (core/ -> repo root), so
# the lookup never depends on the launch working directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent

# A local metadata read is fast; this cap only guards against a wedged Git.
_GIT_TIMEOUT_S = 1.0

# One lookup per process. Set before the subprocess runs so a failure is never
# retried.
_LOOKUP_DONE = False


def _debug_logging_active() -> bool:
    """True when debug-level logging is enabled (the canonical debug signal).

    The logging bootstrap sets the root logger to DEBUG for --debug/--verbose and
    the diagnostic build, so this reflects "debug/runtime mode" without inventing
    a second flag.
    """

    return logging.getLogger().isEnabledFor(logging.DEBUG)


def _read_local_head() -> str | None:
    """Return the 40-char HEAD SHA from local Git metadata, or None on any issue."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=_GIT_TIMEOUT_S,
        )
    except Exception:
        # Git missing, .git absent, timeout, or anything else: no HEAD.
        return None

    if getattr(result, "returncode", 1) != 0:
        return None
    sha = (result.stdout or b"").decode("ascii", "ignore").strip()
    if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
        return sha
    return None


def log_source_head() -> None:
    """Emit one ``[SOURCE_HEAD] <sha>`` line for script/dev debug runs.

    No-op in compiled builds and when debug logging is off. Runs the local Git
    lookup at most once per process and never lets an exception escape.
    """

    global _LOOKUP_DONE
    try:
        if _LOOKUP_DONE:
            return
        # Compiled/frozen builds must never touch Git.
        if is_compiled_runtime():
            return
        if not _debug_logging_active():
            return

        # Commit to the single attempt before spawning: no retry on failure.
        _LOOKUP_DONE = True
        sha = _read_local_head()
        if sha:
            logger.info("[SOURCE_HEAD] %s", sha)
        else:
            logger.info("[SOURCE_HEAD] unavailable")
    except Exception:
        # A harmless diagnostic must never surface as a startup failure.
        pass

"""A real QCoreApplication.exit() stops the session instead of poisoning later tests.

Outside QCoreApplication.exec(), exit() leaves Qt's per-thread quit flag set, so
every later nested event loop returns at once. The conftest tripwire must end
the session right after the test that reached it, naming that test, with
return code 3.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_real_qt_exit_stops_the_session_and_names_the_test():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
         "tests/_qt_exit_tripwire_probe.py"],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 3, output
    assert "_qt_exit_tripwire_probe.py::test_reaches_the_real_qt_exit" in output
    assert "QCoreApplication.exit(1)" in output
    # The inert-loop test never ran, so nothing failed for the wrong reason.
    assert "1 passed" in output and "failed" not in output, output


def test_monkeypatched_exit_does_not_trip(monkeypatch):
    from PySide6.QtCore import QCoreApplication

    calls = []
    monkeypatch.setattr(QCoreApplication, "exit", staticmethod(lambda code=0: calls.append(code)))
    QCoreApplication.exit(1)
    assert calls == [1]

"""Utility to regenerate Qt resource bindings for shared UI assets.

Runs pyside6-rcc (or the PySide6.rcc module fallback) against ui/resources/assets.qrc
and pops a confirmation dialog when the operation succeeds.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parents[1]
QRC_PATH = ROOT / "ui" / "resources" / "assets.qrc"
OUTPUT_PATH = ROOT / "ui" / "resources" / "assets_rc.py"


def _run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def regenerate_icons() -> None:
    if not QRC_PATH.exists():
        raise FileNotFoundError(f"Missing QRC file: {QRC_PATH}")

    commands = [
        ["pyside6-rcc", str(QRC_PATH), "-o", str(OUTPUT_PATH)],
        [sys.executable, "-m", "PySide6.scripts.rcc", str(QRC_PATH), "-o", str(OUTPUT_PATH)],
    ]

    last_error: Exception | None = None
    for command in commands:
        try:
            _run_command(command)
            return
        except Exception as exc:  # pragma: no cover - CLI tool fallback
            last_error = exc
    if last_error:
        raise last_error


def _show_auto_close_message(*, icon: QMessageBox.Icon, title: str, text: str, timeout_ms: int = 5000) -> None:
    dialog = QMessageBox()
    dialog.setIcon(icon)
    dialog.setWindowTitle(title)
    dialog.setText(text)
    dialog.setStandardButtons(QMessageBox.Ok)
    QTimer.singleShot(timeout_ms, dialog.accept)
    dialog.exec()


def main() -> None:
    _app = QApplication.instance() or QApplication(sys.argv)
    try:
        regenerate_icons()
    except Exception as exc:  # pragma: no cover - UI notification path
        _show_auto_close_message(
            icon=QMessageBox.Critical,
            title="QRC Regeneration Failed",
            text=f"assets_rc.py could not be regenerated.\n\nError: {exc}",
        )
        raise
    else:
        _show_auto_close_message(
            icon=QMessageBox.Information,
            title="QRC Regeneration",
            text="Success! assets_rc.py updated.",
        )


if __name__ == "__main__":
    main()

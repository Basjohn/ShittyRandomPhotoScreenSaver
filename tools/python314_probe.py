"""Fail-fast Windows runtime/ABI probe for the canonical Python 3.14 cutover.

This is a dependency smoke, NOT proof of bundled exe/Qt/GL or visual parity.
"""
from __future__ import annotations

from importlib import import_module, metadata
from pathlib import Path
import platform
import struct
import sys

# The versions the probe checks are the repository's own pins (one source: a bump edits requirements.txt only).
_PINNED = ("PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6", "numpy", "Nuitka", "PyAudioWPatch", "psutil")


def pinned_versions(requirements: Path = Path(__file__).resolve().parents[1] / "requirements.txt") -> dict[str, str]:
    """The exact ``==`` pins of the probed distributions in requirements.txt (missing or unpinned raises)."""
    pins: dict[str, str] = {}
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if "==" in line:
            name, version = (part.strip() for part in line.split(";", 1)[0].split("==", 1))
            pins[name] = version
    missing = [name for name in _PINNED if name not in pins]
    if missing:
        raise RuntimeError(f"requirements.txt does not pin {missing} exactly")
    return {name: pins[name] for name in _PINNED}


def main() -> int:
    assert sys.version_info[:2] == (3, 14), sys.version
    assert struct.calcsize("P") == 8, "32-bit interpreter is not supported"
    assert sys._is_gil_enabled(), "Free-threaded Python is not yet supported"
    assert platform.system() == "Windows", "Run this probe on Windows"
    expected = pinned_versions()
    for name, version in expected.items():
        assert metadata.version(name) == version, (name, metadata.version(name), version)
    modules = (
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.QtMultimedia", "shiboken6",
        "numpy", "PIL", "OpenGL", "pyaudiowpatch", "sounddevice",
        "winrt.windows.media.control", "winrt.windows.storage.streams",
        "pycaw", "comtypes", "win32api", "pythoncom", "psutil",
        "PyInstaller",
    )
    for module in modules:
        import_module(module)
    from PySide6 import QtCore
    import numpy as np

    assert QtCore.qVersion() == expected["PySide6"], (QtCore.qVersion(), expected["PySide6"])
    # Verify little-endian tightly packed float32 data used at native GL boundaries.
    values = np.ascontiguousarray([0.0, 0.5, -1.0, 4.0], dtype="<f4")
    assert values.flags.c_contiguous and values.dtype.itemsize == 4
    assert values.tobytes() == struct.pack("<4f", 0.0, 0.5, -1.0, 4.0)
    print("SRPSS_PYTHON314_NATIVE_PROBE_OK", sys.executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

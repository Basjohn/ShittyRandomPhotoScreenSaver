"""Fail-fast Windows runtime/ABI probe for the canonical Python 3.14 cutover.

This is a dependency smoke, NOT proof of bundled exe/Qt/GL or visual parity.
"""
from __future__ import annotations

from importlib import import_module, metadata
import platform
import struct
import sys


def main() -> int:
    assert sys.version_info[:2] == (3, 14), sys.version
    assert struct.calcsize("P") == 8, "32-bit interpreter is not supported"
    assert sys._is_gil_enabled(), "Free-threaded Python is not yet supported"
    assert platform.system() == "Windows", "Run this probe on Windows"
    expected = {
        "PySide6": "6.11.2",
        "PySide6_Addons": "6.11.2",
        "PySide6_Essentials": "6.11.2",
        "shiboken6": "6.11.2",
        "numpy": "2.4.5",
        "Nuitka": "4.2",
        "PyAudioWPatch": "0.2.12.9",
        "psutil": "7.2.2",
    }
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

    assert QtCore.qVersion() == "6.11.2", QtCore.qVersion()
    # Verify little-endian tightly packed float32 data used at native GL boundaries.
    values = np.ascontiguousarray([0.0, 0.5, -1.0, 4.0], dtype="<f4")
    assert values.flags.c_contiguous and values.dtype.itemsize == 4
    assert values.tobytes() == struct.pack("<4f", 0.0, 0.5, -1.0, 4.0)
    print("SRPSS_PYTHON314_NATIVE_PROBE_OK", sys.executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

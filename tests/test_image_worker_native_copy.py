"""The worker handoff retains one owned copy and releases the GIL during it."""
import ctypes

import pytest
from PySide6.QtGui import QImage

from engine.image_pipeline import _copy_shared_rgba_to_owned_qimage


def test_packed_rgba_uses_gil_releasing_native_copy_and_survives_source_retirement(monkeypatch):
    original = ctypes.memmove
    # A Python-API ctypes prototype explicitly holds the GIL. The native
    # memmove prototype must retain ctypes' ordinary foreign-call contract.
    assert not original._flags_ & ctypes._FUNCFLAG_PYTHONAPI
    calls = []

    def observed_copy(destination, source, size):
        calls.append(size)
        return original(destination, source, size)

    monkeypatch.setattr(ctypes, "memmove", observed_copy)
    source = bytearray(range(24))
    view = memoryview(source)
    result = _copy_shared_rgba_to_owned_qimage(view, 3, 2)
    view.release()
    source[:] = bytes(24)
    assert calls == [24]
    assert result.format() == QImage.Format.Format_RGBA8888
    assert result.constBits().tobytes() == bytes(range(24))


@pytest.mark.parametrize("buffer,width,height", [
    (memoryview(bytearray(4)), 2, 1),
    (memoryview(bytearray(4)), 0, 1),
    (memoryview(bytes(4)), 1, 1),
    (memoryview(bytearray(8))[::2], 1, 1),
])
def test_invalid_shared_buffer_fails_before_native_copy(buffer, width, height, monkeypatch):
    def forbidden(*_args):
        raise AssertionError("Invalid source reached native copy")
    monkeypatch.setattr(ctypes, "memmove", forbidden)
    with pytest.raises(ValueError):
        _copy_shared_rgba_to_owned_qimage(buffer, width, height)

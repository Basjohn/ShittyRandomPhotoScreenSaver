"""Verified identity helpers for the current Qt OpenGL share group."""

from __future__ import annotations

from typing import Hashable


def qt_cpp_pointer(obj: object) -> int:
    """Return a stable native Qt pointer when Shiboken is available."""

    try:
        import shiboken6

        pointer = shiboken6.getCppPointer(obj)
        if pointer:
            return int(pointer[0])
    except Exception:
        pass
    return id(obj)


def qt_object_is_valid(obj: object | None) -> bool:
    """Return whether a retained Qt wrapper still owns a live C++ object."""

    if obj is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(obj))
    except Exception:
        return True


def current_share_group_identity() -> tuple[Hashable, object | None]:
    """Return the current context's native share-group key and Qt wrapper."""

    try:
        from PySide6.QtGui import QOpenGLContext

        context = QOpenGLContext.currentContext()
        if context is None:
            return ("no_context", 0), None
        share_group = context.shareGroup()
        if share_group is not None:
            return ("share_group", qt_cpp_pointer(share_group)), share_group
        return ("context", qt_cpp_pointer(context)), context
    except Exception:
        return ("no_context", 0), None

"""Read which QObjects inside a window Python still owns (R-204's ownership test, shared).

A widget added to a layout that has no parent widget yet stays owned by Python while Qt also deletes it
with its window; PySide's exit-time cleanup then deletes it a second time (an access violation at process
exit). Ownership is read from the live wrappers through ``shiboken6.getAllValidWrappers()`` before anything
else touches the tree: ``QObject.findChildren()`` itself hands every wrapper it returns to Qt, which would
hide the defect.
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QObject


def python_owned_descendants(root: QObject) -> list[str]:
    """Name every QObject inside ``root`` (excluding ``root`` itself) that Python still owns."""

    def _inside(obj: QObject) -> bool:
        parent = obj.parent()
        while parent is not None:
            if parent is root:
                return True
            parent = parent.parent()
        return False

    wrappers = [
        (obj, shiboken6.ownedByPython(obj))
        for obj in shiboken6.getAllValidWrappers()
        if isinstance(obj, QObject)
    ]
    inside = [(obj, owned) for obj, owned in wrappers if _inside(obj)]
    assert inside, "the window has no wrapped children to check"
    return [f"{type(obj).__name__}({obj.objectName()!r})" for obj, owned in inside if owned]

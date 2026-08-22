"""Small terminal-retirement fence shared by plain visualizer mode state."""

from __future__ import annotations

import threading
from collections.abc import Callable
from functools import wraps
from typing import Any


class RetirableFrameRuntime:
    """Serialize authored steps with one permanent mode-retirement barrier."""

    def __init__(self) -> None:
        self._retirement_lock = threading.RLock()
        self._retired = False

    def retire(self) -> None:
        with self._retirement_lock:
            self.reset()
            self._retired = True

    def reset(self) -> None:
        raise NotImplementedError


def retirement_fenced(method: Callable[..., Any]) -> Callable[..., Any]:
    """Prevent a detached mode-state reference from authoring after retirement."""

    @wraps(method)
    def guarded(self: RetirableFrameRuntime, *args: Any, **kwargs: Any) -> Any:
        with self._retirement_lock:
            if self._retired:
                return None
            return method(self, *args, **kwargs)

    return guarded


__all__ = ["RetirableFrameRuntime", "retirement_fenced"]

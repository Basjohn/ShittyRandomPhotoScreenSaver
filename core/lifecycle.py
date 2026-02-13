"""Lifecycle protocol for widgets and managers.

Defines the standard start/stop/cleanup interface that widgets and
managers are expected to implement. Used for type-checking only —
no runtime inheritance required (structural subtyping via Protocol).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Lifecycle(Protocol):
    """Protocol for objects with start/stop/cleanup lifecycle."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def cleanup(self) -> None: ...


@runtime_checkable
class Cleanable(Protocol):
    """Protocol for objects that only need cleanup (no start/stop)."""

    def cleanup(self) -> None: ...

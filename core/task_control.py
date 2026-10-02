"""Lightweight task-control exceptions shared by runtime workers.

These exceptions describe scheduler/lifecycle outcomes, not product failures.
They intentionally live outside ``core.threading.manager`` so pure runtime
coordinators can signal expected cancellation without importing Qt.
"""
from __future__ import annotations


class ExpectedTaskCancellation(RuntimeError):
    """The task became obsolete because its owner/source was intentionally retired."""


__all__ = ["ExpectedTaskCancellation"]

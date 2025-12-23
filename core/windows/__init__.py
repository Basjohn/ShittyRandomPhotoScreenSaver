"""
Windows-specific helpers for SRPSS.

This package exposes the session-aware Reddit URL launcher plus the helper
bridge/installer utilities that coordinate the ProgramData queue.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "url_launcher",
    "reddit_helper_bridge",
    "reddit_helper_installer",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

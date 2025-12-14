"""Centralised version and naming information for SRPSS.

This module is the single source of truth for application version,
executable name, and human-readable metadata. Both the runtime and
build tooling import this so we do not duplicate strings across the
codebase.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


APP_NAME: str = "ShittyRandomPhotoScreenSaver"
APP_EXE_NAME: str = "SRPSS"
APP_VERSION: str = "1.4.0"
APP_DESCRIPTION: str = "ShittyRandomPhotoScreenSaver - Random Image Screensaver with several transitions, OpenGL acceleration, support for disk, rss and json sources all at once."
APP_COMPANY: str = "Jayde Ver Elst"


@dataclass(frozen=True)
class VersionInfo:
    major: int
    minor: int
    patch: int

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)


def parse_version(version_str: str = APP_VERSION) -> VersionInfo:
    """Parse a semantic-ish version string ``MAJOR.MINOR.PATCH``.

    Falls back to ``0.0.0`` on parse errors so callers always receive a
    usable object.
    """

    try:
        parts = [int(p) for p in str(version_str).split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        return VersionInfo(parts[0], parts[1], parts[2])
    except Exception:
        return VersionInfo(0, 0, 0)


__all__ = [
    "APP_NAME",
    "APP_EXE_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "APP_COMPANY",
    "VersionInfo",
    "parse_version",
]

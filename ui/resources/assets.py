"""Canonical paths and byte access for registered immutable Qt resources."""

from __future__ import annotations

from PySide6.QtCore import QFile, QIODevice

from .registration import ensure_core_resources

# Package import registers the ordinary pack, but keep direct/module-reload use
# deterministic too. Guided Setup remains outside this boundary.
ensure_core_resources()


_PREFIX = ":/srpss/"


def resource_path(name: str) -> str:
    """Return a validated Qt resource path for one immutable application asset."""

    relative = str(name).replace("\\", "/").lstrip("/")
    if not relative or ".." in relative.split("/"):
        raise ValueError(f"invalid Qt resource name: {name!r}")
    return _PREFIX + relative


def resource_url(name: str) -> str:
    """Return the URL spelling QML image properties require for a resource."""

    return "qrc" + resource_path(name)


def resource_bytes(name: str) -> bytes:
    """Read an immutable resource without extracting it to the filesystem."""

    source = QFile(resource_path(name))
    if not source.open(QIODevice.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Qt resource is unavailable: {name}")
    try:
        return bytes(source.readAll())
    finally:
        source.close()


def resource_exists(name: str) -> bool:
    """Check a registered resource without consulting the filesystem."""

    return QFile.exists(resource_path(name))


__all__ = ["resource_bytes", "resource_exists", "resource_path", "resource_url"]

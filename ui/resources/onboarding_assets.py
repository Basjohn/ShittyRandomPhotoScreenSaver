"""On-demand registration for the Guided Setup preview resource pack."""

from __future__ import annotations

from PySide6.QtCore import QFile, QIODevice


_PREFIX = ":/srpss/onboarding/"


def _register() -> None:
    # Generated registration is idempotent, but importing this large module is
    # deliberately deferred until Guided Setup actually requests an asset.
    from . import onboarding_assets_rc  # noqa: F401


def onboarding_resource_path(name: str) -> str:
    """Register the preview pack on first lookup and return its Qt path."""

    relative = str(name).replace("\\", "/").lstrip("/")
    # Existing Guided Setup callers name assets from the source family root.
    # Keep that stable semantic identity while the QRC owns the physical path.
    if relative.startswith("onboarding/"):
        relative = relative[len("onboarding/"):]
    if not relative or ".." in relative.split("/"):
        raise ValueError(f"invalid onboarding resource name: {name!r}")
    _register()
    return _PREFIX + relative


def onboarding_resource_bytes(name: str) -> bytes:
    source = QFile(onboarding_resource_path(name))
    if not source.open(QIODevice.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"Qt onboarding resource is unavailable: {name}")
    try:
        return bytes(source.readAll())
    finally:
        source.close()


__all__ = ["onboarding_resource_bytes", "onboarding_resource_path"]

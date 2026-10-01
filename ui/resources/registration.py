"""Registration boundary for SRPSS binary Qt resource packs.

The two ``.rcc`` files are generated build products. The ordinary pack is
registered at UI/resource import time; Guided Setup remains lazy and registers
its pack only on first explicit onboarding asset lookup.
"""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from PySide6.QtCore import QFile, QResource


_RESOURCE_DIR = Path(__file__).resolve().parent
_CORE_PACK = _RESOURCE_DIR / "assets.rcc"
_ONBOARDING_PACK = _RESOURCE_DIR / "onboarding_assets.rcc"
_CORE_PROBE = ":/srpss/fonts/Jost-Regular.ttf"
_ONBOARDING_PROBE = ":/srpss/onboarding/manifest.json"
_LOCK = RLock()
_CORE_REGISTERED = False
_ONBOARDING_REGISTERED = False


def resource_pack_path(name: str) -> Path:
    """Return a package-local generated resource pack without path traversal."""
    candidate = str(name).replace("\\", "/").strip("/")
    if not candidate or "/" in candidate or candidate in {".", ".."}:
        raise ValueError(f"invalid Qt resource pack name: {name!r}")
    return _RESOURCE_DIR / candidate


def _register(pack: Path, probe: str) -> None:
    if QFile.exists(probe):
        return
    if pack.is_file() and QResource.registerResource(str(pack)) and QFile.exists(probe):
        return
    if not pack.is_file():
        raise RuntimeError(
            f"Qt resource pack is missing: {pack}. Run Build Foundry or tools/regen_qrc.py first."
        )
    raise RuntimeError(f"Qt rejected resource pack or expected namespace is absent: {pack}")

def ensure_core_resources() -> None:
    global _CORE_REGISTERED
    if _CORE_REGISTERED and QFile.exists(_CORE_PROBE):
        return
    with _LOCK:
        if _CORE_REGISTERED and QFile.exists(_CORE_PROBE):
            return
        _register(_CORE_PACK, _CORE_PROBE)
        _CORE_REGISTERED = True


def ensure_onboarding_resources() -> None:
    global _ONBOARDING_REGISTERED
    if _ONBOARDING_REGISTERED and QFile.exists(_ONBOARDING_PROBE):
        return
    with _LOCK:
        if _ONBOARDING_REGISTERED and QFile.exists(_ONBOARDING_PROBE):
            return
        _register(_ONBOARDING_PACK, _ONBOARDING_PROBE)
        _ONBOARDING_REGISTERED = True


def core_resources_registered() -> bool:
    return _CORE_REGISTERED and QFile.exists(_CORE_PROBE)


def onboarding_resources_registered() -> bool:
    return _ONBOARDING_REGISTERED and QFile.exists(_ONBOARDING_PROBE)


__all__ = [
    "core_resources_registered",
    "ensure_core_resources",
    "ensure_onboarding_resources",
    "onboarding_resources_registered",
    "resource_pack_path",
]

"""Linux user-bound credential key in the Secret Service keyring (the DPAPI counterpart).

GNOME Keyring and KDE Wallet both serve the freedesktop Secret Service API on the
session bus. SRPSS keeps one random 256-bit key there (label "SRPSS credential key",
attributes ``application=SRPSS``/``purpose=credential-key``); credential files are
encrypted with it by ``core/windows/dpapi.py`` (AES-GCM), so they keep their usual
locations and file contract while only the user's unlocked keyring can read them.

A locked collection is unlocked through the keyring's own prompt. With no Secret
Service (no keyring daemon in the session) or a dismissed prompt this raises
``SecretServiceUnavailable``: credentials are then not persisted, never written in
plaintext.
"""
from __future__ import annotations

import secrets
import threading

from core.logging.logger import get_logger

logger = get_logger(__name__)

KEY_LABEL = "SRPSS credential key"
KEY_ATTRIBUTES = {"application": "SRPSS", "purpose": "credential-key"}
KEY_BYTES = 32


class SecretServiceUnavailable(RuntimeError):
    """No usable Secret Service keyring (missing daemon, locked and not unlocked, or refused)."""


_lock = threading.Lock()
_cached_key: bytes | None = None


def _collection():
    try:
        import secretstorage
    except ImportError as exc:  # pragma: no cover - pinned dependency on Linux
        raise SecretServiceUnavailable("secretstorage is not installed") from exc
    try:
        connection = secretstorage.dbus_init()
    except Exception as exc:
        raise SecretServiceUnavailable(f"no D-Bus session bus: {exc}") from exc
    if not secretstorage.check_service_availability(connection):
        raise SecretServiceUnavailable("no Secret Service keyring is running in this session")
    collection = secretstorage.get_default_collection(connection)
    if collection.is_locked():
        dismissed = collection.unlock()
        if dismissed or collection.is_locked():
            raise SecretServiceUnavailable("the keyring stayed locked (unlock prompt dismissed)")
    return collection


def user_key(*, create: bool) -> bytes:
    """Return the user's credential key, creating it once when *create* is true."""

    global _cached_key
    with _lock:
        if _cached_key is not None:
            return _cached_key
        collection = _collection()
        items = list(collection.search_items(KEY_ATTRIBUTES))
        if items:
            item = items[0]
            if item.is_locked():
                item.unlock()
            key = bytes(item.get_secret())
            if len(key) != KEY_BYTES:
                raise SecretServiceUnavailable("the stored SRPSS credential key is malformed")
        elif create:
            key = secrets.token_bytes(KEY_BYTES)
            collection.create_item(KEY_LABEL, KEY_ATTRIBUTES, key, replace=True)
            logger.info("[CREDENTIALS] Created the SRPSS credential key in the Secret Service keyring")
        else:
            raise SecretServiceUnavailable("no SRPSS credential key in the keyring (credentials cannot be read)")
        _cached_key = key
        return key


def available() -> bool:
    """Whether a Secret Service keyring can hold the key in this session (no prompt is shown)."""

    if _cached_key is not None:
        return True
    try:
        import secretstorage

        connection = secretstorage.dbus_init()
        return bool(secretstorage.check_service_availability(connection))
    except Exception:
        return False


def forget_cached_key() -> None:
    """Drop the in-process copy of the key (tests, keyring changes)."""

    global _cached_key
    with _lock:
        _cached_key = None


__all__ = ["SecretServiceUnavailable", "available", "forget_cached_key", "user_key"]

"""User-bound credential protection: the single encrypt/decrypt owner for stored credentials.

* Windows: DPAPI (``CryptProtectData``) binds the blob to the current Windows user and
  machine; blobs are ``dpapi::<base64>``.
* Linux: AES-256-GCM with a random per-user key kept in the Secret Service keyring
  (``core/secret_service_key.py``: GNOME Keyring / KDE Wallet); blobs are
  ``sskey::<base64 nonce+ciphertext>``.

There is no plaintext fallback anywhere: without DPAPI or a keyring, encryption
raises and callers persist nothing. ``is_protected`` recognises either format.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)

DPAPI_PREFIX = b"dpapi::"
KEYRING_PREFIX = b"sskey::"
PROTECTED_PREFIXES = (DPAPI_PREFIX, KEYRING_PREFIX)
_KEYRING_AAD = b"SRPSS credential v1"


# Lazily defined inside each function because ctypes/wintypes are only available on Windows.
# Kept as a module-level helper to avoid duplication between encrypt and decrypt.
_DATA_BLOB = None


def _make_data_blob():
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    return DATA_BLOB


def is_protected(blob: bytes) -> bool:
    """Whether *blob* is a protected credential payload (DPAPI or keyring)."""
    return bytes(blob).startswith(PROTECTED_PREFIXES)


def protected_storage_available() -> bool:
    """Whether credentials can be protected here (DPAPI on Windows; a Secret Service keyring elsewhere)."""
    if os.name == "nt":
        return True
    from core import secret_service_key

    return secret_service_key.available()


def _keyring_encrypt(plaintext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from core.secret_service_key import user_key

    nonce = os.urandom(12)
    sealed = AESGCM(user_key(create=True)).encrypt(nonce, bytes(plaintext), _KEYRING_AAD)
    return KEYRING_PREFIX + base64.b64encode(nonce + sealed)


def _keyring_decrypt(ciphertext: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from core.secret_service_key import user_key

    raw = base64.b64decode(ciphertext[len(KEYRING_PREFIX):])
    return AESGCM(user_key(create=False)).decrypt(raw[:12], raw[12:], _KEYRING_AAD)


def encrypt_user_data(plaintext: bytes) -> bytes:
    """Protect *plaintext* for the current user (DPAPI on Windows, keyring key elsewhere).

    Raises when no protection is available; there is no plaintext fallback.
    """
    if os.name != "nt":
        return _keyring_encrypt(plaintext)

    try:
        import ctypes
        from ctypes import wintypes

        DATA_BLOB = _make_data_blob()
        p_data_in = DATA_BLOB(len(plaintext), ctypes.cast(plaintext, ctypes.POINTER(ctypes.c_ubyte)))
        p_data_out = DATA_BLOB()

        CRYPTPROTECT_UI_FORBIDDEN = 0x01

        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        CryptProtectData.restype = wintypes.BOOL

        if not CryptProtectData(
            ctypes.byref(p_data_in),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(p_data_out),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        encrypted = ctypes.string_at(p_data_out.pbData, p_data_out.cbData)
        ctypes.windll.kernel32.LocalFree(p_data_out.pbData)
        return b"dpapi::" + base64.b64encode(encrypted)

    except Exception as exc:
        logger.error("[DPAPI] Encryption failed: %s", exc)
        raise


def decrypt_user_data(ciphertext: bytes) -> bytes:
    """Recover a protected payload written by ``encrypt_user_data`` on this OS."""
    if ciphertext.startswith(KEYRING_PREFIX):
        if os.name == "nt":
            raise OSError("Keyring-protected ciphertext cannot be decrypted on Windows")
        return _keyring_decrypt(ciphertext)

    if not ciphertext.startswith(DPAPI_PREFIX):
        raise ValueError("Invalid ciphertext format: missing dpapi:: or sskey:: prefix")

    encrypted = base64.b64decode(ciphertext[len(b"dpapi::"):])

    if os.name != "nt":
        raise OSError("DPAPI ciphertext cannot be decrypted on non-Windows platform")

    try:
        import ctypes
        from ctypes import wintypes

        DATA_BLOB = _make_data_blob()
        p_data_in = DATA_BLOB(len(encrypted), ctypes.cast(encrypted, ctypes.POINTER(ctypes.c_ubyte)))
        p_data_out = DATA_BLOB()

        CRYPTUNPROTECT_UI_FORBIDDEN = 0x01

        CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
        CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        CryptUnprotectData.restype = wintypes.BOOL

        if not CryptUnprotectData(
            ctypes.byref(p_data_in),
            None,
            None,
            None,
            None,
            CRYPTUNPROTECT_UI_FORBIDDEN,
            ctypes.byref(p_data_out),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        plaintext = ctypes.string_at(p_data_out.pbData, p_data_out.cbData)
        ctypes.windll.kernel32.LocalFree(p_data_out.pbData)
        return plaintext

    except Exception as exc:
        logger.error("[DPAPI] Decryption failed: %s", exc)
        raise


def save_encrypted(path: Path, data: bytes) -> None:
    """Encrypt and write *data* to *path*.

    Off Windows the file is also created (and kept) owner-only (0600) instead of
    inheriting the umask.
    """
    payload = encrypt_user_data(data)
    if os.name == "nt":
        path.write_bytes(payload)
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
    logger.debug("[DPAPI] Saved encrypted data to %s", path)


def load_encrypted(path: Path) -> Optional[bytes]:
    """Read and decrypt *data* from *path*."""
    if not path.exists():
        return None
    ciphertext = path.read_bytes()
    return decrypt_user_data(ciphertext)

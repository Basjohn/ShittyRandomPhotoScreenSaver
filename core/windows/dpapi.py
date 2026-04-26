"""Windows DPAPI encrypt/decrypt for user-local credential protection.

Encrypts data to the current Windows user + machine via CryptProtectData.
On non-Windows platforms falls back to plain storage with a logged WARNING.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from core.logging.logger import get_logger

logger = get_logger(__name__)


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


def encrypt_user_data(plaintext: bytes) -> bytes:
    """Encrypt *plaintext* using DPAPI (Windows) or return as-is (fallback)."""
    if os.name != "nt":
        logger.warning("[DPAPI] Non-Windows platform: using unencrypted fallback storage")
        return b"plain::" + plaintext

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
    """Decrypt *ciphertext* using DPAPI (Windows) or return plain fallback."""
    if ciphertext.startswith(b"plain::"):
        return ciphertext[len(b"plain::"):]

    if not ciphertext.startswith(b"dpapi::"):
        raise ValueError("Invalid ciphertext format: missing dpapi:: or plain:: prefix")

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
    """Encrypt and write *data* to *path*."""
    path.write_bytes(encrypt_user_data(data))
    logger.debug("[DPAPI] Saved encrypted data to %s", path)


def load_encrypted(path: Path) -> Optional[bytes]:
    """Read and decrypt *data* from *path*."""
    if not path.exists():
        return None
    ciphertext = path.read_bytes()
    return decrypt_user_data(ciphertext)

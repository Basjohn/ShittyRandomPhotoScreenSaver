"""Strict Steam credential storage and redaction helpers.

Steam credentials are not normal widget settings. This module intentionally
refuses plaintext fallback storage even though the shared DPAPI helper keeps
that fallback for older compatibility consumers.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.logging.logger import get_logger
from core.settings.storage_paths import (
    get_steam_cache_dir,
    get_steam_dir,
    get_steam_credential_meta_file,
    get_steam_credentials_file,
)
from core.windows.dpapi import decrypt_user_data, encrypt_user_data

logger = get_logger(__name__)

SCHEMA_VERSION = 1
STEAM_SECRET_FIELD_NAMES = frozenset({
    "steam_api_key",
    "steam_profile_identifier",
    "steam_credential_fingerprint",
    "api_key",
    "profile_identifier",
    "credential_fingerprint",
    "credentials",
    "credential",
    "token",
    "access_token",
    "refresh_token",
})


class SteamCredentialError(RuntimeError):
    """Raised when Steam credential storage cannot complete safely."""


@dataclass(frozen=True)
class SteamCredentialPayload:
    """Structured Steam credential payload kept only in encrypted storage."""

    api_key: str
    profile_identifier: str
    provider_mode: str = "steam_web_api"
    created_at: float | None = None
    updated_at: float | None = None

    def to_json_bytes(self) -> bytes:
        now = time.time()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "api_key": self.api_key,
            "profile_identifier": self.profile_identifier,
            "provider_mode": self.provider_mode,
            "created_at": float(self.created_at if self.created_at is not None else now),
            "updated_at": float(self.updated_at if self.updated_at is not None else now),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "SteamCredentialPayload":
        try:
            raw = json.loads(data.decode("utf-8"))
        except Exception as exc:
            raise SteamCredentialError("Invalid Steam credential payload") from exc
        if not isinstance(raw, Mapping):
            raise SteamCredentialError("Invalid Steam credential payload")
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise SteamCredentialError("Unsupported Steam credential schema")
        api_key = raw.get("api_key")
        profile_identifier = raw.get("profile_identifier")
        if not isinstance(api_key, str) or not api_key.strip():
            raise SteamCredentialError("Steam credential payload is missing an API key")
        if not isinstance(profile_identifier, str) or not profile_identifier.strip():
            raise SteamCredentialError("Steam credential payload is missing a profile identifier")
        provider_mode = raw.get("provider_mode")
        return cls(
            api_key=api_key,
            profile_identifier=profile_identifier,
            provider_mode=provider_mode if isinstance(provider_mode, str) and provider_mode else "steam_web_api",
            created_at=_optional_float(raw.get("created_at")),
            updated_at=_optional_float(raw.get("updated_at")),
        )


@dataclass(frozen=True)
class SteamCredentialInputStatus:
    """UI-safe validation result for proposed Steam credential input."""

    can_test: bool
    can_save_after_test: bool
    message: str


@dataclass(frozen=True)
class SteamCredentialStorageStatus:
    """Non-secret storage status safe for settings UI surfaces."""

    storage_available: bool
    has_credentials: bool
    message: str


@dataclass(frozen=True)
class SteamCredentialMetadata:
    """Non-secret credential metadata usable by cache-first runtime work."""

    profile_cache_key: str
    provider_mode: str
    updated_at: float | None


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def derive_profile_cache_key(profile_identifier: str) -> str:
    """Return an opaque cache folder name for a Steam profile/account id."""
    digest = hashlib.sha256(profile_identifier.strip().encode("utf-8")).hexdigest()
    return f"profile_{digest[:24]}"


def safe_fingerprint(value: str) -> str:
    """Return a short non-reversible fingerprint for diagnostics/metadata."""
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()
    return digest[:12]


def normalize_api_key(api_key: str | None) -> str:
    """Remove copy/paste whitespace from the normal alphanumeric Steam key."""
    return "".join(api_key.split()) if isinstance(api_key, str) else ""


def redact_secret(value: str | None, *, label: str = "redacted") -> str:
    """Return a safe redaction marker that never includes the secret itself."""
    if not value:
        return f"<{label}:empty>"
    return f"<{label}:{safe_fingerprint(value)}>"


def redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursive copy with Steam secret-looking fields redacted."""
    return _redact_mapping(mapping, inside_steam=False)


def _redact_mapping(mapping: Mapping[str, Any], *, inside_steam: bool) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key)
        lowered = key_text.lower()
        next_inside_steam = inside_steam or lowered == "steam" or lowered.startswith("steam_")
        if _is_secret_field(lowered, inside_steam=inside_steam):
            result[key_text] = "<redacted>"
        elif isinstance(value, Mapping):
            result[key_text] = _redact_mapping(value, inside_steam=next_inside_steam)
        elif isinstance(value, list):
            result[key_text] = [
                _redact_mapping(item, inside_steam=next_inside_steam) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            result[key_text] = value
    return result


def strip_secret_fields(mapping: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    """Return a recursive copy with Steam credential fields removed."""
    return _strip_secret_fields(mapping, inside_steam=False)


def _strip_secret_fields(mapping: Mapping[str, Any], *, inside_steam: bool) -> tuple[dict[str, Any], int]:
    removed = 0
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = str(key)
        lowered = key_text.lower()
        next_inside_steam = inside_steam or lowered == "steam" or lowered.startswith("steam_")
        if _is_secret_field(lowered, inside_steam=inside_steam):
            removed += 1
            continue
        if isinstance(value, Mapping):
            child, child_removed = _strip_secret_fields(value, inside_steam=next_inside_steam)
            removed += child_removed
            result[key_text] = child
        elif isinstance(value, list):
            cleaned_list: list[Any] = []
            for item in value:
                if isinstance(item, Mapping):
                    child, child_removed = _strip_secret_fields(item, inside_steam=next_inside_steam)
                    removed += child_removed
                    cleaned_list.append(child)
                else:
                    cleaned_list.append(item)
            result[key_text] = cleaned_list
        else:
            result[key_text] = value
    return result, removed


def _is_secret_field(lowered_key: str, *, inside_steam: bool) -> bool:
    if lowered_key.startswith("steam_") and (
        "key" in lowered_key
        or "secret" in lowered_key
        or "token" in lowered_key
        or "credential" in lowered_key
        or "profile_identifier" in lowered_key
    ):
        return True
    if inside_steam and lowered_key in STEAM_SECRET_FIELD_NAMES:
        return True
    if lowered_key in {"steam_api_key", "steam_profile_identifier", "steam_credential_fingerprint"}:
        return True
    return False


def save_credentials(
    credential: SteamCredentialPayload,
    *,
    profile: str | None = None,
    encrypt_func: Callable[[bytes], bytes] = encrypt_user_data,
    credentials_path: Path | None = None,
    meta_path: Path | None = None,
) -> Path:
    """Strictly encrypt and atomically persist Steam credentials.

    The encrypted blob must start with ``dpapi::``. A ``plain::`` result is
    treated as failure and is never written.
    """
    payload = credential.to_json_bytes()
    encrypted = encrypt_func(payload)
    if not encrypted.startswith(b"dpapi::"):
        logger.error("[STEAM] Credential encryption did not produce DPAPI output; refusing write")
        raise SteamCredentialError("Steam credentials require DPAPI-protected storage")

    path = credentials_path or get_steam_credentials_file(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_bytes(encrypted)
        tmp_path.replace(path)
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.exception("[STEAM] Failed to write encrypted Steam credentials")
        raise SteamCredentialError("Failed to write Steam credentials") from exc

    write_credential_metadata(credential, profile=profile, meta_path=meta_path)
    logger.info(
        "[STEAM] Stored encrypted Steam credentials profile=%s key=%s",
        redact_secret(credential.profile_identifier, label="profile"),
        redact_secret(credential.api_key, label="key"),
    )
    return path


def load_credentials(
    *,
    profile: str | None = None,
    decrypt_func: Callable[[bytes], bytes] = decrypt_user_data,
    credentials_path: Path | None = None,
) -> SteamCredentialPayload | None:
    """Load and decrypt Steam credentials, rejecting plaintext fallback blobs."""
    path = credentials_path or get_steam_credentials_file(profile)
    if not path.exists():
        return None
    encrypted = path.read_bytes()
    if not encrypted.startswith(b"dpapi::"):
        logger.error("[STEAM] Refusing non-DPAPI Steam credential payload at %s", path)
        raise SteamCredentialError("Steam credential file is not DPAPI protected")
    decrypted = decrypt_func(encrypted)
    return SteamCredentialPayload.from_json_bytes(decrypted)


def clear_credentials(*, profile: str | None = None) -> None:
    """Delete Steam credential files without touching broader cache state."""
    for path in (
        get_steam_credentials_file(profile),
        get_steam_credential_meta_file(profile),
    ):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning("[STEAM] Failed to delete Steam credential file: %s", path)


def clear_account_private_state(*, profile: str | None = None) -> None:
    """Delete account-private Steam cache/profile state under the Steam root."""
    cache_dir = get_steam_dir(profile) / "cache"
    try:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("[STEAM] Cleared account-private Steam cache/state")
    except Exception as exc:
        logger.warning("[STEAM] Failed to clear account-private Steam cache/state: %s", exc)
        raise SteamCredentialError("Failed to clear Steam account-private state") from exc


def disconnect_account(*, profile: str | None = None) -> None:
    """Delete Steam credentials plus account-private cache/profile state."""
    clear_credentials(profile=profile)
    clear_account_private_state(profile=profile)


def get_storage_status(*, profile: str | None = None) -> SteamCredentialStorageStatus:
    """Return a non-secret status for settings UI without decrypting secrets."""
    available = steam_storage_available()
    has_credentials = get_steam_credentials_file(profile).exists()
    if not available:
        return SteamCredentialStorageStatus(
            storage_available=False,
            has_credentials=has_credentials,
            message="Strict Steam credential storage is unavailable on this platform.",
        )
    if has_credentials:
        return SteamCredentialStorageStatus(
            storage_available=True,
            has_credentials=True,
            message="Steam credentials are stored for this Windows user.",
        )
    return SteamCredentialStorageStatus(
        storage_available=True,
        has_credentials=False,
        message="Steam is not connected.",
    )


def read_credential_metadata(*, profile: str | None = None) -> SteamCredentialMetadata | None:
    """Read safe cache-routing metadata without decrypting Steam credentials."""
    path = get_steam_credential_meta_file(profile)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or raw.get("schema_version") != SCHEMA_VERSION:
            return None
        profile_cache_key = raw.get("profile_cache_key")
        if not isinstance(profile_cache_key, str) or not profile_cache_key.startswith("profile_"):
            return None
        provider_mode = raw.get("provider_mode")
        return SteamCredentialMetadata(
            profile_cache_key=profile_cache_key,
            provider_mode=provider_mode if isinstance(provider_mode, str) and provider_mode else "steam_web_api",
            updated_at=_optional_float(raw.get("updated_at")),
        )
    except Exception:
        logger.warning("[STEAM] Ignoring invalid non-secret credential metadata")
        return None


def validate_credential_input(api_key: str | None, profile_identifier: str | None) -> SteamCredentialInputStatus:
    """Validate user-provided credential text without persistence or network IO."""
    if not steam_storage_available():
        return SteamCredentialInputStatus(
            can_test=False,
            can_save_after_test=False,
            message="Strict Steam credential storage is unavailable on this platform.",
        )
    normalized_api_key = normalize_api_key(api_key)
    if len(normalized_api_key) < 16:
        return SteamCredentialInputStatus(
            can_test=False,
            can_save_after_test=False,
            message="Enter a Steam API key before testing.",
        )
    if not normalized_api_key.isalnum():
        return SteamCredentialInputStatus(
            can_test=False,
            can_save_after_test=False,
            message="Steam API keys contain letters and numbers only, with no spaces.",
        )
    if not isinstance(profile_identifier, str) or not profile_identifier.strip():
        return SteamCredentialInputStatus(
            can_test=False,
            can_save_after_test=False,
            message="Enter a Steam profile identifier before testing.",
        )
    return SteamCredentialInputStatus(
        can_test=True,
        can_save_after_test=False,
        message="Ready to test. Credentials should be saved only after a successful test.",
    )


def write_credential_metadata(
    credential: SteamCredentialPayload,
    *,
    profile: str | None = None,
    meta_path: Path | None = None,
) -> Path:
    """Write non-secret credential metadata for UI/status surfaces."""
    path = meta_path or get_steam_credential_meta_file(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "provider_mode": credential.provider_mode,
        "profile_cache_key": derive_profile_cache_key(credential.profile_identifier),
        "profile_fingerprint": safe_fingerprint(credential.profile_identifier),
        "api_key_fingerprint": safe_fingerprint(credential.api_key),
        "updated_at": float(credential.updated_at if credential.updated_at is not None else time.time()),
    }
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)
    return path


def get_profile_cache_dir_for_credentials(
    credential: SteamCredentialPayload,
    *,
    profile: str | None = None,
) -> Path:
    """Return the hashed Steam account cache dir for a credential payload."""
    return get_steam_cache_dir(
        profile=profile,
        profile_key=derive_profile_cache_key(credential.profile_identifier),
    )


def steam_storage_available() -> bool:
    """Return whether strict Steam credential persistence is available here."""
    return os.name == "nt"

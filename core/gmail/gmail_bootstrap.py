"""Qt-free Gmail backend bootstrap preparation.

The Gmail backend and OAuth manager are GUI-owned ``QObject`` facades.  This
module performs their cold filesystem, JSON, pickle, and DPAPI preparation on a
shared I/O worker and returns one short-lived immutable snapshot for GUI commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any, Mapping, Optional

from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir
from core.windows.dpapi import encrypt_user_data, load_encrypted


logger = get_logger(__name__)


@dataclass(frozen=True, repr=False)
class PreparedOAuthCredentials:
    """Decoded OAuth credential material for one GUI-owned commit."""

    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: datetime
    scope: str


@dataclass(frozen=True, repr=False)
class PreparedOAuthClientConfig:
    """Prepared OAuth client configuration without Qt state."""

    client_id: Optional[str]
    client_secret: Optional[str]


@dataclass(frozen=True, repr=False)
class PreparedGmailBootstrap:
    """Complete detached state needed to initialize Gmail GUI facades."""

    app_data_path: Path
    backend_config_path: Path
    imap_credentials_path: Path
    backend_mode: str
    imap_email: Optional[str]
    imap_password: Optional[str]
    oauth_credentials_path: Path
    oauth_token_path: Path
    oauth_legacy_token_path: Path
    oauth_client_config: PreparedOAuthClientConfig
    oauth_credentials: Optional[PreparedOAuthCredentials]


def _credentials_from_mapping(data: Mapping[str, Any]) -> PreparedOAuthCredentials:
    return PreparedOAuthCredentials(
        access_token=str(data["access_token"]),
        refresh_token=(
            str(data["refresh_token"])
            if data.get("refresh_token") is not None
            else None
        ),
        token_type=str(data["token_type"]),
        expires_at=datetime.fromisoformat(str(data["expires_at"])),
        scope=str(data["scope"]),
    )


def _credentials_to_mapping(
    credentials: PreparedOAuthCredentials,
) -> dict[str, Any]:
    return {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "token_type": credentials.token_type,
        "expires_at": credentials.expires_at.isoformat(),
        "scope": credentials.scope,
    }


def prepare_oauth_client_config(path: Path) -> PreparedOAuthClientConfig:
    """Read one OAuth client-secrets file without touching Qt objects."""

    target = Path(path)
    try:
        payload = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("[GMAIL_OAUTH] client_secrets.json not found at %s", target)
        return PreparedOAuthClientConfig(None, None)
    except OSError as exc:
        logger.error("[GMAIL_OAUTH] Failed to read client_secrets.json: %s", exc)
        return PreparedOAuthClientConfig(None, None)

    try:
        data = json.loads(payload)
        if "installed" in data:
            data = data["installed"]
        elif "web" in data:
            data = data["web"]
        if not isinstance(data, dict):
            raise ValueError("client_secrets.json root is not an object")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        if not client_id:
            raise ValueError("client_secrets.json missing client_id")
        if not client_secret:
            logger.warning("[GMAIL_OAUTH] client_secret missing from JSON")
        logger.info("[GMAIL_OAUTH] Prepared client configuration")
        return PreparedOAuthClientConfig(
            str(client_id),
            str(client_secret) if client_secret is not None else None,
        )
    except Exception as exc:
        logger.error("[GMAIL_OAUTH] Failed to parse client_secrets.json: %s", exc)
        return PreparedOAuthClientConfig(None, None)


def _load_backend_mode(path: Path) -> str:
    try:
        payload = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "oauth"
    except OSError as exc:
        logger.warning("[GMAIL_BACKEND] Failed to read config: %s", exc)
        return "oauth"
    try:
        data = json.loads(payload)
        mode = str(data.get("mode", "oauth"))
        return mode if mode in {"oauth", "imap"} else "oauth"
    except Exception as exc:
        logger.warning("[GMAIL_BACKEND] Failed to parse config: %s", exc)
        return "oauth"


def _load_imap_credentials(path: Path) -> tuple[Optional[str], Optional[str]]:
    try:
        plaintext = load_encrypted(path)
        if plaintext is None:
            return None, None
        data = json.loads(plaintext.decode("utf-8"))
        email = data.get("email")
        password = data.get("app_password")
        if not email or not password:
            return None, None
        logger.info("[GMAIL_BACKEND] Prepared stored IMAP credentials")
        return str(email), str(password)
    except Exception as exc:
        logger.warning("[GMAIL_BACKEND] Failed to prepare IMAP credentials: %s", exc)
        return None, None


def _load_oauth_credentials(path: Path) -> Optional[PreparedOAuthCredentials]:
    try:
        plaintext = load_encrypted(path)
        if plaintext is None:
            return None
        data = pickle.loads(plaintext)
        if not isinstance(data, dict):
            raise ValueError("OAuth credential payload is not a mapping")
        credentials = _credentials_from_mapping(data)
        logger.info("[GMAIL_OAUTH] Prepared existing credentials")
        return credentials
    except Exception as exc:
        logger.warning("[GMAIL_OAUTH] Failed to prepare credentials: %s", exc)
        return None


def _write_encrypted_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ciphertext = encrypt_user_data(payload)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(ciphertext)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _migrate_legacy_oauth_credentials(
    legacy_path: Path,
    token_path: Path,
) -> Optional[PreparedOAuthCredentials]:
    try:
        payload = legacy_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("[GMAIL_OAUTH] Legacy token read failed: %s", exc)
        return None

    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("legacy OAuth credential payload is not a mapping")
        credentials = _credentials_from_mapping(data)
        _write_encrypted_atomic(
            token_path,
            pickle.dumps(_credentials_to_mapping(credentials)),
        )
    except Exception as exc:
        logger.warning("[GMAIL_OAUTH] Legacy token migration failed: %s", exc)
        return None

    _remove_legacy_oauth_token(legacy_path)
    logger.info("[GMAIL_OAUTH] Migrated legacy token to encrypted storage")
    return credentials


def _remove_legacy_oauth_token(legacy_path: Path) -> bool:
    """Best-effort cleanup after encrypted credentials are authoritative."""

    try:
        legacy_path.unlink(missing_ok=True)
        return True
    except OSError as exc:
        logger.warning("[GMAIL_OAUTH] Legacy token cleanup deferred: %s", exc)
        return False


def prepare_gmail_backend_bootstrap(
    *,
    app_data_path: Path | None = None,
    oauth_credentials_path: Path | None = None,
    oauth_token_path: Path | None = None,
) -> PreparedGmailBootstrap:
    """Prepare the complete Gmail backend snapshot on an I/O worker."""

    app_data = Path(app_data_path) if app_data_path is not None else get_app_data_dir()
    app_data.mkdir(parents=True, exist_ok=True)
    backend_config_path = app_data / "gmail_backend.json"
    imap_credentials_path = app_data / "gmail_imap_creds.enc"

    if oauth_credentials_path is not None:
        credentials_path = Path(oauth_credentials_path)
    else:
        bundled = Path(__file__).resolve().parents[2] / "resources" / "client_secrets.json"
        credentials_path = bundled if bundled.exists() else app_data / "client_secrets.json"

    token_path = Path(oauth_token_path) if oauth_token_path is not None else app_data / "gmail_token.enc"
    legacy_token_path = app_data / "gmail_credentials.json"
    oauth_credentials = _load_oauth_credentials(token_path)
    if oauth_credentials is None:
        oauth_credentials = _migrate_legacy_oauth_credentials(
            legacy_token_path,
            token_path,
        )
    else:
        # Retry removal after a prior launch durably migrated the encrypted
        # token but could not delete the legacy plaintext file.
        _remove_legacy_oauth_token(legacy_token_path)

    imap_email, imap_password = _load_imap_credentials(imap_credentials_path)
    return PreparedGmailBootstrap(
        app_data_path=app_data,
        backend_config_path=backend_config_path,
        imap_credentials_path=imap_credentials_path,
        backend_mode=_load_backend_mode(backend_config_path),
        imap_email=imap_email,
        imap_password=imap_password,
        oauth_credentials_path=credentials_path,
        oauth_token_path=token_path,
        oauth_legacy_token_path=legacy_token_path,
        oauth_client_config=prepare_oauth_client_config(credentials_path),
        oauth_credentials=oauth_credentials,
    )


__all__ = [
    "PreparedGmailBootstrap",
    "PreparedOAuthClientConfig",
    "PreparedOAuthCredentials",
    "prepare_gmail_backend_bootstrap",
    "prepare_oauth_client_config",
]

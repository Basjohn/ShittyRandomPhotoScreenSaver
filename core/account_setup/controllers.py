"""Reusable account setup operations with presentation supplied by callbacks.

These controllers deliberately do not own a QWidget, a thread manager, or any
credential persistence.  Steam credentials stay with ``core.steam.credentials``
and Gmail credentials stay with ``GmailBackend``'s DPAPI-backed owners.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.steam.backend import validate_connection
from core.steam.credentials import (
    SteamCredentialPayload,
    disconnect_account,
    get_storage_status,
    normalize_api_key,
    save_credentials,
    validate_credential_input,
)
from core.steam.models import SteamResultStatus


@dataclass(frozen=True)
class SteamConnectionStatus:
    message: str
    state: str
    identity_ready: bool
    key_ready: bool
    feedback: str | None = None
    feedback_success: bool = False


@dataclass(frozen=True)
class GmailOperationResult:
    success: bool
    message: str


class SteamConnectionController:
    """Run the Steam connection operations shared by Settings and Guided Setup."""

    def __init__(
        self,
        on_status: Callable[[SteamConnectionStatus], None] | None = None,
        *,
        storage_status_reader: Callable[[], object] = get_storage_status,
    ) -> None:
        self._on_status = on_status or (lambda _status: None)
        self._storage_status_reader = storage_status_reader

    def inspect_saved_connection(
        self, pending_profile_identifier: str | None, *, explicit: bool = False
    ) -> SteamConnectionStatus:
        """Inspect DPAPI metadata only; this never decrypts or contacts Steam."""
        storage = self._storage_status_reader()
        if storage.storage_available and storage.has_credentials:
            status = SteamConnectionStatus(
                "Saved Steam identity and API key are available.", "connected", True, True,
                "Connected Successfully" if explicit else None, explicit,
            )
        elif pending_profile_identifier:
            status = SteamConnectionStatus(
                "Steam ID is linked. Add your Web API key to finish connecting.",
                "pending", True, False,
                "Reconnection Needed" if explicit else None,
            )
        else:
            status = SteamConnectionStatus(
                storage.message, "warning", False, False,
                "Reconnection Needed" if explicit else None,
            )
        self._on_status(status)
        return status

    def validate_input(self, api_key: str | None, profile_identifier: str | None):
        """Normalize and validate a user-entered key without retaining it."""
        normalized = normalize_api_key(api_key)
        return normalized, validate_credential_input(normalized, profile_identifier)

    def test_and_save_credentials(
        self, api_key: str | None, profile_identifier: str | None,
    ) -> SteamConnectionStatus:
        """Test an entered key, then delegate accepted persistence to the DPAPI owner."""
        normalized, validation = self.validate_input(api_key, profile_identifier)
        if not validation.can_test:
            status = SteamConnectionStatus(validation.message, "warning", bool(profile_identifier), False)
            self._on_status(status)
            return status
        result = validate_connection(api_key=normalized, steamid=profile_identifier)
        if result.status != SteamResultStatus.SUCCESS:
            status = SteamConnectionStatus(
                "Steam did not accept this API key and identity pair. Your saved connection was left unchanged.",
                "error", True, False,
            )
            self._on_status(status)
            return status
        save_credentials(SteamCredentialPayload(api_key=normalized, profile_identifier=profile_identifier))
        status = SteamConnectionStatus(
            "Steam identity and API key were verified and stored securely.", "connected", True, True,
        )
        self._on_status(status)
        return status

    def disconnect(self) -> SteamConnectionStatus:
        """Delegate encrypted credential and account-private cache removal to its owner."""
        disconnect_account()
        status = SteamConnectionStatus("Steam is disconnected.", "warning", False, False)
        self._on_status(status)
        return status

    def begin_identity_link(self):
        """Create the existing bounded OpenID session only on an explicit action."""
        from core.steam.openid import SteamOpenIdLinkSession
        session = SteamOpenIdLinkSession()
        return session, session.start()


class GmailConnectionController:
    """Run Gmail backend operations without taking ownership of its credentials."""

    def __init__(self, on_status: Callable[[GmailOperationResult], None] | None = None) -> None:
        self._on_status = on_status or (lambda _result: None)

    def select_backend(self, backend, mode) -> GmailOperationResult:
        backend.mode = mode
        result = GmailOperationResult(True, backend.status_text)
        self._on_status(result)
        return result

    def test_imap(self, backend, email_address: str, app_password: str) -> GmailOperationResult:
        """Worker operation: verify TLS credentials without replacing backend state."""
        email = email_address.strip()
        password = app_password.strip()
        if not email or not password:
            result = GmailOperationResult(False, "Email and App Password are both required.")
        elif backend.test_imap_credentials(email, password):
            result = GmailOperationResult(True, f"Connected (IMAP: {email})")
        else:
            result = GmailOperationResult(False, "IMAP login failed")
        self._on_status(result)
        return result

    def save_verified_imap(self, backend, email_address, app_password, verification):
        """GUI-owner commit after a successful test and the caller's lifetime fence."""
        if not isinstance(verification, GmailOperationResult) or not verification.success:
            raise ValueError("Gmail credentials must pass verification before replacement")
        backend.save_imap_credentials(email_address.strip(), app_password.strip())
        return verification

    def sign_out(self, backend) -> GmailOperationResult:
        backend.sign_out()
        result = GmailOperationResult(True, backend.status_text)
        self._on_status(result)
        return result

    def start_oauth(self, backend) -> GmailOperationResult:
        """Start the backend-owned OAuth flow after its caller has refreshed configuration."""
        started = bool(backend.start_oauth_flow())
        result = GmailOperationResult(started, "Browser opened — complete sign-in..." if started else backend.status_text)
        self._on_status(result)
        return result

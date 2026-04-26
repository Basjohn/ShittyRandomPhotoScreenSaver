"""Smoke tests for Gmail backend modules (no Qt app required)."""
from __future__ import annotations

from datetime import datetime

import pytest


def test_gmail_client_imports() -> None:
    from core.gmail.gmail_client import GmailLabel  # noqa: F401
    assert GmailLabel.INBOX.value == "INBOX"


def test_email_metadata_frozen_hashable() -> None:
    from core.gmail.gmail_client import EmailMetadata
    em = EmailMetadata(
        id="1",
        thread_id="t1",
        sender="test@example.com",
        subject="Hello",
        date=datetime.now(),
        labels=("INBOX", "UNREAD"),
        is_unread=True,
    )
    # Frozen dataclass should be hashable
    h = hash(em)
    assert isinstance(h, int)
    # Labels should be stored as tuple
    assert em.labels == ("INBOX", "UNREAD")


def test_dpapi_roundtrip() -> None:
    from core.windows.dpapi import encrypt_user_data, decrypt_user_data
    plaintext = b"test_secret_123"
    ciphertext = encrypt_user_data(plaintext)
    assert ciphertext != plaintext
    assert ciphertext.startswith(b"dpapi::") or ciphertext.startswith(b"plain::")
    recovered = decrypt_user_data(ciphertext)
    assert recovered == plaintext


def test_gmail_oauth_manager_import() -> None:
    """GmailOAuthManager requires Qt; ensure it imports when Qt is available."""
    from PySide6.QtCore import QCoreApplication
    if QCoreApplication.instance() is None:
        pytest.skip("Requires QCoreApplication instance")
    from core.gmail.gmail_oauth import GmailConfigError  # noqa: F401
    assert GmailConfigError is not None

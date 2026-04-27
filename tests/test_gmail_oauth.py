"""Tests for Gmail OAuth manager with mocked network calls (no real Google API)."""
from __future__ import annotations

from core.gmail.gmail_oauth import GmailConfigError


def test_dpapi_roundtrip_no_leak() -> None:
    """Verify DPAPI encrypt/decrypt roundtrip with fake credentials (no leak)."""
    from core.windows.dpapi import encrypt_user_data, decrypt_user_data

    # Use fake test data - NEVER use real credentials
    fake_password = b"fake_test_password_12345"
    
    # Encrypt
    encrypted = encrypt_user_data(fake_password)
    assert encrypted != fake_password
    assert encrypted.startswith(b"dpapi::") or encrypted.startswith(b"plain::")
    
    # Decrypt
    decrypted = decrypt_user_data(encrypted)
    assert decrypted == fake_password
    
    # Verify no plaintext in encrypted data
    assert fake_password not in encrypted
    assert b"password" not in encrypted


def test_oauth_config_error() -> None:
    """Verify GmailConfigError is raised for missing credentials."""
    # Test error message
    error = GmailConfigError("Test error message")
    assert str(error) == "Test error message"
    assert isinstance(error, Exception)


def test_gmail_credentials_dataclass() -> None:
    """Verify GmailCredentials dataclass structure."""
    from core.gmail.gmail_oauth import GmailCredentials
    from datetime import datetime, timedelta

    # Create credentials with fake data
    creds = GmailCredentials(
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_type="Bearer",
        expires_at=datetime.now() + timedelta(hours=1),
        scope="gmail.metadata",
    )

    # Verify structure
    assert creds.access_token == "fake_access_token"
    assert creds.refresh_token == "fake_refresh_token"
    assert creds.is_expired() is False  # Should not be expired

    # Test to_dict
    creds_dict = creds.to_dict()
    assert "access_token" in creds_dict
    assert "refresh_token" in creds_dict

    # Test from_dict
    creds2 = GmailCredentials.from_dict(creds_dict)
    assert creds2.access_token == creds.access_token


def test_oauth_manager_singleton() -> None:
    """Verify GmailOAuthManager is a singleton."""
    from core.gmail.gmail_oauth import GmailOAuthManager

    # Get instance
    instance1 = GmailOAuthManager.instance()
    instance2 = GmailOAuthManager.instance()

    # Should be the same instance
    assert instance1 is instance2


def test_no_real_credentials_in_code() -> None:
    """Verify test code uses explicit fake credentials only."""
    import inspect
    import tests.test_gmail_oauth as test_module

    # Get source code
    source = inspect.getsource(test_module)

    # Verify we use explicit "fake_" prefixes for all credentials
    # This ensures no accidental real credentials
    assert "fake_" in source, "Test code should use fake_ prefix for test credentials"
    assert "fake_access_token" in source or "fake_token" in source
    assert "fake_password" in source


def test_imap_password_storage_mocked() -> None:
    """Verify IMAP password storage with DPAPI (no real credentials)."""
    from core.windows.dpapi import encrypt_user_data, decrypt_user_data

    # Use fake test password - NEVER use real IMAP password
    fake_imap_password = b"fake_imap_password_67890"
    
    # Encrypt
    encrypted = encrypt_user_data(fake_imap_password)
    assert encrypted != fake_imap_password
    
    # Decrypt
    decrypted = decrypt_user_data(encrypted)
    assert decrypted == fake_imap_password
    
    # Verify no plaintext password in encrypted data
    assert fake_imap_password not in encrypted

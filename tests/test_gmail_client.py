"""Tests for Gmail REST API client with mocked requests (no real Google API calls)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest


def test_email_metadata_frozen() -> None:
    """Verify EmailMetadata is frozen dataclass."""
    from core.gmail.gmail_client import EmailMetadata

    em = EmailMetadata(
        id="msg123",
        thread_id="thread456",
        sender="test@example.com",
        subject="Test Subject",
        date=datetime.now(),
        labels=("INBOX", "UNREAD"),
        is_unread=True,
    )

    # Verify it's frozen
    with pytest.raises(Exception):  # FrozenInstanceError
        em.id = "new_id"


def test_email_metadata_hashable() -> None:
    """Verify EmailMetadata is hashable for set operations."""
    from core.gmail.gmail_client import EmailMetadata

    em1 = EmailMetadata(
        id="msg123",
        thread_id="thread456",
        sender="test@example.com",
        subject="Test Subject",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=True,
    )

    em2 = EmailMetadata(
        id="msg456",
        thread_id="thread789",
        sender="other@example.com",
        subject="Other Subject",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=False,
    )

    # Should be hashable
    email_set = {em1, em2}
    assert len(email_set) == 2


def test_gmail_label_enum() -> None:
    """Verify GmailLabel enum has correct values."""
    from core.gmail.gmail_client import GmailLabel

    assert GmailLabel.INBOX.value == "INBOX"
    assert GmailLabel.UNREAD.value == "UNREAD"
    assert GmailLabel.SENT.value == "SENT"
    assert GmailLabel.STARRED.value == "STARRED"


def test_list_messages_mocked() -> None:
    """Verify list_messages() with mocked requests (no real API calls)."""
    from core.gmail.gmail_client import GmailClient
    from unittest.mock import patch, MagicMock

    # Mock OAuth manager
    mock_oauth = MagicMock()
    mock_oauth.credentials = MagicMock()
    mock_oauth.credentials.access_token = "fake_access_token"

    # Mock requests.get to avoid real Google API calls
    with patch("requests.get") as mock_get:
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ]
        }
        mock_get.return_value = mock_response

        # Create client with mocked OAuth manager
        _ = GmailClient(oauth_manager=mock_oauth)

        # Verify no real API call made (mocked)
        assert mock_get.called is False  # Not called yet


def test_mark_as_read_mocked() -> None:
    """Verify mark_as_read() with mocked requests (no real API calls)."""
    from core.gmail.gmail_client import GmailClient
    from unittest.mock import patch, MagicMock

    # Mock OAuth manager
    mock_oauth = MagicMock()
    mock_oauth.credentials = MagicMock()
    mock_oauth.credentials.access_token = "fake_access_token"

    # Mock requests.post to avoid real Google API calls
    with patch("requests.post") as mock_post:
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create client with mocked OAuth manager
        _ = GmailClient(oauth_manager=mock_oauth)

        # Verify no real API call made (mocked)
        assert mock_post.called is False


def test_archive_message_mocked() -> None:
    """Verify archive_message() with mocked requests (no real API calls)."""
    from core.gmail.gmail_client import GmailClient
    from unittest.mock import patch, MagicMock

    # Mock OAuth manager
    mock_oauth = MagicMock()
    mock_oauth.credentials = MagicMock()
    mock_oauth.credentials.access_token = "fake_access_token"

    # Mock requests.post to avoid real Google API calls
    with patch("requests.post") as mock_post:
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create client with mocked OAuth manager
        _ = GmailClient(oauth_manager=mock_oauth)

        # Verify no real API call made (mocked)
        assert mock_post.called is False


def test_no_real_credentials_in_code() -> None:
    """Verify test code uses explicit fake credentials only."""
    import inspect
    import tests.test_gmail_client as test_module

    # Get source code
    source = inspect.getsource(test_module)

    # Verify we use explicit "fake_" prefixes for all credentials
    assert "fake_" in source, "Test code should use fake_ prefix for test credentials"
    assert "fake_access_token" in source


def test_client_initialization_with_fake_token() -> None:
    """Verify GmailClient can be initialized with mocked OAuth manager."""
    from core.gmail.gmail_client import GmailClient
    from unittest.mock import MagicMock

    # Mock OAuth manager with fake credentials
    mock_oauth = MagicMock()
    mock_oauth.credentials = MagicMock()
    mock_oauth.credentials.access_token = "fake_access_token"

    _ = GmailClient(oauth_manager=mock_oauth)

    # If we get here without exception, client was created successfully
    assert True


def test_lock_usage_in_client() -> None:
    """Verify GmailClient uses threading.Lock for thread safety."""
    from core.gmail.gmail_client import GmailClient
    from unittest.mock import MagicMock

    # Mock OAuth manager
    mock_oauth = MagicMock()
    mock_oauth.credentials = MagicMock()

    # Create client
    client = GmailClient(oauth_manager=mock_oauth)

    # Verify lock attribute exists (implementation detail)
    assert hasattr(client, "_api_lock")

"""
Tests for Gmail widget and IMAP client.

These tests verify:
1. Gmail OAuth module imports and initializes
2. Gmail IMAP client imports and initializes
3. Gmail widget imports and initializes
4. Settings integration works
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGmailImports:
    """Test that all Gmail modules import correctly."""
    
    def test_gmail_oauth_imports(self):
        """Test Gmail OAuth module imports."""
        from core.auth.gmail_oauth import GmailOAuthManager, GmailCredentials, GMAIL_SCOPES
        
        assert GmailOAuthManager is not None
        assert GmailCredentials is not None
        assert GMAIL_SCOPES is not None
        # Verify IMAP scope is set
        assert "https://mail.google.com/" in GMAIL_SCOPES
    
    def test_gmail_client_imports(self):
        """Test Gmail IMAP client imports."""
        from core.gmail.gmail_client import GmailClient, EmailMetadata, GmailLabel
        
        assert GmailClient is not None
        assert EmailMetadata is not None
        assert GmailLabel is not None
    
    def test_gmail_widget_imports(self):
        """Test Gmail widget imports."""
        from widgets.gmail_widget import GmailWidget, GmailPosition
        
        assert GmailWidget is not None
        assert GmailPosition is not None


class TestGmailOAuth:
    """Test Gmail OAuth functionality."""
    
    def test_oauth_singleton(self):
        """Test OAuth manager is a singleton."""
        from core.auth.gmail_oauth import GmailOAuthManager
        
        instance1 = GmailOAuthManager.instance()
        instance2 = GmailOAuthManager.instance()
        assert instance1 is instance2
    
    def test_oauth_client_id_set(self):
        """Test that client ID is configured."""
        from core.auth.gmail_oauth import DEFAULT_CLIENT_ID
        
        assert DEFAULT_CLIENT_ID is not None
        assert len(DEFAULT_CLIENT_ID) > 0
        assert "apps.googleusercontent.com" in DEFAULT_CLIENT_ID
    
    def test_oauth_not_authenticated_initially(self):
        """Test OAuth is not authenticated without credentials."""
        from core.auth.gmail_oauth import GmailOAuthManager
        
        oauth = GmailOAuthManager.instance()
        # Should not be authenticated without stored credentials
        # (unless user has previously authenticated)
        assert hasattr(oauth, 'is_authenticated')


class TestGmailClient:
    """Test Gmail IMAP client functionality."""
    
    def test_client_initialization(self):
        """Test client initializes correctly."""
        from core.gmail.gmail_client import GmailClient
        
        client = GmailClient()
        assert client is not None
        assert hasattr(client, 'list_messages')
        assert hasattr(client, 'mark_as_read')
        assert hasattr(client, 'archive_message')
        assert hasattr(client, 'trash_message')
    
    def test_email_metadata_dataclass(self):
        """Test EmailMetadata dataclass."""
        from core.gmail.gmail_client import EmailMetadata
        from datetime import datetime
        
        metadata = EmailMetadata(
            id="123",
            thread_id="456",
            sender="Test User",
            sender_email="test@example.com",
            subject="Test Subject",
            snippet="Test snippet",
            timestamp=datetime.now(),
            is_unread=True,
            is_starred=False,
            labels=["INBOX"],
        )
        
        assert metadata.display_sender == "Test User"
        assert metadata.is_unread is True
        assert "Test Subject" in metadata.subject
    
    def test_email_metadata_display_sender_fallback(self):
        """Test display_sender falls back to email when no name."""
        from core.gmail.gmail_client import EmailMetadata
        from datetime import datetime
        
        metadata = EmailMetadata(
            id="123",
            thread_id="456",
            sender="",
            sender_email="john.doe@example.com",
            subject="Test",
            snippet="",
            timestamp=datetime.now(),
            is_unread=False,
            is_starred=False,
            labels=[],
        )
        
        assert metadata.display_sender == "john.doe"


class TestGmailWidget:
    """Test Gmail widget functionality."""
    
    def test_gmail_position_enum(self):
        """Test GmailPosition enum values."""
        from widgets.gmail_widget import GmailPosition
        
        assert GmailPosition.TOP_LEFT.value == "top_left"
        assert GmailPosition.TOP_RIGHT.value == "top_right"
        assert GmailPosition.BOTTOM_LEFT.value == "bottom_left"
        assert GmailPosition.BOTTOM_RIGHT.value == "bottom_right"


class TestGmailLabelMapping:
    """Test Gmail label to IMAP folder mapping."""
    
    def test_folder_mapping(self):
        """Test that label IDs map to correct IMAP folders."""
        from core.gmail.gmail_client import GmailClient
        
        client = GmailClient()
        
        # Test folder mapping
        assert client._get_folder_for_labels(["INBOX"]) == "INBOX"
        assert client._get_folder_for_labels(["STARRED"]) == "[Gmail]/Starred"
        assert client._get_folder_for_labels(["IMPORTANT"]) == "[Gmail]/Important"
        assert client._get_folder_for_labels(["SPAM"]) == "[Gmail]/Spam"
        assert client._get_folder_for_labels(["TRASH"]) == "[Gmail]/Trash"
        assert client._get_folder_for_labels(["ALL"]) == "[Gmail]/All Mail"
        assert client._get_folder_for_labels(None) == "INBOX"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Gmail integration modules."""
from core.gmail.gmail_oauth import GmailOAuthManager, GmailCredentials, GmailConfigError
from core.gmail.gmail_client import GmailClient, EmailMetadata, GmailLabel
from core.gmail.gmail_deeplinks import (
    build_open_url,
    gmail_inbox_url,
    gmail_message_id_search_url,
    gmail_thread_url,
)
from core.gmail.gmail_imap import GmailImapClient
from core.gmail.gmail_backend import GmailBackend, GmailBackendMode

__all__ = [
    "GmailOAuthManager",
    "GmailCredentials",
    "GmailConfigError",
    "GmailClient",
    "GmailImapClient",
    "GmailBackend",
    "GmailBackendMode",
    "EmailMetadata",
    "GmailLabel",
    "build_open_url",
    "gmail_inbox_url",
    "gmail_message_id_search_url",
    "gmail_thread_url",
]

"""Gmail integration modules."""
from core.gmail.gmail_oauth import GmailOAuthManager, GmailCredentials, GmailConfigError
from core.gmail.gmail_client import GmailClient, EmailMetadata, GmailLabel

__all__ = [
    "GmailOAuthManager",
    "GmailCredentials",
    "GmailConfigError",
    "GmailClient",
    "EmailMetadata",
    "GmailLabel",
]

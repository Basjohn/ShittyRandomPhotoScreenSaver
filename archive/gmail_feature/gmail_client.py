"""
Gmail REST API client for fetching email metadata.

This client uses the Gmail REST API with OAuth2 authentication.
Only accesses email metadata (sender, subject, labels, timestamps).
Never downloads message content, attachments, or body text.

Privacy:
- Uses gmail.readonly scope for metadata access
- Uses gmail.modify scope for label changes (mark read, archive, etc.)
- No message content is ever accessed or stored
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

from core.logging.logger import get_logger
from core.auth.gmail_oauth import GmailOAuthManager

logger = get_logger(__name__)

# Gmail API base URL
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailLabel(Enum):
    """Common Gmail label IDs."""
    INBOX = "INBOX"
    UNREAD = "UNREAD"
    STARRED = "STARRED"
    IMPORTANT = "IMPORTANT"
    SENT = "SENT"
    DRAFT = "DRAFT"
    SPAM = "SPAM"
    TRASH = "TRASH"
    CATEGORY_PRIMARY = "CATEGORY_PRIMARY"
    CATEGORY_SOCIAL = "CATEGORY_SOCIAL"
    CATEGORY_PROMOTIONS = "CATEGORY_PROMOTIONS"
    CATEGORY_UPDATES = "CATEGORY_UPDATES"
    CATEGORY_FORUMS = "CATEGORY_FORUMS"


@dataclass
class EmailMetadata:
    """Metadata for a single email message."""
    id: str
    thread_id: str
    sender: str
    sender_email: str
    subject: str
    snippet: str
    timestamp: datetime
    is_unread: bool
    is_starred: bool
    labels: List[str]
    
    @property
    def display_sender(self) -> str:
        """Get display-friendly sender name."""
        if self.sender:
            return self.sender
        return self.sender_email.split("@")[0] if self.sender_email else "Unknown"
    
    @property
    def display_time(self) -> str:
        """Get display-friendly timestamp."""
        now = datetime.now()
        diff = now - self.timestamp
        
        if diff.days == 0:
            return self.timestamp.strftime("%I:%M %p").lstrip("0")
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return self.timestamp.strftime("%A")
        else:
            return self.timestamp.strftime("%b %d")


class GmailClient:
    """
    Gmail REST API client for fetching email metadata.
    
    Uses Gmail REST API with OAuth2 authentication.
    Only accesses metadata, never message content.
    
    Thread Safety:
        This client is NOT thread-safe. Use from UI thread only,
        or wrap calls with appropriate locking.
    """
    
    def __init__(self, oauth_manager: Optional[GmailOAuthManager] = None):
        """Initialize Gmail REST API client."""
        self._oauth = oauth_manager or GmailOAuthManager.instance()
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication."""
        return self._oauth.is_authenticated
    
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[dict] = None,
    ) -> Optional[dict]:
        """Make an authenticated request to Gmail API."""
        token = self._oauth.get_access_token()
        if not token:
            logger.warning("[GMAIL] No access token available")
            return None
        
        url = f"{GMAIL_API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        try:
            body = json.dumps(data).encode("utf-8") if data else None
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
                
        except urllib.error.HTTPError as e:
            logger.error("[GMAIL] API error %d: %s", e.code, e.reason)
            if e.code == 401:
                if self._oauth._refresh_token():
                    return self._make_request(endpoint, method, data)
            return None
        except Exception as e:
            logger.error("[GMAIL] Request failed: %s", e)
            return None
    
    def list_messages(
        self,
        max_results: int = 10,
        label_ids: Optional[List[str]] = None,
        query: Optional[str] = None,
    ) -> List[EmailMetadata]:
        """List messages with metadata."""
        params = [f"maxResults={max_results}"]
        if label_ids:
            for label in label_ids:
                params.append(f"labelIds={label}")
        if query:
            params.append(f"q={urllib.parse.quote(query)}")
        
        query_string = "&".join(params)
        endpoint = f"/users/me/messages?{query_string}"
        
        response = self._make_request(endpoint)
        if not response or "messages" not in response:
            return []
        
        messages = []
        for msg_ref in response["messages"][:max_results]:
            metadata = self._get_message_metadata(msg_ref["id"])
            if metadata:
                messages.append(metadata)
        
        return messages
    
    def _get_message_metadata(self, message_id: str) -> Optional[EmailMetadata]:
        """Get metadata for a single message."""
        endpoint = (
            f"/users/me/messages/{message_id}"
            "?format=metadata"
            "&metadataHeaders=From"
            "&metadataHeaders=Subject"
            "&metadataHeaders=Date"
        )
        
        response = self._make_request(endpoint)
        if not response:
            return None
        
        try:
            headers = {}
            payload = response.get("payload", {})
            for header in payload.get("headers", []):
                headers[header["name"].lower()] = header["value"]
            
            from_header = headers.get("from", "")
            sender, sender_email = self._parse_from_header(from_header)
            
            internal_date = response.get("internalDate", "0")
            timestamp = datetime.fromtimestamp(int(internal_date) / 1000)
            
            label_ids = response.get("labelIds", [])
            
            return EmailMetadata(
                id=response["id"],
                thread_id=response.get("threadId", ""),
                sender=sender,
                sender_email=sender_email,
                subject=headers.get("subject", "(No Subject)"),
                snippet=response.get("snippet", ""),
                timestamp=timestamp,
                is_unread="UNREAD" in label_ids,
                is_starred="STARRED" in label_ids,
                labels=label_ids,
            )
            
        except Exception as e:
            logger.error("[GMAIL] Failed to parse message metadata: %s", e)
            return None
    
    def _parse_from_header(self, from_header: str) -> tuple:
        """Parse the From header into name and email."""
        match = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>$', from_header.strip())
        if match:
            return match.group(1).strip(), match.group(2).strip()
        
        email_match = re.match(r'^<?([^<>]+@[^<>]+)>?$', from_header.strip())
        if email_match:
            return "", email_match.group(1).strip()
        
        return "", from_header.strip()
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        endpoint = f"/users/me/messages/{message_id}/modify"
        data = {"removeLabelIds": ["UNREAD"]}
        return self._make_request(endpoint, method="POST", data=data) is not None
    
    def mark_as_unread(self, message_id: str) -> bool:
        """Mark a message as unread."""
        endpoint = f"/users/me/messages/{message_id}/modify"
        data = {"addLabelIds": ["UNREAD"]}
        return self._make_request(endpoint, method="POST", data=data) is not None
    
    def archive_message(self, message_id: str) -> bool:
        """Archive a message (remove from INBOX)."""
        endpoint = f"/users/me/messages/{message_id}/modify"
        data = {"removeLabelIds": ["INBOX"]}
        return self._make_request(endpoint, method="POST", data=data) is not None
    
    def mark_as_spam(self, message_id: str) -> bool:
        """Mark a message as spam."""
        endpoint = f"/users/me/messages/{message_id}/modify"
        data = {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]}
        return self._make_request(endpoint, method="POST", data=data) is not None
    
    def trash_message(self, message_id: str) -> bool:
        """Move a message to trash."""
        endpoint = f"/users/me/messages/{message_id}/trash"
        return self._make_request(endpoint, method="POST") is not None
    
    def get_unread_count(self, label_ids: Optional[List[str]] = None) -> int:
        """Get count of unread messages."""
        labels = list(label_ids) if label_ids else ["INBOX"]
        labels.append("UNREAD")
        
        params = "&".join([f"labelIds={label}" for label in labels])
        endpoint = f"/users/me/messages?{params}&maxResults=1"
        
        response = self._make_request(endpoint)
        if response:
            return response.get("resultSizeEstimate", 0)
        return 0
    
    def open_message_in_browser(self, message_id: str) -> bool:
        """Open a message in the user's browser."""
        import webbrowser
        
        try:
            url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.error("[GMAIL] Failed to open browser: %s", e)
            return False

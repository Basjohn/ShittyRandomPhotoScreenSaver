"""Gmail API client for metadata-only email operations.

Security:
- Only accesses message headers (from, subject, date, labels), never body/snippet.
- API calls protected by threading.Lock.
- Uses requests library with timeouts and retries.
- Browser launch uses secure_url_launcher bridge.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from core.logging.logger import get_logger
from core.windows.secure_url_launcher import open_url

logger = get_logger(__name__)

GMAIL_API_BASE = "https://www.googleapis.com/gmail/v1"
DEFAULT_TIMEOUT = (5, 30)  # connect, read
MAX_RETRIES = 2


class GmailLabel(Enum):
    INBOX = "INBOX"
    SENT = "SENT"
    DRAFT = "DRAFT"
    SPAM = "SPAM"
    TRASH = "TRASH"
    UNREAD = "UNREAD"
    STARRED = "STARRED"
    IMPORTANT = "IMPORTANT"
    CATEGORY_PERSONAL = "CATEGORY_PERSONAL"
    CATEGORY_SOCIAL = "CATEGORY_SOCIAL"
    CATEGORY_PROMOTIONS = "CATEGORY_PROMOTIONS"
    CATEGORY_UPDATES = "CATEGORY_UPDATES"
    CATEGORY_FORUMS = "CATEGORY_FORUMS"


@dataclass(frozen=True)
class EmailMetadata:
    """Email metadata — never includes body or snippet content."""
    id: str
    thread_id: str
    sender: str
    subject: str
    date: datetime
    labels: tuple[str, ...]
    is_unread: bool

    def __post_init__(self):
        # Security invariant: metadata-only by design
        object.__setattr__(self, "labels", tuple(self.labels))


class GmailClient:
    """Client for Gmail REST API metadata operations."""

    def __init__(self, oauth_manager):
        self._oauth = oauth_manager
        self._api_lock = threading.Lock()
        self._base_url = GMAIL_API_BASE

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        """Execute an authenticated API request with retry."""
        creds = self._oauth.credentials
        if not creds:
            raise RuntimeError("Not authenticated")

        url = f"{self._base_url}/{endpoint}"
        req_headers = {
            "Authorization": f"Bearer {creds.access_token}",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        import requests

        with self._api_lock:
            last_err: Optional[Exception] = None
            for attempt in range(MAX_RETRIES):
                try:
                    if method.upper() == "GET":
                        resp = requests.get(url, headers=req_headers, params=params, timeout=DEFAULT_TIMEOUT)
                    elif method.upper() == "POST":
                        resp = requests.post(
                            url,
                            headers=req_headers,
                            params=params,
                            json=data,
                            timeout=DEFAULT_TIMEOUT,
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    resp.raise_for_status()
                    return resp.json()
                except requests.exceptions.Timeout as exc:
                    last_err = exc
                    logger.warning("[GMAIL_CLIENT] Request timeout (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, exc)
                except requests.exceptions.RequestException as exc:
                    last_err = exc
                    logger.warning("[GMAIL_CLIENT] Request error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, exc)
            raise last_err or RuntimeError("Gmail API request failed after retries")

    def list_messages(
        self,
        label_ids: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> List[EmailMetadata]:
        """Fetch message metadata (headers only)."""
        params = {"maxResults": max_results}
        if label_ids:
            params["labelIds"] = ",".join(label_ids)
        if query:
            params["q"] = query

        data = self._make_request("GET", "users/me/messages", params=params)
        messages = data.get("messages", [])

        results: List[EmailMetadata] = []
        for msg_summary in messages:
            try:
                metadata = self._get_message_metadata(msg_summary["id"])
                if metadata:
                    results.append(metadata)
            except Exception as exc:
                logger.warning("[GMAIL_CLIENT] Failed to fetch metadata for %s: %s", msg_summary.get("id"), exc)
        return results

    def _get_message_metadata(self, message_id: str) -> Optional[EmailMetadata]:
        """Fetch headers-only metadata for a message."""
        data = self._make_request(
            "GET",
            f"users/me/messages/{message_id}",
            params={"format": "metadata", "metadataHeaders": "From,Subject,Date"},
        )
        payload = data.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        sender = headers.get("from", "Unknown")
        subject = headers.get("subject", "No Subject")
        date_str = headers.get("date", "")
        try:
            date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            date = datetime.now()

        labels = tuple(data.get("labelIds", []))
        return EmailMetadata(
            id=message_id,
            thread_id=data.get("threadId", message_id),
            sender=sender,
            subject=subject,
            date=date,
            labels=labels,
            is_unread="UNREAD" in labels,
        )

    def get_unread_count(self, label_id: str = "INBOX") -> int:
        """Return the number of unread messages in a label."""
        data = self._make_request("GET", "users/me/labels")
        for label in data.get("labels", []):
            if label.get("id") == label_id:
                return label.get("messagesUnread", 0)
        return 0

    def mark_as_read(self, message_id: str) -> bool:
        """Remove UNREAD label from a message."""
        try:
            self._make_request(
                "POST",
                f"users/me/messages/{message_id}/modify",
                data={"removeLabelIds": ["UNREAD"]},
            )
            return True
        except Exception as exc:
            logger.warning("[GMAIL_CLIENT] mark_as_read failed for %s: %s", message_id, exc)
            return False

    def archive_message(self, message_id: str) -> bool:
        """Remove INBOX label (archive)."""
        try:
            self._make_request(
                "POST",
                f"users/me/messages/{message_id}/modify",
                data={"removeLabelIds": ["INBOX"]},
            )
            return True
        except Exception as exc:
            logger.warning("[GMAIL_CLIENT] archive failed for %s: %s", message_id, exc)
            return False

    def spam_message(self, message_id: str) -> bool:
        """Add SPAM label to a message."""
        try:
            self._make_request(
                "POST",
                f"users/me/messages/{message_id}/modify",
                data={"addLabelIds": ["SPAM"]},
            )
            return True
        except Exception as exc:
            logger.warning("[GMAIL_CLIENT] spam failed for %s: %s", message_id, exc)
            return False

    def trash_message(self, message_id: str) -> bool:
        """Move message to trash."""
        try:
            self._make_request("POST", f"users/me/messages/{message_id}/trash")
            return True
        except Exception as exc:
            logger.warning("[GMAIL_CLIENT] trash failed for %s: %s", message_id, exc)
            return False

    def open_message_in_browser(self, message_id: str) -> bool:
        """Open the Gmail web interface for a specific message."""
        url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
        return open_url(url)

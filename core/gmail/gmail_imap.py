"""Gmail IMAP client using App Password authentication.

Connects via IMAP4_SSL to imap.gmail.com using a user-provided App Password.
Returns the same EmailMetadata objects as the REST API client so the widget
layer is backend-agnostic.

Setup for end users:
1. Enable 2-Step Verification on their Google account.
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Enter their email + app password in the SRPSS settings.
"""
from __future__ import annotations

import email as email_lib
import imaplib
import threading
from datetime import datetime
from email.header import decode_header as _decode_header
from email.utils import parsedate_to_datetime
from typing import List, Optional

from core.gmail.gmail_client import EmailMetadata
from core.logging.logger import get_logger
from core.windows.secure_url_launcher import open_url

logger = get_logger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_TIMEOUT = 30


def _decode_header_value(raw: Optional[str]) -> str:
    """Decode a MIME-encoded header into a plain string."""
    if not raw:
        return ""
    parts = _decode_header(raw)
    decoded = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            decoded.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return " ".join(decoded)


def _parse_date(raw: Optional[str]) -> datetime:
    """Parse an email Date header into a datetime, fallback to now()."""
    if not raw:
        return datetime.now()
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return datetime.now()


class GmailImapClient:
    """IMAP-based Gmail client using App Password auth."""

    def __init__(self, email_address: str, app_password: str):
        self._email = email_address
        self._password = app_password
        self._lock = threading.Lock()

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Create and authenticate an IMAP connection."""
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT)
        conn.login(self._email, self._password)
        return conn

    def list_messages(
        self,
        label_ids: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 10,
    ) -> List[EmailMetadata]:
        """Fetch recent message metadata (headers only) via IMAP."""
        mailbox = "INBOX"
        if label_ids:
            first = label_ids[0]
            gmail_label_map = {
                "INBOX": "INBOX",
                "SENT": "[Gmail]/Sent Mail",
                "DRAFT": "[Gmail]/Drafts",
                "SPAM": "[Gmail]/Spam",
                "TRASH": "[Gmail]/Trash",
                "STARRED": "[Gmail]/Starred",
                "IMPORTANT": "[Gmail]/Important",
            }
            mailbox = gmail_label_map.get(first, first)

        with self._lock:
            conn = None
            try:
                conn = self._connect()
                status, _ = conn.select(f'"{mailbox}"', readonly=True)
                if status != "OK":
                    logger.warning("[GMAIL_IMAP] Failed to select mailbox %s", mailbox)
                    return []

                search_criteria = "UNSEEN" if query and "is:unread" in query else "ALL"
                status, data = conn.search(None, search_criteria)
                if status != "OK" or not data[0]:
                    return []

                msg_ids = data[0].split()
                recent_ids = msg_ids[-max_results:]
                recent_ids.reverse()

                results: List[EmailMetadata] = []
                for mid in recent_ids:
                    try:
                        meta = self._fetch_message_metadata(conn, mid)
                        if meta:
                            results.append(meta)
                    except Exception as exc:
                        logger.warning("[GMAIL_IMAP] Failed to fetch msg %s: %s", mid, exc)

                return results
            except imaplib.IMAP4.error as exc:
                logger.error("[GMAIL_IMAP] IMAP error: %s", exc)
                raise
            except Exception as exc:
                logger.error("[GMAIL_IMAP] Connection error: %s", exc)
                raise
            finally:
                if conn:
                    try:
                        conn.logout()
                    except Exception:
                        pass

    def _fetch_message_metadata(
        self, conn: imaplib.IMAP4_SSL, msg_id: bytes
    ) -> Optional[EmailMetadata]:
        """Fetch headers + flags for a single message."""
        status, data = conn.fetch(msg_id, "(FLAGS BODY[HEADER.FIELDS (FROM SUBJECT DATE)] X-GM-MSGID X-GM-THRID X-GM-LABELS)")
        if status != "OK" or not data or not data[0]:
            return None

        raw_flags = b""
        raw_headers = b""
        gmail_msgid = ""
        gmail_thrid = ""
        gmail_labels: tuple = ()

        for part in data:
            if isinstance(part, tuple):
                header_info = part[0] if isinstance(part[0], bytes) else b""
                raw_headers = part[1] if len(part) > 1 and isinstance(part[1], bytes) else b""
                header_str = header_info.decode("utf-8", errors="replace")
                if b"FLAGS" in header_info:
                    import re
                    flags_match = re.search(r"FLAGS \(([^)]*)\)", header_str)
                    if flags_match:
                        raw_flags = flags_match.group(1).encode()
                    msgid_match = re.search(r"X-GM-MSGID (\d+)", header_str)
                    if msgid_match:
                        gmail_msgid = msgid_match.group(1)
                    thrid_match = re.search(r"X-GM-THRID (\d+)", header_str)
                    if thrid_match:
                        gmail_thrid = thrid_match.group(1)
                    labels_match = re.search(r'X-GM-LABELS \(([^)]*)\)', header_str)
                    if labels_match:
                        raw_label_str = labels_match.group(1)
                        gmail_labels = tuple(
                            lbl.strip('"').replace("\\\\", "")
                            for lbl in raw_label_str.split()
                            if lbl
                        )

        msg = email_lib.message_from_bytes(raw_headers)
        sender = _decode_header_value(msg.get("From", "Unknown"))
        subject = _decode_header_value(msg.get("Subject", "No Subject"))
        date = _parse_date(msg.get("Date"))

        is_unread = b"\\Seen" not in raw_flags

        label_list = list(gmail_labels) if gmail_labels else ["INBOX"]
        if is_unread:
            if "UNREAD" not in label_list:
                label_list.append("UNREAD")

        return EmailMetadata(
            id=gmail_msgid or msg_id.decode("utf-8", errors="replace"),
            thread_id=gmail_thrid or gmail_msgid or msg_id.decode("utf-8", errors="replace"),
            sender=sender,
            subject=subject or "No Subject",
            date=date,
            labels=tuple(label_list),
            is_unread=is_unread,
        )

    def get_unread_count(self, label_id: str = "INBOX") -> int:
        """Return the number of unseen messages."""
        with self._lock:
            conn = None
            try:
                conn = self._connect()
                conn.select("INBOX", readonly=True)
                status, data = conn.search(None, "UNSEEN")
                if status == "OK" and data[0]:
                    return len(data[0].split())
                return 0
            except Exception as exc:
                logger.error("[GMAIL_IMAP] Unread count failed: %s", exc)
                return 0
            finally:
                if conn:
                    try:
                        conn.logout()
                    except Exception:
                        pass

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read. Requires message UID or sequence number."""
        logger.warning("[GMAIL_IMAP] mark_as_read not supported via IMAP app password flow for Gmail message ID %s", message_id)
        return False

    def archive_message(self, message_id: str) -> bool:
        """Archive not directly supported via simple IMAP."""
        logger.warning("[GMAIL_IMAP] archive_message not supported via IMAP for Gmail message ID %s", message_id)
        return False

    def spam_message(self, message_id: str) -> bool:
        """Spam not directly supported via simple IMAP."""
        logger.warning("[GMAIL_IMAP] spam_message not supported via IMAP for Gmail message ID %s", message_id)
        return False

    def trash_message(self, message_id: str) -> bool:
        """Trash not directly supported via simple IMAP."""
        logger.warning("[GMAIL_IMAP] trash_message not supported via IMAP for Gmail message ID %s", message_id)
        return False

    def open_message_in_browser(self, message_id: str) -> bool:
        """Open Gmail web UI. Uses numeric Gmail message ID if available."""
        url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
        return open_url(url)

    def test_connection(self) -> bool:
        """Verify credentials by attempting login."""
        conn = None
        try:
            conn = self._connect()
            conn.select("INBOX", readonly=True)
            logger.info("[GMAIL_IMAP] Connection test successful for %s", self._email)
            return True
        except imaplib.IMAP4.error as exc:
            logger.error("[GMAIL_IMAP] Auth failed for %s: %s", self._email, exc)
            return False
        except Exception as exc:
            logger.error("[GMAIL_IMAP] Connection test failed: %s", exc)
            return False
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

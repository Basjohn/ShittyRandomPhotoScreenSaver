"""Gmail IMAP client using App Password authentication.

Connects via IMAP4_SSL to imap.gmail.com using a user-provided App Password.
Returns the same EmailMetadata objects as the REST API client so the widget
layer is backend-agnostic.

Setup for end users:
1. Enable 2-Step Verification on their Google account.
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Enter their email + app password in the SRPSS settings.

Transport contract (Docs/Contracts.md -> Network transports): every blocking
step (lookup, connect, TLS handshake, LOGIN, SELECT, SEARCH, FETCH, STORE,
LOGOUT) is bounded by ``IMAP_TIMEOUT`` per step, and the whole session is
interruptible through a ``core.network.interruptible_socket.SocketInterrupt``:
a retiring Gmail runtime interrupts its sessions (a signal only); the waiting worker
raises at once and closes its own socket instead of waiting for the server.
"""
from __future__ import annotations

import email as email_lib
import imaplib
import re
import ssl
import threading
from datetime import datetime, timezone
from email.header import decode_header as _decode_header
from email.utils import parsedate_to_datetime
from typing import Callable, List, Optional

from core.gmail.gmail_deeplinks import build_open_url, gmail_inbox_url
from core.gmail.gmail_client import EmailMetadata, GmailFetchCancelled
from core.logging.logger import get_logger
from core.network.interruptible_socket import SocketInterrupt
from core.windows.secure_url_launcher import open_url

logger = get_logger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
# Per blocking step (connect, handshake, each server response), never per session.
IMAP_TIMEOUT = 30


class InterruptibleIMAP4_SSL(imaplib.IMAP4):
    """IMAP over TLS whose every wait can be interrupted by the session's ``SocketInterrupt``.

    ``_create_socket`` returns ``SocketInterrupt.open_tls``: a non-blocking TCP connect and TLS through an
    ``SSLObject`` over memory BIOs, so connect, handshake, each read and each write wait on the socket and
    the session's wake socket together, bounded by ``timeout`` per step. The interrupting thread only signals;
    this (the worker) thread raises ``SocketInterrupted`` and closes its own socket (``shutdown``).
    Certificate and hostname checks are exactly ``ssl_context``'s.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        ssl_context: ssl.SSLContext,
        timeout: float,
        interrupt: SocketInterrupt,
        should_continue: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.ssl_context = ssl_context
        self._srpss_interrupt = interrupt
        self._srpss_should_continue = should_continue
        super().__init__(host, port, timeout)

    def _create_socket(self, timeout):
        return self._srpss_interrupt.open_tls(
            self.host, self.port, timeout if timeout else IMAP_TIMEOUT, self.ssl_context,
            should_continue=self._srpss_should_continue,
        )


def _decode_header_value(raw: Optional[str]) -> str:
    """Decode a MIME-encoded header into a plain string.

    ``decode_header`` keeps each fragment's own spacing (an unencoded fragment
    after an encoded word starts with its space, and RFC 2047 drops the space
    between adjacent encoded words), so the fragments join without a separator.
    ``make_header`` applies those rules; a malformed or unknown charset falls
    back to a lenient per-fragment decode.
    """
    if not raw:
        return ""
    from email.header import make_header

    parts = _decode_header(raw)
    try:
        return str(make_header(parts))
    except (LookupError, UnicodeError, ValueError):
        pass
    decoded = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            try:
                decoded.append(fragment.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                decoded.append(fragment.decode("utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return "".join(decoded)


def _parse_date(raw: Optional[str]) -> datetime:
    """Parse an email Date header into an AWARE datetime; fallback to now (UTC).

    ``parsedate_to_datetime`` returns a naive datetime for a ``-0000`` zone (RFC 5322: UTC, local offset unknown);
    it is UTC. Every date must be aware: the widget sorts cached (aware) and fresh dates together, and one naive
    date made that sort raise, leaving the widget stuck on its busy state (7 Nov 2026).
    """
    if not raw:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(raw)
    except Exception:
        return datetime.now(timezone.utc)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class GmailImapClient:
    """IMAP-based Gmail client using App Password auth."""

    # Owners pass a ``SocketInterrupt`` (``interrupt=``) to list_messages and
    # the message actions and interrupt it when they retire.
    supports_session_interrupt = True

    def __init__(self, email_address: str, app_password: str):
        self._email = email_address
        self._password = app_password
        self._lock = threading.Lock()
        self._supports_gmail_extensions = False

    def _connect(
        self,
        should_cancel: Optional[Callable[[], bool]] = None,
        interrupt: Optional[SocketInterrupt] = None,
    ) -> imaplib.IMAP4_SSL:
        """Create and authenticate an IMAP connection.

        ``imaplib`` would resolve the host with an unbounded ``getaddrinfo``;
        the connection resolves it through ``core/network`` instead (bounded,
        cancelled with the caller's fence, the interrupt and at process exit).
        Every socket the session opens is bound to ``interrupt``.
        """
        from core.network.bounded_dns import DnsLookupError
        from core.network.tls import verified_client_context

        if interrupt is None:
            interrupt = SocketInterrupt()
        should_continue = (
            (lambda: not should_cancel()) if should_cancel is not None else None
        )
        try:
            # Without a context imaplib uses an unverified one (no certificate
            # or hostname check) and the app password would go to any
            # interceptor.
            conn = InterruptibleIMAP4_SSL(
                IMAP_HOST, IMAP_PORT, timeout=IMAP_TIMEOUT,
                ssl_context=verified_client_context(),
                interrupt=interrupt,
                should_continue=should_continue,
            )
        except DnsLookupError:
            if should_cancel is not None and should_cancel():
                raise GmailFetchCancelled("imap:connect")
            raise
        try:
            conn.login(self._email, self._password)
            self._supports_gmail_extensions = self._detect_gmail_extensions(conn)
        except BaseException:
            try:
                conn.shutdown()
            except Exception:
                pass
            raise
        return conn

    @staticmethod
    def _session_interrupt(interrupt: Optional[SocketInterrupt]) -> SocketInterrupt:
        return interrupt if interrupt is not None else SocketInterrupt()

    @staticmethod
    def _was_interrupted(
        interrupt: SocketInterrupt, should_cancel: Optional[Callable[[], bool]] = None
    ) -> bool:
        if interrupt.interrupted:
            return True
        return bool(should_cancel is not None and should_cancel())

    def _detect_gmail_extensions(self, conn: imaplib.IMAP4_SSL) -> bool:
        """Return whether the server advertises Gmail IMAP extensions."""
        try:
            caps = getattr(conn, "capabilities", ()) or ()
            cap_text = " ".join(
                cap.decode("ascii", errors="ignore") if isinstance(cap, bytes) else str(cap)
                for cap in caps
            )
            if "X-GM-EXT-1" in cap_text.upper():
                return True
            status, data = conn.capability()
            if status == "OK":
                joined = b" ".join(part for part in data if isinstance(part, bytes))
                return b"X-GM-EXT-1" in joined.upper()
        except Exception as exc:
            logger.debug("[GMAIL_IMAP] Capability check failed: %s", exc)
        return False

    def list_messages(
        self,
        label_ids: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 10,
        should_cancel: Optional[Callable[[], bool]] = None,
        interrupt: Optional[SocketInterrupt] = None,
    ) -> List[EmailMetadata]:
        """Fetch recent message metadata (headers only) via IMAP.

        ``should_cancel`` matches the API client contract: a fetch whose owning
        runtime generation has retired stops traversing instead of holding an IO
        worker past the runtime destruction barrier. ``interrupt`` ends a
        blocking step (connect, TLS, LOGIN, FETCH...) the moment its owner
        retires; the fetch then raises ``GmailFetchCancelled``.
        """
        interrupt = self._session_interrupt(interrupt)
        if self._was_interrupted(interrupt, should_cancel):
            interrupt.release()
            raise GmailFetchCancelled("imap:list_messages")
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
                conn = self._connect(should_cancel, interrupt)
                status, _ = conn.select(f'"{mailbox}"', readonly=True)
                if status != "OK":
                    logger.warning("[GMAIL_IMAP] Failed to select mailbox %s", mailbox)
                    return []

                search_criteria = "UNSEEN" if query and "is:unread" in query else "ALL"
                status, data = conn.uid("SEARCH", None, search_criteria)
                if status != "OK" or not data[0]:
                    return []

                msg_ids = data[0].split()
                recent_ids = msg_ids[-max_results:]
                recent_ids.reverse()

                results: List[EmailMetadata] = []
                failed_ids: List[str] = []
                for mid in recent_ids:
                    if self._was_interrupted(interrupt, should_cancel):
                        raise GmailFetchCancelled("imap:list_messages")
                    try:
                        meta = self._fetch_message_metadata(conn, mid)
                        if meta:
                            results.append(meta)
                    except GmailFetchCancelled:
                        raise
                    except Exception as exc:
                        if interrupt.interrupted:
                            raise GmailFetchCancelled("imap:list_messages") from exc
                        failed_ids.append(
                            mid.decode("ascii", errors="replace") if isinstance(mid, bytes) else str(mid)
                        )
                        logger.warning("[GMAIL_IMAP] Failed to fetch msg %s: %s", mid, exc)

                if failed_ids:
                    raise RuntimeError(
                        "IMAP partial fetch failure for UIDs: " + ", ".join(failed_ids)
                    )

                return results
            except GmailFetchCancelled:
                raise
            except Exception as exc:
                if interrupt.interrupted:
                    raise GmailFetchCancelled("imap:list_messages") from exc
                if isinstance(exc, imaplib.IMAP4.error):
                    logger.error("[GMAIL_IMAP] IMAP error: %s", exc)
                else:
                    logger.error("[GMAIL_IMAP] Connection error: %s", exc)
                raise
            finally:
                self._end_session(conn, interrupt)

    @staticmethod
    def _end_session(conn: Optional[imaplib.IMAP4_SSL], interrupt: SocketInterrupt) -> None:
        """LOGOUT unless interrupted (the socket is already closed), then release."""
        try:
            if conn is not None:
                if interrupt.interrupted:
                    try:
                        conn.shutdown()
                    except Exception:
                        pass
                else:
                    try:
                        conn.logout()
                    except Exception:
                        pass
        finally:
            interrupt.release()

    def _fetch_message_metadata(
        self, conn: imaplib.IMAP4_SSL, msg_id: bytes
    ) -> Optional[EmailMetadata]:
        """Fetch headers + flags for a single message."""
        fetch_parts = "FLAGS BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]"
        if self._supports_gmail_extensions:
            fetch_parts += " X-GM-MSGID X-GM-THRID X-GM-LABELS"
        try:
            status, data = conn.uid("FETCH", msg_id, f"({fetch_parts})")
        except (AttributeError, TypeError):
            status, data = conn.fetch(msg_id, f"({fetch_parts})")
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
        rfc822_message_id = msg.get("Message-ID")

        is_unread = b"\\Seen" not in raw_flags

        label_list = list(gmail_labels) if gmail_labels else ["INBOX"]
        if is_unread:
            if "UNREAD" not in label_list:
                label_list.append("UNREAD")

        meta = EmailMetadata(
            id=gmail_msgid or msg_id.decode("utf-8", errors="replace"),
            thread_id=gmail_thrid or gmail_msgid or msg_id.decode("utf-8", errors="replace"),
            sender=sender,
            subject=subject or "No Subject",
            date=date,
            labels=tuple(label_list),
            is_unread=is_unread,
            provider="gmail" if self._supports_gmail_extensions else "imap",
            account_email=self._email,
            imap_uid=msg_id.decode("utf-8", errors="replace"),
            rfc822_message_id=rfc822_message_id,
            gmail_thread_id=gmail_thrid or None,
            gmail_message_id=gmail_msgid or None,
        )
        if self._supports_gmail_extensions:
            return EmailMetadata(
                id=meta.id,
                thread_id=meta.thread_id,
                sender=meta.sender,
                subject=meta.subject,
                date=meta.date,
                labels=meta.labels,
                is_unread=meta.is_unread,
                provider=meta.provider,
                account_email=meta.account_email,
                imap_uid=meta.imap_uid,
                rfc822_message_id=meta.rfc822_message_id,
                gmail_thread_id=meta.gmail_thread_id,
                gmail_message_id=meta.gmail_message_id,
                open_url=build_open_url(meta),
            )
        return meta

    def get_unread_count(
        self, label_id: str = "INBOX", *, interrupt: Optional[SocketInterrupt] = None
    ) -> int:
        """Return the number of unseen messages."""
        interrupt = self._session_interrupt(interrupt)
        with self._lock:
            conn = None
            try:
                conn = self._connect(interrupt=interrupt)
                conn.select("INBOX", readonly=True)
                status, data = conn.search(None, "UNSEEN")
                if status == "OK" and data[0]:
                    return len(data[0].split())
                return 0
            except Exception as exc:
                logger.error("[GMAIL_IMAP] Unread count failed: %s", exc)
                return 0
            finally:
                self._end_session(conn, interrupt)

    def _coerce_imap_uid(self, message_id: str) -> str:
        uid = str(message_id or "").strip()
        if not uid or not uid.isdigit():
            raise ValueError("IMAP action requires a numeric UID")
        return uid

    def _run_uid_action(
        self,
        message_id: str,
        action_name: str,
        action: Callable[[imaplib.IMAP4_SSL, str], bool],
        interrupt: Optional[SocketInterrupt] = None,
    ) -> bool:
        """Run a UID-based IMAP action against INBOX."""
        interrupt = self._session_interrupt(interrupt)
        try:
            uid = self._coerce_imap_uid(message_id)
        except ValueError as exc:
            interrupt.release()
            logger.warning("[GMAIL_IMAP] %s skipped: %s", action_name, exc)
            return False

        with self._lock:
            conn = None
            try:
                conn = self._connect(interrupt=interrupt)
                status, _ = conn.select('"INBOX"', readonly=False)
                if status != "OK":
                    logger.warning("[GMAIL_IMAP] %s failed: could not select INBOX", action_name)
                    return False
                return action(conn, uid)
            except Exception as exc:
                logger.warning("[GMAIL_IMAP] %s failed for UID %s: %s", action_name, uid, exc)
                return False
            finally:
                self._end_session(conn, interrupt)

    @staticmethod
    def _uid_store(conn: imaplib.IMAP4_SSL, uid: str, operation: str, flags: str) -> bool:
        status, _ = conn.uid("STORE", uid, operation, flags)
        return status == "OK"

    @staticmethod
    def _uid_move(conn: imaplib.IMAP4_SSL, uid: str, mailbox: str) -> bool:
        status, _ = conn.uid("MOVE", uid, mailbox)
        return status == "OK"

    def mark_as_read(self, message_id: str, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Mark a message as read using its IMAP UID."""
        return self._run_uid_action(
            message_id,
            "mark_as_read",
            lambda conn, uid: self._uid_store(conn, uid, "+FLAGS", r"(\Seen)"),
            interrupt,
        )

    def mark_as_unread(self, message_id: str, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Mark a message as unread using its IMAP UID."""
        return self._run_uid_action(
            message_id,
            "mark_as_unread",
            lambda conn, uid: self._uid_store(conn, uid, "-FLAGS", r"(\Seen)"),
            interrupt,
        )

    def archive_message(self, message_id: str, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Archive a Gmail IMAP message by removing the Inbox label."""
        def _archive(conn: imaplib.IMAP4_SSL, uid: str) -> bool:
            # Gmail treats labels as IMAP folders. Archiving is the removal of
            # the Inbox label; moving to All Mail is mailbox-name dependent and
            # can report success without matching Gmail's Archive button.
            removed = self._uid_store(conn, uid, "-X-GM-LABELS", r"(\Inbox)")
            if removed:
                return True
            return self._uid_move(conn, uid, '"[Gmail]/All Mail"')

        return self._run_uid_action(
            message_id,
            "archive_message",
            _archive,
            interrupt,
        )

    def spam_message(self, message_id: str, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Move a Gmail IMAP message to Spam via Gmail labels."""
        def _spam(conn: imaplib.IMAP4_SSL, uid: str) -> bool:
            added = self._uid_store(conn, uid, "+X-GM-LABELS", r"(\Spam)")
            removed = self._uid_store(conn, uid, "-X-GM-LABELS", r"(\Inbox)")
            return added and removed

        return self._run_uid_action(message_id, "spam_message", _spam, interrupt)

    def trash_message(self, message_id: str, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Move a Gmail IMAP message to Trash via Gmail labels."""
        def _trash(conn: imaplib.IMAP4_SSL, uid: str) -> bool:
            added = self._uid_store(conn, uid, "+X-GM-LABELS", r"(\Trash)")
            removed = self._uid_store(conn, uid, "-X-GM-LABELS", r"(\Inbox)")
            return added and removed

        return self._run_uid_action(message_id, "trash_message", _trash, interrupt)

    def open_message_in_browser(self, message_id: str) -> bool:
        """Open Gmail inbox as a fallback for IMAP messages."""
        return open_url(gmail_inbox_url(), source="gmail:inbox")

    def test_connection(self, *, interrupt: Optional[SocketInterrupt] = None) -> bool:
        """Verify credentials by attempting login."""
        interrupt = self._session_interrupt(interrupt)
        conn = None
        try:
            conn = self._connect(interrupt=interrupt)
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
            self._end_session(conn, interrupt)

"""Gmail web URL builders for metadata-only message links."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote


GMAIL_WEB_BASE = "https://mail.google.com/mail/u"


def _clean_account_slot(account_slot: str) -> str:
    value = str(account_slot or "0").strip()
    return value if value.isdigit() else "0"


def gmail_thread_url(
    thread_id_decimal: str,
    account_slot: str = "0",
    mailbox: str = "all",
) -> str:
    """Build a Gmail conversation URL from decimal X-GM-THRID."""
    thread_hex = format(int(str(thread_id_decimal).strip()), "x")
    slot = _clean_account_slot(account_slot)
    box = str(mailbox or "all").strip().strip("#/") or "all"
    return f"{GMAIL_WEB_BASE}/{slot}/#{box}/{thread_hex}"


def gmail_message_id_search_url(
    rfc822_message_id: str,
    account_slot: str = "0",
) -> str:
    """Build a Gmail search URL for an RFC Message-ID fallback."""
    msg_id = str(rfc822_message_id or "").strip().strip("<>")
    query = quote(f"rfc822msgid:{msg_id}", safe=":")
    slot = _clean_account_slot(account_slot)
    return f"{GMAIL_WEB_BASE}/{slot}/#search/{query}"


def gmail_inbox_url(account_slot: str = "0") -> str:
    """Build the Gmail inbox URL for the configured browser account slot."""
    return f"{GMAIL_WEB_BASE}/{_clean_account_slot(account_slot)}/#inbox"


def build_open_url(meta: Any, account_slot: str = "0") -> Optional[str]:
    """Build the best Gmail web URL from metadata fields, if available."""
    existing = getattr(meta, "open_url", None)
    if existing:
        return str(existing)

    provider = str(getattr(meta, "provider", "") or "").lower()
    gmail_thread_id = getattr(meta, "gmail_thread_id", None)
    if gmail_thread_id:
        try:
            return gmail_thread_url(str(gmail_thread_id), account_slot=account_slot)
        except (TypeError, ValueError):
            return None

    message_id = getattr(meta, "rfc822_message_id", None)
    if message_id and provider in {"gmail", "imap_gmail"}:
        return gmail_message_id_search_url(str(message_id), account_slot=account_slot)

    return None

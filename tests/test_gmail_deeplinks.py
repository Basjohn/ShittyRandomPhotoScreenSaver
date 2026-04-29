"""Tests for Gmail web deep-link helpers."""
from __future__ import annotations

from datetime import datetime


def test_gmail_thread_url_converts_decimal_to_hex() -> None:
    from core.gmail.gmail_deeplinks import gmail_thread_url

    url = gmail_thread_url("1372213338078123456")

    assert url == "https://mail.google.com/mail/u/0/#all/130b14c2bc3315c0"
    assert "1372213338078123456" not in url


def test_gmail_message_id_search_url_strips_and_encodes() -> None:
    from core.gmail.gmail_deeplinks import gmail_message_id_search_url

    url = gmail_message_id_search_url("<abc+def@example.com>", account_slot="1")

    assert url == "https://mail.google.com/mail/u/1/#search/rfc822msgid:abc%2Bdef%40example.com"
    assert "<" not in url
    assert ">" not in url


def test_build_open_url_uses_thread_before_message_id() -> None:
    from core.gmail.gmail_client import EmailMetadata
    from core.gmail.gmail_deeplinks import build_open_url

    meta = EmailMetadata(
        id="msg",
        thread_id="thread",
        sender="fake_sender@example.com",
        subject="Fake Subject",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=False,
        provider="gmail",
        rfc822_message_id="<abc@example.com>",
        gmail_thread_id="1372213338078123456",
    )

    assert build_open_url(meta, account_slot="2") == (
        "https://mail.google.com/mail/u/2/#all/130b14c2bc3315c0"
    )


def test_build_open_url_non_gmail_without_thread_returns_none() -> None:
    from core.gmail.gmail_client import EmailMetadata
    from core.gmail.gmail_deeplinks import build_open_url

    meta = EmailMetadata(
        id="msg",
        thread_id="thread",
        sender="fake_sender@example.com",
        subject="Fake Subject",
        date=datetime.now(),
        labels=("INBOX",),
        is_unread=False,
        provider="imap",
        rfc822_message_id="<abc@example.com>",
    )

    assert build_open_url(meta) is None


def test_imap_metadata_builds_gmail_open_url() -> None:
    from core.gmail.gmail_imap import GmailImapClient

    class FakeConn:
        def fetch(self, msg_id, _query):
            header_info = (
                b"1 (FLAGS (\\Seen) X-GM-MSGID 123 X-GM-THRID "
                b"1372213338078123456 X-GM-LABELS (\\Inbox))"
            )
            headers = (
                b"From: fake_sender@example.com\r\n"
                b"Subject: Fake Subject\r\n"
                b"Date: Tue, 28 Apr 2026 12:00:00 +0000\r\n"
                b"Message-ID: <abc@example.com>\r\n\r\n"
            )
            return "OK", [(header_info, headers)]

    client = GmailImapClient("fake_user@gmail.com", "fake_app_password")
    client._supports_gmail_extensions = True

    meta = client._fetch_message_metadata(FakeConn(), b"42")

    assert meta is not None
    assert meta.gmail_thread_id == "1372213338078123456"
    assert meta.open_url == "https://mail.google.com/mail/u/0/#all/130b14c2bc3315c0"
    assert meta.provider == "gmail"


def test_imap_metadata_without_gmail_extensions_has_no_open_url() -> None:
    from core.gmail.gmail_imap import GmailImapClient

    class FakeConn:
        def fetch(self, msg_id, _query):
            headers = (
                b"From: fake_sender@example.com\r\n"
                b"Subject: Fake Subject\r\n"
                b"Date: Tue, 28 Apr 2026 12:00:00 +0000\r\n"
                b"Message-ID: <abc@example.com>\r\n\r\n"
            )
            return "OK", [(b"1 (FLAGS ())", headers)]

    client = GmailImapClient("fake_user@example.com", "fake_app_password")
    client._supports_gmail_extensions = False

    meta = client._fetch_message_metadata(FakeConn(), b"42")

    assert meta is not None
    assert meta.provider == "imap"
    assert meta.open_url is None

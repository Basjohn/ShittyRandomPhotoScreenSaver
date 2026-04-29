"""Focused tests for Gmail IMAP action helpers."""


class FakeImapActionConn:
    def __init__(self):
        self.selected = []
        self.uid_calls = []
        self.logged_out = False

    def select(self, mailbox, readonly=False):
        self.selected.append((mailbox, readonly))
        return "OK", [b""]

    def uid(self, command, uid, operation, flags):
        self.uid_calls.append((command, uid, operation, flags))
        return "OK", [b""]

    def logout(self):
        self.logged_out = True


def test_imap_mark_as_read_uses_uid_store(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    conn = FakeImapActionConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")
    monkeypatch.setattr(client, "_connect", lambda: conn)

    assert client.mark_as_read("42") is True
    assert conn.selected == [('"INBOX"', False)]
    assert conn.uid_calls == [("STORE", "42", "+FLAGS", r"(\Seen)")]
    assert conn.logged_out is True


def test_imap_archive_removes_inbox_label(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    conn = FakeImapActionConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")
    monkeypatch.setattr(client, "_connect", lambda: conn)

    assert client.archive_message("42") is True
    assert conn.uid_calls == [("STORE", "42", "-X-GM-LABELS", r"(\Inbox)")]


def test_imap_spam_and_trash_use_gmail_labels(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    spam_conn = FakeImapActionConn()
    trash_conn = FakeImapActionConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")

    monkeypatch.setattr(client, "_connect", lambda: spam_conn)
    assert client.spam_message("42") is True
    assert spam_conn.uid_calls == [
        ("STORE", "42", "+X-GM-LABELS", r"(\Spam)"),
        ("STORE", "42", "-X-GM-LABELS", r"(\Inbox)"),
    ]

    monkeypatch.setattr(client, "_connect", lambda: trash_conn)
    assert client.trash_message("42") is True
    assert trash_conn.uid_calls == [
        ("STORE", "42", "+X-GM-LABELS", r"(\Trash)"),
        ("STORE", "42", "-X-GM-LABELS", r"(\Inbox)"),
    ]


def test_imap_action_rejects_non_numeric_uid(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    client = GmailImapClient("fake@example.com", "fake_app_password")
    monkeypatch.setattr(client, "_connect", lambda: (_ for _ in ()).throw(AssertionError("should not connect")))

    assert client.archive_message("gmail-message-id") is False


def test_imap_metadata_fetch_prefers_uid_fetch() -> None:
    from core.gmail.gmail_imap import GmailImapClient

    class FakeUidFetchConn:
        def __init__(self):
            self.uid_calls = []

        def uid(self, command, uid, query):
            self.uid_calls.append((command, uid, query))
            headers = (
                b"From: fake_sender@example.com\r\n"
                b"Subject: Fake Subject\r\n"
                b"Date: Tue, 01 Jan 2024 12:00:00 +0000\r\n"
                b"Message-ID: <fake@example.com>\r\n\r\n"
            )
            return "OK", [(b"42 (FLAGS ())", headers)]

    conn = FakeUidFetchConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")

    meta = client._fetch_message_metadata(conn, b"42")

    assert meta is not None
    assert meta.imap_uid == "42"
    assert conn.uid_calls[0][0] == "FETCH"

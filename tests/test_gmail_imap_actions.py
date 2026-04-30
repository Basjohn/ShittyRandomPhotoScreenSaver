"""Focused tests for Gmail IMAP action helpers."""


class FakeImapActionConn:
    def __init__(self):
        self.selected = []
        self.uid_calls = []
        self.logged_out = False

    def select(self, mailbox, readonly=False):
        self.selected.append((mailbox, readonly))
        return "OK", [b""]

    def uid(self, command, uid, operation, flags=None):
        if flags is None:
            self.uid_calls.append((command, uid, operation))
        else:
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


def test_imap_mark_as_unread_uses_uid_store(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    conn = FakeImapActionConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")
    monkeypatch.setattr(client, "_connect", lambda: conn)

    assert client.mark_as_unread("42") is True
    assert conn.selected == [('"INBOX"', False)]
    assert conn.uid_calls == [("STORE", "42", "-FLAGS", r"(\Seen)")]
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


def test_imap_list_messages_preserves_recent_uid_order(monkeypatch) -> None:
    from core.gmail.gmail_imap import GmailImapClient

    class FakeListConn:
        def __init__(self):
            self.fetch_uids = []
            self.logged_out = False

        def capability(self):
            return "OK", [b""]

        def select(self, mailbox, readonly=True):
            assert mailbox == '"INBOX"'
            assert readonly is True
            return "OK", [b""]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [b"1 2 3 4 5 6 7 8 9 10"]
            if command == "FETCH":
                uid = args[0].decode("ascii") if isinstance(args[0], bytes) else str(args[0])
                self.fetch_uids.append(uid)
                dates = {"9": "Mon, 13 Jan 2025 12:00:00 +0000", "10": "Tue, 14 Jan 2025 12:00:00 +0000"}
                date = dates.get(uid, "Wed, 01 Jan 2025 12:00:00 +0000")
                headers = (
                    b"From: fake_sender@example.com\r\n"
                    + f"Subject: Message {uid}\r\n".encode("ascii")
                    + f"Date: {date}\r\n".encode("ascii")
                    + f"Message-ID: <fake-{uid}@example.com>\r\n\r\n".encode("ascii")
                )
                return "OK", [(f"{uid} (FLAGS (\\Seen))".encode("ascii"), headers)]
            raise AssertionError(f"unexpected command {command}")

        def logout(self):
            self.logged_out = True

    conn = FakeListConn()
    client = GmailImapClient("fake@example.com", "fake_app_password")
    monkeypatch.setattr(client, "_connect", lambda: conn)

    messages = client.list_messages(label_ids=["INBOX"], max_results=2)

    assert [message.subject for message in messages] == ["Message 10", "Message 9"]
    assert conn.fetch_uids == ["10", "9"]
    assert conn.logged_out is True


def test_backend_tests_supplied_imap_credentials_without_saving(monkeypatch, tmp_path) -> None:
    from core.gmail.gmail_backend import GmailBackend

    calls = []

    class FakeImapClient:
        def __init__(self, email, password):
            calls.append((email, password))

        def test_connection(self):
            return True

    monkeypatch.setattr("core.gmail.gmail_backend.GmailImapClient", FakeImapClient)

    backend = GmailBackend()
    backend._app_data = tmp_path
    backend._imap_creds_path = tmp_path / "gmail_imap_creds.enc"
    backend._imap_email = None
    backend._imap_password = None

    assert backend.test_imap_credentials("fake@example.com", "fake_app_password") is True
    assert calls == [("fake@example.com", "fake_app_password")]
    assert backend._imap_email is None
    assert backend._imap_password is None
    assert not backend._imap_creds_path.exists()

"""Qt-free Gmail cache preparation and persistence tests."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
import threading

from core.gmail.gmail_client import EmailMetadata
from core.gmail.gmail_preparation import (
    deserialize_email_cache,
    load_gmail_startup_snapshot,
    reserve_gmail_cache_write,
    serialize_email_cache,
    write_gmail_email_cache,
)


def _email(message_id: str, *, minute: int = 0) -> EmailMetadata:
    return EmailMetadata(
        id=message_id,
        thread_id=f"thread-{message_id}",
        sender="Sender <sender@example.com>",
        subject=f"Subject {message_id}",
        date=datetime(2026, 8, 11, 12, minute),
        labels=("INBOX",),
        is_unread=False,
    )


def test_gmail_startup_snapshot_preserves_order_and_filters_invalid_rows(tmp_path):
    cache_path = tmp_path / "gmail_cache.json"
    first = json.loads(serialize_email_cache([_email("first")]))[0]
    second = json.loads(serialize_email_cache([_email("second", minute=1)]))[0]
    cache_path.write_text(
        json.dumps([first, {"id": "incomplete"}, "not-an-object", second]),
        encoding="utf-8",
    )

    snapshot = load_gmail_startup_snapshot(cache_path, max_age_hours=24)

    assert snapshot.state == "fresh"
    assert snapshot.cache_timestamp is not None
    assert [email.id for email in snapshot.emails] == ["first", "second"]


def test_gmail_invalid_cache_root_forces_refresh_timestamp_miss(tmp_path):
    cache_path = tmp_path / "gmail_cache.json"
    cache_path.write_text('{"unexpected": "object"}', encoding="utf-8")

    snapshot = load_gmail_startup_snapshot(cache_path, max_age_hours=24)

    assert snapshot.state == "invalid"
    assert snapshot.emails == ()
    assert snapshot.cache_timestamp is None


def test_gmail_stale_cache_retains_timestamp_but_not_content(tmp_path):
    cache_path = tmp_path / "gmail_cache.json"
    cache_path.write_text(serialize_email_cache([_email("old")]), encoding="utf-8")
    stale_time = datetime.now() - timedelta(hours=25)
    os.utime(cache_path, (stale_time.timestamp(), stale_time.timestamp()))

    snapshot = load_gmail_startup_snapshot(cache_path, max_age_hours=24)

    assert snapshot.state == "stale"
    assert snapshot.emails == ()
    assert snapshot.cache_timestamp is not None
    assert snapshot.cache_timestamp <= datetime.now() - timedelta(hours=24)


def test_gmail_concurrent_cache_writes_leave_one_complete_atomic_payload(tmp_path):
    cache_path = tmp_path / "gmail_cache.json"
    barrier = threading.Barrier(3)

    def _write(message_id: str) -> None:
        barrier.wait()
        assert write_gmail_email_cache(cache_path, [_email(message_id)]) is True

    first = threading.Thread(target=_write, args=("first",))
    second = threading.Thread(target=_write, args=("second",))
    first.start()
    second.start()
    barrier.wait()
    first.join()
    second.join()

    persisted = deserialize_email_cache(cache_path.read_text(encoding="utf-8"))
    assert [email.id for email in persisted] in (["first"], ["second"])
    assert list(tmp_path.glob("*.tmp")) == []


def test_gmail_reserved_write_identity_rejects_out_of_order_completion(tmp_path):
    cache_path = tmp_path / "gmail_cache.json"
    older_id = reserve_gmail_cache_write(cache_path)
    newer_id = reserve_gmail_cache_write(cache_path)

    assert write_gmail_email_cache(
        cache_path,
        [_email("newer")],
        write_id=newer_id,
    ) is True
    assert write_gmail_email_cache(
        cache_path,
        [_email("older")],
        write_id=older_id,
    ) is False

    persisted = deserialize_email_cache(cache_path.read_text(encoding="utf-8"))
    assert [email.id for email in persisted] == ["newer"]

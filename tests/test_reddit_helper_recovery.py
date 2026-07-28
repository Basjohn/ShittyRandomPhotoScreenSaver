from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from unittest.mock import patch

from core.windows import reddit_helper_bridge as bridge
from core.windows import reddit_helper_installer as installer
from core.windows.reddit_helper_storage import (
    HELPER_LOG_MAX_BYTES,
    HELPER_LOG_SEGMENT_MAX_BYTES,
    QUEUE_ENTRY_MAX_BYTES,
)
from helpers import reddit_helper_worker as worker


def _reset_bridge(monkeypatch, root: Path) -> Path:
    queue = root / "url_queue"
    monkeypatch.setattr(bridge, "_BASE_DIR", root)
    monkeypatch.setattr(bridge, "_QUEUE_DIR", queue)
    monkeypatch.setattr(bridge, "_SIGNAL_DIR", root / "helper_signals")
    monkeypatch.setattr(bridge, "_SPOOL_READY", False)
    monkeypatch.setattr(bridge, "_SPOOL_LAST_PROBE", 0.0)
    return queue


def test_bridge_uses_unique_probe_when_diagnostic_marker_is_unwritable(monkeypatch, tmp_path):
    queue = _reset_bridge(monkeypatch, tmp_path)
    queue.mkdir()
    (queue / ".bridge_ready").mkdir()

    assert bridge.is_bridge_available() is True
    assert bridge.enqueue_url("https://www.reddit.com/r/test/?secret=discarded") is True

    entries = list(queue.glob("*.json"))
    assert len(entries) == 1
    payload = json.loads(entries[0].read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert not list(queue.glob(".bridge_probe_*"))


def test_bridge_rejects_oversized_entry_and_invalidates_cached_probe(monkeypatch, tmp_path):
    queue = _reset_bridge(monkeypatch, tmp_path)

    assert bridge.enqueue_url("https://example.invalid/" + ("x" * QUEUE_ENTRY_MAX_BYTES)) is False
    assert bridge._SPOOL_READY is False
    assert not list(queue.glob("*.json"))


def test_worker_log_and_breadcrumb_log_never_exceed_one_megabyte(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    assert worker.configure_logging(log_dir, verbose=False) is True
    for _ in range(90):
        logging.info("x" * (16 * 1024))
    logging.shutdown()

    monkeypatch.setenv("SRPSS_ALLOW_TEST_HELPER_BREADCRUMBS", "1")
    monkeypatch.setattr(installer, "BASE_DIR", tmp_path)
    for _ in range(90):
        installer._log_helper_event("y" * (16 * 1024))

    for name in ("reddit_helper.log", "scr_helper.log"):
        segments = list(log_dir.glob(f"{name}*"))
        assert all(path.stat().st_size <= HELPER_LOG_SEGMENT_MAX_BYTES for path in segments)
        assert sum(path.stat().st_size for path in segments) <= HELPER_LOG_MAX_BYTES


def test_log_initialization_failure_does_not_block_queue_processing(tmp_path):
    blocked_log_dir = tmp_path / "not_a_directory"
    blocked_log_dir.write_text("occupied", encoding="utf-8")
    queue = tmp_path / "queue"
    signal_dir = tmp_path / "signals"
    queue.mkdir()
    signal_dir.mkdir()
    (queue / "entry.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "entry",
                "action": "open_url",
                "url": "https://www.reddit.com/r/test/",
            }
        ),
        encoding="utf-8",
    )

    assert worker.configure_logging(blocked_log_dir, verbose=False) is False
    with patch.object(worker, "open_url", return_value=True), patch.object(
        worker,
        "bring_browser_foreground",
        return_value=True,
    ):
        processed, opened = worker.process_queue(queue, 10, signal_dir)

    assert (processed, opened) == (1, True)
    assert not (queue / "entry.json").exists()
    assert (queue / "entry.receipt").exists()


def test_reconcile_recovers_valid_tmp_and_prunes_old_terminal_entries(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    (queue / "pending.tmp").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "token": "recovered",
                "action": "open_url",
                "url": "https://www.reddit.com/r/test/",
            }
        ),
        encoding="utf-8",
    )
    stale = queue / "old.failed"
    stale.write_text("last resort", encoding="utf-8")
    old = time.time() - worker.QUEUE_TERMINAL_MAX_AGE_SECONDS - 60
    os.utime(stale, (old, old))

    result = worker.reconcile_queue(queue)

    assert result == {"recovered": 1, "quarantined": 0, "pruned": 1}
    assert (queue / "recovered.json").exists()
    assert not stale.exists()


def test_oversized_and_unknown_entries_are_quarantined_without_launch(tmp_path):
    queue = tmp_path / "queue"
    signal_dir = tmp_path / "signals"
    queue.mkdir()
    signal_dir.mkdir()
    (queue / "oversized.json").write_bytes(b"{" + (b"x" * QUEUE_ENTRY_MAX_BYTES) + b"}")
    (queue / "unknown.json").write_text(
        json.dumps({"schema_version": 1, "token": "unknown", "action": "run_anything"}),
        encoding="utf-8",
    )

    with patch.object(worker, "open_url") as open_mock:
        processed, opened = worker.process_queue(queue, 10, signal_dir)

    assert (processed, opened) == (0, False)
    open_mock.assert_not_called()
    assert len(list(queue.glob("*.corrupt"))) == 2

"""Tests for the reddit_helper_worker watcher mode.

Validates queue processing, corrupt file handling, and the continuous
polling loop added in the Reddit Helper Refactor.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from helpers.reddit_helper_worker import (
    HEARTBEAT_FILE_NAME,
    iter_queue_files,
    process_queue,
    _run_watcher,
)


class TestQueueProcessing:
    """Test one-shot queue processing logic."""

    def test_iter_queue_files_returns_json_and_retry_sorted(self, tmp_path: Path):
        """iter_queue_files yields canonical queue files in sorted order."""
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "c.retry").write_text("{}", encoding="utf-8")
        (tmp_path / "c.txt").write_text("{}", encoding="utf-8")

        names = [p.name for p in iter_queue_files(tmp_path)]
        assert names == ["a.json", "b.json", "c.retry"]

    def test_process_queue_opens_url(self, tmp_path: Path):
        """process_queue should call open_url for open_url actions."""
        entry = {"action": "open_url", "url": "https://example.com/test"}
        (tmp_path / "entry.json").write_text(json.dumps(entry), encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        opened: list[str] = []

        with patch("helpers.reddit_helper_worker.open_url") as mock_open, \
             patch("helpers.reddit_helper_worker.bring_browser_foreground", return_value=False):
            mock_open.side_effect = lambda url: (opened.append(url) or True)
            processed = process_queue(tmp_path, max_batch=10, signal_dir=signal_dir)

        assert processed == 1
        assert opened == ["https://example.com/test"]
        assert not (tmp_path / "entry.json").exists()

    def test_process_queue_renames_corrupt(self, tmp_path: Path):
        """Corrupt JSON files should be renamed to .corrupt."""
        (tmp_path / "bad.json").write_text("NOT JSON!", encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        processed = process_queue(tmp_path, max_batch=10, signal_dir=signal_dir)

        assert processed == 0
        assert not (tmp_path / "bad.json").exists()
        assert (tmp_path / "bad.corrupt").exists()

    def test_process_queue_rewrites_failures_to_canonical_json_retry(self, tmp_path: Path):
        """Failed actions should stay retryable instead of vanishing into .retry files."""
        entry = {"action": "open_url", "url": "https://example.com/fail"}
        entry_path = tmp_path / "entry.retry"
        entry_path.write_text(json.dumps(entry), encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        with patch("helpers.reddit_helper_worker.open_url", return_value=False):
            processed = process_queue(tmp_path, max_batch=10, signal_dir=signal_dir)

        assert processed == 1
        retried_path = tmp_path / "entry.json"
        assert retried_path.exists()
        payload = json.loads(retried_path.read_text(encoding="utf-8"))
        assert payload["retry_count"] == 1
        assert payload["next_attempt_ts"] > time.time()
        assert not entry_path.exists()

    def test_process_queue_expires_old_open_url_entries(self, tmp_path: Path):
        """Very old queued URLs should be quarantined instead of opening later."""
        entry = {
            "action": "open_url",
            "url": "https://example.com/old",
            "timestamp": time.time() - 7200.0,
        }
        entry_path = tmp_path / "old.json"
        entry_path.write_text(json.dumps(entry), encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        with patch("helpers.reddit_helper_worker.open_url") as mock_open:
            processed = process_queue(tmp_path, max_batch=10, signal_dir=signal_dir)

        assert processed == 1
        assert not entry_path.exists()
        assert (tmp_path / "old.expired").exists()
        mock_open.assert_not_called()

    def test_process_queue_respects_max_batch(self, tmp_path: Path):
        """process_queue should stop after max_batch entries."""
        for i in range(5):
            entry = {"action": "open_url", "url": f"https://example.com/{i}"}
            (tmp_path / f"{i:03d}.json").write_text(json.dumps(entry), encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        with patch("helpers.reddit_helper_worker.open_url", return_value=True), \
             patch("helpers.reddit_helper_worker.bring_browser_foreground", return_value=False):
            processed = process_queue(tmp_path, max_batch=3, signal_dir=signal_dir)

        assert processed == 3
        remaining = list(tmp_path.glob("*.json"))
        assert len(remaining) == 2

    def test_process_queue_handles_empty_dir(self, tmp_path: Path):
        """Empty queue directory should process 0 entries without error."""
        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        processed = process_queue(tmp_path, max_batch=10, signal_dir=signal_dir)
        assert processed == 0


class TestWatcherMode:
    """Test the continuous watcher loop."""

    def test_watcher_processes_and_stops(self, tmp_path: Path):
        """Watcher should process files and exit when _watcher_running is cleared."""
        import helpers.reddit_helper_worker as worker

        entry = {"action": "open_url", "url": "https://example.com/watch"}
        (tmp_path / "watch.json").write_text(json.dumps(entry), encoding="utf-8")

        signal_dir = tmp_path / "signals"
        signal_dir.mkdir()

        opened: list[str] = []

        original_running = worker._watcher_running

        def fake_open_url(url: str) -> bool:
            opened.append(url)
            worker._watcher_running = False
            return True

        try:
            worker._watcher_running = True
            with patch("helpers.reddit_helper_worker.open_url", side_effect=fake_open_url), \
                 patch("helpers.reddit_helper_worker.bring_browser_foreground", return_value=False):
                rc = _run_watcher(tmp_path, max_batch=10, signal_dir=signal_dir, poll_interval=0.5)
        finally:
            worker._watcher_running = original_running

        assert rc == 0
        assert opened == ["https://example.com/watch"]
        assert not (tmp_path / "watch.json").exists()
        assert (signal_dir / HEARTBEAT_FILE_NAME).exists()

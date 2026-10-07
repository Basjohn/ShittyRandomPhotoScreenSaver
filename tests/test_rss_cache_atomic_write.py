"""RSS startup index writes must remain atomic and fail denial once."""

import json
from pathlib import Path

import pytest

from sources.rss.cache import RSSCache


def test_pool_state_permission_denial_is_one_create_and_preserves_last_good(tmp_path, monkeypatch, caplog):
    cache = RSSCache(cache_dir=tmp_path)
    cache.state_dir.mkdir()
    original = '{"version":1,"entries":{},"retired":[],"rejected":{}}'
    cache._state_file.write_text(original, encoding="utf-8")
    attempts = []
    path_open = Path.open

    def deny_pool_create(path, mode="r", *args, **kwargs):
        if path.parent == cache.state_dir and path.name.startswith(".pool."):
            attempts.append((path.name, mode))
            raise PermissionError("sandbox denied native temporary creation")
        return path_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_pool_create)
    cache.save_state()
    assert len(attempts) == 1
    assert attempts[0][1] == "x"
    assert cache._state_file.read_text(encoding="utf-8") == original
    assert list(cache.state_dir.glob(".pool.*.tmp")) == []
    assert any("Pool index write failed" in record.message for record in caplog.records)


def test_pool_state_replacement_failure_removes_owned_temp_and_preserves_last_good(tmp_path, monkeypatch):
    cache = RSSCache(cache_dir=tmp_path)
    cache.state_dir.mkdir()
    cache._state_file.write_text("last good", encoding="utf-8")
    attempts = []

    def fail_replace(source, target):
        attempts.append((source, target))
        assert source.is_file()
        raise PermissionError("atomic replacement denied")

    monkeypatch.setattr("sources.rss.cache.os.replace", fail_replace)
    cache.save_state()
    assert len(attempts) == 1
    assert cache._state_file.read_text(encoding="utf-8") == "last good"
    assert list(cache.state_dir.glob(".pool.*.tmp")) == []


def test_pool_state_atomic_success_roundtrips_canonical_payload_without_temporary_debris(tmp_path):
    cache = RSSCache(cache_dir=tmp_path)
    cache._index = {"image.jpg": {"width": 3840, "height": 2160, "fetched": 123.0}}
    cache._retired = {"retired.jpg"}
    cache._rejected = {"key": [0, 0, 123.0]}
    cache.save_state()
    payload = json.loads(cache._state_file.read_text(encoding="utf-8"))
    assert payload == {"version": 1, "entries": cache._index,
                       "retired": ["retired.jpg"], "rejected": cache._rejected}
    assert list(cache.state_dir.glob(".pool.*.tmp")) == []

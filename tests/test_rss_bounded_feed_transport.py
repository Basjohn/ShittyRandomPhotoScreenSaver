from core.feeds.transport import FeedHttpResponse
from sources.rss.downloader import RSSDownloader


def test_legacy_rss_document_fetch_uses_bounded_transport_then_parses_bytes(monkeypatch):
    downloader = RSSDownloader(timeout=7.0)
    calls = []
    payload = b"<rss version='2.0'><channel><title>X</title></channel></rss>"

    def fake_fetch(url, **kwargs):
        calls.append((url, kwargs))
        return FeedHttpResponse("ok", payload, url)

    parsed_inputs = []
    monkeypatch.setattr(downloader._feed_transport, "fetch", fake_fetch)
    monkeypatch.setattr(
        "sources.rss.downloader.feedparser.parse",
        lambda value: parsed_inputs.append(value) or {"entries": []},
    )

    result = downloader.fetch_rss("https://example.test/feed.xml")
    assert result == {"entries": []}
    assert calls == [("https://example.test/feed.xml", {})]
    assert parsed_inputs == [payload]


def test_legacy_rss_shared_transport_keeps_configured_read_timeout():
    downloader = RSSDownloader(timeout=11.5)
    connect_timeout, read_timeout = downloader._feed_transport.timeout
    assert connect_timeout <= 4.0
    assert read_timeout == 11.5


def test_no_legacy_rss_owner_gives_feedparser_a_network_url():
    import ast
    from pathlib import Path

    for relative in (
        "sources/rss/downloader.py",
        "core/process/workers/rss_worker.py",
    ):
        tree = ast.parse(Path(relative).read_text(encoding="utf-8"), filename=relative)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "feedparser"
            and node.func.attr == "parse"
        ]
        assert calls, f"expected a feedparser.parse bytes seam in {relative}"
        for call in calls:
            assert call.args, f"feedparser.parse without payload in {relative}"
            argument = call.args[0]
            # Guard the actual ownership boundary, not comments/docstrings. Legacy
            # network-owned parsing used feed_url/url directly; the bounded path
            # must parse an already-fetched response payload (or equivalent bytes).
            assert not (
                isinstance(argument, ast.Name)
                and argument.id in {"url", "feed_url"}
            ), f"{relative} still hands a network URL directly to feedparser.parse"

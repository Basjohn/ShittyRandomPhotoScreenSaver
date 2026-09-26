"""Feed magnet links: one strict admission rule, validated once per published row."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from core.feeds.magnet import MAX_MAGNET_LENGTH, admitted_magnet_uri
from core.feeds.projection import FeedDisplayRow

HEX = "0123456789abcdef0123456789abcdef01234567"
TRACKER = "udp%3A%2F%2Ftracker.example.org%3A1337%2Fannounce"
VALID = f"magnet:?xt=urn:btih:{HEX}&dn=Release.Name.2026.1080p&tr={TRACKER}"


@pytest.mark.parametrize("uri", [
    VALID,
    f"magnet:?xt=urn:btih:{HEX.upper()}",
    "magnet:?xt=urn:btih:ABCDEFGHIJKLMNOPQRSTUVWXYZ234567",  # base32 v1
    "magnet:?xt=urn:btmh:1220" + "ab" * 32,  # v2
    f"magnet:?dn=Name&xt.1=urn:btih:{HEX}&xt.2=urn:btmh:1220{'cd' * 32}",
    f"  {VALID}  ",
])
def test_real_bittorrent_magnets_are_admitted(uri):
    assert admitted_magnet_uri(uri) == uri.strip()


@pytest.mark.parametrize("uri", [
    "magnet:?xt=urn:btih:abc",  # not an info hash
    "magnet:?dn=Only.A.Name",
    f"magnet:?xt=urn:sha1:{HEX}",
    f"magnet:xt=urn:btih:{HEX}",  # no query marker
    f"magnet://host/?xt=urn:btih:{HEX}",
    f'magnet:?xt=urn:btih:{HEX}&dn=a"b',  # a quote could break command-line quoting
    f"magnet:?xt=urn:btih:{HEX}&dn=a b",
    f"magnet:?xt=urn:btih:{HEX}&dn=a<b>",
    f"magnet:?xt=urn:btih:{HEX}&dn=a\\b",
    f"magnet:?xt=urn:btih:{HEX}&dn=a|b",
    f"magnet:?xt=urn:btih:{HEX}&dn=a^b",
    f"magnet:?xt=urn:btih:{HEX}&dn=100%",  # malformed escape
    f"magnet:?xt=urn:btih:{HEX}#frag",
    f"magnet:?xt=urn:btih:{HEX}&dn=é",
    f"magnet:?xt=urn:btih:{HEX}&dn=a\nb",
    f"magnet:?xt=urn:btih:{HEX}&tr=" + "a" * MAX_MAGNET_LENGTH,
    f"https://example.test/?xt=urn:btih:{HEX}",
    "",
    None,
])
def test_anything_else_is_refused(uri):
    assert admitted_magnet_uri(uri) == ""


def test_card_validates_each_row_once_and_never_on_role_reads_or_clicks(qt_app):
    """Running the cursor down a magnet feed costs nothing in Python: hover is
    QML-only, role reads return the published value and a click is one set
    lookup."""
    from rendering.quick.widgets import feeds

    calls = []
    real = feeds.admitted_magnet_uri

    def counting(value):
        calls.append(value)
        return real(value)

    rows = tuple(
        FeedDisplayRow(str(i), f"Release {i}", "", "", url, None)
        for i, url in enumerate((
            VALID,
            f"magnet:?xt=urn:btih:{'f' * 40}",
            "https://example.test/page",
            "magnet:?xt=urn:btih:abc",
        ))
    )
    with patch.object(feeds, "admitted_magnet_uri", counting):
        model = feeds.FeedRowsModel()
        assert model.replace_rows(rows) is True
        assert len(calls) == 3  # the HTTPS row never reaches the magnet rule
        urls = [model.data(model.index(i), model.UrlRole) for i in range(4)]
        for _ in range(200):
            for i in range(4):
                model.data(model.index(i), model.UrlRole)
            assert model.is_admitted_action(VALID)
            assert not model.is_admitted_action("magnet:?xt=urn:btih:abc")
        assert model.replace_rows(rows) is False  # identical republish: no work
        assert len(calls) == 3
    assert urls == [VALID, f"magnet:?xt=urn:btih:{'f' * 40}", "https://example.test/page", ""]


def test_feed_product_action_opens_a_valid_magnet_and_nothing_malformed():
    from core.widget_product_actions import dispatch_feed_url_product_action

    opened, exited = [], []
    assert dispatch_feed_url_product_action(
        VALID, opener=lambda url: opened.append(url) or True,
        request_saver_exit=lambda: exited.append(True), interactive_build=False,
    ) is True
    assert opened == [VALID] and exited == [True]
    for bad in (f'magnet:?xt=urn:btih:{HEX}&dn=a"b', "magnet:?dn=x", "ms-settings:privacy"):
        assert dispatch_feed_url_product_action(
            bad, opener=lambda url: opened.append(url) or True,
            request_saver_exit=lambda: exited.append(True), interactive_build=False,
        ) is False
    assert opened == [VALID]


def test_secure_helper_admits_the_same_magnets_and_skips_browser_foreground():
    from helpers import reddit_helper_worker as worker

    assert worker._validate_queue_payload({"action": "open_url", "url": VALID})["url"] == VALID
    for bad in ("magnet:?xt=urn:btih:abc", f'magnet:?xt=urn:btih:{HEX}&dn=a"b', "javascript:alert(1)"):
        with pytest.raises(ValueError):
            worker._validate_queue_payload({"action": "open_url", "url": bad})

    with patch.object(worker, "open_url", return_value=True), \
            patch.object(worker, "bring_browser_foreground") as foreground:
        assert worker._handle_open_url({"url": VALID}) == (True, "", None)
    foreground.assert_not_called()

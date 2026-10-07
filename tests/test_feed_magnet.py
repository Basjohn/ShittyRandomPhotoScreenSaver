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


def test_ordinary_feed_refresh_reconciles_rows_without_a_model_reset(qt_app):
    """A normal source refresh keeps retained article delegates alive."""
    from PySide6.QtCore import QPersistentModelIndex
    from rendering.quick.widgets.feeds import FeedRowsModel

    def row(identity, title, url, artwork):
        return FeedDisplayRow(
            identity, title, f"Summary {identity}", f"Author {identity}", url,
            1_700_000_000, image_source=artwork,
        )

    model = FeedRowsModel()
    initial = (
        row("a", "A", "https://example.test/a", "file:///a.png"),
        row("b", "B", "https://example.test/b", "file:///b.png"),
        row("c", "C", "https://example.test/c", "file:///c.png"),
    )
    assert model.replace_rows(initial) is True
    retained_b = QPersistentModelIndex(model.index(1))
    retained_c = QPersistentModelIndex(model.index(2))

    resets: list[bool] = []
    inserted: list[tuple[int, int]] = []
    removed: list[tuple[int, int]] = []
    moved: list[tuple[int, int, int]] = []
    changes: list[tuple[int, int, list[int]]] = []
    model.modelReset.connect(lambda: resets.append(True))
    model.rowsInserted.connect(lambda _parent, first, last: inserted.append((first, last)))
    model.rowsRemoved.connect(lambda _parent, first, last: removed.append((first, last)))
    model.rowsMoved.connect(
        lambda _source_parent, first, last, _destination_parent, destination:
        moved.append((first, last, destination))
    )
    model.dataChanged.connect(
        lambda first, last, roles: changes.append((first.row(), last.row(), list(roles)))
    )

    refreshed = (
        row("b", "B revised", "https://example.test/b-revised", "file:///b-revised.png"),
        row("x", "X", "https://example.test/x", "file:///x.png"),
        row("c", "C", "https://example.test/c", "file:///c.png"),
    )
    assert model.replace_rows(refreshed) is True

    assert resets == []
    assert removed == [(0, 0)]
    assert inserted == [(1, 1)]
    assert [row.item_id for row in model.rows] == ["b", "x", "c"]
    assert model.data(model.index(0), model.TitleRole) == "B revised"
    assert model.data(model.index(0), model.UrlRole) == "https://example.test/b-revised"
    assert model.data(model.index(0), model.ImageRole) == "file:///b-revised.png"
    assert retained_b.isValid() and retained_b.row() == 0
    assert model.data(retained_b, model.TitleRole) == "B revised"
    assert retained_c.isValid() and retained_c.row() == 2
    assert model.is_admitted_action("https://example.test/b-revised")
    assert not model.is_admitted_action("https://example.test/b")
    assert len(changes) == 1
    changed_index, changed_last, roles = changes[0]
    assert (changed_index, changed_last) == (0, 0)
    assert FeedRowsModel.IdentityRole not in roles
    assert {FeedRowsModel.TitleRole, FeedRowsModel.UrlRole, FeedRowsModel.ImageRole} <= set(roles)

    resets.clear()
    inserted.clear()
    removed.clear()
    moved.clear()
    changes.clear()
    assert model.replace_rows(refreshed) is False
    assert resets == [] and inserted == [] and removed == [] and moved == [] and changes == []

    reordered = (refreshed[2], refreshed[0], refreshed[1])
    assert model.replace_rows(reordered) is True
    assert resets == [] and inserted == [] and removed == [] and changes == []
    assert moved == [(2, 2, 0)]
    assert [row.item_id for row in model.rows] == ["c", "b", "x"]
    assert retained_c.isValid() and retained_c.row() == 0
    assert retained_b.isValid() and retained_b.row() == 1


def test_row_model_keeps_qt_structural_contract_for_grouped_replacements(qt_app):
    from PySide6.QtTest import QAbstractItemModelTester
    from rendering.quick.widgets.feeds import FeedRowsModel

    def rows(*identities):
        return tuple(
            FeedDisplayRow(
                identity, identity.upper(), "", "", f"https://example.test/{identity}", None,
            )
            for identity in identities
        )

    model = FeedRowsModel()
    tester = QAbstractItemModelTester(
        model, QAbstractItemModelTester.FailureReportingMode.Warning,
    )
    resets: list[bool] = []
    inserted: list[tuple[int, int]] = []
    removed: list[tuple[int, int]] = []
    model.modelReset.connect(lambda: resets.append(True))
    model.rowsInserted.connect(lambda _parent, first, last: inserted.append((first, last)))
    model.rowsRemoved.connect(lambda _parent, first, last: removed.append((first, last)))

    for replacement, expected_insert, expected_remove in (
        (rows("a", "b"), [(0, 1)], []),
        (rows("x", "y", "z", "a", "b"), [(0, 2)], []),
        (rows("x", "y", "z"), [], [(3, 4)]),
        (rows(), [], [(0, 2)]),
        (rows("replacement-a", "replacement-b"), [(0, 1)], []),
    ):
        assert model.replace_rows(replacement) is True
        qt_app.processEvents()
        assert inserted == expected_insert
        assert removed == expected_remove
        assert [row.item_id for row in model.rows] == [row.item_id for row in replacement]
        inserted.clear()
        removed.clear()

    assert tester.model() is model
    assert resets == []


def test_row_model_rejects_duplicate_article_identity_instead_of_resetting(qt_app):
    from rendering.quick.widgets.feeds import FeedRowsModel

    model = FeedRowsModel()
    resets: list[bool] = []
    model.modelReset.connect(lambda: resets.append(True))
    duplicate = FeedDisplayRow("same", "Story", "", "", "https://example.test/story", None)
    with pytest.raises(ValueError, match="unique article identities"):
        model.replace_rows((duplicate, duplicate))
    assert model.rowCount() == 0
    assert resets == []


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

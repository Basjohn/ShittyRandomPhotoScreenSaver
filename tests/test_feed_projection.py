from core.feeds.models import (
    FeedDocument, FeedImageCandidate, FeedItem, FeedSnapshot,
)
from core.feeds.projection import preferred_image_candidate, project_feed


def _snapshot(*items: FeedItem) -> FeedSnapshot:
    return FeedSnapshot(
        document=FeedDocument(
            title="Goblin Gazette", home_url="https://example.test/", format="rss20", items=items,
        ),
        fetched_at=123.0,
    )


def _item(item_id: str, *, image: str = "", width=None, height=None) -> FeedItem:
    images = () if not image else (
        FeedImageCandidate(image, width=width, height=height, relation="media"),
    )
    return FeedItem(
        item_id=item_id, title=f"Item {item_id}", action_url=f"https://example.test/{item_id}", images=images,
    )


def test_grid_admits_each_local_image_without_suppressing_other_stories():
    snap = _snapshot(_item("a", image="https://cdn/a.jpg"), _item("b", image="https://cdn/b.jpg"))
    partial = project_feed(
        snap, view_mode="grid", item_limit=10,
        local_artwork_by_item={"a": "file:///cache/a.jpg"},
    )
    assert partial.image_mode == "sparse"
    assert [row.image_source for row in partial.rows] == ["file:///cache/a.jpg", ""]
    assert [row.image_candidate_url for row in partial.rows] == ["https://cdn/a.jpg", "https://cdn/b.jpg"]

    complete = project_feed(
        snap, view_mode="grid", item_limit=10,
        local_artwork_by_item={"a": "file:///cache/a.jpg", "b": "file:///cache/b.jpg"},
    )
    assert complete.image_mode == "complete"
    assert [row.image_source for row in complete.rows] == ["file:///cache/a.jpg", "file:///cache/b.jpg"]


def test_grid_missing_art_card_reflows_to_text_without_hiding_other_art():
    snap = _snapshot(_item("a", image="https://cdn/a.jpg"), _item("b"))
    projected = project_feed(
        snap, view_mode="grid", item_limit=10,
        local_artwork_by_item={"a": "file:///cache/a.jpg"},
    )
    assert projected.image_mode == "sparse"
    assert [row.image_source for row in projected.rows] == ["file:///cache/a.jpg", ""]


def test_list_may_use_sparse_thumbnails_without_creating_grid_holes():
    snap = _snapshot(_item("a", image="https://cdn/a.jpg"), _item("b"))
    projected = project_feed(
        snap, view_mode="list", item_limit=10,
        local_artwork_by_item={"a": "file:///cache/a.jpg"},
    )
    assert projected.image_mode == "sparse"
    assert projected.rows[0].image_source == "file:///cache/a.jpg"
    assert projected.rows[1].image_source == ""


def test_compact_is_text_only_even_when_local_artwork_is_complete():
    snap = _snapshot(_item("a", image="https://cdn/a.jpg"))
    projected = project_feed(
        snap, view_mode="compact", item_limit=10,
        local_artwork_by_item={"a": "file:///cache/a.jpg"},
    )
    assert projected.image_mode == "none"
    assert projected.rows[0].image_source == ""


def test_projection_caps_rows_without_mutating_snapshot():
    snap = _snapshot(*(_item(str(i)) for i in range(5)))
    projected = project_feed(snap, view_mode="list", item_limit=3)
    assert len(projected.rows) == 3
    assert projected.omitted_count == 2
    assert len(snap.document.items) == 5


def test_preferred_image_candidate_prefers_usable_declared_media_over_tiny_asset():
    item = FeedItem(
        item_id="x", title="X",
        images=(
            FeedImageCandidate("https://cdn/tiny.png", width=1, height=1, relation="media"),
            FeedImageCandidate("https://cdn/thumb.jpg", width=320, height=180, relation="thumbnail"),
            FeedImageCandidate("https://cdn/hero.jpg", width=1280, height=720, relation="media"),
        ),
    )
    assert preferred_image_candidate(item) == "https://cdn/hero.jpg"


def test_grid_artwork_is_stable_across_geometry_and_does_not_suppress_available_items():
    snap = _snapshot(_item("a", image="https://cdn/a.jpg"),
                     _item("b", image="https://cdn/b.jpg"),
                     _item("c"))
    shown = project_feed(
        snap, view_mode="grid", item_limit=3,
        local_artwork_by_item={"a": "file:///cache/a.png", "b": "file:///cache/b.png"},
    )
    assert shown.image_mode == "sparse"
    assert [row.image_source for row in shown.rows] == [
        "file:///cache/a.png", "file:///cache/b.png", ""]
    # QML visibility alone chooses which rows acquire an Image source. The
    # projection and retained model do not change on geometry-only resize.
    assert project_feed(snap, view_mode="grid", item_limit=3,
                        local_artwork_by_item={"a": "file:///cache/a.png", "b": "file:///cache/b.png"}) == shown

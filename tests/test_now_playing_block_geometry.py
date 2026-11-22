"""Now Playing block (Expanded Visualizer) geometry: widening and side mirroring (operator defects, 22 Nov).

Real QML on the hidden scene, as the Fullscreen Edit tests drive it; no preset or default value is pinned.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtQuick import QQuickItem

from tests.test_visualizer_expansion_fullscreen_edit import (  # noqa: F401  (display is a fixture)
    BLOCK, _Fullscreen, _manager, _projection, _room, _seed, _shown_and_settled, display,
)
from tests.test_visualizer_expansion_overlays import _Media, _draw, _open, _rect, _root, _run, _slot

PARTS = {"artwork": "expandedOverlayArtwork", "metadata": "expandedOverlayNowPlayingMetadata",
         "artist": "expandedOverlayArtist", "seek": "expandedOverlaySeekBar",
         "controls": "expandedOverlayMediaControls"}

# A stored record: every X-offset part moved a little, as an edit leaves it (test input, not a default).
EDITED = {"artwork": {"x_offset": -0.06, "y_offset": 0.03},
          "metadata": {"x_offset": 0.09},
          "artist": {"x_offset": 0.04},
          "seek_bar": {"x_offset": 0.05, "width_scale": 0.7},
          "controls": {"x_offset": 0.07}}


def _open_block(display, tmp_path, **options):
    settings = _manager(tmp_path)
    seeded = _seed(settings, now_playing={"always_show": True, "seek_bar": True, "media_controls": True, **options})
    _draw(display, media=_Media(title="A Track Title", artist="An Artist"), config=_projection(seeded))
    _open(display)
    return settings


def _parts(display) -> dict[str, QRectF]:
    root = _root(display)
    _run(display, 60)
    return {name: _rect(root.findChild(QQuickItem, object_name), root) for name, object_name in PARTS.items()}


@pytest.mark.qt
def test_the_artwork_widens_to_the_square_its_height_asks_for_and_the_seek_bar_widens_with_the_box(display, tmp_path):
    settings = _open_block(display, tmp_path, corner="bottom_left")
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    slot = _slot(display, "expandedOverlayNowPlaying")
    art = _root(display).findChild(QQuickItem, PARTS["artwork"])
    seek_before = _parts(display)["seek"].width()
    def room() -> float:
        return float(slot.property("blockWidth")) - float(slot.property("gap")) - float(slot.property("artRoom"))

    edit.side("now_playing", "top", -90)                        # height given (upward from the bottom corner): a tall block
    _run(display, 90)
    # Square where the text's room allows it (never the narrow strip beside a wide empty column).
    assert art.width() == pytest.approx(min(art.height(), room()), abs=1.5), (
        art.width(), art.height(), room())
    edit.side("now_playing", "right", 160)                       # width given: it widens, never narrower than square
    _run(display, 90)
    assert art.width() >= min(art.height(), room()) - 1.5
    # The seek bar spans the text column, so it widens with the box.
    column = _rect(_root(display).findChild(QQuickItem, "expandedOverlayNowPlayingText"), _root(display))
    seek = _parts(display)["seek"]
    assert seek.width() > seek_before + 20.0
    # ... and stops short of the block's far border by the gap the artwork side has (no run into the border).
    gap = float(slot.property("gap"))
    assert seek.width() == pytest.approx(column.width() - gap, abs=1.5)
    assert seek.left() == pytest.approx(column.left(), abs=1.5)
    edit.owner.cancel()


@pytest.mark.qt
def test_width_given_to_a_wide_short_block_goes_to_the_artwork_not_to_an_empty_text_column(display, tmp_path):
    settings = _open_block(display, tmp_path, corner="bottom_left")
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    slot = _slot(display, "expandedOverlayNowPlaying")
    art = _root(display).findChild(QQuickItem, PARTS["artwork"])
    edit.side("now_playing", "right", 220)
    _run(display, 90)
    column = _rect(_root(display).findChild(QQuickItem, "expandedOverlayNowPlayingText"), _root(display))
    keep = float(slot.property("artTextKeep"))
    # The text column keeps what the text needs and no more; the artwork took the rest (up to its widest shape).
    assert column.width() <= keep + 1.5 or art.width() >= art.height() * float(slot.property("artMaxAspect")) - 1.5, (
        column.width(), keep, art.width(), art.height())
    assert art.width() > art.height()
    edit.owner.cancel()


@pytest.mark.qt
def test_an_edited_block_on_the_other_half_of_the_display_is_the_mirror_image(display, tmp_path):
    """The side a block lies on mirrors its layout; every part's offset mirrors with it, so no edit collides."""
    drawn = {}
    for corner in ("bottom_left", "bottom_right"):
        _open_block(display, tmp_path / corner, corner=corner, child_geometry=EDITED)
        block = _rect(_slot(display, "expandedOverlayNowPlaying"), _root(display))
        drawn[corner] = (block, _parts(display))
    (left_block, left), (right_block, right) = drawn["bottom_left"], drawn["bottom_right"]
    for name in PARTS:
        from_left = left[name].left() - left_block.left()
        from_right = right_block.right() - right[name].right()
        assert from_left == pytest.approx(from_right, abs=1.5), name
        assert left[name].width() == pytest.approx(right[name].width(), abs=1.0), name
    for parts in (left, right):                                   # and nothing collides with the artwork
        for name in ("metadata", "seek", "controls"):
            assert not parts[name].intersects(parts["artwork"].adjusted(1, 1, -1, -1)), name


@pytest.mark.qt
@pytest.mark.parametrize("role", ["artwork", "metadata"])
def test_a_child_gesture_stores_the_same_record_on_either_side_and_the_part_follows_the_pointer(display, tmp_path, role):
    stored, moved = {}, {}
    names = {"artwork": "artwork", "metadata": "metadata", "seek": "seek_bar"}
    for corner in ("bottom_left", "bottom_right"):
        settings = _open_block(display, tmp_path / corner, corner=corner)
        edit = _Fullscreen(display, settings)
        assert edit.start()
        _shown_and_settled(display)
        right = corner.endswith("right")
        edit.side("now_playing", "left" if right else "right", -160 if right else 160)   # room, inward from its corner
        edit.side("now_playing", "bottom", 70)
        _run(display, 60)
        edit.open_children()
        before = _parts(display)[role]
        pointer = 22 if corner == "bottom_left" else -22          # the same gesture, mirrored with the block
        edit.child_move(names[role], pointer, 0)
        after = _parts(display)[role]
        record = edit.item("now_playing").current_size_payload["child_geometry"][names[role]]
        stored[corner], moved[corner] = record["x_offset"], after.left() - before.left()
        edit.owner.cancel()
    assert moved["bottom_left"] == pytest.approx(22.0, abs=2.5)
    assert moved["bottom_right"] == pytest.approx(-22.0, abs=2.5)  # the part follows the pointer on either side
    assert stored["bottom_left"] == pytest.approx(stored["bottom_right"], abs=0.002)

"""Regression gates for duplicate QML header bindings and General opacity layout.

Pure source tests deliberately run without PySide6. Qt/QML runtime load and
native rendering still require the Windows runtime smoke check.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"

HEADERS = {
    "RedditPresentation.qml": "redditRoot",
    "FeedPresentation.qml": "feedRoot",
    "FriendPulsePresentation.qml": "friendRoot",
    "SystemStatsPresentation.qml": "statsRoot",
    "AbandonmentIssuesPresentation.qml": "abandonmentRoot",
    "GmailPresentation.qml": "gmailRoot",
    "AchievementPulsePresentation.qml": "achievementRoot",
    "MediaPresentation.qml": "mediaRoot",
    "GamesYouFollowPresentation.qml": "followsRoot",
}


def test_all_nine_branded_header_material_bindings_are_unique() -> None:
    # Duplicate assignments to the same QML property prevent the entire scene
    # factory from loading, not just the offending family (Reddit was first).
    for file, owner in HEADERS.items():
        contents = (QML / file).read_text(encoding="utf-8")
        matches = re.findall(
            r"^\s*materialOpacityAdjust\s*:\s*"
            + re.escape(owner)
            + r"\.cardHeaderSurfaceOpacityAdjust\s*$",
            contents,
            re.MULTILINE,
        )
        assert len(matches) == 1, f"{file}: expected exactly one header materialOpacityAdjust binding"


def test_no_back_to_back_duplicate_qml_property_assignments() -> None:
    # Cheap global defence for copy-paste duplication. It allows repeated keys
    # in different QML items, but catches the immediate repeated assignment that
    # caused the broken screensaver startup in this revision.
    declaration = re.compile(r"^\s*([a-zA-Z_][\w.]*)\s*:\s*(.+?)\s*$")
    for path in QML.glob("*.qml"):
        previous: tuple[str, str] | None = None
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = declaration.match(line)
            if match is None or line.lstrip().startswith("//"):
                previous = None
                continue
            current = (match.group(1), match.group(2))
            assert current != previous, f"{path.name}:{line_no}: repeated QML property {current[0]}"
            previous = current


def test_general_material_selectors_precede_contiguous_slider_group() -> None:
    page = (ROOT / "ui" / "tabs" / "widgets_tab_defaults.py").read_text("utf-8")
    header = page.index('style_overrides_layout, "Header Surface:"')
    media = page.index('style_overrides_layout, "Media Bar Surface:"')
    slider_names = ("header_surface", "media_controls", "settings", "widget")
    positions = [page.index(f'add_material_opacity_slider("{name}",', media) for name in slider_names]
    assert header < media < positions[0] < positions[1] < positions[2] < positions[3]
    # No other row or unrelated control gets inserted between these sliders.
    block = page[positions[0]: positions[-1] + len('add_material_opacity_slider("widget", "Widget Opacity:")')]
    assert block.count("add_material_opacity_slider(") == 4
    assert "add_aligned_row(" not in block
    assert "style_overrides_layout.add" not in block
    # Identical alignment and ranges for all four are owned by the helper.
    helper = page[page.index("    def add_material_opacity_slider("):page.index("    media_material_row", page.index("    def add_material_opacity_slider("))]
    assert "label_width=label_width" in helper
    assert "slider.setRange(-100, 100)" in helper
    assert 'slider.valueChanged.connect(lambda _value, owner=tab: owner._save_settings())' in helper

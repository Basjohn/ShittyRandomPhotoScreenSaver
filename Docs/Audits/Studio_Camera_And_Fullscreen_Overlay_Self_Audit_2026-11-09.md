# Studio camera handoff and fullscreen overlay self-audit | 9 Nov 2026

**Scope:** This is a focused repair and audit of the delivered `9872ca1814` GODZIP, not a P2/P3 native renderer change.
All runtime claims requiring the real Windows Qt Quick window remain awaiting physical confirmation.

## Confirmed causes and repairs

1. **Studio Save Camera from the S glyph:** The runtime handed Settings the right mode ID and camera snapshot,
   but Settings keeps mode bodies lazy. `open_initial_studio()` previously compared the current mode ID and skipped
   `_select_mode_page()` when it matched. That allowed a Studio to render while `_<mode>_lazy_values` never existed;
   saving reached `collect_spec_mode_settings()` and raised `AttributeError`. The one Studio entry owner
   (`ui/studio/settings_link.py::open_mode_studio`) now checks the selected/constructed state on
   `VisualizerModeBodyHost` and calls the existing `tab._select_mode_page(mode)` before creating its store. The
   deferred Settings entry no longer duplicates this condition. **No preset file is modified on launch.**
2. **Now Playing corner-alignment after relocation:** `nowPlayingSlot.rightSide` reflected only the authored
   corner. Fullscreen Edit can move its frame across the display without changing that corner, leaving artwork and
   metadata facing the wrong way. `contentRightSide` now reads the frame's real horizontal center relative to its
   display; only the artwork/text/transport presentation rails change. The saved anchor and per-child geometry
   records remain untouched. The frame's overall width is independent of facing direction.
3. **Artwork fading again on entering Fullscreen Edit:** `onEditingChanged` called `reveal()` for an already-visible
   track. That routine intentionally animates `contentOpacity` down for a track/preset swap, so unchanged artwork
   faded out and back. `holdForEdit` now stops the current visibility cycle and holds existing latched content;
   a partial fade may finish naturally. A hidden overlay or changed content still follows the proper reveal path,
   including the editing placeholder. A hover/resume replay also avoids a zero-opacity content swap.

## Focused checks

- Python AST/syntax parsing: Studio, Settings and both modified Qt test modules.
- 7 pure artwork-sizing tests exercised here without Qt.
- Added a real-Settings Qt regression to `tests/test_studio_runtime_handoff.py` reproducing a matching mode ID
  with no lazy body, then exercising the Studio store's Save Camera without touching source curated presets.
- Added real-QML tests to `tests/test_visualizer_expansion_fullscreen_edit.py` covering inward alignment on four
  cross-screen offset cases and zero new content-opacity dip when Fullscreen Edit opens on visible artwork.
- Existing Studio glyph, Rotate, camera flight, context-menu and native renderer owners were not changed.
- PySide6 is unavailable in this execution container: the real Qt tests must run in the Windows project venv.

## Operator live checks

Open Neon Lake from the fullscreen S glyph after flying the camera; verify Studio reproduces its position/FOV,
then **Save Camera**, close and reopen it to confirm durability. In Fullscreen Edit move Now Playing across the
horizontal midpoint in either direction; artwork and text should reverse order with no Save-time mutation of custom
child positions. Enter Edit while Now Playing is fully visible; artwork should remain fully opaque. Repeat with a
hidden overlay, which still needs to appear for editing. Finish with Save/Cancel and ordinary fullscreen return.

# R-08 — 2026-02-26 / 2026-03-05 — Pixel Shift Visualizer Bleed-Through (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Visualizer bar content briefly flashed inside the weather widget every pixel shift tick.
- Earlier investigation (Feb 26) found no code delta in the pixel shift subsystem itself; the bug was architectural.

**Failed / insufficient attempts**
1. *Feb 26 audit:* Diffed `base_overlay_widget.py`, `pixel_shift_manager.py`, `display_setup.py` — found no functional changes. Concluded issue was outside the subsystem.
2. *Mar 5 — skip `parent.update()` for small moves (≤3px):* Reduced generic overlay flicker during pixel shift, but did NOT fix the visualizer-specific bleed. The GL overlay content still appeared over the weather widget.

**Root Cause**
Double-shifting of `SpotifyVisualizerWidget` (card) and `SpotifyBarsGLOverlay` (GL surface).

Both were registered with `PixelShiftManager` (PSM), but they are **dependent widgets** that already inherit pixel shift through the media widget chain:
1. PSM shifts `MediaWidget` via `apply_pixel_shift()` → `_update_position()` → `media_layout` → `_position_spotify_visualizer()` → vis card repositioned relative to shifted media 
2. PSM **also** direct-moved the vis card by `offset` on top → **double-shift** 
3. Every tick, `set_state(rect=vis.geometry())` set the GL overlay to the card's double-shifted position
4. PSM **also** direct-moved the GL overlay → **triple offset** possible 
5. The GL overlay drifted past the card boundary and overlapped the weather widget

**Fix**
- `display_setup.py`: Removed `spotify_visualizer_widget` from the PSM registration loop. The card is positioned relative to the media widget (same pattern as the volume widget, which was already excluded).
- `display_image_ops.py`: Removed `pixel_shift_manager.register_widget(overlay)` for the GL overlay. The overlay tracks the card's geometry via `set_state(rect=vis.geometry())` every tick.
- `widget_manager.py`: Removed stale `update_original_position()` call for the vis widget.
- `base_overlay_widget.py`: Added secondary defence — skip `parent.update(old_geo.united(new_geo))` when move delta ≤3px per axis and no size change (reduces unnecessary repaints).

**Status**
- **Resolved** — User confirmed pixel shift no longer causes visualizer bleed into weather widget.

**Takeaways**
- Widgets positioned relative to a pixel-shifted parent must NOT be independently registered with PSM — they inherit the shift through the positioning chain.
- `QOpenGLWidget` overlays that track their source widget's geometry every tick are especially vulnerable to double-shift because the per-tick `setGeometry()` resets any PSM offset, creating visible jitter.
- The volume widget was already excluded from PSM for the same reason (comment in `display_setup.py`). The vis card and GL overlay should have followed the same pattern from the start.

## Record Provenance

This standalone file preserves the complete former inline `R-08` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

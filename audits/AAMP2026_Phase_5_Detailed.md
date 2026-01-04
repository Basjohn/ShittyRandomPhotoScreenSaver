# AAMP2026 Phase 5 Detailed Plan – MC Specialization & Layering (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Phase 4 (Widget & Settings Modularity) complete.
- [ ] MC build profile isolation verified in SettingsManager.

## 1) Scope & Goals
- [ ] Add window layering control for MC builds (Always on Top / Always on Bottom).
- [ ] Implement automatic Eco Mode that pauses processing when the window is 95%+ occluded.
- [ ] Ensure Eco Mode is strictly gated (disabled in "On Top" mode).

## 2) Window Layering Control
- [ ] Implement `set_always_on_top(bool)` in `rendering/display_widget.py`.
- [ ] Add "On Top / On Bottom" toggle to `widgets/context_menu.py` (restricted to MC builds via `is_mc_build()` check).
- [ ] Ensure internal widget Z-order (managed by `WidgetManager`) is preserved across layering changes.
- [ ] Persist layering choice in MC-specific settings profile.

## 3) Visibility Detection
- [ ] Implement `VisibilityMonitor` in `rendering/` to detect occlusion.
- [ ] Use OS-level window events (Win32 API or Qt screen intersection) to calculate coverage threshold (95%).
- [ ] Log visibility state changes with `[MC]` prefix.

## 4) Eco Mode Implementation
- [ ] Implement `EcoModeManager` to coordinate pausing.
- [ ] Pause `TransitionController` (hold current frame).
- [ ] Pause `SpotifyBeatEngine` (halt FFT and Bar updates).
- [ ] Pause `SourceManager` / `ImageQueue` prefetching where beneficial.
- [ ] Automatic recovery: restore all animations immediately when visibility > 5% regained.

## 5) Tests & Telemetry
- [ ] `tests/test_mc_layering_mode.py`: Cover multi-monitor overlap and Eco Mode triggering.
- [ ] Log activation/deactivation effectiveness in telemetry.
- [ ] Verify no "black frame" flicker during Eco Mode entry/exit.

## 6) Documentation & Backups
- [ ] Update `Index.md` with layering/visibility modules.
- [ ] Update `Spec.md` with layering persistence and Eco Mode behavior.
- [ ] `/bak` snapshots for `display_widget.py` and `context_menu.py`.

## 7) Exit Criteria
- [ ] Checkboxes resolved; main audit in sync.

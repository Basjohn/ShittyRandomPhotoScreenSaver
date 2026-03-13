# Media Key Debug Log

Living document tracking the MC media key loss investigation. Update whenever we learn something new.

## Current Status (2026-02-14)
- **State:** Keys still fail after MC window regains focus unless the context menu is actively open.
- **Latest Build:** `SRPSS.scr` and `SRPSS_Media_Center.exe` from 2026-02-13 after grabKeyboard()/releaseKeyboard() attempt.

## Observations
1. **Context menu keeps keys alive**
   - Right-click → open menu → media keys work.
   - Closing the menu by *any* means instantly breaks keys again.
   - Implication: whatever state the menu puts Qt/Windows into (keyboard grab, activation stack, effect invalidation) must be preserved.

2. **Top-level hooks**
   - `InputHandler.handle_mouse_press()` invalidates overlay effects and emits `context_menu_requested`.
   - `display_context_menu.show_context_menu()` sets both `DisplayWidget` and `InputHandler` `_context_menu_active = True`, then calls `QMenu::popup()`.
   - `QMenu` is configured with `WA_ShowWithoutActivating` + `WindowDoesNotAcceptFocus`, so Windows should still consider the DisplayWidget active while the menu is up.

3. **Menu lifecycle**
   - `aboutToHide` resets `_context_menu_active`, calls `InputHandler.set_context_menu_active(False)`, and schedules more effect invalidation.
   - No other state is restored; the grab (if any) ends automatically when Qt closes the popup.

4. **Grab/release experiment (current code)**
   - Both `WM_ACTIVATE` handler and `DisplayWidget.focusInEvent` now perform `activateWindow()+setFocus()+grabKeyboard()+releaseKeyboard()`.
   - Result: no noticeable improvement; key routing still dies unless the popup stays open.

## Leading Theories
1. **Popup holds implicit keyboard grab**
   - Qt popups install a grab while visible. When open, the DisplayWidget effectively receives keyboard events via that grab. When closed, Qt never reinstates the grab for SplashScreen windows → no keys.
   - Fix idea: maintain our own grab (e.g., keep `grabKeyboard()` active) while MC window owns focus, releasing only on exit.

2. **WM_MOUSEACTIVATE/WM_CONTEXTMENU ordering**
   - Right-click triggers `WM_MOUSEACTIVATE` + `WM_CONTEXTMENU`, which may reset some hidden Qt state that our manual focus reclaim doesn’t.
   - Need to inspect `display_native_events.handle_nativeEvent` to see if we miss the `WM_MOUSEACTIVATE` path or can synthesize equivalent logic without showing the menu.

3. **Effect invalidation side-effect**
   - Menu open path flushes `QGraphicsEffect` caches locally and across displays (`invalidate_overlay_effects("menu_before_popup")` + broadcast).
   - Perhaps the focus/keyboard corruption is tied to stale drop shadows; menu open clears them, but closing reintroduces corrupted state.
   - Counterpoint: We now invalidate on focusIn, so this alone shouldn’t explain the behavior.

4. **Hidden state in `InputHandler._context_menu_active`**
   - Numerous code paths gate exits + gestures while menu is active. Side-effects from those gates (e.g., `widget._coordinator.set_halo_owner`) might be keeping the coordinator in a “controlled” mode that ensures the DisplayWidget remains focus owner.
   - Need to trace `MultiMonitorCoordinator` focus ownership transitions vs. `_context_menu_active`.

## Next Investigation Steps
1. Inspect `display_native_events` for `WM_MOUSEACTIVATE`/`WM_CONTEXTMENU` handling; mimic necessary sequences without showing the menu.
2. Prototype persistent keyboard grab: call `grabKeyboard()` when MC window becomes focus owner, defer `releaseKeyboard()` until focus actually leaves or widget closes.
3. Log `MultiMonitorCoordinator` focus owner changes before/after menu open to see if the menu refresh manipulates coordinator state.

---
Update this doc after each experiment (what changed, result, logs).

## 2026-02-14 Postmortem – Focus Grab Removal
- **Change:** Deleted the WM_ACTIVATE focus-reclaim loop in `rendering/display_native_events.py` and the corresponding `focusInEvent` grab/release block in `rendering/display_widget.py`.
- **Why:** That logic constantly forced every DisplayWidget to `activateWindow()/setFocus()/grabKeyboard()` whenever Winlogon delivered WM_ACTIVATE. On Winlogon builds, this yanked focus away from the Settings dialog immediately after it opened, leaving the dialog visually present but unresponsive. It also never restored media-key routing, so the complexity bought us nothing.
- **Scope:** The code ran in both the standard saver and MC build (shared modules), so the regression affected all Winlogon sessions—not MC-only behavior.
- **Guidance:** Do **not** reintroduce global WM_ACTIVATE focus reclaims. Any future media-key work must be scoped to the MC window and validated against screensaver settings interactivity. Document the reasoning in this file before landing similar changes so we avoid repeating this dead-end approach.

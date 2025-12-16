# Phase E: Context Menu / Effect Cache Corruption

## Summary
The screensaver intermittently exhibits **overlay shadow/opacity corruption** (most visible on widget card shadows and/or opacity fade behavior) after certain UI interactions, primarily:
- Opening/closing the **context menu** repeatedly.
- Interacting with overlay widgets (notably Reddit click handling) and then opening the menu.
- Occurring more often on **secondary displays**, but can present on **both displays simultaneously**.

The strongest current hypothesis is a **Qt cache corruption / invalidation ordering issue involving `QGraphicsEffect` (drop shadows / opacity)** under rapid **focus/activation + z-order changes** across multiple topmost fullscreen windows.

This document:
- Captures symptom/repro and log-cited evidence.
- Describes current mitigation and its limits.
- Lays out root-cause theories.
- Proposes instrumentation to confirm.
- Describes likely refactor leverage points and higher-fidelity alternative shadow pipelines.

Related docs:
- `audits/REFACTOR_DISPLAY_WIDGET.md`
- `audits/REFACTOR_GL_COMPOSITOR.md`
- `Docs/10_WIDGET_GUIDELINES.md`

---

## Symptoms
- Widget shadows become visually “wrong” (distorted, clipped, offset, or otherwise corrupted).
- Widget opacity/fade may appear inconsistent or “stuck” until later redraws.
- Issue sometimes appears on **both displays**, suggesting a shared trigger (activation/z-order cascade) rather than a per-display GL state problem.

---

## Reproduction (current best-known)
These are not guaranteed, but have the highest observed hit rate:

1. Run screensaver on multi-monitor.
2. Interact with a widget (notably Reddit click path) on a **secondary** display.
3. Open the context menu on the same display.
4. Rapidly open/close the context menu multiple times.

---

## Log Evidence (screensaver_verbose.log)
The following excerpts correlate context menu activity with focus/activation cascades and Windows window position changes.

### A) Menu open/close triggers effect invalidation
From `screensaver_verbose.log` around `12:15:02`:

```text
2025-12-16 12:15:02 - win_diag - DEBUG - [MENU_OPEN] begin ... screen=0 ...
2025-12-16 12:15:02 - win_diag - DEBUG - [EFFECT_INVALIDATE] screen=0 reason=menu_before_popup
2025-12-16 12:15:02 - win_diag - DEBUG - [EFFECT_INVALIDATE] screen=0 reason=menu_about_to_show
```

### B) Cross-display WM_WINDOWPOSCHANGING happens during menu activity
From `screensaver_verbose.log` around `12:15:04` (menu on screen 1):

```text
2025-12-16 12:15:04 - win_diag - DEBUG - [WIN_STATE] nativeEvent screen=0 ... msg=WM_WINDOWPOSCHANGING ...
2025-12-16 12:15:04 - win_diag - DEBUG - [WIN_STATE] nativeEvent screen=1 ... msg=WM_WINDOWPOSCHANGING ...
2025-12-16 12:15:04 - win_diag - DEBUG - [MENU_OPEN] begin ... screen=1 ...
2025-12-16 12:15:04 - win_diag - DEBUG - [EFFECT_INVALIDATE] screen=1 reason=menu_before_popup
2025-12-16 12:15:04 - win_diag - DEBUG - [EFFECT_INVALIDATE] screen=1 reason=menu_about_to_show
```

This is important: **opening a popup menu on one display is associated with window position changes on both displays**.

### C) Reddit click path correlates with the same global windowpos churn
From `screensaver_verbose.log` around `12:51:34`:

```text
2025-12-16 12:51:34 - win_diag - DEBUG - [WIN_STATE] nativeEvent screen=0 ... msg=WM_WINDOWPOSCHANGING ...
2025-12-16 12:51:34 - win_diag - DEBUG - [WIN_STATE] nativeEvent screen=1 ... msg=WM_WINDOWPOSCHANGING ...
2025-12-16 12:51:34 - widgets.reddit_widget - INFO  - [REDDIT] Deferred URL for exit: https://www.reddit.com/r/interestingasfuck/comments/...
2025-12-16 12:51:34 - rendering.display - INFO - [REDDIT] URL deferred for exit (all displays taken): https://www.reddit.com/r/interestingasfuck/comments/...
```

This suggests widget interactions can coincide with cross-display window state churn, which likely increases the probability of effect cache corruption.

---

## Current Mitigation (Implemented)
The current mitigation is **cache-busting and invalidation** around high-risk events:

- On context menu open/close:
  - Trigger `_invalidate_overlay_effects(...)` with reasons like:
    - `menu_before_popup`
    - `menu_about_to_show`
    - `focus_in`
- Invalidation is designed to be **non-destructive first** (update/invalidate), with **occasional guarded recreation** of the QGraphics effect objects as a cache-bust mechanism.
- Scheduling avoids raw Qt timers where possible (uses centralized thread/timer facilities).

### Why this helps
- If Qt’s internal cached pixmap/texture backing a `QGraphicsEffect` becomes stale/corrupt due to rapid reparent/raise/activation changes, recreating the effect forces a clean render path.

### Why this is not ideal
- It is inherently reactive.
- It may mask the true ordering/ownership problem.
- It risks micro-stutters or subtle visual inconsistencies if done too often (though the current approach rate-limits/guards).

---

## Root-Cause Theories (Most Plausible)

### 1) Qt `QGraphicsEffect` caching breaks under rapid activation + popup menu sequencing
- `QMenu` is typically a native popup window.
- Showing it can trigger activation changes and z-order recomputation.
- Under multi-monitor + multiple topmost windows, Windows/Qt may emit cascaded state changes to both windows.
- `QGraphicsDropShadowEffect` / `QGraphicsOpacityEffect` can cache intermediate results; rapid invalidations + stacking changes can leave those caches corrupted.

### 2) Cross-display z-order repair and effect invalidation are interleaving in the wrong order
- Today, invalidation and stack repair happen from multiple locations (menu handlers, focus handlers, overlay manager raising, etc.).
- This increases the chance of:
  - invalidating while a widget is mid-stack transition
  - recreating effects while a widget is temporarily hidden/occluded
  - inconsistent ordering between display 0 and display 1

### 3) Backing store / DPR-related cache invalidation edge case
- Effects are sensitive to DPR and device pixel alignment.
- The system runs multiple screens with potentially different refresh/DPR.
- A popup menu + windowpos changes may cause a transient change in backing store invalidation behavior, exposing a Qt edge case.

### 4) Not primarily a GL compositor bug
- Evidence points to corruption in overlay visuals (shadows/opacity) rather than base-image GL texture state.
- The correlation to `QGraphicsEffect` invalidation and menu activity is stronger than to any specific shader path.

---

## Instrumentation Plan (High Signal / Low Risk)
Goal: confirm the ordering and identify which exact step causes cache corruption.

### A) Log effect identity and lifecycle transitions
On each invalidation/recreate pass (menu open/close, focus_in):
- Log per overlay widget:
  - widget name
  - `id(widget.graphicsEffect())`
  - effect type name
  - whether we recreated vs invalidated
  - widget visibility and `updatesEnabled()`

### B) Log cross-display ordering explicitly
When menu opens on any display:
- Log a cross-display “transaction id”:
  - `menu_tx_id`
  - affected screens
  - timestamps of invalidate/stack repair per screen

### C) Add a corruption sentinel
Add a cheap runtime check (debug-only):
- Detect “impossible” effect states (e.g., effect is present but shadow alpha output becomes effectively 0 while opacity claims 1.0).
- Or track QGraphicsEffect output bounding rect vs expected widget rect.

### D) Tie instrumentation to reproducible triggers
- Reddit click path (deferred URL)
- Menu open/close
- Focus/activation events

---

## (R0) Refactor Leverage Points (Fix It Along the Pipeline)
This is the preferred route: **make ordering deterministic**, then remove mitigation.

### (R1.1) DisplayWidget decomposition (Primary)
From `audits/REFACTOR_DISPLAY_WIDGET.md`:
- Move context menu creation/management and overlay effect lifecycle ownership out of the DisplayWidget god class.

Likely winners:
- **InputHandler** owns:
  - menu open/close sequencing
  - click interaction gating and “side effects” (e.g. Reddit click)
- **WidgetManager** owns:
  - per-widget effect lifecycle
  - overlay stacking repair
  - deterministic cross-display coordination decisions

### (R2.1) GLCompositor refactor (Supporting)
From `audits/REFACTOR_GL_COMPOSITOR.md`:
- Even if the root cause is Qt effects, a cleaner compositor boundary helps:
  - isolate overlay visuals from base-image rendering
  - improve diagnostics
  - enable future shadow implementations that avoid Qt’s `QGraphicsEffect` caching

---

## Alternative Shadow / Effect Implementations (Minimize Fidelity + Performance Loss)
These are candidates to eliminate reliance on fragile Qt effect caching.

### Option A (Best long-term): shader-backed drop shadow for overlay cards
- Render card + shadow in a single pass using a simple shader (blurred rounded-rect mask).
- Pros:
  - deterministic
  - fast on GPU
  - avoids QGraphicsEffect cache issues
  - can match current fidelity (soft radius, offset, opacity)
- Cons:
  - larger architectural change
  - must integrate with existing overlay pipeline (and respect `Docs/10_WIDGET_GUIDELINES.md`)
(User Note: Option A here is disliked because it sounds like it would break our start up fade in and shadow fade in behaviour. Let me know if it doesn't damage this.)


### Option B: pre-rendered shadow pixmap cache (QImage/QPixmap), owned by WidgetManager
- Generate a shadow texture for a rounded-rect once per size/theme config.
- Then paint it behind the card (no QGraphicsEffect).
- Pros:
  - high fidelity possible
  - stable and deterministic
  - relatively low risk
- Cons:
  - needs careful DPR handling
  - requires explicit invalidation when size/theme changes

### Option C (Not ideal): always recreate QGraphicsEffects on risky triggers
- Keep current visuals with minimal code churn.
- Pros:
  - simplest
- Cons:
  - reactive, not principled
  - can still fail on pathological ordering
  - can introduce micro-costs and complexity

### Option D: avoid QGraphicsEffect by painting a blurred shadow manually (QPainter)
- Draw multiple expanded alpha layers (approximate blur) behind the card.
- Pros:
  - no effect cache
  - predictable
- Cons:
  - may cost more CPU, can be hard to match fidelity

---

## Terminology Note: Legacy Key Name (`adaptive_sensitivity`) vs “Recommended”
The UI label is **Recommended**, but the stored key name is `widgets.spotify_visualizer.adaptive_sensitivity` for backward compatibility.

To avoid confusion:
- Internal variable names and docs should prefer **recommended**.
- Keep the persisted key name unchanged (unless a migration system is added).

---

## Status
- Evidence gathering: ongoing (logs confirm cross-display WM_WINDOWPOSCHANGING during menu interactions).
- Mitigation: implemented via invalidation + occasional effect recreation.
- **2025-12-16 Progress - DisplayWidget Refactor Complete (Phases 1-4)**:
  
  **Phase 1a: WidgetManager Enhancement**
  - `invalidate_overlay_effects()` now owned by WidgetManager (deterministic ordering)
  - `_recreate_effect()` for QGraphicsEffect cache-busting with animation guards
  - `schedule_effect_invalidation()` for deferred invalidation
  - Fade coordination methods migrated to WidgetManager
  - All widgets registered with WidgetManager during _setup_widgets
  
  **Phase 2a/2b: InputHandler Extraction**
  - Created `rendering/input_handler.py` for centralized input handling
  - Single choke point for context menu open/close triggers
  - InputHandler notifies WidgetManager on menu state changes
  - Effect invalidation flows through WidgetManager on menu close
  
  **Phase 3a: TransitionController Extraction**
  - Created `rendering/transition_controller.py` for transition lifecycle
  - Centralizes transition state for deterministic overlay visibility
  - Watchdog timer management moved to TransitionController
  
  **Phase 4a: ImagePresenter Extraction**
  - Created `rendering/image_presenter.py` for pixmap lifecycle
  - Consistent pixmap state during transitions
  
- **Impact on Phase E**: The refactor provides:
  - Deterministic ordering of effect invalidation during menu open/close
  - Single choke point for context menu triggers
  - Consistent state between InputHandler, WidgetManager, and TransitionController
  
- **Phase 5 Complete (2025-12-16)**: MultiMonitorCoordinator created
  - Created `rendering/multi_monitor_coordinator.py` singleton
  - Thread-safe state access with `threading.Lock`
  - Weak references prevent memory leaks
  - All class-level variables migrated to coordinator methods
  - Signals for state change notifications
  
- Next: Complete remaining migration (Phases 1b-4b) for full logic delegation.

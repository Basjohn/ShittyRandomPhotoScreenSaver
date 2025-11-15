# Flash Flicker Diagnostic

_Last updated: 2025-11-14_

## Current Symptoms

### Crossfade Transition
- **Visible artefact:** Thin horizontal band at the top of display 1 during initial presentation; occurs before the overlay fully obscures the desktop. (Applies to all transitions at startup currently)
- **Severity:** Minor but visible; introduced after the short-lived base snapshot instrumentation and now reduced yet still present.
- **Latest telemetry:** `[DIAG] Base paint fallback executing (overlay_visible=False, has_error=False, seed_age_ms=N/A, current=None, seed=None)` logged once per display at startup, proving the QWidget paints black before we seed any pixmap.

### Blinds Transition
- **Visible artefact:** Black frame flash preceding the first slat movement, plus the same top-of-screen band seen in Crossfade.
- **Severity:** High; longstanding regression target.
- **Latest telemetry:** Identical fallback log as Crossfade, followed by instantaneous readiness gate satisfaction (`gl_initialized=True`, `first_frame_drawn=True`, `has_drawn=True`). Hitching eliminated, but initial flash persists.

## Instrumentation & Observations
- **Readiness Gate:** `has_drawn` now true before overlays are shown, so the gate itself is not stalling presentation.
- **Base fallback telemetry (2025-11-13):** Updated logs capture `seed_age_ms` and pixmap descriptors. First fallback occurs *before* any seed pixmap exists, confirming a paint race between `showFullScreen()` and the initial `set_image`.
- **Overlay readiness hook:** DisplayWidget now exposes `notify_overlay_ready`, but no overlays emit to it yet—future work item.
- **Overlay Prewarm:** All GL overlays prewarm successfully on both monitors (<300 ms), ensuring contexts are live before first transition.
- **Pan & Scan Logs:** `Pan and scan disabled` spam is expected; emitted whenever we stop the helper during transition prep.

## Mitigations Attempted
1. **Overlay Readiness Gate** (2025-10-xx)
   - **Goal:** Prevent overlays from appearing until their first frame is fully rendered.
   - **Result:** Removed “white flash”/timing hitch; did not solve initial black flash.

2. **Persistent Base Pixmap Seeding** (2025-11-xx)
   - **Goal:** Copy the previous frame into `current_pixmap` before raising the overlay to avoid a black QWidget repaint.
   - **Result:** Reduced flash but introduced Crossfade banding due to forced `grab()` and `update()`. Side effects reverted on 2025-11-12.

3. **GL Capture Sequencer** (removed 2025-11-11)
   - **Goal:** Save first N frames to PNG for visual inspection.
   - **Result:** Impacted runtime responsiveness and produced unusable diagnostics; removed at user request.

4. **Refresh-Rate / Swap-Interval Audit** (2025-11-11)
   - **Goal:** Ensure Blinds respects triple buffering & `display.refresh_sync`.
   - **Result:** Confirmed swap interval toggles correctly; no change to flicker.

5. **Final Frame Tail Repaint Fixes** (pre-2025-11)
   - **Goal:** Eliminate end-of-transition hitching.
   - **Result:** Hitching resolved; unrelated to current flash.

6. **Base Pixmap Seeding Without QWidget.grab()** (2025-11-12 PM)
   - **Goal:** Keep `current_pixmap` populated with a real frame before raising overlays, removing the need for the black fallback paint.
   - **Result:** Widget now seeds `current_pixmap` with either the prior image or the incoming processed pixmap prior to transition start. However, the fallback still triggers pre-seed during the gap between `showFullScreen()` and the first `set_image`.

7. **Persistent GL Overlay Warmup + Initial Flush** (2025-11-14)
   - **Goal:** Eliminate “cold start” flashes by maintaining pre-warmed GL overlays and forcing a synchronous flush before first presentation.
   - **Result:** `_prewarm_gl_contexts` now reuses persistent overlays registered with `ResourceManager`, `_perform_initial_gl_flush` issues `glFinish()`/`glFlush()` to drain the queue, and `_reuse_persistent_gl_overlays` ensures geometry/parenting consistency. Cold-start flicker is no longer reproducible in initial transition tests.

## Current Investigation Log

- (2025-10-28) Regressions after D3D removal: first-transition banding traced to missing `current_pixmap` seed during overlay prewarm. Temporary workaround is forcing immediate base repaint.
- (2025-10-29) Added telemetry counters for backend selection/fallback. Logging indicates GL preferred path stabilizing except cold-start flicker.
- (2025-11-02) Persistent FBO attachments in `DisplayWidget` confirmed; cold-start flicker minimized but overlay Z-order still inconsistent on multi-monitor.
- (2025-11-14) DisplayWidget now re-applies `set_overlay_geometry` and `schedule_raise_when_ready` via centralized helper after every transition, display, resize. Need to schedule multi-monitor verification pass to confirm clock/weather remain above GL overlays across DPI mixes.

### 2025-11-14 Debug Session Anomalies
- **Swap downgrade warnings (screens 0 & 1):** every GL overlay reported downgrade to `SwapBehavior.DoubleBuffer` despite triple-buffer request. Track driver constraints and document expected behaviour in roadmap §7.1.
- **Transition skip spam:** `Transition in progress - skipping this image request` emitted when rotation timer fired mid-transition. Measure frequency to ensure queue pacing stays within tolerance (roadmap §7.3).
- **Random cache persistence:** After cycling to Slide, transitions remained GL BlockFlip; indicates `transitions.random_choice` not cleared. Investigate engine/UI synchronization (roadmap §7.4).
- **ResourceManager churn:** Multiple `ResourceManager initialized` log entries during steady state hint at redundant instantiation. Verify lifecycle reuse (roadmap §7.6).
- **Overlay warmup latency:** Prewarm stages hovered around ~175–300 ms for each overlay. Capture metrics and determine optimization vs. documentation (roadmap §7.2).
- **Weather widget fetch on disabled monitor:** Weather overlay initiated network request even when disabled on screen 1; confirm per-monitor gating (roadmap §7.5).
- **Pan & scan stop spam:** Exit sequence logged repeated "Pan and scan stopped" messages. Audit cleanup idempotence (roadmap §7.8).

## Root Cause Assessment (2025-11-13)
- **Primary:** QWidget paints black before any seed pixmap exists (pre-first-image race). This manifests as `[DIAG] Base paint fallback...` with `seed_age_ms=N/A`.
- **Secondary:** GL overlays raise after readiness, but telemetry doesn’t confirm the exact timing because notify hook is unused; we must integrate hooks to guarantee correlation.
- **Tertiary:** Repeated `processEvents()` loops in GL transitions risk re-entrant paints while overlays are mid-start, potentially widening the fallback window.

## Updated Action Items
1. **Block base paints until seeded** — widget disables updates before `showFullScreen()` and re-enables on first seed (done, pending visual confirmation).
2. **Overlay readiness telemetry** — GL overlays now emit `notify_overlay_ready(...)` during GL init/first frame; readiness polling centralized (done).
3. **Fallback log enrichment** — base fallback logs include screen, update state, and pixmap descriptors (done).
4. **Audit follow-through** — overlay lifecycle helper consolidates creation/prepaint/raise, and `processEvents()` loops replaced with non-blocking readiness polling (done, monitor results).
5. **GL Warmup Persistence** — persistent overlays and synchronous flush added; document behaviour and monitor for regressions (done; see Mitigation #7).

## Remaining Hypotheses
- **Overlay Raise Timing:** Even with base paints blocked, confirm overlays raise before updates resume to avoid exposing stale content.
- **Crossfade Banding:** After base fallback removal and persistent warmup, re-evaluate whether compositor artefact still occurs; if so, investigate alpha ramp or swap interval issues.
- **Multi-monitor Consistency:** Validate that persistent overlays honour per-screen DPI/geometry and remain synchronized after reshuffle.

## Candidate Next Steps
1. **Verify Base Fallback Elimination:** After blocking base paints, run Blinds & Crossfade in debug builds to confirm `[DIAG] Base paint fallback…` no longer fires and that visible banding is gone.
2. **Delay Base Clear Until Overlay Visible (if needed):** Only pursue if fallback log persists after updates-blocking fix.
3. **Headless/Offscreen GL Harness (See discussion below):** Would allow automated capture and regression gating once implemented.
4. **Targeted Logging:** Once overlays report readiness via the new hook, record deltas between seed timestamps, readiness, update re-enable events, and the new persistent flush timing.

## Offscreen GL Harness – Pros & Cons
- **Advantages:**
  - Deterministic frame capture for automated regression tests.
  - Ability to assert pixel output (e.g., detect black frames) without human observation.
  - Stress-test transitions under varied timing / swap-interval configurations.
- **Challenges:**
  - Requires reliable headless GPU context creation on Windows (likely ANGLE/OSMesa or WGL pbuffer); maintenance heavy.
  - Needs deterministic asset loading and event processing, or a simulator for Qt’s event loop.
  - Risk of diverging behaviour vs real monitors (e.g., compositor, vsync timing) leading to false positives/negatives.

## Open Questions
- Can we cache the first frame on the base widget without forcing an immediate repaint (maintaining readiness gate semantics)?
- Would deferring `clear()` until after overlays hide reduce the exposure window?
- Does disabling the synthetic “black pixmap” helper and supplying the next real image prevent the base fallback entirely?

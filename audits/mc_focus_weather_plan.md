# Weather Widget + MC Focus Repair Plan

> **Immediate Priority**: Fix Weather widget margins/positioning so that every preset slot (top-left, top-right, bottom-left, bottom-right, center) honors the configured padding and never bleeds into other overlays. This fix must ship alongside the MC focus repair to prevent another round of layout regressions.

---

## Goals

1. **Weather Widget Layout**
   - Audit `widgets/weather_widget.py` for hardcoded offsets.
   - Cross-check against `Docs/10_WIDGET_GUIDELINES.md` and ensure we reuse the shared spacing helpers.
   - Add regression tests (screenshot diff or geometry assertions) that instantiate `WeatherWidget` in each position and verify `geometry().margins()` respect the configured values.

2. **MC Focus / Shadow Stability**
   - Left-click repair must restore media keys without forcing halo hides or triggering shadow invalidations while inactive.
   - Right-click context menu remains the “gold standard” reference: it never corrupts shadows when switching focus. We must extract the minimal subset of that pipeline and reapply it safely for left-clicks.
   - Provide a design that works in both script and Nuitka builds.
[Problem of keys being swallowed is solved if we mimic right click activity for left clicks but this 1. Introduces shadow artifacts EVERY single time we go into a different application window and 2. Makes Cntrl Halo vanish. Both unacceptable tradoffs and higher priority than keys.]


3. **Rollback + Clean Slate** [DONE BY USER MANUALLY]
   - Return `rendering/display_widget.py` (and related tests) to the last known-good state _before_ `_pending_light_click_refresh` was introduced.
   - Confirm baseline behavior: keys break again, but halo and shadows stay stable when alt-tabbing or moving focus.

4. **Iterative Redesign**
   - Produce a detailed call graph showing how native `WM_ACTIVATE`, Qt `ActivationChange`, context menu open/close, and halo ownership interact.
   - Only after design approval should we re-introduce any new code.

---

## Investigation Steps

1. **Weather Widget**
   1. Capture current geometry for each anchor using a tiny diagnostic script (`tests/manual/weather_layout_probe.py`).
   2. Compare with guideline values (margins, spacing tokens). Document discrepancies.
   3. Patch widget to use centralized spacing helpers rather than inline `+/- 10` offsets.
   4. Add geometry assertions to `tests/test_widget_layouts.py` (new file if necessary).

2. **MC Focus Baseline**
   1. Roll back the recent `_pending_light_click_refresh` changes and re-run MC script build.
   2. Collect logs showing:
      - `[MC TOOL FOCUS]` entries when right-clicking vs. left-clicking.
      - Shadow corruption (or lack thereof) when focus changes.
   3. Confirm halo behavior matches expectations (only hides when Ctrl/Hard-Exit is active).

3. **Design Document**
   1. Diagram the event order for both right-click and left-click:
      - InputHandler → DisplayWidget → WidgetManager → MultiMonitorCoordinator → Qt native events.
   2. Explicitly list which methods touch `_pending_effect_invalidation`, `_invalidate_overlay_effects`, and the GL compositor.
   3. Identify minimal calls needed to:
      - Reassert focus atomically.
      - Schedule an effect invalidation only after reactivation.
      - Avoid touching halo unless we truly need to hide it.
   4. Produce a test matrix that covers script vs. Nuitka, single vs. multi-display.

4. **Implementation Plan (post-design)**
   - Introduce a tiny “activation repair queue” that stores pending repairs per display.
   - Use the native `WM_ACTIVATE` hook to drain the queue only when Windows reports `WA_ACTIVE`.
   - For left-clicks while already active, run the repair immediately but scoped to the owning display.
   - Ensure `_invalidate_overlay_effects` is only called once per activation cycle to avoid repeated shadow rebuilds.

5. **Testing & Validation**
   - Script MC build: verify keys, halo, and shadows.
   - Nuitka MC build: repeat the same, since previous regressions only appeared there.
   - Weather widget snapshots before/after to confirm margins.
   - Update `Docs/TestSuite.md` with new tests and procedures.

---

## Deliverables Checklist

- [ ] Weather widget margin fixes + geometry tests.
- [ ] MC focus rollback patch.
- [ ] Design doc/diagram explaining the final approach.
- [ ] Revised implementation with guarded activation refresh.
- [ ] Regression tests covering:
  - Media key passthrough.
  - Halo visibility rules.
  - Shadow stability on focus changes.
- [ ] TestSuite.md update with new regression coverage.

---

## Notes

- Keep logging concise: use `[MC TOOL FOCUS]` with structured key/value pairs so we can grep easily.
- Avoid touching `Spec.md` until the design is approved (to prevent churn).
- Once weather widget fix lands, schedule time to audit other overlays for margin drift.

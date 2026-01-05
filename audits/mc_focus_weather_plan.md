# Weather Widget + MC Focus Repair Plan

> **Immediate Priority**: Fix Weather widget margins/positioning so that every preset slot (top-left, top-right, bottom-left, bottom-right, center) honors the configured padding and never bleeds into other overlays. This fix must ship alongside the MC focus repair to prevent another round of layout regressions.

---

Short summary of problem:
In MC mode no keys work at all until the user right clicks, then keys work until the user changes focus and tries to come back in.
Right click is importantly conntected to trying to prevent shadow cache corruption. We have/had a lot of this.
Shadows would suddenly "double up" or distort on clicks or changing windows and we have mechanisms in place (like right click) to fix them. Ideally we'd not have the corruption at all but this is a QT problem. Do online research.
Shadows still occasioanlly corrupt on focus changes as things are now, most attempts at a solution to the keys issues resulted in worse/more frequent shadow corruption.

We would like to get this to work but avoiding shadow corruption is a higher priority than keys.

Shadow corruption happens in both builds but almost never in non-mc ones with current mitigations.

## Goals

1. **MC Focus / Shadow Stability**
   - Left-click repair must restore keys without forcing halo hides or triggering shadow invalidations while inactive.
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

1. **MC Focus Baseline**
   1. Roll back the recent `_pending_light_click_refresh` changes and re-run MC script build.
   2. Collect logs showing:
      - `[MC TOOL FOCUS]` entries when right-clicking vs. left-clicking.
      - Shadow corruption (or lack thereof) when focus changes.
   3. Confirm halo behavior matches expectations (only hides when Ctrl/Hard-Exit is active).

2. **Design Document**
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
  - All key passthrough.
  - Halo visibility rules.
  - Shadow stability on focus changes.
- [ ] TestSuite.md update with new regression coverage.

---

## Notes

- Keep logging concise: use `[MC TOOL FOCUS]` with structured key/value pairs so we can grep easily.
- Avoid touching `Spec.md` until the design is approved (to prevent churn).
- Once weather widget fix lands, schedule time to audit other overlays for margin drift.

# Widget Overlay Investigation Plan (Jan 4, 2026)

Tracking the three user-reported regressions while keeping progress visible. Check items off once verified/fixed.

## Checklist

- [x] Weather widget bottom-right margin misalignment
- [ ] Clock & Weather stacking failure at TOP_RIGHT vs Media/Reddit success at other anchors
- [ ] MC mode suppressing global media keys

---

## Weather widget bottom-right margin

- Status: _done_
- Findings:
  - Root cause was asymmetric padding: `_padding_right` (28) is larger than `_padding_left` (21), so the label looked inset compared to other cards when anchored on the right/bottom using the raw margin.
  - Added a custom `_update_position` override that subtracts the padding difference from the effective horizontal margin for all right-anchored positions. This realigns the card edge without affecting left/middle anchors.
  - BOTTOM anchors still use the configured vertical margin, so shadows stay consistent.

Validation:
1. Manual inspection confirms BOTTOM_RIGHT now matches other widgets’ edge spacing.
2. Need to add an automated regression check once visual stacking suite exists (follow-up, not blocking).

---

## Clock & Weather stacking at TOP_RIGHT

- Status: _done_
- Findings:
  - Root cause: Clock and Weather overrides skipped `_stack_offset`, so WidgetManager’s stacking adjustments never took effect at TOP_RIGHT (and other shared anchors).
  - Fixes applied: Weather now reuses base positioning logic with padding-aware margins plus `_stack_offset`; Clock adds `_stack_offset` and keeps timezone label aligned; Media widget now also applies `_stack_offset` to stay consistent with Reddit + BaseOverlayWidget defaults.
  - Regression tests: Added `tests/test_widget_overlay_regressions.py` to cover weather margins at all anchors, clock stack offsets, and combined clock+weather stacking at TOP_RIGHT. Suite passes via `python -m pytest tests/test_widget_overlay_regressions.py`.

Next steps:
1. Continue plan with MC mode media key suppression investigation.
2. Keep regression tests expanded if new cases turn up.

---

## Investigation Notes Template

For each item capture:
1. **Symptoms / reproduction**
2. **Suspected root cause**
3. **Fix / mitigation**
4. **Tests / validation**

Update below as you work through each issue.

### Weather widget bottom-right margin
- Notes: _pending_

### Clock + Weather stacking regression
- Notes: _pending_

### MC mode media key suppression
- Notes: _pending_

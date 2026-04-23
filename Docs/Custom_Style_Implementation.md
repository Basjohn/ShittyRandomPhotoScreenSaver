# Custom Style Implementation

Last updated: 2026-04-23

Guidance for SRPSS custom UI styling.

## 1. Goals
- Keep the settings/dialog UI visually consistent and intentionally styled.
- Centralize style definitions to avoid per-widget/per-tab drift.
- Avoid style changes that hide runtime bugs instead of fixing root causes.

## 2. Source of Truth
- Shared styles live in the UI shared style modules and theme QSS.
- Reusable custom controls should be implemented once and reused.
- Avoid duplicating large style blocks in individual tabs/widgets.

## 3. Styling Contracts
- Use shared combo/slider/spinbox/input styling constants where available.
- Preserve established typography, spacing, and card/chrome language.
- Maintain cross-tab alignment consistency in settings rows.

## 4. Technical Safety
- Keep styling changes compatible with frameless/acrylic dialog behavior.
- Validate style changes against startup/show behavior to avoid transient ghost/flicker regressions.
- Do not remove custom shell styling as a workaround for runtime launch issues.

## 5. Change Process
When modifying UI styling:
1. update shared style source,
2. confirm affected tabs/widgets adopt it consistently,
3. run relevant UI/settings tests,
4. validate runtime behavior for show/focus/startup correctness.

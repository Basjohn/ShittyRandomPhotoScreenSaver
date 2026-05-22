# Custom Style Implementation

Last updated: 2026-05-22

Guidance for SRPSS custom UI styling.

## 1. Goals
- Keep the settings/dialog UI visually consistent and intentionally styled.
- Centralize style definitions to avoid per-widget/per-tab drift.
- Avoid style changes that hide runtime bugs instead of fixing root causes.

## 2. Source of Truth
- Shared styles live in the UI shared style modules and theme QSS.
- Reusable custom controls should be implemented once and reused.
- Avoid duplicating large style blocks in individual tabs/widgets.
- Styled confirmation and affordance surfaces should use the shared styled-popup/chrome path instead of inventing one-off dialog visuals in tabs.

## 3. Styling Contracts
- Use shared combo/slider/spinbox/input styling constants where available.
- Preserve established typography, spacing, and card/chrome language.
- Maintain cross-tab alignment consistency in settings rows.
- Temporary UX affordances, such as CUSTOM lock notices or edit-shell controls, should look intentionally part of the same SRPSS UI family rather than default Qt widgets dropped into the surface.

## 4. Technical Safety
- Keep styling changes compatible with frameless/acrylic dialog behavior.
- Validate style changes against startup/show behavior to avoid transient ghost/flicker regressions.
- Do not remove custom shell styling as a workaround for runtime launch issues.
- Avoid style changes that force constructor-time show/hide churn, popup creation, or focus side effects just to “make it look right”.

## 5. Change Process
When modifying UI styling:
1. update shared style source,
2. confirm affected tabs/widgets adopt it consistently,
3. run relevant UI/settings tests,
4. validate runtime behavior for show/focus/startup correctness.

## 6. SRPSS-Specific Current Rules
- Settings warnings that trigger actions, such as `Disable Custom Mode To Change!`, should be styled as part of the normal dialog language and use the shared popup path for confirmation.
- Edit-mode shell controls should remain visually subordinate to widget content but still read as deliberate affordances; avoid introducing a second design language for runtime edit controls.
- If a new widget family needs special chrome, prefer extending shared style helpers or shared base-widget paint behavior before adding local QSS fragments.

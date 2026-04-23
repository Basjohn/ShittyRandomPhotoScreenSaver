# Widget Guidelines

Last updated: 2026-04-23

Canonical implementation guidelines for overlay widgets.

## 1. Ownership and Lifecycle
- Widget creation/destruction is coordinated through `rendering/widget_manager.py`.
- Qt object cleanup follows `ResourceManager` conventions.
- Widget startup/fade behavior must align with shared startup/fade policy.

## 2. Threading Rules
- Background work uses `ThreadManager`; no ad hoc worker threads in widget code.
- UI updates occur on the UI thread only.
- Polling and network/file fetches do not run in paint/update paths.

## 3. Positioning Rules
- Positioning is centralized through rendering/widget positioning helpers.
- Anchor-dependent widgets (for example mute/volume relative to media card) must follow shared dependent-visibility logic.
- Widgets should not implement independent ad hoc geometry systems when a shared one exists.

## 4. Startup Staging Rules
- Primary-stage and secondary-stage startup responsibilities must be respected.
- Secondary-stage widgets wait until anchor visibility and initial geometry are valid.
- Avoid first-frame flash/teleport behavior by computing position before reveal.

## 5. Styling Rules
- Preserve the established custom visual style system.
- Keep shared style helpers and constants centralized.
- Do not use one-off styling overrides to mask behavior bugs.

## 6. Interaction Rules
- Input routing remains centralized in rendering/input handlers.
- Widget-specific click/gesture behavior should integrate through shared routing contracts.
- Do not add global event hooks inside individual widgets unless architecture explicitly requires it.

## 7. Performance Rules
- Keep paint/update work minimal and cache where appropriate.
- Avoid expensive operations inside `paintEvent` and high-frequency callbacks.
- Prefer coalesced updates over rapid repeated repaints.

## 8. Change Checklist
When adding/changing a widget, verify:
- settings defaults + model plumbing,
- settings load/save path,
- runtime creation + teardown,
- startup fade/stage behavior,
- dependent visibility + positioning,
- focused tests for lifecycle and behavior regressions.

# Widget Guidelines

Last updated: 2026-05-17

Canonical implementation guidelines for overlay widgets.

## 1. Ownership and Lifecycle
- Widget creation/destruction is coordinated through `rendering/widget_manager.py`.
- Factory-backed widget family metadata is centralized through `rendering/widget_descriptors.py`.
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

## 9. New Widget Integration Checklist
Use this when adding a new widget family such as a future Steam widget. The goal is to touch the real ownership seams once, not scatter one-off glue.

1. Runtime widget implementation
- Add the widget runtime module under `widgets/`.
- Reuse `BaseOverlayWidget` when the widget is a framed overlay card; only diverge when the runtime truly requires it.

2. Factory registration
- Add or extend the widget factory in `rendering/widget_factories.py`.
- Inject `ThreadManager` / `ProcessSupervisor` only through the established factory and manager seams.
- Add or extend the widget descriptor in `rendering/widget_descriptors.py` so identity, reuse, factory routing, and startup-stage intent are not duplicated elsewhere.

3. Setup orchestration
- Register creation, expected-overlay tracking, and parent-attribute binding through the descriptor-driven path in `rendering/widget_setup_all.py`.
- If the widget has complex dependent anchoring or staged startup, wire that through `rendering/widget_manager.py` rather than adding a private startup path.

4. Runtime capability ownership
- Extend the runtime descriptor metadata in `rendering/widget_descriptors.py` for startup stage, anchor dependence, service-backed status, settings-section ownership, and live-refresh routing.
- Extend the descriptor-owned preview/settings metadata there too when a standard widget family participates in `WidgetsTab` preview/save composition; do not leave a second handwritten `_build_current_widgets_config()` truth behind for those same fields.
- If a widget family already has a descriptor-owned live refresh handler, do not add a parallel handwritten prefix route in `rendering/widget_manager.py`.
- Position-option ownership belongs there too. If a widget exposes the standard settings position chooser, consume descriptor-owned labels/capabilities instead of retyping the same 9-grid list in each settings builder.
- If a widget may eventually participate in custom edit-mode resize, record that as descriptor-owned capability metadata and keep the size change tied to real widget-owned logical controls, with a clear settings-side reset affordance.

4.1 Service-backed lifecycle mechanics
- For service-backed widgets such as Gmail, Reddit, and Weather-style overlays, reuse `widgets/service_widget_runtime.py` for parent transition probes, deferred single-shot timers, deferred refresh/result staging, spinner suspend/resume, fetch-in-progress begin/end guards, manual-refresh request flow, and timer-stop cleanup where that contract matches.
- Do not force provider logic or authored UI into the shared helper. Keep fetch semantics, cache fallback policy, and paint/layout behavior widget-owned.

5. Positioning and dependent geometry
- Add positioning support in `rendering/widget_positioner.py`.
- If the widget depends on another widget's geometry, follow the shared anchor/dependent-visibility contract instead of inventing ad hoc coordinate math.

6. Effects, fade, and invalidation
- Ensure the widget participates in the shared overlay fade/effect lifecycle through `rendering/widget_manager.py` and `rendering/widget_effects.py` when appropriate.
- Do not add private focus/effect hacks to paper over stale shadow or fade bugs.

7. Input routing
- Add hit testing and click/URL routing in `rendering/input_handler.py` only if the widget is interactive.
- Keep non-URL controls separate from real URL opens so helper/exit behavior is not triggered accidentally.

8. Settings defaults and persistence
- Add canonical defaults in `core/settings/default_settings.py`.
- If the widget uses typed settings models, extend the relevant model in `core/settings/models/` and keep `from_settings`, `from_mapping`, and `to_dict` symmetric.
- If the widget is intentionally following an existing flat-dict exception, document that exception explicitly instead of silently creating a second pattern.

9. Settings UI
- Add the settings builder/load/save wiring in `ui/tabs/widgets_tab.py` and the relevant `ui/tabs/widgets_tab_*.py` helper module.
- Extend the descriptor-owned WidgetsTab section registry in `rendering/widget_descriptors.py` so section order, labels, gating, and builder routing stay centralized.
- Respect settings-dialog flicker guardrails: no constructor-time show/hide churn, no broad update disabling, and preserve bucket-state persistence if the widget uses buckets.

10. Display/runtime integration
- Update `rendering/display_widget.py` only when the widget needs display-level callbacks, transition-aware busy checks, or top-level runtime references.
- Keep routine widget creation out of `DisplayWidget` when `WidgetManager`/factory/setup seams already own it.

11. Documentation and tests
- Refresh `Spec.md`, `Index.md`, and `Docs/TestSuite.md` when the widget changes live contracts or adds regression coverage.
- Add focused lifecycle, settings, and interaction tests before broad runtime/manual validation.

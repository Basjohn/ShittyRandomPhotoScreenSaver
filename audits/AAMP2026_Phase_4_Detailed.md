# AAMP2026 Phase 4 Detailed Plan – Widget & Settings Modularity (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Lock-free/atomic + ThreadManager policy reaffirmed; no raw Qt timers.
- [ ] Phase 1/2 plans finalized (workers, schemas, supervisor, shared memory).

## 1) Scope & Goals
- [ ] Slim WidgetManager into coordinator; factories + positioner own creation/placement.
- [ ] Enforce typed settings end-to-end (runtime + UI) with MC vs Screensaver profile separation.
- [ ] Overlay guideline compliance across all widgets.

## 2) WidgetManager Refactor
- [ ] Remove widget-specific conditionals; expose minimal API to DisplayWidget (fade/raise/start/stop).
- [ ] Centralize overlay fade/raise logic; integrate ResourceManager for lifecycle cleanup.
- [ ] Ensure lock-free patterns where possible; document any unavoidable locks.

## 3) Typed Settings Adoption
- [ ] Define dataclasses/models for widgets/rendering settings with validation.
- [ ] Helper to/from dot-notation for persistence; ensure SettingsManager mapping preserves MC vs Screensaver profiles.
- [ ] UI tabs consume models; changes propagate via SettingsManager change notifications.

## 4) Overlay Guidelines Audit
- [ ] Audit all widgets against `Docs/10_WIDGET_GUIDELINES.md` (header/logo alignment, fade sync, ResourceManager registration).
- [ ] Include `ui/widget_stack_predictor.py` alignment.

## 5) Testing Strategy (Design)
- [ ] Expand `tests/test_widget_factories.py`, `tests/test_widget_positioner.py` for new cases.
- [ ] Integration tests for multi-widget start/stop sequences verifying lifecycle ordering and fade sync.
- [ ] Settings model tests: serialization/deserialization, profile separation, validation.

## 6) Documentation & Backups Plan
- [ ] Keep audit Phase 4 checklist in sync with this doc.
- [ ] Spec.md stays current-state (no planning).
- [ ] Index.md: update WidgetManager/factories/positioner/settings entries when implemented.
- [ ] `/bak`: snapshots pre/post for modules touched.

## 7) Exit Criteria (Planning Only)
- [ ] All checkboxes resolved with concrete decisions documented.
- [ ] Main audit updated with any deltas; no code written.

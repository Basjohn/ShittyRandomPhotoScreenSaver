# AAMP2026 Phase 4 Detailed Plan – Widget & Settings Modularity (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Lock-free/atomic + ThreadManager policy reaffirmed; no raw Qt timers.
- [ ] Phase 1/2 plans finalized (workers, schemas, supervisor, shared memory).

## 1) Scope & Goals
- [ ] Slim WidgetManager into coordinator; factories + positioner own creation/placement.
- [ ] Enforce typed settings end-to-end (runtime + UI) with MC vs Screensaver profile separation.
- [ ] Overlay guideline compliance across all widgets.
- [ ] Ensure modal Settings workflows do not depend on engine restarts; live widget configs must react instantly to slider/toggle changes.
- [ ] Guard against unintended engine shutdown when monitors or the “primary display” toggle change while Settings is open; the dialog must not clobber the running screensaver session.

## 2) WidgetManager Refactor
- [ ] Remove widget-specific conditionals; expose minimal API to DisplayWidget (fade/raise/start/stop).
- [ ] Delegate instantiation to widget factories; WidgetManager only orchestrates (no per-widget branching).
- [ ] Integrate `WidgetPositioner` end-to-end: `set_container_size()`, `position_widget_by_anchor()`, collision handling, stack offsets.
- [ ] Centralize overlay fade/raise logic; integrate ResourceManager for lifecycle cleanup.
- [ ] Ensure lock-free patterns where possible; document any unavoidable locks (only when coordinator state truly shared).
- [ ] Document how WidgetManager enforces profile separation (Media Center vs Screensaver) when spawning widgets.

## 3) Typed Settings Adoption
- [x] Update `SettingsManager` to use dataclass models end-to-end (load/save + change notifications). ✅ _2026‑01‑01_: Added Spotify visualizer/media/reddit typed helpers plus `set_many`; existing models audited.
- [x] Migrate every `settings.get`/`settings.set` caller to typed accessors; remove legacy flat keys. ✅ _2026‑01‑01_: WidgetManager creation + refresh for media/reddit/Spotify VIS now resolve through typed models, and widgets consume typed configs.
- [x] Ensure helper to/from dot-notation for persistence; MC vs Screensaver profiles stay isolated. ✅ _2026‑01‑01_: Model `from_settings` + `from_mapping` + `to_dict` cover both dotted and section maps.
- [x] UI tabs consume models (form binding helpers convert dataclasses <-> UI state). ✅ _2026‑01‑01_: Widgets tab produces full section dicts that typed models deserialize; no direct `settings.get` calls remain in UI logic for migrated widgets.
- [x] Add migration shim for legacy configs (one-time transform) and document removal timeline. ✅ _2026‑01‑01_: `from_mapping` accepts both dotted keys and legacy embedded dicts to keep backward compatibility; removal noted for Phase 5.
- [x] Capture live-setting reaction requirements explicitly: widget-facing services (e.g. Spotify visualizer sensitivity/floor) must subscribe to the typed settings model so manual overrides take effect even if the engine stays running. ✅ _2026‑01‑01_: WidgetManager now refreshes Spotify VIS/media/reddit on `settings_changed`, with tests covering VIS + Spotify volume live behaviour.
- [x] Document the monitoring/display dependency: if the “primary display” checkbox gets toggled off, the settings model must inform DisplayWidget without killing the engine; typed accessors should expose the linkage so UI modals can issue non-destructive refreshes instead of triggering full restarts. ✅ _2026‑01‑01_: Settings doc updated; WidgetManager hooks reuse typed monitor fields without engine restart.

## 4) Overlay Guidelines Audit
- [ ] Audit all widgets against `Docs/10_WIDGET_GUIDELINES.md` (header/logo alignment, fade sync, ResourceManager registration).
- [ ] Include `ui/widget_stack_predictor.py` alignment.

## 5) Testing Strategy (Design)
- [ ] Expand `tests/test_widget_factories.py`, `tests/test_widget_positioner.py` for new cases (multi-monitor, collision, stacking).
- [ ] Add `tests/test_widget_manager.py` lifecycle suite (start/stop order, ResourceManager cleanup, fade orchestration).
- [ ] Settings model tests: serialization/deserialization, profile separation, validation; ensure `tests/test_settings_type_safety.py` stays green.
- [ ] Integration tests for UI tabs using typed models; migration tests verifying legacy config upgrade path.

## 6) Documentation & Backups Plan
- [ ] Keep audit Phase 4 checklist in sync with this doc.
- [ ] Spec.md stays current-state (no planning).
- [ ] Index.md: update WidgetManager/factories/positioner/settings entries when implemented.
- [ ] `/bak`: snapshots pre/post for modules touched.

## 7) Exit Criteria (Planning Only)
- [ ] All checkboxes resolved with concrete decisions documented.
- [ ] Main audit updated with any deltas; no code written.

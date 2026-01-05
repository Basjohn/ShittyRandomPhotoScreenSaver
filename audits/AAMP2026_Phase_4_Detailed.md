# AAMP2026 Phase 4 Detailed Plan – Widget & Settings Modularity (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [x] Lock-free/atomic + ThreadManager policy reaffirmed; no raw Qt timers. ✅ _2026-01-05_
- [x] Phase 1/2 plans finalized (workers, schemas, supervisor, shared memory). ✅ _2026-01-05_ (113 tests passing)

## 1) Scope & Goals
- [ ] Slim WidgetManager into coordinator; factories + positioner own creation/placement.
- [ ] Enforce typed settings end-to-end (runtime + UI) with MC vs Screensaver profile separation.
- [ ] Overlay guideline compliance across all widgets.
- [ ] Ensure modal Settings workflows do not depend on engine restarts; live widget configs must react instantly to slider/toggle changes.
- [ ] Guard against unintended engine shutdown when monitors or the “primary display” toggle change while Settings is open; the dialog must not clobber the running screensaver session.

## 2) WidgetManager Refactor
- [x] Remove widget-specific conditionals; expose minimal API to DisplayWidget (fade/raise/start/stop). ✅ _2026-01-05_
- [x] Delegate instantiation to widget factories; WidgetManager only orchestrates (no per-widget branching). ✅ _2026-01-05_
- [x] Integrate `WidgetPositioner` end-to-end: `set_container_size()`, `position_widget_by_anchor()`, collision handling, stack offsets. ✅ _2026-01-05_
- [x] Centralize overlay fade/raise logic; integrate ResourceManager for lifecycle cleanup. ✅ _2026-01-05_
- [x] Ensure lock-free patterns where possible; document any unavoidable locks (only when coordinator state truly shared). ✅ _2026-01-05_
  - Note: QTimer.singleShot used for UI-thread deferred execution (acceptable per Qt threading model)
  - Rate-limited raise uses time.time() comparison (lock-free)
  - Fade coordination uses dict/set (single-threaded UI access)
- [ ] Document how WidgetManager enforces profile separation (Media Center vs Screensaver) when spawning widgets.

## 3) Typed Settings Adoption
- [x] Update `SettingsManager` to use dataclass models end-to-end (load/save + change notifications). ✅ _2026‑01‑01_: Added Spotify visualizer/media/reddit typed helpers plus `set_many`; existing models audited.
- [x] Migrate every `settings.get`/`settings.set` caller to typed accessors; remove legacy flat keys. ✅ _2026‑01‑01_: WidgetManager creation + refresh for media/reddit/Spotify VIS now resolve through typed models, and widgets consume typed configs.
- [x] Ensure helper to/from dot-notation for persistence; MC vs Screensaver profiles stay isolated. ✅ _2026‑01‑01_: Model `from_settings` + `from_mapping` + `to_dict` cover both dotted and section maps.
- [x] UI tabs consume models (form binding helpers convert dataclasses <-> UI state). ✅ _2026‑01‑01_: Widgets tab produces full section dicts that typed models deserialize; no direct `settings.get` calls remain in UI logic for migrated widgets.
- [x] Add migration shim for legacy configs (one-time transform) and document removal timeline. ✅ _2026‑01‑01_: `from_mapping` accepts both dotted keys and legacy embedded dicts to keep backward compatibility; removal noted for Phase 5.
- [x] Capture live-setting reaction requirements explicitly: widget-facing services (e.g. Spotify visualizer sensitivity/floor) must subscribe to the typed settings model so manual overrides take effect even if the engine stays running. ✅ _2026‑01‑01_: WidgetManager now refreshes Spotify VIS/media/reddit on `settings_changed`, with tests covering VIS + Spotify volume live behaviour.
- [x] Document the monitoring/display dependency: if the “primary display” checkbox gets toggled off, the settings model must inform DisplayWidget without killing the engine; typed accessors should expose the linkage so UI modals can issue non-destructive refreshes instead of triggering full restarts. ✅ _2026‑01‑01_: Settings doc updated; WidgetManager hooks reuse typed monitor fields without engine restart.
## 4) Modal Settings Conversion
- [ ] **Defaults realignment gate (pre-modal work)** – Follow `audits/setting manager defaults/Setting Defaults Guide.txt`: import both SST snapshots (`SRPSS_Settings_Screensaver.sst`, `SRPSS_Settings_Screensaver_MC.sst`), verify SettingsManager canonical defaults cover every value the SSTs relied on, ensure reset-to-defaults immediately applies those values, assert MC build defaults fall back to a single available monitor when display 2 is missing, confirm automatic geo detection remains the default for weather location, and document the “no sources” popup + Just Make It Work/Ehhhh flow before proceeding to modal settings improvements. Remove dependence on SST files after parity is proven.
- [ ] Convert the existing settings dialog into the modal workflow defined in Spec.md, preserving the custom title bar/theme and ensuring both SRPSS and MC builds can summon it without restarting the engine.
- [ ] Wire the modal lifecycle to `SettingsManager.settings_changed` so edits apply live (DisplayWidget refresh, widget config updates, queue/source changes) without forcing teardown/reinit.
- [ ] Integrate the Just Make It Work/Ehhhh guard into the modal flow: enforce sources validation, show the canonical popup styling, and persist the choice through SettingsManager.
- [ ] Update Spec.md + Docs/TestSuite.md with the modal workflow, launch triggers, and regression coverage; add pytest covering modal open/close sequencing, live updates, and reset-to-defaults behavior.

## 5) Overlay Guidelines Audit
- [ ] Audit all widgets against `Docs/10_WIDGET_GUIDELINES.md` (header/logo alignment, fade sync, ResourceManager registration).
- [ ] Include `ui/widget_stack_predictor.py` alignment.

## 6) Testing Strategy (Design)
- [ ] Expand `tests/test_widget_factories.py`, `tests/test_widget_positioner.py` for new cases (multi-monitor, collision, stacking).
- [x] Add `tests/test_widget_manager.py` lifecycle suite (start/stop order, ResourceManager cleanup, fade orchestration). ✅ _2026-01-05_ (20 tests)
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

# SRPSS Guardrails

Last updated: 2026-05-22

Policy rules to keep architecture coherent and prevent repeat regressions.

## 1. Documentation Boundaries
- `Spec.md` for architecture contracts.
- `Index.md` for module ownership map.
- `Current_Plan.md` for active work only.
- `Docs/Historical_Bugs.md` for dated bug narratives.
- `Docs/Visualizer_Change_Checklist.md` for visualizer setting changes.
- Runtime logging families should present a CLI-first operator surface. Prefer explicit flags such as `--perf`, `--viz`, `--geo`, `--set`, and `--life`; do not reintroduce environment-variable activation for diagnostic families.

## 2. Centralized Ownership
- Threading through `ThreadManager`.
- Qt lifecycle through `ResourceManager`.
- Settings through `SettingsManager`.
- Shared timeline/tick-driven runtime animation through `AnimationManager`.
- Cross-module publish/subscribe events through `EventSystem`.
- Worker process orchestration through `ProcessSupervisor`.
- Worker-process callers should consume supervisor-owned correlated response helpers or polling surfaces, not raw response queues. Do not keep a second queue-drain contract in engine/rendering code, and do not reintroduce the dormant callback-listener facade as if it were a live runtime path.
- Leaf/runtime helper code should prefer the app-shared `ThreadManager` / `ResourceManager` seam rather than constructing ad hoc manager instances.
- Leaf/runtime animation helpers should prefer the app-shared `AnimationManager` seam rather than constructing ad hoc managers when they only need ordinary shared-timeline animation ownership.
- If a helper path truly must create its own `ThreadManager`, keep that fallback intentionally narrow instead of silently creating another full-size compute-heavy manager.
- Do not let `ThreadManager` active-task truth depend on deferred UI-thread bookkeeping. Submit/complete/cancel/shutdown paths must see the same authoritative in-flight task registry immediately.
- Prefer one clean contract path over mirrored implementations. If the code already has a canonical seam for a behavior, extend that seam instead of adding a second “similar but slightly different” path nearby.
- During display/widget startup, do not keep two lifecycle-start authorities alive. If `widget_setup_all` already initializes/activates the created widgets, display glue must not immediately run another initialize pass over the same set.

No shadow frameworks or parallel ownership paths.

## 3. Settings Safety
- Canonical defaults are single-source.
- Section/root writes must invalidate descendant cache entries.
- Root `widgets` writes, widgets-map replacement helpers, and SST widget imports must share one widgets-map normalization/schema contract. Do not allow `set("widgets", ...)`, `set_widgets_map(...)`, or import flows to drift into different visualizer-schema or default-merge behavior.
- Public settings mutation APIs should not drift in sync/signal semantics. If `set`/`set_section` notify runtime listeners and flush critical roots, do not leave `remove`/`clear` behind as silent special cases unless that silence is a deliberate documented contract.
- Reset/import preserve behavior uses one shared preservation contract.
- Retired global preset schema keys stay retired.

## 4. Visualizer Safety
- Mode identity and labels come from the mode registry.
- Internal ids remain stable even when user-facing labels change.
- Shared seams stay explicit and neutral.
- Reindex logic is index/filename normalization, not creative payload rewriting.
- `core/settings/models/_spotify_visualizer.py` is the grouped field-spec source of truth for visualizer settings ingestion/persistence. When a settings family changes, update its defaults/build specs/serializer specs together and preserve ordered grouped merges for `from_settings()`, `from_mapping()`, and `to_dict()`.
- Do not reintroduce bespoke entry-point-specific field families or fallback paths once a visualizer settings group has been centralized.
- `rendering/transition_registry.py` is the canonical source of truth for ordinary transition identity, legacy alias handling, cycle/random participation, hardware gating, and startup shader warmup metadata. Do not add new handwritten transition-name lists to the tab, context menu, engine, factory, or compositor when the registry can own the same truth.
- `widgets/spotify_visualizer/card_geometry.py` is the canonical source of truth for Spotify visualizer outer card geometry. Keep mode/preset-owned preferred height, blob-width reduction, and media-relative placement there; keep painted-card stencil math in `widgets/spotify_visualizer/overlay_mask.py` / `overlay_frame_shell.py` rather than blending the two contracts together.

## 5. UI/UX Safety
- Do not remove custom styling to hide runtime issues.
- Fix startup/focus/visibility bugs at root cause.
- Respect staged startup contracts for dependent overlay widgets.
- If startup or a display-recreation path cannot show the first image immediately, use a bounded immediate retry seam before falling back to the long rotation timer. Do not leave recreated/cold startup displays blank just because a transient load was already in progress.
- When settings entry, stop, or teardown is involved, suppress new runtime work through the explicit quiesce boundary (`ScreensaverEngine.stop` → `DisplayManager.quiesce_all()` → `DisplayWidget.quiesce_for_runtime_pause()` → `WidgetManager.prepare_for_runtime_pause()`) instead of layering more late cleanup side effects onto display clear/hide paths.
- Settings-driven and CUSTOM-driven display recreation must arm a short recreated-display pointer-input suppression window so the save/revert/settings click that triggered the rebuild cannot be re-consumed by the newly created fullscreen displays.
- Browser-window preference work must stay narrow and centralized: helper/SCR and MC direct-open flows may share a best-effort display-0 foreground preference, but widget click handlers must not grow their own browser/window-selection logic or broader automation behavior.
- Do not over-centralize tiny widget-local effect fades just for purity. `AnimationManager` should own shared timeline/tick animation seams; tightly local `QVariantAnimation`/effect fades may remain widget-local when they are explicitly owned, cleaned up, and not recreating a second broader animation registry.

## 5.1 Widget Registry Safety
- `rendering/widget_descriptors.py` is the canonical source of truth for factory-backed widget family metadata.
- Do not add new handwritten setup branches in `rendering/widget_setup_all.py` for ordinary factory-backed widgets when the descriptor registry can own the same truth.
- Keep the remaining Spotify-dependent setup special cases explicit as one ordered setup plan, not as scattered helper-call coincidence. If a future widget introduces a real startup/reconcile dependency, add it as an explicit phase or extend descriptor truth; do not hide it in ad hoc local ordering.
- When a widget needs base-settings inheritance, shadow-config injection, or environment gating, extend the descriptor contract rather than duplicating that setup logic at the call site.
- `ui/tabs/widgets_tab.py` must consume the descriptor-owned widget section registry for section order, labels, dev gating, and builder routing. Do not keep a parallel handwritten subtab list there once the descriptor path owns it.
- `ui/tabs/widgets_tab.py` must use descriptor-owned standard-section signal-block target collection during load-time population instead of re-scanning standard section attr names inline. Keep only genuinely special non-standard control groups explicit where the descriptor layer would not improve clarity.
- Descriptor-layer cleanup should reduce fragmented helper surfaces and duplicate UI truth, not invent a second level of implicit magic. If a UI descriptor needs routing authority, prefer deriving it from the runtime descriptor contract instead of storing a second settings-key truth.
- Cached active descriptor views are acceptable, but they must stay environment-aware so dev-gated families such as Imgur do not go stale across tests or runtime toggles.
- `rendering/widget_manager.py` must consume descriptor-owned runtime capability metadata for live settings routing when a widget family already has a canonical handler. Do not reintroduce handwritten `startswith("widgets....")` ownership checks for descriptor-owned families.
- Descriptor-owned service-runtime contract participation also belongs in `rendering/widget_descriptors.py`. Do not widen shared service-backed behavior based only on `service_backed=True` when the finer-grained contract can be recorded explicitly.
- `WidgetsTab` preview/save truth for standard widget families should prefer descriptor-owned stack-preview/settings-composition metadata over handwritten per-widget UI reads. If a widget field must stay special-cased, document why the descriptor contract could not express it.
- `WidgetsTab` should also prefer descriptor-owned application of standard saved section payloads once persisted-key ownership already lives in the descriptor registry. Keep special persistence merges, such as visualizer mode-preserving save behavior, explicit rather than hiding them in a generic helper.
- Keep the Defaults section on the same descriptor-owned build/load/save path as the other standard sections. Do not reintroduce a half-special inline branch for shared widget shadow toggles or card-border-width persistence.

## 5.2 Service-Backed Widget Safety
- Shared service-backed widget lifecycle mechanics belong in `widgets/service_widget_runtime.py`.
- Do not re-copy parent transition probes, deferred single-shot timer ownership, deferred refresh/result staging, spinner suspend/resume logic, simple fetch-in-progress begin/end guard bookkeeping, manual-refresh request flow, or visible-fallback preservation for non-authoritative empty/error results into Gmail/Reddit/Weather-style widgets when the shared helper already expresses the contract.
- Do not treat `service_backed=True` as enough detail by itself when broadening shared widget behavior. Extend descriptor-owned service-runtime contract metadata first so widening stays explicit and reviewable.
- Keep provider behavior, cache semantics, and authored rendering local; the shared seam is for lifecycle mechanics, not a new widget superclass or manager hierarchy.

## 5.3 CUSTOM Layout Safety
- CUSTOM layout/edit mode must continue to extend descriptor-owned position/capability metadata rather than inventing a second widget-position registry.
- Edit mode remains a global active-display shell session; do not reintroduce display-local partial edit semantics.
- Edit-mode shell/grid ownership should follow normal runtime where possible: prefer display-owned child surfaces with explicit cross-display reparenting over separate top-level tool windows plus repeated `raise_()` correction.
- In edit mode, keep geometry authority clean too: `EditShellWidget` should emit/request global rects only, and `CustomLayoutManager` should own the live apply path plus global-to-local conversion instead of letting the shell move against an old parent first and then correcting it afterward.
- Drag feel matters as much as correctness. Live move drag should stay guide/clamp-driven and defer hard snap commits until release; do not make shells feel sticky by forcing full snap-to-grid/peer correction on every mouse-move event.
- While a CUSTOM edit session is active, treat the real system cursor as the only cursor authority. Suspend interaction-mode / Ctrl halo state for the whole session and restore only the ordinary hidden-cursor screensaver policy when the session exits.
- Edit-mode stack ownership should stay session-level, not caller-level. Background clicks, shell context-menu requests, and menu show/hide should request one shared deferred restack contract, and active context menus should suspend shell/grid restacks until the menu closes.
- Dragging must keep explicit snapping and compositor-backed-display target resolution; do not fall back to freehand or raw-screen heuristics.
- Resize must remain widget-logical and descriptor-owned. Plain scroll wheel and corner-drag resize are the current resize gestures; both must flow through the same widget-logical resize authority, and corner drag should keep the opposite corner anchored instead of inventing a separate freeform transform path.
- Any widget that supports CUSTOM resize must keep clear recovery affordances: runtime edit-shell reset plus settings-side authored-layout revert.
- Treat DPR and multi-monitor portability as a first-class constraint. Persist committed geometry through the shared CUSTOM layout contract, not ad hoc raw-pixel paths.
- While a saved CUSTOM rect is active, widget-local content/typography refresh logic must not become a second geometry authority. If a widget recalculates its own minimum/maximum size, the shared overlay/custom-layout seam must reassert the committed rect rather than letting the live widget silently resize itself.
- Saved CUSTOM rect replay must still respect real display bounds. Do not preserve a denormalized saved size so literally that replay can leak a widget past the target display edge.
- Keep the current runtime positioning system as the authored/default fallback path. `Custom` should remain unavailable until a real saved payload exists.
- Prefer safe edit shells/bounds during editing if live widget behavior would introduce churn, network work, or rendering instability.

## 6. Testing and Validation
- Add automated regression coverage for changed contracts.
- Do not treat tests alone as sufficient for visual/timing-sensitive bug closure.
- Preserve useful harnesses/probes that materially improve diagnosis quality.

## 7. Focus and Shadow Cache Safety (U-05 Lessons)

### 7.1 Focus Policy Manipulation
- **Never manipulate focus policies on large widget trees at runtime.**
- Recursive `setFocusPolicy()` on dozens of widgets destabilizes Qt's focus tree, causing `focusInEvent`/`focusOutEvent` cascades. Runtime widget shadows must stay on the painter-owned card/text/header paths; do not reintroduce `QGraphicsDropShadowEffect` for overlay shadows.
- If focus policy changes are required, apply them at widget construction time only.

### 7.2 Dead Code Verification
- **Always verify a new function is actually wired into a call chain before declaring a fix complete.**
- A function that "looks correct" but is never invoked is a regression waiting to happen. Use `grep` to confirm all new helpers have ≥1 caller in production code (excluding tests).

### 7.3 Multi-Top-Level Window Z-Order
- **When restoring focus/activation to a top-level window that has separate top-level overlays (halo, tooltips), always re-raise the overlays after raising the main window.**
- `widget.raise_()` on a top-level window changes its position in the desktop stack, which can push separate top-level overlay windows behind it even if they have `WindowStaysOnTopHint`.
- Re-raising overlays with `overlay.raise_()` after focus restoration preserves visual layering without affecting keyboard focus (overlays should have `WindowDoesNotAcceptFocus`).

### 7.4 Graphics Effect Recreation During Active Animations
- **Never recreate or replace a `QGraphicsEffect` (opacity, shadow, etc.) while a `QVariantAnimation` is actively driving it.**
- Overlay card/text/header shadows are painter-owned now, so broad menu/focus/display-change effect-cache busting should stay retired.
- `rendering/widget_effects.py` is a narrow transient-opacity refresh seam only: it may request repaint for widgets that currently own a live `QGraphicsOpacityEffect`, but it must not toggle, recreate, or broadcast effect churn just because a menu opened or focus changed.
- If a future regression appears, fix the real fade/effect owner or visual backing-store issue instead of reintroducing global cache-busting.

## 8. Visualizer State Isolation (R-22 Lessons)

### 8.1 Runtime Arrays and Caches Are Mode-Owned
- **Mode-specific runtime arrays, cached render-state buffers, and activation-era transient data must be cleared before a new visualizer mode or preset is allowed to commit fresh display state.**
- R-22 showed that reset/overlay cleanup alone is not enough if previous-mode arrays, floors, or pending compute work can still mutate shared runtime state after activation changes.
- Bar arrays, dynamic floors, AGC-like envelopes, transient buses, renderer-local history, and similar mode-owned caches must not survive a mode or preset boundary unless the new activation explicitly reuses them by contract.

### 8.2 Activation Must Be Transactional
- **Startup create, settings refresh, context-menu mode switch, double-click cycle, preset cycle, and forced preset activation must all consume the same resolved mode/preset payload before touching widget, engine, or overlay state.**
- Do not maintain separate "hot path" and "settings path" interpretations of the target mode config.
- Activation-id checks, generation tracking, and fresh-frame gates are not optional polish. They are part of the runtime isolation contract and must survive refactors.

### 8.3 Shared Settings Must Not Reintroduce Cross-Mode Bleed
- **Technical settings and preset-varying runtime visuals that belong to one mode must not leak back through shared/global authored keys after normalization.**
- Legacy shared/global technical keys may be accepted as migration inputs, but normalized settings, custom snapshots, and preset payloads must store mode-owned values under the owning mode.
- If diagnostics/logging report active visualizer state, they must reflect the resolved preset identity and the actual applied runtime/worker state, not only raw pre-normalized settings payloads.

# Widget Creation Guide

Last updated: 2026-06-30

Canonical A-to-Z guide for adding or deeply refactoring a non-visualizer widget in SRPSS.

Use this when the task is:
- adding a brand-new widget family,
- migrating an older widget onto current descriptor/setup/settings contracts,
- or checking whether a proposed widget design fits the current architecture cleanly.

This document is intentionally generic. It does not replace:
- `Spec.md` for live architecture contracts,
- `Index.md` for file ownership and module discovery,
- `Docs/Guardrails.md` for anti-regression policy,
- `Docs/Defaults_Guide.md` for defaults/reset behaviour,
- `Docs/Custom_Style_Implementation.md` for shared style/chrome rules,
- `Docs/Visualizer_Change_Checklist.md` for visualizer-specific work,
- or `Docs/Transition_Change_Checklist.md` for transition work.

## 1. Success Standard

If this guide is followed well, a new widget should:
- use one clean runtime ownership path,
- use canonical settings/defaults persistence,
- integrate into `WidgetsTab` without duplicate truth,
- keep the settings dialog cheap: a new section must not be built, hydrated, or made to touch a provider merely because the dialog opens,
- respect startup/fade/transition/custom-layout contracts,
- log through existing CLI families,
- and ship with focused regression bars rather than relying on runtime luck.

## 2. Decide What Kind Of Widget You Are Building

Before touching code, classify the widget:

1. Framed overlay card
- Most standard widgets belong here.
- Prefer `BaseOverlayWidget`.

2. Service-backed widget
- Gmail/Reddit/Weather style: refreshes, caching, deferred results, visible-fallback policy.
- Reuse `widgets/service_widget_runtime.py` where the contract fits.

3. Anchor-dependent widget
- Mute/volume/visualizer-adjacent style.
- Position/visibility must follow shared anchor logic instead of private geometry math.

4. Special display/runtime widget
- Only when the widget truly needs display-level callbacks, compositor awareness, or staged startup beyond ordinary descriptor/factory/setup seams.

5. `Custom`-participating widget
- If the family supports edit mode, treat authored/default geometry and committed custom geometry as separate authorities.
- Any size change must remain widget-logical, descriptor-owned, and recoverable.

If the answer is “several of the above”, keep each concern explicit. Do not solve service-backed, custom-layout, and anchor behavior by blending them into one opaque helper.

## 3. Canonical Documents To Read First

Read these before implementation:
- `Spec.md`
- `Index.md`
- `Docs/Guardrails.md`
- `Docs/Defaults_Guide.md`
- `Docs/Documentation_Maintenance.md`
- `Docs/TestSuite.md`
- `Current_Plan.md` if the widget area is under active work
- `Docs/Historical_Bugs.md` if the area is fragile or similar to a past regression

Also read these when relevant:
- `Docs/Custom_Style_Implementation.md` for shared visual language
- `Docs/Harness_Index.md` if the widget has behavior we can diagnose with an existing harness
- the current custom-layout traces/audits when the widget participates in `Custom`, especially when it has dynamic text, sizing, or asynchronous refreshes

## 4. Canonical Ownership Map

These are the seams a new widget should usually flow through:

- Runtime widget class: `widgets/`
- Factory construction: `rendering/widget_factories.py`
- Canonical widget family metadata: `rendering/widget_descriptors.py`
- Creation/reuse/startup orchestration: `rendering/widget_setup_all.py`
- Runtime lifecycle/fade/refresh routing: `rendering/widget_manager.py`
- Positioning math: `rendering/widget_positioner.py`
- Input routing: `rendering/input_handler.py`
- Settings UI section build/load/save and lazy subtab routing: `ui/tabs/widgets_tab.py` plus `ui/tabs/widgets_tab_<family>.py`
- Canonical defaults: `core/settings/default_settings.py`
- Defaults/reset contract: `core/settings/defaults.py`
- Typed settings model, if used: `core/settings/models/`
- Persistent storage paths: `core/settings/storage_paths.py`
- Shared service-backed runtime helpers: `widgets/service_widget_runtime.py`

Do not add a second creation path, second settings truth, second lifecycle owner, or second settings-dialog construction path just because the canonical seam feels annoying.

## 5. A-To-Z Build Order

### A. Define the widget contract first

Write down, at least briefly:
- what the widget shows,
- whether it is interactive,
- whether it is service-backed,
- whether it participates in `Custom`,
- whether it depends on another widget,
- whether it has standard `WidgetsTab` section behavior,
- whether its settings need a lazy-built subtab,
- what work is forbidden while the settings dialog is merely opening,
- and which logs/tests will prove it works.

If this contract is fuzzy, code will drift fast.

### B. Build the runtime widget

- Add the widget module under `widgets/`.
- Prefer `BaseOverlayWidget` for framed cards.
- Keep paint/layout behavior widget-owned.
- Keep provider/network/cache policy widget-owned unless the repo already has a shared seam for that exact behavior.
- Do not do blocking work in `paintEvent`, update paths, or constructors.
- When a `Custom` widget has dynamic content, make its inner layout respond to the committed size payload; a correct outer rect alone is not proof that text, columns, margins, or child geometry are correct.

### C. Use centralized managers only

- Background work: `ThreadManager`
- Qt object lifecycle: `ResourceManager`
- Settings: `SettingsManager`
- Shared animations: `AnimationManager`
- Cross-module events: `EventSystem`
- Worker processes, if truly needed: `ProcessSupervisor`

No ad hoc worker threads, second managers, or private queue systems.

### D. Add factory creation

- Create or extend the family factory in `rendering/widget_factories.py`.
- Thread manager, config injection, and base settings inheritance should enter through the factory seam.
- If the widget needs special setup kwargs, put that truth in the descriptor/factory seam, not in random call sites.

### E. Add the descriptor

`rendering/widget_descriptors.py` is where a new ordinary widget becomes real.

Capture there:
- stable widget id,
- live runtime attr name,
- factory routing,
- settings section ownership,
- position-option/layout-edit capability,
- startup stage,
- anchor/service-backed/runtime capability metadata,
- live-refresh handler ownership,
- `WidgetsTab` section metadata and lazy-builder routing,
- preview/settings-composition metadata,
- and `Custom`-related capability/lock metadata where relevant.

A descriptor may describe how a settings section is reached, but it must not force that section to instantiate. Any exception such as `bootstrap_in_lazy_mode` needs a concrete reason: what cannot work without it, why a small placeholder cannot solve it, and which unrelated dialog-open cost it adds.

If a widget needs handwritten truth somewhere else after the descriptor exists, treat that as a smell and justify it.

### F. Hook creation into setup orchestration

- Use `rendering/widget_setup_all.py` for creation/reuse/expected-overlay/startup orchestration.
- Do not add a second creation path inside `DisplayWidget` unless the runtime truly demands it.
- If the widget has staging or dependency ordering, make it explicit in the setup flow rather than as hidden side effects.

### G. Wire runtime lifecycle and positioning

- Use `rendering/widget_manager.py` for fades, visibility fan-out, settings refresh, and runtime interactions.
- Use `rendering/widget_positioner.py` for authored/default geometry.
- If the widget depends on an anchor widget, use shared dependent-visibility and positioning rules.
- Do not invent a private geometry system if the widget fits the shared one.

### H. Respect `Custom` layout correctly

If the widget participates in edit mode:
- descriptor metadata must declare that participation,
- authored/default position and committed `Custom` rect must stay separate,
- live content refresh must not become a second outer-geometry authority,
- any resize contract must remain widget-logical and recoverable,
- and tests/logs must distinguish outer widget geometry from the internal painted/content geometry.

If the widget does not participate in `Custom`, do not half-implement it accidentally.

### I. Add settings defaults and persistence

- Add canonical defaults in `core/settings/default_settings.py`.
- Respect the shared defaults/reset preservation contract in `core/settings/defaults.py`.
- If the widget uses a typed settings model, keep `from_settings()`, `from_mapping()`, and `to_dict()` symmetric.
- If the widget is intentionally using a flat-dict exception, document that rather than silently cloning a second pattern.
- Use `core/settings/storage_paths.py` for persistent files or caches. Do not invent home-dir or temp-dir storage paths when a canonical app-data seam already exists.
- Use public `SettingsManager` path accessors when UI code needs the active settings file or folder.
- Verify that a root/section write does not leave stale dotted-key cache values behind.

### J. Add `WidgetsTab` integration without growing dialog-open cost

A new widget normally gets a **registered but unbuilt** settings section. Opening the settings dialog must only create the lightweight `WidgetsTab` shell, route metadata, and whichever subtab is actually selected; it must not construct every widget’s controls just because they exist.

- Add settings builder/load/save code in the relevant `ui/tabs/widgets_tab_<family>.py` helper.
- Extend descriptor-owned section order, labels, and builder routing instead of keeping a second handwritten list in `widgets_tab.py`.
- Default the section to lazy-built. It should construct when the user first opens that subtab, or at a documented unavoidable programmatic entry point—not during `WidgetsTab.__init__`, dialog restoration, general settings load, or another widget's build.
- Treat `bootstrap_in_lazy_mode` as a rare exception. Record why it is required and prove that it does not pull unrelated sections or provider work into dialog startup.
- Keep lazy dependencies and programmatic dependencies minimal and explicit. A new widget section must not build another widget section merely to borrow a control, read a label, or reuse a helper.
- Keep imports at registration time light. If a family module has expensive Qt construction, optional provider imports, cache reads, credential probing, or environment detection, defer that work until its builder is genuinely selected.
- The builder may create controls, hydrate them from persisted settings, wire signals, and restore its shared bucket/scroll state. It must not create the runtime overlay, start a worker, contact a provider, test credentials, walk caches, scan media, or perform synchronous backend work.
- Extend descriptor-owned signal-block metadata/helpers for ordinary controls. Hydrate controls with signals blocked so first construction does not emit writes, runtime refreshes, repeated `update()` calls, or accidental auth/provider actions.
- Prefer descriptor-owned persisted-payload application helpers over manual one-off reassignment.
- Preserve lazy correctness on save: an unvisited/unbuilt section must not be serialized as an empty or default payload that overwrites existing persisted settings. Save only controls that exist, and merge with the canonical persisted/default structure through the normal settings path.
- Respect settings-dialog flicker rules: no constructor-time show/hide churn, no broad update disabling, preserve bucket-state persistence.
- Reuse shared bucket-state and scroll-state patterns rather than widget-local persistence sidecars.
- Keep a focused `--perf` measurement for expensive builds. A first visit may cost work; repeated visits must not rebuild the section, and opening the dialog without visiting it must cost essentially nothing for that family.

### K. Add input only through shared routing

If the widget is interactive:
- add hit testing/click routing through `rendering/input_handler.py`,
- keep non-URL controls separate from real URL opens,
- do not add global hooks in the widget unless architecture truly requires it,
- and keep keyboard behavior on the shared input contract when it belongs to runtime interaction policy.

### L. Add logging through existing CLI families

- Use the relevant existing family such as `--geo`, `--cache`, `--life`, `--set`, `--viz`, or `--perf`.
- Do not add noisy ad hoc always-on logging when an existing family fits.
- Any fallback must log loudly.
- For a heavy settings section, log lazy-build duration under the shared settings/performance family so dialog regressions are visible.
- If you notice churn risk while doing unrelated work, avoid it now but note it for future work.

### M. Add focused regression coverage

At minimum, cover the real contract changes:
- factory/descriptor/setup integration,
- settings load/save/defaults and no stale-cache behaviour,
- lazy settings routing: dialog opening does not build the new section; first visit builds it once; repeat visits reuse it,
- save safety: untouched/unbuilt settings survive opening and saving the dialog,
- absence of provider/auth/cache work while the section is unbuilt or merely hydrated,
- startup/fade/lifecycle behavior,
- service-backed caching/fallback/refresh behavior if relevant,
- custom-layout participation and inner-content response if relevant,
- input behavior if interactive,
- and anchor/position logic if dependent.

Prefer bars that fail the real user-visible bad behavior, not just helper math.

### N. Update docs in the same sweep

When a new widget lands or an old one is migrated:
- update `Spec.md` if a live architecture/behavior contract changed,
- update `Index.md` for module ownership/discovery,
- update `Docs/Defaults_Guide.md` if defaults/reset behaviour changed,
- update `Docs/TestSuite.md` if new regression files or harness expectations matter,
- update `Current_Plan.md` when it is active and affected,
- and update this guide only if the shared widget-creation pattern itself changed.

## 6. Service-Backed Widget Rules

For Gmail/Reddit/Weather-like widgets:
- reuse `widgets/service_widget_runtime.py` for shared lifecycle mechanics when the contract fits,
- keep provider semantics, cache authority, and widget rendering local,
- preserve visible valid content when empty/error fetches are non-authoritative,
- keep refresh/result apply transition-aware when the display is busy,
- use canonical storage paths for persistent cache/state,
- keep initial visible cache rendering separate from live provider refresh,
- and ensure the settings UI never turns section construction into a provider probe, credential test, cache migration, or refresh dispatch.

Do not widen shared service-backed helpers based only on “this widget does network too”.

## 7. Style And UX Rules

- Preserve the app’s custom visual language.
- Use `Docs/Custom_Style_Implementation.md` for style-specific guidance.
- Do not remove styling, fades, or shadows to hide behavior bugs.
- Startup, focus, reveal, and interaction problems should be fixed at root cause.

## 8. Common Failure Shapes To Avoid

- A second handwritten widget family list outside the descriptor registry.
- Widget-local persistence path that ignores `core/settings/storage_paths.py`.
- A widget that does work in `paintEvent` or blocks in UI-thread callbacks.
- A section registered as “lazy” but constructed from `WidgetsTab` startup, tab restoration, a sibling builder, or a broad `load_settings()` sweep.
- `bootstrap_in_lazy_mode` added for convenience rather than a documented necessity.
- A settings builder that instantiates the live runtime overlay or triggers a worker, provider probe, credential action, cache scan, or synchronous backend task.
- Hydration signals that write defaults, refresh the runtime, or erase persisted state while a section first builds.
- A save path that writes empty/default data for unbuilt sections and silently destroys existing settings.
- Service-backed behavior copied from Gmail/Reddit/Weather instead of shared where appropriate.
- Widget-local geometry fighting the shared authored or `Custom` seams.
- Treating correct outer geometry as proof that dynamic content fits inside a resized `Custom` card.
- Logging added without the relevant CLI family.
- Tests that prove a helper but not the real user-visible contract.

## 9. Fast New-Widget Checklist

- [ ] Widget runtime class added under `widgets/`
- [ ] Factory added/updated in `rendering/widget_factories.py`
- [ ] Descriptor metadata added/updated in `rendering/widget_descriptors.py`
- [ ] Setup/reuse/startup path wired through `rendering/widget_setup_all.py`
- [ ] Runtime lifecycle/positioning wired through `rendering/widget_manager.py` / `rendering/widget_positioner.py`
- [ ] Settings defaults and reset contract updated
- [ ] Typed model updated, or flat-dict exception documented
- [ ] `WidgetsTab` routing uses a lazy-built section by default
- [ ] No provider/runtime/cache/auth work occurs when the dialog opens or the section first hydrates
- [ ] Unbuilt-section save path preserves existing persisted values
- [ ] First visit builds once; repeat visits reuse; perf timing is checked when non-trivial
- [ ] Input routing integrated through shared handlers if interactive
- [ ] `Custom` behavior declared and isolated correctly if supported, including inner-content resize response
- [ ] Storage/cache paths use canonical app-data seams
- [ ] Logs use the relevant CLI family and fallbacks are loud
- [ ] Focused regression coverage added
- [ ] `Spec.md`, `Index.md`, `Docs/Defaults_Guide.md`, and `Docs/TestSuite.md` refreshed if needed

## 10. Recommendation

This file should remain the single canonical widget-creation guide.

Do not create a second “new widget checklist” unless it is truly domain-specific, like the visualizer and transition checklists. If this guide drifts, refresh it in place instead of spawning another overlapping doc.

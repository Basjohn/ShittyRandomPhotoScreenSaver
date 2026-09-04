# Visualizer Mode Modularization + Settings Tab — Decomposition

Date: 2026-09-02
Status: **V0-V4 COMPLETE (2026-09-03) — mode wiring centralized, per-mode enable state persisted (no settings lost) + routed + dormancy-proven; V5-V8 UI REHOST/FUTURE-MODE WORK STILL DEFERRED UNTIL HITCH OWNERS ARE STABLE**

V0-V4 landed as commits 54c87e0c (V1), dc8d6670 (V2), c5c0d69e (V3), fd3fbbe8 (V4)
on top of the reconciled green visualizer floor (V0). Descriptor is now the single
per-mode runtime/renderer wiring source; `enabled_modes` persists additively with a
full no-settings-lost audit; cycling/context-menu/initial-mode route through the
effective enabled set; dormancy is proven in a fresh interpreter. Behavior is
transparent today because every mode is enabled by default (no disable UI until V5-V8).

**PRE-V5 boundary:** `81019d5dd196cc5522ca9041d8773c8f2fa62df3` is the immediate
pre-V5 Settings-migration rollback/comparison boundary (pre-V5/V6 gate items 1-3
fixed; no Settings migration yet). Keep it distinct from later V5 work.

**V5 opening slice (2026-09-04):** the canonical lazy Settings-body ownership
contract is built and proven ahead of the pixel move — `VisualizerModeBodyHost`
(`core/settings/visualizer_mode_body_host.py`, Qt-free) owns per-mode body
lifecycle (construct-on-select, retire-on-disable preserving persisted state,
reconstruct-from-authority on reselect, single state authority, no
timers/pollers/workers); the descriptor gains lazy `settings_builder_module/
factory` wiring (`load_mode_settings_builder`) so no builder imports on registry
import. Tests: `tests/test_visualizer_settings_body_dormancy.py`. This proves the
ownership contract for pre-V5/V6 gate item 4 but does NOT rewire the live dialog —
`build_visualizers_ui` still builds all five bodies eagerly. The mechanical rehost
that adopts the host and retires the eager path is V6/V7 and closes gate item 4.

This document decomposes a future refactor that makes each Visualizer mode genuinely optional/dormant and then moves Visualizer Settings out of the overloaded Widgets tab into a dedicated top-level Visualizers tab.

The work is worthwhile because the existing architecture is already partly mode-modular, but it is **not yet safe** to treat individual modes like fully plugin-like components. The UI move must come **after** activation/dormancy is made real.

This plan is subordinate to:

- `Current_Plan.md`
- `Docs/Visualizer_Change_Checklist.md`
- `Docs/Visualizer_Reference.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md`

If a convenient registry/UI refactor conflicts with those visualizer contracts, the refactor loses.

Current sequencing authority (2026-09-03): after a short hitch-attribution baseline, V0-V4 may proceed because they establish the final enabled-mode owner graph and prove disabled modes dormant. Deep active-path performance optimization then targets only the surviving work. V5-V8 Settings-host extraction/rehosting/dependency/future-mode proof remain deferred until the main hitch owners are stable. See `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md`.

---

## 1. Product target

Desired Settings shape:

```text
Visualizers
    SETUP
        Enable Visualizers / dependency status
        [x] Spectrum
        [x] Oscilloscope
        [x] Sine Waves
        [x] Bubble
        [x] Spline Curve
        shared Visualizer controls / position where appropriate

    Spectrum        <- pill exists only while Spectrum is active
    Oscilloscope    <- pill exists only while Oscilloscope is active
    Sine Waves      <- pill exists only while Sine Waves is active
    Bubble          <- pill exists only while Bubble is active
    Spline Curve    <- pill exists only while Spline Curve is active
```

Each mode pill reuses its existing mode builder, preset slider and mode-level Custom/preset system. The purpose is **rehosting and modular admission**, not redesigning the visualizers.

If Media is disabled at the Widgets capability/setup level:

- the Visualizers top-level tab is disabled/greyed;
- hover tooltip is exactly **`Enable Media In Widgets`**;
- Visualizers does not silently enable Media;
- no Visualizer mode runtime/provider/presentation work is admitted through the disabled tab;
- re-enabling Media restores Visualizers tab eligibility using persisted Visualizer settings.

The Visualizer family still has one master activation state. If the family is active, **at least one mode must be active**, but any single mode may be the sole active mode.

---

## 2. Why this is feasible

Current source already has useful modular seams:

- `core/settings/visualizer_mode_registry.py` owns canonical mode descriptors and an active-descriptor iterator;
- the whole `visualizers` family is capability-gated and depends on Media;
- Settings mode binding, Context Menu/double-click mode cycling already consume active descriptors in several paths;
- Quick renderers are split by mode and are lazy-imported by the renderer registry;
- mode frame runtimes are separate modules;
- `VisualizerRuntimeController` retires/switches mode-owned logical state;
- Settings builders are already split into mode-specific modules;
- preset ownership is mode-addressable rather than one undifferentiated blob.

So this is **not** a rewrite of the Visualizer stack.

The remaining risk comes from duplicated hard-coded mode authorities and from the fact that "known mode" currently does not always mean "enabled mode".

---

## 3. Current coupling / seams that must be reconciled

### 3.1 Canonical registry is only partially an activation authority

`core/settings/visualizer_mode_registry.py` currently distinguishes `_ALL_DESCRIPTORS` from `_active_descriptors()`, but:

- `_GATED_MODES` is scaffolding rather than persisted product activation;
- `VISUALIZER_MODE_IDS` intentionally contains **all** canonical modes;
- `get_visualizer_mode_descriptor()` searches all modes;
- `coerce_visualizer_mode_id()` accepts any canonical mode even if it is currently gated/disabled.

This distinction is useful and should be kept, but an explicit **effective enabled-mode resolver** is missing.

### 3.2 Runtime factory is hard-coded separately

`widgets/spotify_visualizer/quick_display_visualizer_owner.py::_mode_runtime_factory()` is a five-way switch importing each mode frame runtime.

That preserves lazy imports, which is good, but duplicates mode wiring outside the descriptor authority.

### 3.3 Renderer implementation registry is another authority

`rendering/quick/visualizer/implementation_registry.py` has its own implementation table/validation against canonical IDs.

The registry must remain lazy and must not import heavy renderers for disabled modes.

### 3.4 Logical capture / mode-specific current behavior contains legitimate specialization

`widgets/spotify_visualizer/logical_frame_capture.py`, the render item and mode capabilities contain mode-specific branches.

Do **not** mechanically eliminate every `if mode == ...`. Some are real authored behavior, not activation metadata. This refactor centralizes **identity/admission/wiring**, not the physics/render semantics of every mode.

### 3.5 Settings currently builds Visualizers through Widgets-tab ownership

`ui/tabs/widgets_tab_media.py::build_visualizers_ui()` builds the current Visualizers group inside Widgets. The mode builders/preset widgets rely on `WidgetsTab` helpers/attributes/save machinery, and at least one preset helper walks upward looking for a `WidgetsTab`.

Therefore the safe move is not copy/paste into a new tab. Extract a narrow shared Visualizer Settings host/context first, then rehost the existing builders.

### 3.6 Static mode lists remain valid for schema/migration work

Several settings/preset/default modules iterate `VISUALIZER_MODE_IDS` to preserve all canonical mode fields.

That is **not automatically a bug**. Disabled modes must retain their settings/presets and remain recoverable. The refactor needs two explicit concepts:

```text
registered/canonical modes
    -> schema/default/migration/persistence authority

enabled/effective modes
    -> UI pills, mode selection/cycling, runtime construction, renderer/runtime import authority
```

Do not replace every `VISUALIZER_MODE_IDS` call site with active descriptors blindly.

---

## 4. Non-negotiable guardrails

### 4.1 No behavior tuning during modularization

This tranche is an **ownership/admission/Settings composition refactor**. It may not deliberately change:

- BeatEngine analysis;
- input gain / AGC / dynamic floor;
- mode presets or preset interpretation;
- mode authored logical cadence;
- source freshness/readiness semantics;
- renderer numerical transfer;
- Bubble physics/BTF;
- Spectrum smoothing/hysteresis;
- Oscilloscope/Sine/DevCurve temporal behavior;
- idle motion/reveal semantics;
- card size/aspect/viewport response;
- current fades;
- playback warm/cold behavior.

If a visible/reactivity difference appears, stop and classify it as a regression rather than "tuning it back" inside the refactor.

### 4.2 Scaling/reactivity contract is sacred

R-69 and the current viewport contract remain binding.

Never make mode modularity easier by:

- globally compressing Bubble head radius, motion, reaction amplitude or Ghost/history displacement;
- adding another `baseline/current`, `1/viewport`, or equivalent compensation to already-normalized state;
- reducing logical cadence or renderer demand;
- changing `uniform_visual_scale` semantics;
- changing `viewport_extent` semantics;
- reintroducing retired per-mode `*_growth` sizing authority;
- forcing CUSTOM visualizers back to the 1.5 baseline aspect;
- allowing anisotropic final-pixel stretch.

Required resize semantics remain:

```text
scroll wheel / corner handles -> uniform scale
left/right edges             -> viewport width only
top/bottom edges              -> viewport height only
```

All active current modes must preserve baseline + wide + tall behavior.

### 4.3 One clock / latest wins

No per-mode timer, QML timer, paint acknowledgement, FIFO or catch-up queue.

```text
one VisualizerLogicalRuntime
-> one active mode frame runtime
-> immutable latest publication
-> one retained Quick sync owner
```

Mode activation may swap the active mode runtime transactionally; it may not add a second authored cadence.

### 4.4 Disabled means dormant

A disabled mode must preserve its persisted configuration while contributing **no meaningful runtime work**:

- no mode renderer import/construction;
- no mode frame-runtime construction;
- no mode Settings body construction until/if enabled;
- no per-mode recurring timer/poller/thread/worker;
- no mode-specific GPU resources;
- no participation in mode cycling;
- no hidden provider/controller ownership.

Common lightweight registry metadata may remain imported.

### 4.5 Family activation and mode activation remain different

Visualizers family OFF means the family is not admitted.

Visualizers family ON means one or more modes are enabled. The UI must prevent the last enabled mode from being disabled unless the family itself is being turned OFF.

Do not use "zero enabled modes" as a second, ambiguous family-disable mechanism.

### 4.6 Media dependency remains one-way product admission

Visualizers depends on Media availability. The new tab may explain the dependency but must not own Media activation or provider/runtime state.

### 4.7 Preserve both meanings of Custom

There are two different concepts:

- **mode preset Custom** — the existing useful per-mode preset/custom authoring system;
- **global layout CUSTOM** — the display layout mode that disables authored stacking/Media↔Visualizer adjacency globally.

Do not merge their persistence, labels, lifecycle or enable-state logic.

### 4.8 Global layout CUSTOM remains untouched

The three global CUSTOM entry paths remain binding:

1. persisted/effective Custom layout exists;
2. live Edit Layout starts;
3. a number-key saved-layout load starts its fenced rebuild.

Mode activation changes must not re-enable ordinary stacking/adjacency under any of those paths.

---

## 5. Target descriptor / activation architecture

Do **not** build a giant generic Visualizer class. Keep mode implementations isolated.

The canonical descriptor should eventually be sufficient to route mode identity and lazy wiring without importing implementations eagerly. Suitable metadata may include:

```text
mode_id
stable display_name
setting prefixes
preset identity / slider identity
presentation policy
lazy frame-runtime factory/import identity
lazy Quick renderer factory/import identity
Settings builder identity
optional focused capability metadata
```

Implementation references should remain lazy (for example import-path/factory indirection) so importing the registry does not import every renderer/runtime/UI module.

The descriptor must **not** absorb mode physics, renderer shader contents, giant settings schemas or arbitrary technical-state mirrors.

---

## 6. Effective mode resolver

Introduce one product-level resolver for a requested canonical mode under the current enabled set.

Required behavior:

```text
requested is enabled
    -> requested

requested is canonical but disabled
    -> deterministic enabled substitute + explicit log

requested is unknown/retired
    -> deterministic enabled default + explicit existing migration/fallback policy
```

Preferred deterministic substitute when the user disables the currently active mode:

1. switch transactionally to the next enabled descriptor in canonical order, wrapping once;
2. persist the new selected mode and enabled set coherently;
3. retire the old mode-owned state after the new selection is admitted through the existing activation transaction.

For startup/stale persisted state, use the configured default when enabled, otherwise first enabled canonical descriptor. Never silently re-enable a user-disabled mode to satisfy a stale selected ID.

The last-enabled-mode UI toggle is rejected/disabled while the Visualizer family remains ON.

---

## 7. Phase decomposition

### V0 — pin the behavior floor before structural edits

Add/identify focused regression bars for:

- all five current modes activating through the current runtime;
- current double-click/context-menu cycling order;
- middle-click/preset slider + Custom round-trip;
- live source readiness/freshness;
- canonical/wide/tall scale/extent contract;
- Bubble/BTF deterministic behavior;
- one authored logical cadence / one engine lane;
- lazy Quick renderer import/construction;
- global layout CUSTOM entry including number-key layout load.

Do not proceed from V0 with unexplained red.

### V1 — centralize wiring, no user-visible activation yet

- extend the neutral descriptor only as much as required to replace duplicated **identity/wiring** tables;
- keep imports lazy;
- make Quick renderer lookup consume descriptor wiring;
- make mode frame-runtime lookup consume descriptor wiring;
- preserve mode-specific behavior branches where they express real semantics;
- source-audit duplicated five-mode tables and classify each as canonical-schema vs enabled-runtime vs legitimate mode behavior.

Acceptance: all existing modes behave identically and all current tests remain green.

### V2 — persisted mode enable set

Persist an explicit enabled-mode set/list beneath Visualizer settings without deleting any disabled mode's configuration.

Rules:

- family ON -> at least one enabled mode;
- family OFF -> mode enable selections remain persisted for later restoration;
- toggling one mode does not destroy presets/settings;
- disabling current mode performs one transactional switch to another enabled mode;
- enabling a mode does not automatically select it unless product UX explicitly asks for that later.

Default migration for existing users: **all current canonical modes enabled**, preserving today's product behavior.

### V3 — make every caller obey effective enabled modes

Audit and route at least:

- Settings mode selector/binding;
- runtime initial mode;
- Context Menu cycling;
- double-click cycling;
- preset/middle-click mode interactions;
- renderer implementation resolution;
- frame-runtime construction;
- any logical frame capture entry that can instantiate mode-owned state;
- diagnostic/harness mode enumerations where product activation matters.

Schema/default serialization continues to know all registered modes.

Acceptance: a disabled mode cannot be reached through stale setting, cycling, preset action or direct normal UI path.

### V4 — prove dormancy

For each mode, disable it in isolation and prove in a fresh process/generation that its heavy modules are not imported/constructed.

Useful source/runtime assertions:

- no renderer module in `sys.modules` merely because common Visualizer code imported;
- no frame runtime object for disabled modes;
- no mode Settings body built until enabled/tab selected;
- no new timer/thread/worker count;
- no mode GPU resource creation;
- no mode in cycling list.

Also prove one-mode-only operation with each of the five modes as the sole enabled mode.

### V5 — extract Visualizers Settings host/context

Before moving presentation, create a narrow host/context exposing only what the existing mode builders need:

- Settings save/read helpers;
- common Visualizer shared controls;
- preset slider registration;
- mode selection publication;
- shared style/bucket helpers;
- navigation refresh hooks.

Remove assumptions that a mode builder must have a `WidgetsTab` ancestor. Do not duplicate WidgetsTab wholesale into a VisualizersTab.

Acceptance: current Widgets-hosted UI can run through the extracted host first. This proves the extraction before moving pixels.

### V6 — create top-level Visualizers tab

Move/rehost:

- shared SETUP controls into `SETUP` pill;
- one active-mode pill per enabled mode;
- the existing mode builder/preset slider/Custom UI into its corresponding pill.

Inactive mode pills are not merely hidden prebuilt bodies; preferably do not build them until mode activation requires them.

Keep existing persistence keys unless a schema change is truly required. A Settings-navigation refactor alone does not justify migrating all Visualizer configuration data.

### V7 — Media dependency UX

At Settings navigation authority:

```text
Media capability/setup disabled
    -> Visualizers tab disabled/greyed
    -> tooltip: "Enable Media In Widgets"

Media enabled
    -> Visualizers tab eligibility restored
```

No click-through "helpful" auto-enabling. No extra Media runtime owner. Dependency should be obvious and inert.

### V8 — future-mode authoring proof

Only call the modularization successful when a hypothetical new mode has a bounded addition path:

1. define one descriptor;
2. add isolated logical/frame runtime module(s);
3. add isolated renderer module;
4. add mode Settings builder/preset definition;
5. add focused tests/fixtures;
6. no edits to five unrelated mode-switch tables.

A new mode may still require deliberate mode-specific physics/render code. "Plugin-like" means bounded admission/ownership, not zero specialization.

---

## 8. Settings UX details

### SETUP pill

Owns only shared family/mode-admission concerns and truly common Visualizer controls.

Suggested content:

- master Visualizers enabled state;
- enabled-mode toggles;
- shared position/common presentation controls that are genuinely mode-neutral;
- dependency explanation when Media is unavailable.

Do not move mode-specific technical controls into SETUP for symmetry.

### Mode pills

Each active mode gets one pill with its current builder/custom/preset experience.

Mode pill order follows canonical descriptor order, not activation time.

Enabling/disabling a mode should update pills through a Settings event/navigation boundary, not polling.

### Preset sliders / Custom

Preserve the existing slider and Custom system because it is productive authored behavior.

A disabled mode's preset state remains persisted. When re-enabled, its previous selected preset/Custom state returns unchanged unless current migration/default policy says otherwise.

---

## 9. Performance expectations

This refactor should be **performance-neutral or slightly cheaper**:

- no runtime polling for enabled modes;
- mode enable set resolved at Settings/configuration/activation boundaries;
- disabled renderers/frame runtimes not imported or constructed;
- inactive Settings mode pages lazy rather than all five built eagerly;
- no extra per-frame mode abstraction layer that allocates/copies dynamic state;
- no additional lock/queue/thread.

Do not trade runtime freshness for cleaner plugin boundaries.

---

## 10. Test plan

### Pure/source contracts

- descriptor IDs unique/stable;
- all registered vs enabled sets are distinct and correctly used;
- cannot disable final active mode while family ON;
- stale disabled selected mode resolves deterministically without re-enabling it;
- mode cycling contains enabled modes only;
- disabled mode settings/presets remain serialized;
- Settings pill list equals enabled descriptors;
- Media dependency disables tab with exact tooltip;
- no new timer/poller/thread ownership in activation code;
- no eager renderer/frame-runtime imports from common registry.

### Qt/runtime

- each mode works as sole enabled mode;
- enable/disable active mode transitions once and cleanly;
- no duplicate controllers/engines/Quick items;
- inactive mode Settings bodies are not created;
- Media disable/enable greys/restores tab without corrupting Visualizer settings;
- link to existing Context Menu/double-click/middle-click behavior remains correct.

### Golden Visualizer regression suite

Re-run the existing reactivity/freshness/geometry suite unchanged. Especially:

- Bubble BTF + R-69;
- Spectrum canonical/wide/tall temporal behavior;
- Sine/Oscilloscope/DevCurve canonical/wide/tall geometry;
- scale/extent persistence + CUSTOM Save/Cancel;
- layout-slot/number-key global CUSTOM behavior;
- pause/play source freshness;
- retained snapshot delivery;
- heavy-load cadence/latency envelope where appropriate.

### Eyes-on

For every current mode:

- canonical viewport;
- extreme wide;
- extreme tall;
- idle/paused/live playback;
- preset switch and Custom preset;
- mode enable/disable/re-enable preserving authored settings;
- one-mode-only configuration;
- multi-display placement/admission.

Any reactivity/scaling discrepancy blocks closure even if the new Settings UI looks correct.

---

## 11. Explicit non-goals

This tranche does **not**:

- redesign mode visuals;
- retune reactivity;
- add/remove current modes;
- implement future 3D modes;
- change the shared BeatEngine architecture;
- change visualizer card surface/theme ownership;
- change global smart stacking/CUSTOM rules;
- change Media event ownership;
- migrate every Visualizer settings key merely for prettier storage;
- generify all mode-specific renderer/runtime code into one monolith.

---

## 12. Stop conditions

Stop the refactor and classify before continuing if any of these occur:

- Bubble canonical/wide/tall response changes;
- source/snapshot age rises materially;
- logical cadence changes;
- a disabled mode still gets constructed/imported through a normal product path;
- a new timer/poller/thread is proposed for activation state;
- preset/Custom round-trip changes;
- global layout CUSTOM accidentally enables authored adjacency/stacking;
- Media dependency starts owning/auto-enabling Media;
- moving Settings requires duplicating `WidgetsTab` rather than extracting a narrow host;
- registry centralization starts absorbing mode physics/renderer implementation.

The correct response is to repair the ownership seam or shrink the slice, not to weaken the Visualizer contract.

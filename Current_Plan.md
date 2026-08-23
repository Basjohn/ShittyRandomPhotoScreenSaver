# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-24

## Current reviewed checkpoint

Independent review basis:

```text
8fcbc57a41c0b402fd4253d9668a0c6548b3100f
Phase E1 slice 1 — WidgetRuntimeManager establishment by extraction — independently audited GREEN
```

E1 remains active. E2/E2.7 remain implementation-closed; physical R-26 dual-display acceptance remains
deferred hardware evidence.

The subsequent documentation-only checkpoint `9adb74916010304f622a843e1b6d48e054792e6d` temporarily
over-scoped the next E1 slice as a generic live family-retirement/recreation mechanism. Source review
showed that current production family activation is applied through Settings-owned full runtime
teardown/recreation, so that prescription is superseded by the corrected E1 sequencing below.

Always inspect exact current `main` before acting. Repository state outranks this file if a later
checkpoint has landed.

## What this file is for

`Current_Plan.md` is the **active execution authority**, not a migration diary.

Earlier completed migration chronology is archived at:

```text
Docs/Historical_Plans/QtQuick_Migration_Completed_Through_2026-08-23.md
```

That archive is a **historical snapshot**, not a continuously rewritten completion mirror. It was
captured before the final E2/E2.7 closure checkpoints, so any wording inside it that calls E2/E2.7
active, queued, awaiting audit, or next work is **OBSOLETE AS CURRENT STATUS**. The current plan,
focused current docs and exact source own the later closure state.

Do not read historical planning by default. Consult it only when a demonstrated regression reopens a
closed phase or historical rationale is specifically needed.

For active work use:

```text
exact current source / pushed diff
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Compositor_Architecture.md + Docs/Contracts.md
        ↓
Docs/Guardrails.md + relevant focused guardrail
        ↓
ONLY the active Docs/QtQuick_Migration decomposition
        ↓
focused tests / current evidence
```

`Index.md` remains the routing authority when unsure where a contract lives.

---

# Active execution window

| Phase | Current status | Implementation permission |
| --- | --- | --- |
| A — bootstrap/render-node proof | **CLOSED** | Do not reopen without contradictory evidence |
| B — runtime-host decomposition | **CLOSED** | Do not reopen without contradictory evidence |
| C — base image + transitions | **IMPLEMENTATION CLOSED** | Only explicit acceptance/test debt or a demonstrated regression may reopen it |
| D — visualizer | **IMPLEMENTATION CLOSED** | Do not reopen renderer/mode architecture without contradictory evidence |
| **E — widget presentation + capability setup foundation** | **IN PROGRESS** | **Normal implementation work belongs here now** |
| F — widget families | Waiting for E | Reference only |
| G — CUSTOM/input/auxiliary pixels | Waiting for F | Reference only |
| H — settings epoch + production cutover | Waiting for A–G implementation | Reference only |
| I — legacy presenter deletion | Waiting for H cutover | Reference only |
| J — tooling/final validation/docs closure | Waiting for migration implementation | Reference only |

Closed-phase physical/compiled/eyes-on acceptance debt remains operator-scheduled and does not require
agents to reread the completed implementation history unless that evidence is actively being gathered.

## Phase promotion rule

A phase may move forward when its implementation dependencies are structurally closed even if
hardware-dependent/eyes-on acceptance remains explicitly deferred. A later failure reopens the
smallest demonstrated owner/phase defect; it does not roll the entire migration backward.

---

# 0. Mission

Perform one production presentation migration:

```text
current QWidget / QRhiWidget runtime presentation
                    ↓
one standalone threaded QQuickWindow per physical display
                    ↓
Qt Quick retained scene + inline custom GL render nodes
```

Do not plan a second presenter migration afterward.

Keep unaffected product systems unless a later phase explicitly replaces a presentation-coupled part:

- `ScreensaverEngine` orchestration except display-runtime calls that must change;
- image source/provider backends;
- SettingsManager and persistence infrastructure;
- source/account/credential ownership;
- QWidget Settings UI;
- RSS/folder/media/GSMTC/provider logic;
- ProcessSupervisor / ThreadManager where still appropriate;
- `VisualizerLogicalRuntime`;
- authored visualizer algorithms/mode personality;
- useful CUSTOM layout math/behavior;
- transition registry/settings identity;
- product features/customization, **except presentation controls explicitly retired by this plan** (notably the pre-Quick per-mode visualizer card-height/growth controls).

Backward compatibility with pre-Quick **presentation state** is deliberately not a migration goal;
Phase H0 creates a new settings epoch.

---

# 1. Hard architecture rules

## 1.1 One production presenter

Do not add or preserve as final architecture:

- a QRhiWidget-vs-Quick runtime setting/env switch;
- `QQuickWidget`;
- a permanent facade making QQuickWindow pretend to be DisplayWidget;
- QWidget presentation embedded above/below the Quick runtime;
- a second accelerated visualizer/transition window;
- QRhiWidget fallback when Quick rendering fails;
- transition-by-transition fallback to the old compositor;
- a supported software-only/CPU presentation mode or GL capability-demotion ladder used as runtime
  compatibility fallback;
- screenshot-to-texture QWidget wrappers as final widgets;
- duplicated legacy and Quick widget presentation pipelines after cutover.

During migration, old production code may coexist as reference/current production until Phase H.
Once production cuts over, Phase I deletion begins immediately.

The selected custom-GL seam is:

```text
QQuickItem(ItemHasContents)
-> updatePaintNode()
-> QSGRenderNode
-> direct OpenGL inside the owning Quick scene
```

`QQuickRhiItem` is not the normal SRPSS custom-render path. If the selected `QSGRenderNode` seam is
proven fundamentally unusable in pinned PySide/compiled product, stop and revise the **single**
primitive deliberately; do not keep competing product primitives.

## 1.2 Refactor only presentation overload that migration exposes

Expected decomposition:

```text
DisplayWidget
    -> QuickDisplayRuntime/window owner
    -> RuntimeInputController
    -> QuickSceneController
    -> WidgetRuntimeManager
    -> CustomLayoutSession

GLCompositorWidget
    -> transition renderer/resource implementations
    -> visualizer renderer/resources
    -> presentation pacer ownership
```

Do not use the migration to rewrite unrelated provider/backend systems.

## 1.3 Preserve visual capability

Migration parity includes current supported presentation capabilities such as opacity,
backgrounds/cards, borders/radius, fonts/colors, shadows, artwork, separators/icons, progress
controls, stacking, monitor routing, pixel shift, dimming, CUSTOM geometry/edit, context interaction,
visualizer all five modes, transitions, and Media Center interaction.

Do not solve migration defects by flattening/removing authored effects. Explicitly retired legacy presentation controls are not parity requirements; the pre-Quick per-mode visualizer card-height/growth sliders are deliberately retired in Phase D rather than copied into Quick.

## 1.4 No premature full/compiled builds

During Phases C–G, normal gates are focused Python/static/runtime harnesses.

Do not run Nuitka/full installed builds merely as routine migration validation. Keep packaging inputs
current. Compiled/installed validation remains operator-scheduled unless explicitly requested earlier.

---

# 2. Git / agent / review workflow

## 2.1 The local worktree is the mutation authority

Normal SRPSS file mutation happens in the operator's real local Git worktree, either by the operator or
a coding agent working in that checkout.

For this project, repository connectors/APIs are **read/audit tools**, not the normal write path.

Do not use a GitHub/repository connector to create/update/delete SRPSS source or documentation files.
Do not invent API blob/tree/branch-ref workflows as a substitute for normal Git editing.

When a reviewer/ChatGPT session materially changes durable guidance but cannot safely edit the real
worktree, return complete replacement files in a handoff pack. The operator/local coding agent applies
them, reviews the local diff, commits, and pushes normally.

## 2.2 Checkpoints are mandatory

Normal low-risk local-agent slice:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> continue
```

Do not stop after every successful low-risk checkpoint merely to ask permission.

Audit-required slice:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> STOP
-> independent audit of actual pushed source/diff
-> correction if required
-> continue
```

Use an audit-required stop for:

- high-risk visual preservation such as BlockSpin, Burn, Particle, or Bubble;
- lifecycle/topology ownership;
- settings epoch;
- production cutover;
- large deletion batches;
- architecture-boundary changes;
- work performed by an agent the operator has explicitly asked to audit checkpoint-by-checkpoint.

The audit reads the pushed commit/source. Agent prose is not the evidence.

## 2.3 Trust evidence, not agent prose

An agent saying tests passed or code was implemented is not evidence. Inspect current repository
state, pushed commit, diff, relevant source, and independent test/harness evidence from the
environment appropriate to the claim.

Repository state outranks stale orientation prose.

## 2.4 Documentation handoff / replacement-file rule

When durable migration guidance is materially changed outside the real local worktree, return complete
replacement copies of every affected repository document. Include a refreshed stand-alone
reorientation/handoff only when it is needed to preserve migration continuity.

When several replacement files are easier to hand over as one archive, a ZIP may preserve their
repository-relative paths. Do **not** generate a manifest, checksum, inventory, index/helper file, or
other packaging debris unless the operator explicitly asks for it. The replacement filenames and
repository-relative paths should make placement self-evident.

A chat explanation, partial snippet, or claim that a remote document was updated is not a substitute
for the required complete replacement file(s).

---

# 3. Test execution and evidence rules

SRPSS does **not** use repository-hosted CI as the normal migration test workflow. Do not add GitHub
Actions or another hosted test workflow unless the operator explicitly asks for it.

Use the environment appropriate to the claim:

- deterministic Python/source/settings/registry tests: the current capable Windows worktree;
- a clean checkout only when isolation/reproduction specifically benefits from one;
- Quick/OpenGL/runtime-shaped tests: proper Windows/Qt/OpenGL environment;
- multi-display, mixed-refresh, DPR, GPU/resource, physical cadence, and eyes-on claims: the
  corresponding real hardware/display environment.

The broad chunk wrapper remains a deliberate local diagnostic tool only:

```text
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

A broad-suite failure must be isolated before attributing it to the active migration slice. A completed
pytest summary followed by a process that never exits is a shutdown/lifecycle ownership defect to
isolate, not a reason to increase the timeout. A chunk that stalls during execution likewise requires
smaller/verbose local isolation.

No unexecuted test or gate is assumed green. Acceptance records must name the exact command, tested
commit, environment, and result.

Do not weaken Windows/Qt/OpenGL/physical-display tests merely because another environment cannot run
them.

---

# 4. Destination runtime architecture

```text
ScreensaverEngine
    |
    +-- providers / image queue / settings / persistence / media
    |
    +-- DisplayManager
            |
            +-- QuickDisplayRuntime (one per selected physical display)
                    |
                    +-- QuickDisplayWindow : QQuickWindow
                    |
                    +-- QuickSceneController
                    |       |
                    |       +-- background/transition QSGRenderNode item
                    |       +-- visualizer QSGRenderNode item
                    |       +-- retained Quick widget items
                    |       +-- dimming / halo / edit overlays
                    |
                    +-- RuntimeInputController
                    +-- WidgetRuntimeManager
                    +-- CustomLayoutSession
```

Feature activation target:

```text
cheap descriptor/catalog metadata
        ↓
application-level capability activated?
  yes                               no
   ↓                                 ↓
resolve implementation/model         implementation/provider/resources stay dormant
        ↓
per-instance/per-feature enabled?
  yes          no
   ↓            ↓
present/run     loaded capability remains available but inactive
```

Application-level **activation/loading** and ordinary runtime **enabled/disabled** state are separate
authorities. Phase E2 makes this distinction explicit in Settings for transitions and widget families.

---

---

# 5–8. Closed implementation phases — routing only

Phases A–D are closed for normal implementation work. Their detailed implementation chronology,
checkpoint evidence, renderer inventories, test-hardening rationale and completed acceptance records
live in the historical plan archive named at the top of this file.

Current durable authorities remain:

- Phase A/B host/lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` plus current contracts;
- Phase C transitions: `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`,
  `Docs/Transition_Change_Checklist.md`, `Docs/TestSuite.md`, `Docs/Harness_Index.md`;
- Phase D visualizer: `Docs/QtQuick_Migration/03_Visualizer.md`,
  `Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`,
  `Docs/Visualizer_Reference.md`.

Do not use the historical plan archive as current implementation authority.

---

# 9. Phase E — widget presentation + capability setup foundation

Read for active Phase E work:

- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- current source and tests at exact `main`

## E2 — application-level capability/Settings slice — IMPLEMENTATION CLOSED

Independent audit of exact current source at `b787c57a` is **GREEN**. E2 implementation is closed.

Verified final invariants include:

- final Random admission revalidates activation, hardware and current saved-pool membership;
- delayed/final remote CUSTOM Visualizer creation re-reads current Media + Visualizers capability state;
- invalid persisted Media→Visualizers state is durably repaired at SettingsManager load;
- context-menu Visualizer availability and mode switching fail closed when current capability state is
  unresolvable, while a valid mapping with absent activation keys retains the canonical compatibility
  semantics;
- the two real context-menu boundaries are regression-covered, including missing manager, failed read,
  malformed root and valid-empty-map controls.

Detailed E2 correction chronology belongs in the historical plan archive, not here.

Remaining operator eyes-on confirmation of responsive Settings layout / Visualizers dependency UX is
deferred acceptance and does **not** block the next Phase-E implementation slice under the phase
promotion rule.

### E2.7 Visualizer CUSTOM display failover/reclaim lifecycle — IMPLEMENTATION CLOSED

Independent audit of exact pushed checkpoint
`5b3cbaef4d443c79941e5ac780252f82a4e77bc4` is **GREEN**. E2.7 implementation is closed and E1 is
the active next Phase-E slice.

Verified final invariants include:

- the persisted CUSTOM monitor remains canonical; temporary fallback ownership is runtime-only and does
  not persist fallback monitor/position/size/viewport geometry;
- an unavailable configured target, whether runtime-known/non-participating or absent, receives the same
  **30-second one-shot grace** before any temporary fallback is created;
- grace authority is global for the single Visualizer: one outage owns one coordinator generation,
  repeated reconcile from another display cannot restart/extend it, and every delayed callback validates
  that global generation before acting;
- a configured target returning during grace is handled by event/topology reconciliation immediately;
  reclaim/return invalidates the old generation so stale callbacks are no-ops;
- if the target remains unavailable at the deadline, at most one temporary fallback may be created on a
  participating display; no participating fallback fails closed;
- reclaim re-reads current Settings, follows a changed current CUSTOM target, and retires the temporary
  owner before creating/reusing the configured owner; unconfirmed retirement fails closed and retains
  recoverable failover state;
- a successful reclaim followed by a later target loss is a genuinely new outage with a fresh generation
  and a fresh full 30-second grace;
- Media/Visualizers capability admission is re-read at delayed, reclaim, final-create and live capability
  change boundaries; effective capability deactivation retires pending global grace state and invalidates
  its generation, while a live temporary owner is only forgotten after confirmed retirement;
- later explicit reactivation with the configured target still unavailable can therefore arm a genuinely
  fresh 30-second grace rather than inheriting stale failover state;
- stale Media/runtime objects and copied settings maps do not grant permission to create/reclaim a
  Visualizer; and
- the pushed regression coverage exercises absent-target grace, event-before-deadline return, stale
  generation fencing across multiple display origins, current-target changes, deadline fallback,
  retire-before-create failure paths, capability-off retirement/reactivation and no-persistence behavior.

The independent audit inspected the pushed source and regression intent. The coding agent reported its
local focused E2/E2.7 sweep green; that Windows test execution was not independently rerun by the reviewer.

Physical dual-display sleep/wake/late-return behavior remains **deferred hardware acceptance**. That does
not block Phase-E promotion under the phase-promotion rule.
`Docs/Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md` therefore remains
**PARTIAL / AWAITING VALIDATION** until the corresponding physical evidence is gathered; do not mark it
SOLVED from deterministic tests alone.

Detailed E2.7 implementation/correction chronology is historical evidence, not active execution guidance.
Do not reopen E2.7 without contradictory runtime/source evidence.

## E1 — presentation-neutral runtime/model/provider ownership — ACTIVE

E2 and E2.7 are implementation-closed. Complete the broader `WidgetRuntimeManager` ownership split
across bounded, individually-audited slices (do not batch every provider into one commit).

Required destination:

- canonical widget identity/settings metadata independent of QWidget factories;
- presentation-neutral provider/model lifecycle ownership;
- activated/enabled/visible state and monitor participation without QWidget presentation authority;
- when a capability is deactivated, its exclusive provider/model/process/poll/timer/resource ownership
  must not survive the legal runtime lifecycle that applies that configuration;
- shared infrastructure survives while another real consumer still needs it;
- deactivated capability before first use does not unnecessarily import/resolve heavy implementation;
- ordinary instance-disabled state remains distinct from family deactivation;
- no giant Python `QuickBaseOverlayWidget` replacement god object.

### Current capability-lifetime fact

Current production family activation is not an in-place runtime hot-toggle architecture.

The normal user flow is:

```text
running screensaver
-> Settings request
-> engine.stop(exit_app=False, reason="settings")
-> complete display/runtime teardown
-> destruction barrier
-> Settings dialog opens
-> family activation is changed/saved
-> new runtime generation is created
-> creation admission applies the new capability state
```

Therefore the durable requirement “deactivated capability owns no exclusive runtime resources” does
**not** imply that E1 must invent a second generic live family-retirement/recreation system.

If future/current source gains a real family-activation writer while the screensaver runtime remains
alive, that path must satisfy the same ownership contract. Do not build such a path speculatively.

The existing E2.7 live Visualizer capability/failover reaction is a special closed lifecycle seam and is
not precedent for making every widget family hot-retire in place.

### E1 slice 1 — establish the owner by extraction — AUDITED GREEN

Pushed/audited implementation checkpoint:

```text
8fcbc57a41c0b402fd4253d9668a0c6548b3100f
```

Independent source audit confirmed:

- `rendering/widget_runtime_manager.py` establishes the presentation-neutral owner shell without
  creating/owning QWidget or Quick instances;
- `widget_manager.py` shrank by 110 lines rather than absorbing another subsystem;
- the old initialize/activate/deactivate/cleanup lifecycle routing was relocated without material
  behavior change and `cleanup_widget()` still returns an explicit bool required by E2.7;
- factory-backed creation now delegates family activation admission through `WidgetRuntimeManager`;
- capability-change dispatch still reaches the landed E2.7 Visualizer failover retirement;
- no provider/model lifetime was migrated in this slice;
- no E3/E4/F work entered the checkpoint.

The coding agent reported its local focused/broader Windows gate as `325 passed, 4 skipped`; the
independent reviewer audited pushed source/diff/regression intent but did not independently rerun that
Windows execution.

#### Slice-1 YELLOWs / remaining guardrails

1. `is_family_effective()` is the canonical **activation + dependency-satisfaction** query. It is not a
   generic shared-provider last-consumer counter. Correct the slice-1 source/doc wording when that file
   is next touched; do not invent a refcount merely to replace the wording.
2. `handle_capability_change()` still lazily calls the legacy
   `rendering.widget_setup_all.retire_visualizer_failover_on_capability_change` seam. Treat that as the
   transitional E2.7 bridge it is; do not grow it into a family-specific presenter switchboard.
3. One `WidgetRuntimeManager` per display runtime is compatible with the destination decomposition.
   The later hoist moves ownership out of legacy `WidgetManager` into the display-runtime boundary; do
   not invent a process-global god manager merely to remove the temporary host edge.

### E1 slice 2 — first real provider/model ownership extraction — AUDIT-CORRECTED, RE-AUDIT REQUIRED

#### Audit correction (blocker: duplicate construction / fail-open to default provider)

Independent audit found that the real `RedditWidgetFactory` created `RedditWidget` with no provider, so
`RedditWidget.__init__` constructed the old default provider before the neutral owner injected — both
duplicating provider construction and making a neutral service build/inject failure **fail open** to the
QWidget-owned default. Corrected:

- `RedditWidget.__init__` gained `build_default_provider` (default `True`, preserving standalone use);
  the factory now passes `build_default_provider=False` so a runtime-managed widget builds **no** default
  provider (`_post_provider is None` until injection). `_fetch_feed` guards a `None` provider (never
  fetches on a default);
- `WidgetRuntimeManager.ensure_widget_service` now **fails closed** on build *or* injection failure
  (retires any partially-owned service, returns `None`); `_inject_reddit_service` raises if the widget
  cannot accept the provider; new `has_runtime_service(widget_id)` lets the creation path distinguish
  "no spec" from "required-service failure";
- `_create_factory_widgets` now, for a widget that requires a runtime service, retires the widget via
  `_fail_closed_runtime_service_widget` (unregister / unbind / drop expected-overlay / cleanup / delete)
  when the service is `None` — the widget is never registered/started on a default;
- removed the remaining stale "shared-consumer accounting" wording and the "generic future live
  family-retirement" framing in `widget_runtime_manager.py` / its tests (live in-place family retirement
  is not an E1 deliverable; the capability-change hook is the E2.7 transitional bridge only).

New production-seam regressions: `tests/test_reddit_widget.py` (factory-created widget builds no default
provider and defers ownership; standalone still builds its default; deferred widget fails closed on
fetch); `tests/test_widget_manager_refresh.py` (a failed provider build fails closed — no widget created,
none owned). Local sweep: `440 passed, 4 skipped`.

#### Landed this checkpoint

Chosen seam: the **Reddit post-provider** (`core.reddit_post_provider`). Rationale: it is the smallest
single-purpose provider still *constructed and owned by a runtime QWidget* (built in
`RedditWidget.__init__`/`RedditWidgetFactory` and held on `self._post_provider`), unlike the already-
neutral clock ticker singleton or the `GmailBackend.instance()` singleton; it is per-instance (not
shared → no artificial consumer machinery); and it has no live-rebuild coupling.

What moved:

- new `rendering/widget_runtime_services.py` — a neutral registry (`RuntimeServiceSpec` +
  `get_runtime_service_spec`) holding the family-specific build/inject/retire knowledge (reddit +
  reddit2, honoring reddit2 family provider inheritance). Heavy provider import is lazy;
- `WidgetRuntimeManager` gained generic `ensure_widget_service` / `get_widget_service` /
  `retire_widget_service` / `retire_all_services` (retired in `cleanup()`). It owns the provider
  lifetime keyed by widget id and stays generic (no `if family == …` switchboard — family knowledge
  lives in the registry);
- `_create_factory_widgets` builds/owns/injects the service through the owner at creation (synchronous,
  pre-start);
- `RedditWidgetFactory` no longer constructs/injects the provider (bare `RedditWidget` keeps its
  `__init__` default only for standalone use);
- corrected the slice-1 wording: `is_family_effective()` is documented as activation +
  dependency-satisfaction (not shared-consumer accounting), and the owner's "imports no renderer code"
  claim is narrowed to module-top only (transitional seams are lazily imported). Slice-1 YELLOW #1 is
  thereby addressed.

Regressions: `tests/test_widget_runtime_manager.py` (owner builds/owns/injects independent of QWidget;
idempotent re-own; retire/cleanup exactly once; build-failure fails closed), `tests/test_widget_manager_refresh.py`
(provider owned via real `setup_all_widgets`; deactivated family owns no provider; disabled instance ≠
family deactivation), `tests/test_reddit_provider_settings.py` (reddit2 inheritance / override / rss
default now asserted through the neutral registry). Local sweep: `419 passed, 4 skipped`.

Not done (deliberately, per this slice's bounds): no other family migrated; no shared-consumer
accounting added (reddit is per-instance); E2.7 hook untouched; owner not hoisted.

#### Original slice-2 contract (satisfied above)

Move one **actual** provider/model/service lifetime seam out of QWidget presentation ownership and into
presentation-neutral runtime ownership.

Before choosing the seam, inspect current source and select the smallest family/service where a real
provider/model/process/poll/timer lifetime is still materially owned by a runtime QWidget. Do not
manufacture work for a family whose relevant ownership is already neutral.

Required boundaries:

- one bounded family/service seam only; no all-family migration;
- provider/model/service lifetime becomes presentation-neutral and is not owned merely because a
  QWidget exists;
- current Settings-owned teardown/recreation remains the normal family-activation application path;
- deactivated-before-recreation must not recreate/resolve the migrated exclusive owner;
- reactivation through the next normal runtime generation may recreate it from preserved detailed
  settings;
- ordinary member `enabled=False` remains distinct from family deactivation;
- preserve existing legal ownership for genuinely shared services when it already gives correct
  lifetime; add explicit consumer accounting **only if the concrete migrated seam demonstrably needs
  it**;
- do not generalize the E2.7 Visualizer live hook into ordinary family lifecycle;
- `WidgetRuntimeManager` remains generic: no central `if family == ...` provider/presenter switchboard;
- correct the slice-1 `is_family_effective()` / “imports no renderer code” overstatements while touching
  the owner, without redesigning E2.7.

Regression bar for the chosen seam:

- provider/model owner exists independently of QWidget pixel ownership;
- family deactivated before runtime recreation -> migrated exclusive owner is not created/resolved;
- family reactivated -> one normal fresh-generation owner can be created with preserved detailed config;
- normal runtime teardown cleans the migrated owner exactly once;
- ordinary instance disabled is not treated as family deactivation;
- if the chosen service is truly shared, prove the actual surviving-consumer lifetime contract; if it is
  not shared, do not add artificial shared-consumer machinery;
- existing E2/E2.7 capability/failover regressions remain green where touched.

Push this bounded slice and stop for independent audit.

### E1 remaining after slice 2

- continue provider/model lifetime migration off member QWidgets, one bounded family/service seam at a
  time;
- fresh-process import dormancy: catalogued-but-deactivated capability resolves no unnecessary heavy
  family implementation before first use;
- hoist the per-display owner out of legacy `WidgetManager` into the final display-runtime boundary as
  that boundary lands.

A live in-place family retirement mechanism is **not** an E1 deliverable unless exact current source
introduces a real live activation writer or another demonstrated product flow requires it.

Each substantial ownership/lifecycle slice remains an audit checkpoint.


## E3 — shared retained Quick primitives

Build small reusable retained primitives for cards/backgrounds, border/radius, foreground opacity,
shadows, text/header shadow, image/artwork, separators, text, fades/visibility, click targets and
controls.

Do not create another monolithic presentation base class.

## E4 — eight-direction shadow authority

Add one global presentation-neutral direction setting:

```text
NW   N   NE
 W   ·    E
SW   S   SE
```

Eight outer directions; default `SE`; center is not a ninth mode.

Direction changes signs while preserving each family's authored magnitude/blur/spread/opacity/color.
Cover cards, text, headers, icons/artwork, controls, volume slider, visualizer, clocks, Weather, Media,
Reddit/Gmail, Steam families, multiple DPRs and CUSTOM geometry.

Do not reintroduce QWidget `QGraphicsDropShadowEffect`.

## Phase E execution order

Unless stronger current evidence forces a smaller corrective detour:

```text
E1 runtime/model/provider ownership  <- ACTIVE
-> independent audit
-> E3 retained primitives
-> E4 shadow authority
-> Phase-E closure review
-> Phase F
```

Do not start Phase F merely because E2 UI is visually usable; E1 ownership and E3/E4 foundation still
belong to Phase E.

### Known unrelated test watch items

These were reported as pre-existing on the `4ac884f8` baseline and are not evidence against the narrow
E2 correction unless current investigation proves otherwise:

- `test_visualizer_settings_plumbing.py::TestVisualizerModeBinding::test_load_visualizer_mode_selection_falls_back_when_saved_mode_is_unknown`;
- `test_sine_line4_builder_integration.py::test_actual_save_media_settings_includes_line4`;
- `test_visualizer_doc_references.py::test_contracts_route_visualizer_shell_clip_and_geometry_owners`
  (stale assertion around legitimate `QSGClipNode` historical/contract wording).

Do not silently ignore new failures; isolate before attributing them.

---

# 10. Phase F — widget families

Port runtime pixels, not Settings GUI/backends.

## F0 — remove deprecated Imgur instead of porting it

Remove its live gate/defaults/settings controls/descriptor/runtime/provider/CUSTOM/tests/package/
current-authority docs/Foundry metadata. Do not build compatibility around stale Imgur presentation
keys.

Recommended family order:

1. Clock / Clock2 / Clock3
2. Weather
3. Media core
4. media volume/mute/progress/control sub-elements
5. Reddit / Reddit2
6. Gmail
7. Steam Progress
8. Achievement Pulse
9. Abandonment Issues
10. Friend Pulse
11. other deliberately supported canonical families

Per family:

```text
identify provider/business logic
-> compact runtime model
-> retained Quick presentation
-> preserve customization
-> deterministic tests/gallery
-> CUSTOM expectations
-> commit/push
-> audit when risk warrants
```

The E2 application-level activation gate must already prevent deactivated families from resolving
during these ports.

Do not rewrite provider/network logic into QML or use QWidget screenshots as final presentation.

After F implementation exits, rewrite widget authoring guidance for the final
descriptor/model/family/Quick component contract.

---

# 11. Phase G — CUSTOM, input, interaction, auxiliary pixels

Read `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

## G1 — CUSTOM session + visualizer viewport-resize QoL

Refactor `CustomLayoutManager` into presentation-neutral session/state + Quick edit presentation.

Edit the real retained Quick item. Keep uncommitted session geometry separate from persisted settings.
Save commits; Cancel restores baseline. Grid/outline/handles are separate Quick edit items.

Cross-monitor transfer moves/recreates one presentation instance on the target scene; no simultaneous
duplicate live pixel owners.

Do not spend migration effort translating old QWidget geometry; H0 resets it.

### G1.1 — visualizer resize has two distinct operations

The Phase-D geometry contract separates **uniform whole-visualizer scale** from **viewport extent**.

Preferred edit semantics:

```text
scroll-wheel resize
    -> uniform whole-visualizer scale
    -> canonical baseline aspect preserved

corner-handle resize
    -> uniform whole-visualizer scale
    -> canonical baseline aspect preserved

left/right edge-handle resize
    -> viewport width only
    -> visual scale unchanged

top/bottom edge-handle resize
    -> viewport height only
    -> visual scale unchanged
```

This deliberately preserves the existing useful CUSTOM interaction: scroll/corner resize makes the
entire visualizer larger or smaller as one object. Edge-only dragging is the new operation that gives
a mode more or less playroom.

Viewport resizing is not post-render image stretching.

The renderer/logical mode consumes the new viewport dimensions so content adapts/reflows:

- Spectrum redistributes bars across available width and uses the new vertical extent;
- Bubble changes spatial bounds/aspect without turning circles into ellipses or scaling X/Y velocities
  differently;
- Oscilloscope/Sine/DevCurve adapt domain/layout while preserving authored stroke/visual scale;
- future frameless 3D modes use aspect-correct camera/projection.

When a card shell exists, its outer geometry follows the viewport extent plus canonical shell/border
insets. A frameless mode changes only its transparent assigned viewport.

`Reset Size` should restore both uniform scale and viewport extent to the canonical baseline geometry
unless a later deliberate UX adds separate reset affordances.

Persist scale and viewport extent as distinct new-schema values. Do not resurrect the old per-mode
`*_growth` controls as hidden aliases for either field.

### G1.2 — non-blocking migration rule

This QoL is preferred because Phase D is already paying the architectural cost to keep the geometry
seam clean.

It is **not a production-cutover blocker** if focused implementation evidence shows that one or more
current modes cannot support freeform viewport extents without substantial BTF/fidelity risk.

If that happens:

- keep the Phase-D scale/viewport separation;
- disable viewport-edge handles for the affected mode(s);
- preserve ordinary uniform scale resize;
- record the deferred mode-specific work explicitly;
- do not fake support by stretching the rendered visualizer texture.


## G2 — input/interaction

Refactor `InputHandler` away from DisplayWidget assumptions and route QQuickWindow events to existing
actions.

Preserve exit gestures, hotkeys/media keys, Ctrl interaction mode, layout slots under the new schema,
clicks, right-click context menu, Media Center behavior.

Transient QWidget control UI/settings dialog may remain if decoupled from DisplayWidget and not used
as accelerated presentation.

## G3 — auxiliary runtime pixels

Port cursor halo, dimming, pixel-shift scene transform, required error/fail-safe display, edit
grid/handles, and any remaining runtime overlay pixel owner.

---

# 12. Phase H — settings epoch + production cutover

No production-owner cutover until Quick implementation contains base images, all active transitions,
all five visualizer modes, runtime widget families, CUSTOM, input/context, dimming/pixel shift/halo,
multi-display/lifecycle, and packaging inputs ready for later compiled validation.

## H0 — one-time Qt Quick settings epoch

Do not accumulate a museum of per-feature pre-Quick presentation migrations.

### Preserve only an explicit durable whitelist

Intended durable categories:

- image/source configuration and configured locations/selections;
- credentials/tokens/secrets;
- account identities/slots/auth data;
- genuinely presentation-neutral provider/backend connection information;
- any other leaf only after inspection proves its meaning/schema survives unchanged.

Do not preserve an entire old subtree merely because it contains one durable leaf.

### Reset migration-sensitive presentation state to final Quick defaults

Reset, where present:

- transition selection/pools/durations/directions/parameters/easing debris;
- **transition capability activation and new random-mode/pool defaults to their final canonical
  Quick-era defaults**;
- widget enablement/presentation/style/position/dimensions;
- **widget-family capability activation to final canonical Quick-era defaults**;
- presentation monitor routing;
- CUSTOM geometry/restore payloads/layout slots;
- display geometry assumptions;
- old shadow/effect settings;
- visualizer presentation/geometry, including old per-mode `*_growth`/card-height controls and any Quick-era shell/clip/scale/viewport state where persisted;
- old user visualizer presentation presets unless deliberately retained under a new-schema decision;
- other QWidget/QRhi/compositor-era presentation state.

No heroic coordinate translation.

Built-in visualizer presets remain product baseline; users can edit/create/save new presets in the new
schema.

### Epoch operation

```text
pre-Quick settings detected
-> copy explicit durable whitelist
-> construct fresh final Quick defaults
-> restore whitelist
-> atomically persist new epoch/version through normal durability boundary
-> future current-epoch starts do nothing
```

Prove reset exactly once, durable source/auth data survives, presentation state resets, malformed old
presentation state cannot leak through, second startup does not reset again, and persistence reaches
normal durability boundary.

Checkpoint/push H0 before H1.

## H1 — production-owner switch

Make one explicit switch:

```text
DisplayManager
    from DisplayWidget
    to QuickDisplayRuntime
```

Change callers to the real new API. No DisplayWidget compatibility facade and no production flag back
to QRhiWidget.

Run focused/chunked gates as meaningful. Do not initiate installed/full build unless operator
scheduled.

Checkpoint/push cutover immediately when accepted.

---

# 13. Phase I — immediate legacy removal

Use `Future_Cleanup.md` as deletion ledger.

After cutover, remove in small proven batches:

- QRhiWidget physical presenter;
- `GLCompositorWidget` scheduling/presentation ownership;
- old GL RHI surface helpers without callers;
- compositor visualizer layer;
- old GUI `present_tick` paths;
- old QWidget runtime widget presentation classes after settings/test consumers move;
- old QWidget CUSTOM edit shell/grid presentation;
- dead transition controller classes whose only purpose was old compositor presentation;
- obsolete effect/cache-busting presentation code;
- legacy presenter/factory consumers;
- one-off pre-Quick presentation migration helpers obsolete after H0;
- obsolete transition dropdown/random-pool UI code replaced by E2;
- obsolete eager Widgets/Transitions settings-section creation paths replaced by E2;
- legacy visualizer per-mode card-height/growth settings/UI/bindings/helpers/tests once the old presenter no longer calls them (`spectrum_growth`, `osc_growth`, `sine_wave_growth`, `bubble_growth`, `devcurve_growth`, and compatibility height helpers);
- legacy GL capability-demotion / compositor-only / software-only rendering support and tests whose only
  purpose is preserving that fallback ladder, after caller proof. Software-only rendering is not a
  supported Quick-era product mode;
- migration-only scaffolding.

Do not delete presentation-neutral authored shaders/math merely because the old compositor also used
them; shared assets survive when Quick is their real consumer.

For every deletion batch:

```text
caller proof
-> focused tests
-> commit
-> push
-> audit when risk warrants
-> continue
```

Do not leave both presenter architectures "for safety."

---

# 14. Phase J — Defaults Foundry, final validation, documentation closure

Read `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`.

## J0 — retarget Defaults Foundry

Current tool:

```text
tools/default_settings_editor.py
```

It currently reads canonical `DEFAULT_SETTINGS` directly via AST/literal, recursively edits leaves,
writes Normal base + MC differential, and regenerates snapshot/SST artifacts.

After H0/H1/I establish final schema:

- keep direct literal-reading if `core/settings/default_settings.py` remains canonical;
- otherwise retarget explicitly;
- remove deleted metadata such as Imgur;
- add finite-value metadata for new canonical settings such as shadow direction;
- remove legacy visualizer per-mode card-height/growth leaves from canonical defaults/preset authoring/Foundry metadata; visualizer presets must not change viewport shape through those retired keys;
- expose/validate final transition capability-activation, random-mode/pool and widget-family
  activation defaults without importing heavy implementation modules;
- remove retired compatibility-preservation behavior;
- align import/filter rules with H0 durable-data policy;
- regenerate default snapshots and Normal/MC SSTs;
- update parity tests and `Docs/Defaults_Guide.md`;
- keep the standalone Foundry QWidget UI unless a separate tooling decision changes it.

## J1 — operator-scheduled final validation

When explicitly scheduled, validate:

- script RUN;
- normal compiled `.scr`;
- diagnostic build;
- Media Center build where relevant;
- Settings open/recreate;
- Widgets/Transitions SETUP activation persistence and dormancy;
- CUSTOM Save/Cancel;
- all five visualizer modes;
- all transitions;
- all widgets;
- mixed 60 Hz/high-refresh;
- monitor off/wake/topology recreation;
- clean shutdown;
- resource baseline;
- PresentMon cadence where useful;
- external heavy-load resilience;
- long soak.

Do not rerun obsolete manual worker-heavy baselines merely out of habit.

Beyond-parity closure should show no QWidget effect-cache shadow architecture, no per-widget accelerated
surfaces, retained Quick widgets not rebuilding stable content every physical frame, clean
render-thread ownership, true deactivated-capability dormancy, and decomposition of overloaded old
presentation modules.

## J2 — documentation closure

Update current-authority docs to landed class/file names; make Quick transition/widget/visualizer
authoring guides sole current implementation authority; update Defaults guide; remove current
instructions that teach dead QWidget/QRhi/compositor owners.

Preserve historical bug/evidence documents as history rather than rewriting them as current
architecture.

---

# 15. Current next work

**E2 implementation is CLOSED by independent audit at `b787c57a`.**

**E2.7 implementation is CLOSED by independent audit at
`5b3cbaef4d443c79941e5ac780252f82a4e77bc4`.**

Physical dual-display sleep/wake/late-return acceptance for R-26 remains deferred hardware evidence;
it does not reopen E2.7 implementation or block the next Phase-E slice.

**E1 slice 1 is CLOSED / AUDITED GREEN at
`8fcbc57a41c0b402fd4253d9668a0c6548b3100f`.**

The `9adb7491...` documentation prescription for generic live family retirement is superseded. Current
production family activation is applied through Settings-owned full runtime teardown/recreation.

The active next checkpoint is:

```text
inspect current provider/model ownership
-> choose one smallest real QWidget-coupled provider/model/service seam
-> extract that lifetime into presentation-neutral ownership
-> preserve Settings teardown/recreation as capability application path
-> add shared-consumer machinery only if that concrete seam actually requires it
-> focused ownership/dormancy/lifecycle regressions
-> diff/status
-> commit + push
-> STOP for independent audit
```

Do not invent a generic live family OFF/ON lifecycle without a real current runtime writer.

After E1 completes across its bounded slices:

```text
E3 retained Quick primitives
-> E4 global eight-direction shadow authority
-> Phase-E closure review
-> Phase F
```

Do not send an implementation agent back into E2/E2.7 unless new source/runtime evidence demonstrates
a specific regression.

---

# 16. Cross-links

Technical decompositions:

- `Docs/QtQuick_Migration/README.md`
- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`
- `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`

Durable routing/guardrails:

- `Index.md`
- `Spec.md`
- `Docs/Contracts.md`
- `Docs/Compositor_Architecture.md`
- `Docs/Guardrails.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

Current transition/visualizer references:

- `Docs/Transition_Change_Checklist.md`
- `Docs/Harness_Index.md`
- `Docs/TestSuite.md`
- `Docs/Visualizer_Reference.md`

Defaults/tooling:

- `Docs/Defaults_Guide.md`
- `tools/default_settings_editor.py`
- `tools/regenerate_defaults_snapshot_artifacts.py`
- `tools/regenerate_sst_defaults.py`

Deletion/deferred scope:

- `Future_Cleanup.md`
- `Future_Work.md`

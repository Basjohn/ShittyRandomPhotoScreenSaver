# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-24

## Current checkpoint

Latest pushed/self-audited implementation basis:

```text
ad71421d395806e78898593c71a3bc25a53bcdf1
Phase E1 slice 9 — fresh-process/deactivated-family import dormancy — self-audited GREEN; reused-agent reviews GREEN
```

Independent review basis:

```text
c320887cc27e1b2bace10ba562a36e24ae9307ca
Phase E1 slice 2 — Reddit post-provider runtime ownership — independently audited GREEN after correction
```

E1 remains active. E2/E2.7 remain implementation-closed; physical R-26 dual-display acceptance remains
deferred hardware evidence.

The earlier `9adb74916010304f622a843e1b6d48e054792e6d` prescription for a generic live family
OFF/ON retirement mechanism remains superseded: current production family activation is applied through
Settings-owned full runtime teardown/recreation. E1 migrates real provider/model/runtime ownership; it
does not invent a second hot-reload lifecycle without a demonstrated live writer.

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
across bounded, individually-audited slices. Do not batch every family into one commit.

Required destination:

- canonical widget identity/settings metadata independent of QWidget factories;
- presentation-neutral provider/model/runtime-data lifecycle ownership;
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

### E1 slice 1 — establish `WidgetRuntimeManager` by extraction — AUDITED GREEN

Pushed/audited checkpoint:

```text
8fcbc57a41c0b402fd4253d9668a0c6548b3100f
```

Landed:

- presentation-neutral admission/lifecycle owner shell;
- capability admission routed through it;
- E2.7 capability-change bridge preserved;
- `WidgetManager` reduced by 110 lines rather than enlarged;
- no provider/model family migration yet.

Reported local gate: `325 passed, 4 skipped`. The independent reviewer audited pushed source/diff/test
intent but did not independently rerun that Windows execution.

### E1 slice 2 — Reddit post-provider ownership — AUDITED GREEN

Final audited implementation checkpoint:

```text
c320887cc27e1b2bace10ba562a36e24ae9307ca
```

The original slice landed at `61483372...`; independent audit found one real blocker: the production
`RedditWidgetFactory` still allowed `RedditWidget.__init__` to build its old default provider before the
neutral owner injected a second provider. That duplicated construction and made neutral service failure
fail open to the QWidget-owned default.

The correction at `c320887c...` is independently GREEN:

- `rendering/widget_runtime_services.py` is the static family-specific runtime-service registry;
- `WidgetRuntimeManager` generically owns/builds/injects/retires runtime services without a central
  family `if/elif` switchboard;
- production `RedditWidgetFactory` creates runtime-managed Reddit widgets with default-provider
  construction explicitly suppressed;
- standalone `RedditWidget()` retains its convenience default where direct construction is genuinely
  used;
- runtime service build **or injection** failure leaves no neutral service and causes the production
  creation path to fail closed rather than run on a QWidget-owned fallback;
- deactivated Reddit capability creates neither widget nor provider;
- ordinary instance `enabled=False` remains distinct from family deactivation;
- Reddit/Reddit2 provider inheritance remains preserved;
- no shared-consumer machinery was invented because the Reddit post-provider seam is per-instance;
- the E2.7 Visualizer bridge was not generalized into ordinary family hot-retirement.

Reported corrected local gate: `440 passed, 4 skipped`, plus `py_compile` and `git diff --check` clean.
The independent reviewer audited the pushed source and regressions but did not independently rerun that
Windows execution.

Non-blocking cleanup for the next time the owner tests are touched: add a dedicated generic
service-injection-exception regression (build failure is already covered through the real production
setup seam). Do not create a separate checkpoint solely for that test.

### Reviewer family triage after slice 2

The reviewer inspected the remaining current families rather than delegating selection to the coding
agent.

**Slice-3 selection at that checkpoint: Weather.**

Reasoning:

- **Clock / Clock2 / Clock3:** the shared `GlobalClockTicker` is already presentation-neutral; do not
  manufacture an E1 provider migration merely because the current pixels are QWidget.
- **Reddit / Reddit2:** provider ownership is now landed and audited GREEN in slice 2.
- **Weather:** before slice 3, `WeatherWidget` owned the refresh/retry lifecycle, async request
  generations, cache-first startup orchestration and the worker closure that constructed
  `OpenMeteoProvider`. That was the clearest next ordinary-family runtime-data ownership seam.
- **Gmail:** `GmailBackend.instance()` is already a neutral process singleton backend. Gmail still has
  a real per-display poll/cache/fetch/model/action-controller seam to migrate later, but it is broader
  than the next bounded owner extraction; preserve the singleton rather than wrapping it.
- **Steam card families:** Progress and Friend Pulse are provider/task/timer-inert. Source inspection
  after Weather proved that Achievement Pulse and Abandonment Issues then owned detached cache/refresh
  request generations in QWidget code, with Abandonment additionally owning recurring cache-backed
  rotation. Slices 4–5 have since migrated those separate owners; do not force them into a generic Steam
  provider/service shape.
- **Media:** `MediaWidget` really does construct/hold a `BaseMediaController`, so Media is a substantial
  later E1 owner migration. It is deliberately **not next** because it is high-blast-radius: Spotify
  controls, Visualizer/media dependency behavior, transport state and cross-display/shared state all
  meet there.
- **Imgur:** do not migrate; Phase F0 removes it.

This ordering is an E1 migration decision, not a permanent family ranking.

### E1 slice 3 — Weather runtime-data/provider ownership — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `25f6ca4e7cdcaf82409a184c1d2999c01a7283e4`.

The completed checklist is pruned. The durable result is one registry-owned, presentation-neutral
`WeatherRuntimeService` for production Weather provider/network/cache/refresh/retry/request-generation
ownership; `WeatherWidget` is the temporary legacy pixel consumer. Production suppresses its standalone
convenience owner and fails closed on service build/injection failure.

The self-audit proved factory/setup ownership, activation dormancy, instance-disabled distinction,
single cadence, stale location/request fencing, cache/error/retry/`--noupdates`/manual-refresh behavior,
standalone separation and idempotent retirement. Focused Weather/owner/factory/setup/lifecycle gate:
`270 passed`, plus `py_compile`, fresh-process registry import dormancy and `git diff --check` clean.

Retirement deliberately fences unavoidable late shared-pool work rather than assuming running tasks can
be killed. All Weather tasks are runtime-generation tagged and the full runtime destruction barrier owns
generation-wide callback/task drainage. Accepted cache persistence may finish after presentation stop;
service-local teardown must not cancel unrelated delayed callbacks that share the display generation.

### E1 slice 4 — Steam Abandonment runtime/model ownership — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `86872ab92a6b0960f2a3746d43dc6056cb013d47`.

The completed checklist is pruned. The durable result is one per-card/display, registry-owned
`AbandonmentRuntimeService` for cache-first load, source/manual refresh, cache-only rotation, recurring
cadence, request generations and accepted prepared model/QImage state. It reuses the existing
process-scoped `core.steam` cache/backend/credential/asset authorities. `AbandonmentIssuesWidget` is now
only the temporary geometry/QPainter/fade/transition/input consumer; no generic shared-Steam service was
introduced.

Production suppresses the standalone convenience owner, injects the required service and validates the
exact live widget/service edge on repeated setup. Invalid registry entries retire; stale active reuse
fails closed; inactive reuse may rebuild through normal activation. All detached tasks/callbacks are
runtime-generation tagged and retirement fences unavoidable late shared-pool work.

Focused Abandonment/Steam/factory/setup/runtime-owner/lifecycle gate: `426 passed`, plus `py_compile`,
fresh-process registry and deactivated-family import dormancy, structural old-owner search and
`git diff --check` clean. Exact-diff self-audit and reused-agent repeated-setup audit were GREEN.

### E1 remaining after import-dormancy slice 9

- keep Steam Progress and Friend Pulse as E1 no-ops unless current source later gains a real runtime
  owner;
- hoist the per-display runtime owner out of legacy `WidgetManager` into an injected display-runtime
  boundary only after exact construction/lifecycle dependencies prove one owner serves the current
  presenter and can transfer to `QuickDisplayRuntime` without creating a duplicate proof-only owner.

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
- `test_spotify_visualizer_widget.py::test_on_tick_does_not_double_throttle_when_timer_already_paces`
  (synthetic Bubble harness omits the required `runtime_controller`; reproduced before Media slice 6 and
  recorded in `Future_Cleanup.md`).

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

**E1 slice 2 is CLOSED / AUDITED GREEN at
`c320887cc27e1b2bace10ba562a36e24ae9307ca`.**

**E1 slice 3 is CLOSED / SELF-AUDITED GREEN at
`25f6ca4e7cdcaf82409a184c1d2999c01a7283e4`.**

**E1 slice 4 is CLOSED / SELF-AUDITED GREEN at
`86872ab92a6b0960f2a3746d43dc6056cb013d47`.**

**E1 slice 5 is CLOSED / SELF-AUDITED GREEN at
`51948dc3956bc10549eb3e8440b2c3e25857f952`.**

**E1 slice 6 is CLOSED / SELF-AUDITED GREEN at
`4680130b8371adf74452eb76f64318e8fc6571a9`.**

The earlier generic live family-retirement prescription remains superseded. Current production family
activation is applied through Settings-owned full runtime teardown/recreation.

### E1 slice 5 — Steam Achievement Pulse runtime/model/artwork ownership — CLOSED

The completed checklist is pruned. The durable result is one per-card/display, registry-owned
`AchievementPulseRuntimeService` over the existing process-shared Steam cache/backend/credential/asset
authorities. It owns cache-first load, source/manual refresh, semantic model creation, request fencing,
unscaled decoded app/icon artwork with stable identity, replay and retirement. `SteamCardWidget` retains
only geometry, QPainter/fade/input/style concerns and DPR-specific image scaling/cropping caches.

Production suppresses the standalone convenience owner, injects exactly one required service and
validates the live presenter/service edge on repeated setup. Progress and Friend Pulse remain
unregistered and source-inert. All detached tasks/callbacks are runtime-generation tagged and weak-owner
fenced; the service adds no recurring timer or alternate Steam cache/backend path.

Focused Achievement/Steam/factory/setup/runtime-owner/lifecycle gate: `471 passed`, plus `py_compile`,
fresh-process registry/deactivated-family dormancy, structural old-owner search and `git diff --check`
clean. Exact-diff self-audit and reused-agent ownership review were GREEN; the review's suggested real
queued-UI stop fence was added and passed before checkpoint.

### E1 bounded post-slice-5 correction checkpoint — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `9ab4f47e6e7c081710a046ae38e6f310467249ca`.

The completed checklist is pruned. Abandonment now keeps source-resolution decoded artwork plus stable
identity in its neutral runtime while its temporary QWidget presenter owns logical-size/DPR cover
scaling, centered cropping and projection caching. Fetch, fallback, desaturation and decode remain one
unchanged path. Weather no longer exposes private cache/request/generation/timer properties as a model
API; only the real standalone/test forwarding methods remain and are explicitly transitional.

Focused Abandonment and Weather files plus their owner/factory/setup/lifecycle dependencies: `547
passed`, plus `py_compile`, structural owner searches, exact old/new QPainter pixel comparison (`0`
differing pixels), `git diff --check` and exact-diff self-audit clean. Both reused-agent boundary reviews
were GREEN.

### E1 slice 6 — Media shared runtime ownership — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `4680130b8371adf74452eb76f64318e8fc6571a9`.

The completed checklist is pruned. One `MediaRuntimeService` lease per participating display now joins
one runtime-generation shared owner for controller/provider lifetime, adaptive polling, query/cache/
retained state, provider/request/runtime/playback generations, optimistic transport confirmation and
one source-resolution artwork decode per stable identity. First/last active and attached lease
accounting prevents one display from stopping another and retires the family owner exactly once.

`MediaWidget` is now the temporary QWidget projection: it retains metadata/progress/control pixels,
QPixmap/DPR scaling/crop caches, transition deferral/fades and local keyboard/feedback presentation
timing. Production suppresses standalone construction and fails closed on service injection/reuse;
direct construction retains an isolated compatibility owner. No new thread or scheduler was added.
Visualizer seeding now reads the neutral accepted snapshot while the existing `media_updated` and
`refresh_playback_state` contracts remain intact.

Focused Media gate: `191 passed`; owner/factory/setup/runtime-destruction gate: `99 passed`; relevant
Visualizer bridge gate: `228 passed, 7 skipped, 1 deselected`. `py_compile`, focused Ruff, fresh-process
registry/deactivated-family dormancy, structural owner searches and `git diff --check` were clean. The
exact-diff self-audit and both reused-agent lifecycle/wiring reviews were GREEN after adding explicit
activation rollback, stop/restart freshness, real production reuse, worker/UI-boundary and
runtime-generation regressions.

The deselected Visualizer synthetic Bubble harness failure reproduces before this slice and is recorded
in `Future_Cleanup.md`; it is not being repaired inside the landed Media owner checkpoint.

### E1 slice 7 — Gmail shared runtime/model/action ownership — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `4f7dc8695c0f5096512f8fd421abc0c51faa2b6d`.

The completed checklist is pruned. One `GmailRuntimeService` lease per participating display now joins
one runtime-generation shared owner over the unchanged process-scoped `GmailBackend.instance()`.
That owner coordinates one backend bootstrap, cache-first startup decision, poll/fetch cadence,
accepted raw-email/unread/error/refresh stream, detached atomic cache persistence, new-mail sound
decision and serialized semantic action/post-action refresh path. It adds no backend, thread, scheduler
or cache format.

`GmailWidget` is now the temporary QWidget projection: it retains row grouping/formatting/capacity,
transition deferral, spinner/fade, geometry, QPixmap/QPainter caches, hit regions, menus and input.
Production suppresses the isolated convenience owner and fails closed on missing/stale service wiring;
direct construction retains standalone compatibility. First/last lease accounting preserves a
remaining display and retires the family owner exactly once. Runtime/startup/fetch/action generations
fence late work, custom filters survive presenter setting sync, and UI-dispatch decline cannot wedge
the serialized action slot.

All Gmail-focused files: `202 passed, 1 skipped`; owner/lifecycle/manager gate: `190 passed`; cross-family
registry gate: `50 passed`. Focused Ruff, `py_compile`, fresh-process registry dormancy, structural
owner searches and `git diff --check` were clean. The non-green repository-wide run reached `5362
passed, 159 skipped, 121 failed, 1 error`; those unrelated legacy/Quick/environment failures contained
no Gmail failure and were not repaired inside this landed slice. Exact-diff self-audit and both
reused-agent reviews were GREEN.

### E1 slice 8 — Media volume and mute accessory ownership — CLOSED / SELF-AUDITED GREEN

Pushed checkpoints:

```text
55bc73b0 — shared Media app-volume runtime owner
216c7da5 — shared system-mute runtime owner
```

The completed checklist is pruned. Per-display app-volume leases now join one runtime-generation owner
for controller/accepted-target lifetime, read/write generations, optimistic state and 80 ms write
coalescing. Separate per-display system-mute leases join one runtime-generation UI-thread owner for
endpoint availability, accepted mute state, one 30-second poll chain and semantic mute/system-volume
actions. These owners remain separate from each other and from the primary `MediaRuntimeService`.

`SpotifyVolumeWidget` and `MuteButtonWidget` retain only anchor/visibility/fade/CUSTOM geometry,
drag/input feedback and QPainter/QPixmap/style presentation. Production suppresses isolated defaults,
injects before activation, validates active reuse and fails closed on missing/stale services; standalone
construction retains isolated compatibility. First/final display accounting, target/owner/runtime
generations and authoritative cross-display hotkey routing prevent duplicate work and stale callbacks.
No controller, endpoint, poll chain, thread or scheduler is duplicated per display.

Focused volume checkpoint gate: `178 passed`. Final combined Media accessory/provider/setup/runtime
manager gate: `207 passed`, plus focused Ruff, `py_compile`, fresh-process registry probes, structural
owner searches and `git diff --check`. Exact-diff self-audit and reused-agent reviews were GREEN after
correcting queued-write fencing and stale-local/live-remote system-audio routing.

### E1 slice 9 — fresh-process/deactivated-family import dormancy — CLOSED / SELF-AUDITED GREEN

Pushed checkpoint: `ad71421d395806e78898593c71a3bc25a53bcdf1`.

The completed checklist is pruned. Annotation-only Clock/Weather/Media/Reddit/Visualizer/accessory types
in the two legacy host modules now resolve only under `TYPE_CHECKING`; genuine factories remain explicit
lazy creation seams. The `widgets` package itself is inert instead of activating Clock, Weather and
Media whenever any shared `widgets.*` helper is imported. Repository search found no caller of the
removed package-level class aliases, so no lazy compatibility facade was introduced.

Fresh-process host-import and real deactivated-Media setup probes prove no Media widget/runtime,
Visualizer, volume, mute, controller or Core Audio implementation resolves before admission. Focused
manager/setup/Media gate: `277 passed`; Clock/Weather/Reddit/Media-family gate: `179 passed`; relevant
Visualizer gate: `282 passed, 7 skipped, 1 deselected` (the deselected synthetic Bubble harness is the
known pre-existing failure recorded in `Future_Cleanup.md`). Strict new-file/fatal-host Ruff,
`py_compile`, structural import searches and `git diff --check` were clean. Both reused-agent reviews
were GREEN.

### E1 slice 10 — hoist `WidgetRuntimeManager` to the display-runtime boundary — IMPLEMENTATION ACTIVE

Exact current production still constructs and terminally owns `WidgetRuntimeManager` inside the legacy
`WidgetManager`. The current production display runtime is `DisplayWidget`; `QuickDisplayRuntime` is not
yet a production host and must not gain a second proof-only owner. Hoist the one real owner to the
current display-runtime boundary and inject it into the current presenter manager so Phase F can replace
the presenter without inheriting a QWidget-owned lifetime.

Live checklist:

- [ ] let `WidgetRuntimeManager` bind an explicit runtime-widget registry host contract instead of
  reading `WidgetManager._widgets` directly; preserve all lifecycle/E2.7/service APIs and fail closed on
  invalid/double host binding;
- [ ] construct exactly one `WidgetRuntimeManager` per production `DisplayWidget` runtime generation and
  inject it into `WidgetManager`; retain direct `WidgetManager(...)` convenience ownership only for
  standalone/tests and expose the injected edge as non-owning;
- [ ] move terminal service-owner cleanup to `rendering/display_cleanup.py` after presenter/widget
  cleanup and before display teardown completes; preserve idempotence, widget-before-service order,
  confirmed E2.7 cleanup semantics and runtime-generation destruction barriers;
- [ ] update setup/internal callers to consume a read-only runtime-manager accessor while retaining only
  the minimum transitional private alias needed by existing standalone tests;
- [ ] prove production identity/cardinality (`DisplayWidget -> one owner <- WidgetManager`), no duplicate
  service/controller/timer construction, injected-vs-standalone cleanup ownership, host detach/rebind
  rules, repeated setup and exact first/final shared-family retirement behavior;
- [ ] run focused runtime-manager/setup/factory/family-owner/display-cleanup/destruction/Visualizer gates,
  Ruff, `py_compile`, structural owner-construction searches and `git diff --check`; self-audit and
  commit/push the coherent hoist checkpoint.

Non-goals: constructing a `WidgetRuntimeManager` in dormant `QuickDisplayRuntime`, Quick pixels,
provider/cache redesign, E3/E4 or Phase F.

After E1 completes across bounded owner slices:

```text
E3 retained Quick primitives
-> E4 global eight-direction shadow authority
-> Phase-E closure review
-> Phase F
```

Do not send implementation work back into E2/E2.7 without a demonstrated regression.

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
- `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`

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

# 01 | Expanded Visualizer: SRPSS / MC Implementation Plan

**Prepared:** 2026-11-05. **Live tracked document since 2026-11-07** (extracted from the plans zip, which was never  
tracked; this file is the one source of truth). Reviewed 7 Nov against `8328a6d2` with the  
[Architecture Checklist](../../Reference/Architecture_Checklist.md); §0 below holds the phase ladder, gates, owners,  
dormancy, lifecycle, 2D/3D consistency, budgets and risks the review added. Sections A-J are the original plan,  
corrected where the review found drift.  
**Status:** FUTURE, NOT ADMITTED. This is a detailed implementation plan, not a patch, an approved runtime contract change, a build instruction, or authority to bypass `Current_Plan.md`.  
**Entry gate:** Begin **only when Waveform Ribbon is physically accepted and its live checklist closed**, and only after  
the prerequisite phase P-A (§0.1) has landed. The existing ordered `Current_Plan.md` retains authority until the operator explicitly admits this feature and adjusts the plan. Do not erase or silently reorder the later 3D work.  
**Initial supported visualizer:** Extruded Bubble (EB), only. Subsequent modes opt in explicitly by descriptor and pass identical gates.  
**Products:** existing Standard SRPSS and existing Media Center (MC) sharing the current Quick scene. No additional screensaver window, no product fork.  
**Companion:** `02_ShittyMusicPlayer_Implementation_Plan.md` begins after this plan's acceptance and reuses its proven presentation **semantics**, not the screensaver's physical window manager.

## 0. Phase ladder, prerequisites, owners and budgets (7 Nov review)

### 0.1 Prerequisites from the architecture checklist

| Checklist item | Must land before | Why |
| --- | --- | --- |
| **AC-02** Visualizer host binding extracted from `DisplayManager`; Media docking a declared placement policy | **M2** (the takeover transaction binds to the owner); M1's pure reducer may start on today's owner | The takeover state machine (§D) must be a sibling of one host-neutral Visualizer owner, not a fourth concern inside the 6k-line `DisplayManager`. Doing it afterwards moves the new code twice. |
| **AC-11** one 3D camera control contract (operator decision) | a second mode opts into expansion | At full display the card is large and orbiting likely; Sphere and Extruded Spectrum have no Reset Camera today. EB (the first mode) already has the framed camera. |
| **AC-04** inactive-renderer release failure no longer blacks out the active mode | M5 (mode requests while expanded) | Capable -> incapable collapses and switches mode; a stuck release would black out the whole display, not a card. |
| **AC-09** one card border width resolver | M2 (expanded card chrome) | The expanded presentation variant must not inherit `DisplayManager`'s private copy. |

**Does not need:** AC-03 (application-service tier). Expansion intent is a settings value that the next display
generation re-evaluates once at its readiness edge (§B.8); nothing outlives a generation.

### 0.2 Phase ladder with entry and exit gates

Each phase has an entry gate (what must be true to start), an exit gate (measurable evidence that closes it) and the
owner that signs it. The original milestones (§H) keep their checklists; this table binds them.

| Phase | Entry gate | Exit gate (evidence) | Signs |
| --- | --- | --- | --- |
| **P-A** AC-02 host binding | Waveform accepted; `Current_Plan.md` admits P-A | AC-02's regression bar green; Edit/Arrange parity maps byte-identical; `DisplayManager` no longer constructs the owner | lead |
| **M0** baseline | P-A merged; operator admits plan 01 | EB baseline receipts at canonical, wide/tall and display-sized views, one and two monitors, idle and game60: fps, tick median/p90, GIL share, frame age, lease counts; written to `.artifacts/evidence/expanded_visualizer/baseline/`; no Visualizer code changed | lead |
| **M1** capability + persistence + reducer | M0 receipts exist | all pure reducer tests green incl. stale generation, duplicate glyph, Edit cancel, topology loss; `replace_visualizer_runtime_preset_state` round-trips the intent; no dormant-mode import (import scan) | agent |
| **M2** full-display viewport | M1 green; AC-02, AC-09 merged | production-host screenshots at 16:9, 16:10, 21:9, portrait, mixed DPR show the display-wide viewport; reactivity packet digests identical to M0 on recorded clips; ordinary rect round-trips to the byte | lead + operator look |
| **M3** fades, HUD, widget suspension | M2 accepted | consumer counts equal before/after N cycles (Media, OSD, Gmail, Feeds, Steam leases); no QObject/subscription growth over 20 cycles; HUD visible only on events, fades within its bounded window | agent |
| **M4** wallpaper policy and GPU savings | E0 state diagram written and reviewed | batch traces: expected/published/covered identities, zero stalled batch, zero backlog on collapse; measured GPU and render-thread CPU delta on the covered display vs M0 (relative, load recorded) | lead |
| **M5** transactional lifecycle | M3, M4 green | deterministic event traces for capable->capable, capable->incapable, failed activation, transfer at mixed DPI, Settings open/close x10, Edit Save/Cancel, hotplug; resource counts flat | agent |
| **M6** performance, fidelity, admission | M5 green | §0.7 budgets met at 4K under game60 (or a trigger recorded); EB BTF/reattack/settle/stream/drift unchanged vs M0; docs updated for proven semantics only | operator physical acceptance |

### 0.3 SSOT owners (who owns what; nothing gets a second owner)

| Thing | Owner | Never |
| --- | --- | --- |
| mode capability `supports_expanded_display` | `core/settings/visualizer_mode_registry.py` descriptor (default False; EB True first) | a Settings flag, a preset field |
| persisted intent `widgets.spotify_visualizer.expanded_display_requested` | canonical defaults + `SettingsManager` normaliser; excluded from mode/Custom payload | a sidecar file, a per-preset copy |
| effective state (DORMANT..RETIRING) | the takeover coordinator next to the Visualizer host binding (AC-02), one per process | QML state, `DisplayManager` ad hoc flags |
| expanded viewport geometry | `ResolvedVisualizerPresentation` variant from the canonical presentation resolver | a stretched texture, authored CUSTOM geometry |
| widget visibility while covered | one display-local transient visual policy on the retained host (§F) | `widgets.<id>.enabled`, family activation, layout slots |
| per-display wallpaper admission | one policy at the engine/manager batch seam (§E) | a second queue, dropped callbacks |
| HUD data | existing Media model / volume model (§G) | a second GSMTC query, decoder or art cache |
| the one Visualizer owner, controller, clock, DSP lane, renderer | unchanged (`Docs/Contracts.md` → Transition / visualizer) | anything new |

### 0.4 Dormancy: nothing costs anything while full display is off

Prove, not assert, each of these at M1 and again at M6:

- `tools/overhead_baseline.py` transition and Visualizer GL/Python call counts identical to the stored baseline
  with the capability present and the intent False (the glyph and HUD are `Loader`s that stay inactive unless the
  mode is capable and the pointer is over the card; the coordinator is a plain object with no timer).
- The AST import scan shows no new module reachable from the common Quick import or from an incapable mode.
- No new QObject, signal connection, timer or per-frame branch on the ordinary path: the reducer is called only on
  events (glyph, mode request, transfer, Settings, topology), never per frame.
- Zero new work while displays are off (`Spec.md` → Lifecycle → Displays off): an expanded display parks like an
  ordinary one; no fade animation runs while parked.

### 0.5 Lifecycle contracts the takeover must honour

- One display generation owns one effective state; every event carries runtime generation, visualizer activation
  and physical display identity; stale ones are rejected, never queued.
- Settings keeps today's teardown (`engine_handlers.py::on_settings_requested`): intent persists, state dies; the
  replacement generation re-evaluates once at the reveal coordinator's readiness edge, before any retained root is
  exposed (no ordinary-card flash, no double fade).
- Display power: an expanded display parks and resumes exactly as an ordinary one; the fresh-frame fence covers the
  first expanded frame after wake.
- Topology: loss of the owning display retires the generation under the existing barriers; the intent survives;
  a return re-evaluates. Transfer is one transaction on the existing `_transfer_quick_visualizer_unit` seam with
  rollback fences for both takeover scopes (§D4).
- Edit: entering Edit collapses through the same transaction; an active draft is resolved by the session's own
  Save/Cancel path (§D5); the CUSTOM working override and committed geometry are untouched by expansion.
- Terminal exit: HUD animations, leases and GL resources retire under the existing render-thread owner; no new
  release path.

### 0.6 2D/3D consistency at full display

Every registered mode must look and behave as the same mode at the card and at the display; expansion is a viewport,
not a different renderer.

- **Clip policy stays mode-owned.** `CARD_INTERIOR` modes (Bubble, Spectrum, Neon Lake, Extruded Bubble, Waveform)
  keep their card interior semantics scaled to the display rect; `VIEWPORT_RECT` modes (Sphere, Extruded Spectrum)
  keep theirs. The expanded variant is resolved per policy and proven per mode (§B2), never by flipping policies.
- **2D modes:** the line halo scales with the visible area's square root against 420x280 (`Docs/Contracts.md`), and
  Bubble sizes its radius unit from the canonical card times `world_scale` (R-170; a 4K card draws up to 72 live
  heroes / 110 with trails). Expansion must not add a second compressor (R-69). Measure Bubble's tick and GPU at
  4K before calling 2D "free".
- **3D modes:** the shared framed camera (`core/settings/framed_camera.py`) resolves its frustum from the expanded
  aspect; authored poses, preset starting views and saved camera values are unchanged; W/A/S/D, drag orbit, inertia
  and wrap behave exactly as at the card (AC-11 decides the contract for modes without a framed spec before they opt
  in). Control hints and Reset Camera sit in the same safe zone as the collapse glyph (§B1).
- **Input:** double-click cycles the mode, middle-click cycles the preset, the collapse glyph consumes its own presses
  (including the second press of a double-click, as the queued Reset Camera fix requires), for 2D and 3D alike.
- **Audio:** one engine, one tick, one cadence; expansion changes no DSP, floor, smoothing or ramp.

### 0.7 Performance budgets, including 4K, and the backend triggers

Budgets are the live-shape ones in `Docs/Guides/Visualizer_Change_Checklist.md` §1C, applied at the display size.
Measure with `tools/visualizer_live_check.py --mode <mode> --preset N --load game60` on the quiet machine, A/B
alternated against the card size, system conditions recorded (`Docs/Reference/Benchmarks.md`), median and p90.

| Budget | Card (today) | Full display, up to 3840x2160 | If exceeded |
| --- | --- | --- | --- |
| logical tick median | ≤ 2.5 ms | ≤ 2.5 ms (resolution-independent, except Bubble's density growth: measure) | optimise the tick first (Graphics decision step) |
| render-mode time (render thread, live) | ≤ 8 ms | ≤ 8 ms | mixed resolution for soft layers (mist, bloom, reflection blur) at their quality floor, lines/dots/particles native |
| GPU time per frame (`TIME_ELAPSED`, median / p90) | recorded per mode | ≤ 8 ms / ≤ 11 ms with soft layers at the quality floor | **Trigger 1** of the Graphics Backend Decision fires: record it in `Current_Plan.md`; the native Vulkan core precedes new 3D modes |
| publish -> swap median | ≤ 20 ms | ≤ 20 ms | frame age gone: find the owner (tick, GL call count, GIL share) before any knob |
| late frames under game60 | mode's accepted figure | not worse than at the card by more than the GPU delta explains | regression; not accepted |
| GPU memory | scene targets at card size | scene targets at display size: record bytes per target (an RGBA16F 4K target is ~66 MB; a 4x multisampled one ~265 MB plus depth); no permanent extra target | a quality floor that reduces MSAA at full display is an authored choice, recorded per mode |

- Record per-mode GPU time at 4K with and without the reduced-resolution soft layers; that table is the evidence the
  backend decision waits for (`Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` → Meanwhile).
- **Trigger 2** (render-thread starvation) is judged only after the Waveform logical tick cut lands
  (`Current_Plan.md` §4); do not judge it on expanded Waveform before then.
- Port-readiness rules bind any new GPU code written here (there should be none: the variant is a viewport).

### 0.8 Full rearrangement

Expansion is not a layout. It writes no geometry, moves no widget, and collapses to the exact committed layout. The
Visualizer's resting place is decided by its placement policy (AC-02: `docked_to: media | none`), so a user who has
arranged the Visualizer away from Media gets it back there. Arrange and Edit never show an expanded state; they edit
the ordinary layout, and entering Edit collapses first.

### 0.9 Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| per-display wallpaper suppression wedges a global batch (§E) | medium | critical | pure state tests of the batch accounting first (E1.1); the fallback keeps the transaction contract and records one unresolved perf item |
| 4K GPU cost of EB/Waveform exceeds budget | medium | high (decides the backend) | mixed resolution for soft layers; otherwise trigger 1 recorded, not hidden by a knob |
| widget re-admission after fade creates duplicate owners or orphans shared backends | medium | high | symmetric, idempotent, exact-generation `admit_widget` on the binder (§F); consumer counts in the regression bar |
| expansion persisted on a now-incapable mode flashes or loops at startup | low | medium | one evaluation at the readiness edge; deterministic incapable rule (§D3) |
| HUD/OSD/control hit overlap | medium | low | one visibility lease with priority (§G); native QML hit tests |
| plan drift from the source by the time it starts | high | medium | M0 re-audits every seam in §A and records amendments |

---

## A. Source audit and interpretation

Repository `Basjohn/ShittyRandomPhotoScreenSaver`, default `main`, examined 2026-11-05. Revalidate sources before beginning; proposal input is `Docs/Future_Work/ShittyMusicPlayer/Proposal.md` in `SRPSS_ShittyMusicPlayer_Proposal_Expanded_2026-11-05(1).zip`. The audits cited below are **source inspection, not executed tests or physical validation**.

| Existing fact / seam | Actual source of authority | Consequence for implementation |
| --- | --- | --- |
| One accelerated retained `QQuickWindow` per participating display, Qt 6.11.2/OpenGL 4.6, `QSGRenderNode` | `Spec.md` Build/runtime presentation; `Docs/Contracts.md` Physical presentation; `rendering/quick/runtime.py`; `rendering/quick/qml/DisplayScene.qml` | Expansion enlarges the existing retained visualizer inside the **existing** display, not an extra window, `QQuickWidget` or second GL context. |
| One Visualizer owner/controller/logical clock/DSP lane and newest-state bridge | `Docs/Contracts.md` Transition / visualizer; `Docs/Reference/Visualizer_Reference.md`; `widgets/spotify_visualizer/quick_display_visualizer_owner.py`; `widgets/spotify_visualizer/quick_presentation_sync.py` | Expansion must not recreate simulation, analysis, mode, preset, camera or frame cadence. |
| `DisplayManager` admits exactly one visualizer to participating displays | `engine/display_manager.py::_admit_quick_visualizer`, `_construct_quick_visualizer_owner_on`; `rendering/quick/visualizer_admission.py` | Expansion attaches to that owner; `ALL` still selects first participating display; unavailable explicit monitor does **not** silently reroute. |
| Existing cross-display visualizer transfer is transactional | `engine/display_manager.py::_transfer_quick_visualizer_unit`; `rendering/quick/scene_controller.py::_release_visualizer_for_transfer/_adopt_visualizer_transfer` | Extend this seam for takeover handoff. Never use retire/recreate for a normal move. |
| Visualizer geometry is one `ResolvedVisualizerPresentation` | `rendering/quick/scene_controller.py::apply_visualizer_presentation`; `Docs/Guardrails/Visualizer_Presentation.md` | Resolve expanded viewport at a **presentation policy** layer. Do not overwrite saved CUSTOM bounds, preset geometry or authored camera pose. |
| Ordinary widgets have retained, display-local presentation and neutral services | `rendering/quick/widgets/host.py`; `rendering/quick/widgets/family_binder.py`; `rendering/widget_runtime_manager.py`; `rendering/quick/display_presenter.py` | Fade, display-local suspend and reactivation must be attached to existing owners. Binder has `retire_widget` today but no symmetric targeted re-admission contract; design and test one only if actual resource suspension is needed. |
| Media controller is shared per generation across display leases | `widgets/media_runtime.py::_SharedMediaRuntimeOwner` (generation key, active leases, media serial lane); `rendering/quick/widgets/media.py` | HUD must consume already-admitted playback metadata. **Hiding Media paint cannot discard the last required Media/Visualizer consumer.** |
| Visualizer playback truth already resolves a Media model from another display | `engine/display_manager.py::_resolve_quick_visualizer_media_model/_bind_quick_visualizer_media` | Preserve cross-display Media truth. A non-owning display's Media need not be duplicated on the expanded display. |
| OSD has a foreground scene lane and shared Core Audio endpoint | `rendering/quick/qml/DisplayScene.qml` OSD foreground (`z:30`); `Docs/Reference/System_Volume_OSD.md`; `Docs/Contracts.md` shared system audio dormancy | Preserve OSD independently, including with Media visually suppressed. Never add a second endpoint subscriber or volume poll. |
| Wallpaper image changes are whole, admitted batches; expected-screen accounting controls completion | `engine/screensaver_engine.py::_show_next_image/_try_begin_image_change_work`; `engine/display_manager.py::_begin_quick_transition_batch/_finish_quick_transition_batch_if_complete/_present_quick_captured_image` | There is **no currently proven display-local 'pause transitions' toggle**. Per-display suppression requires a new transaction with explicit completion/accounting semantics; simply hiding a background or ignoring a callback can deadlock a batch. |
| Current source→destination image contract rejects overwrite during active transition | `rendering/quick/runtime.py::set_presentation_image/start_transition`; `engine/display_manager.py::_present_quick_captured_image` | Do not cancel/snap a live run to enter expansion. Settle on a safe completion/admission edge. |
| QML scene order: wallpaper -> ordinary widgets -> visualizer -> OSD -> Edit -> context menu | `rendering/quick/qml/DisplayScene.qml` | HUD and expansion glyph must respect context menu, OSD, tooltip and Edit z/hit policy, not use an extra native overlay. |
| Settings fully stops and replaces SRPSS runtime | `engine/engine_handlers.py::on_settings_requested/_restart_after_settings_dialog_destroyed`; `engine/runtime_destruction.py` | Keep this exact lifecycle. Persist **intent**, never a retained Qt item, and reapply only after the replacement generation is ready. |
| Mode and preset changes have distinct semantic paths | `engine/display_manager.py::_request_quick_visualizer_mode/_request_quick_visualizer_preset_change`; `Docs/Reference/Visualizer_Reference.md` | Capability checks and expansion transfer must wrap canonical mode transitions, never replace them. |
| Universal glyph chrome and local visualizer glyphs already exist | `rendering/quick/qml/WidgetHoverEditGlyphs.qml`; `VisualizerPresentation.qml`; `OverlayWidget.qml` | Reuse the input admission/theme/hover/tooltip semantics and avoid overlapping reset/preset/transfer controls. The expand glyph is a distinct semantic action, **not** an Edit glyph. |
| Mode-owned preset change writes the whole normalized Visualizer child | `core/settings/settings_manager.py::replace_visualizer_runtime_preset_state` | New expanded intent MUST survive the normalization/atomic replacement; exclude it from mode/Custom payload and regression-test the exact transaction. |
| Profile settings are distinct but non-settings data root shared | `core/settings/json_store.py::determine_storage_path`; `core/settings/storage_paths.py`; `Docs/Contracts.md` | Standard and MC may have independent expansion preferences. No sidecar state file or new profile resolver. |

**Binding review first:** `Spec.md`, `Docs/Contracts.md`, `Docs/Guardrails/Performance_Optimization_Contract.md`, `Docs/Guardrails/Visualizer_Presentation.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`, `Docs/Guides/Visualizer_Change_Checklist.md`, `Docs/Reference/Visualizer_Reference.md`, `Docs/Reference/Scene3D_Resources.md`, `Docs/Reference/Extruded_Bubble/*`, `Docs/TestSuite.md`, and exact historical bug lessons R-69 / R-71 / R-87 / native Qt retirement. Documentation is contract authority, but source may reveal an unimplemented contract; never silently weaken it to pass a test.

## B. Product behaviour / scoped definitions

1. **Expanded** means the *existing selected Quick display scene's logical display rectangle*, not exclusive OS fullscreen, a new window or altered screen/desktop shell. It covers all compositor space intended by the product, respecting actual selected display geometry and viewport/DPR, not an arbitrary 16:9 crop. Preserve current screen-window policy and monitor identity.
2. **Entering:** operator presses a contextual diagonal upper-right expansion glyph on a capable visualizer. Normal hover/interaction eligibility applies. User sees a short, gentle coordinated transition from ordinary visualizer rect to display-wide viewport; ordinary widgets on **that** display fade out. Other displays behave normally. OSD remains available. There is no extra mode activation.
3. **Exiting:** reverse glyph (diagonal lower-left), explicit collapse, Edit entry, loss of capability, or relocation. Return exact authored pre-expansion presentation rather than saving the temporary screen-sized rect. Collapse/restore is independent of preset and CUSTOM values.
4. **Mode selection:** ordinary double-click and context-menu mode switches retain current meaning. Capable -> capable stays expanded through the canonical activation (when more capabilities exist). Capable -> incapable collapses in a strictly ordered handoff, then changes mode. A rejected mode request leaves the current mode/expansion intact. Middle-click still cycles preset only.
5. **Other display:** no fades, audio change, transition suppression, image queue mutation or OSD change, except legitimate shared-source work already occurring. A shared provider survives while any real consumer still needs it.
6. **HUD:** tiny, tasteful bottom-right media information (artist/title/cover and volume rail, optional playback state). Event-revealed by track, play/pause, eligible volume or pointer activity; fade away after a short bounded visibility period. No permanent timer/poller, no duplicate transport controller, and no overlap/hitbox conflict with OSD, camera, presets or collapse glyph.
7. **Persistence:** expansion is a user intent, per existing settings profile. It is effective only if the currently resolved mode supports it, owner is live, monitor participates, and Edit/Settings/retirement aren't active. Losing eligibility must not rewrite user intent as a false 'off' unless the user explicitly toggles it off; a deliberately selected incapable mode can normalize effective state off without destroying the original authored layout.
8. **Restore:** startup/Settings restart/topology replacement re-evaluates persisted intent **once at an already-defined readiness edge**; no unguarded early fade, first-wallpaper duplication or reentry loop. Missing explicit target remains unadmitted (no theft of another display), and later reconnection restores safely.
9. **DPR/size:** recompute physical frame/viewport from target display and its existing display identity, not from screen-1 cached values. Treat camera, frustum, stream volume, near field, lighting reach, translucency and particles as authored mode semantics, not as a stretched old texture.
10. **No accidental global style changes:** preserve selected themes, card chrome policy, opacity, OSD palette, default user content and existing settings. SMP later reuses the **semantic display takeover contract**, not this screensaver-only physical compositor.

### B1. Input and chrome priority

- [ ] Show an **expand ↗** control (vector drawn, not a platform-dependent font emoji) for eligible modes, initially EB only. On expanded view, replace with **collapse ↙**. Distinct from SMP's later square-with-diagonal-arrow **Pop Out**, which moves a window.
- [ ] Use the existing interaction/admission gate: no invisible clickable hits, no action under an active context menu, no conflicting visualizer double-click/preset middle-click, no edit pointer gesture leak.
- [ ] Reserve a safe zone for collapse glyph, camera-reset and preset-controls row; auto-relocate HUD within target display when OSD or controls are visible. Inspect the actual `VisualizerPresentation.qml` bottom-right controls (`cameraResetGlyph`, `presetControls`) before choosing anchors. Do not stack HUD on them.
- [ ] Context-menu and mouse actions are single semantic events. If a fullscreen glyph receives a click, consume it before image-next / visualizer-mode-cycle fallback; no duplicate action due to Qt TapHandler propagation.
- [ ] Keyboard path for collapse must be documented and not steal current exit/media/CUSTOM keys. Offer a visible control usable with mouse and keyboard focus; avoid an unadvertised global key override.

### B2. Mode policy vs authored state

**Recommended minimal source addition** (names illustrative; fit registry naming before implementation):

```text
VisualizerModeDescriptor / presentation capability:
  supports_expanded_display: bool = False

widgets.spotify_visualizer (product-level canonical persisted intent):
  expanded_display_requested: bool = False

Resolved display policy (runtime, never a preset):
  requested, effective, owning_display_identity, runtime_generation,
  visualizer_activation_id, expanded_viewport, exclusion_policy
```

- [ ] Define *registered*, *enabled*, *active*, *capable* and *expanded-effective* as five different predicates. A disabled/experimental/unavailable mode cannot be made active by expansion.
- [ ] Exactly one persisted intent; do not persist a second mirror of current mode/monitor/geometry. Existing mode/physical route keys are authoritative. If the Visualizer section normalization cannot retain the new non-preset key across `replace_visualizer_runtime_preset_state`, extend its canonical schema/normalizer and tests, or choose a deliberately documented sibling SSOT. **Never** solve by patching each preset or writing a separate JSON file.
- [ ] Keep `Custom` *preset* payload mode-owned. Keep global layout `CUSTOM` editor/slots separate. Expansion overwrites neither.
- [ ] Framed vs frameless renderer policy stays mode-owned. Capability alone does not change `CARD_INTERIOR` to `VIEWPORT_RECT` across unrelated modes; explicitly resolve an expanded presentation variant for eligible modes and prove its clip/shell behaviour.

## C. Hard invariants / fail-closed rules

- [ ] One existing Quick scene/window for each participating display, one visualizer controller, one logical clock, one audio worker lane, one renderer per current owning display; zero surprise second windows/context/visualizer sources.
- [ ] No per-frame GUI scans, Python timers, render-driven animation/physics clocks, `frameSwapped`-update feedback loops, synthetic source capture, additional BeatEngine or duplicated Media queries.
- [ ] No change to EB bubble counts, drift/stream speed, smoothing, sources, particle/microbubble inheritance, light/reflection material, collision physics, BTF/temporal fidelity, mode preset data or user-created Custom values in order to improve timing.
- [ ] No early resource retirement: existing visualizer logical runtime must satisfy stop/join barrier; Qt item release, queued callbacks, context-local GL resources and display transfers retain generation fences.
- [ ] Shared data/source/endpoint lifetime is consumer-based; per-display visibility does not infer global service dormancy. A widget still needed on another display remains fully functional there.
- [ ] OSD is an independently admitted foreground consumer (not implicitly disabled by suppressing other overlays). No attempt to use OSD Core Audio as a substitute for provider-specific app volume.
- [ ] Wallpaper images and transitions on **other** displays preserve source order, identity accounting, authored transition type/duration and stagger. No spurious Crossfade substitution.
- [ ] A pending or running display transition reaches its existing finalization contract before a policy change that would detach its resources. Never cancel/snap/destroy a transition solely to acquire expansion.
- [ ] No backlog of missed wallpaper transitions or deferred image tasks while expanded; exit must have a bounded, precisely defined rejoin rule, not 'replay every skipped slide'.
- [ ] Real user Settings still performs existing stop -> destruction barrier -> dialog -> replacement. A retained fullscreen viewport never leaks into the dialog.
- [ ] Native physical evidence is still required for final appearance and dual-display frame pacing; automated tests should cover virtually all correctness before operator review.

## D. State machine, authority and atomic transactions

**Proposed pure state vocabulary** (single display-manager-level semantic coordinator; do not create a global renderer):

```text
DORMANT            no visualizer owner or no current capability
ORDINARY           canonical visualizer rect, widgets and wallpaper normal
ENTER_PENDING      eligibility fenced; active wallpaper batch/EDIT resolving
ENTERING           precomputed scope + one-shot paint fade; old rect saved by owner
EXPANDED           full logical display viewport, HUD/OSD; scoped omissions active
EXITING            restore wallpaper/widget admission and ordinary geometry
TRANSFER_PENDING   source/target admission transaction, no duplicate owner
RETIRING           generation closing; never process late callbacks
```

The operator's intended *expanded* bool is separate from transient state. Only the current `DisplayManager`/canonical owner may commit a state transition; QML owns animation and hit-target visuals, **not** persisted state or Media/source work. Idempotent repeated clicks are coalesced by this owner. Cancellation/target loss rolls back to the last fully admitted coherent state, never a half-faded scene. Every event carries current runtime-generation, visualizer activation, and physical display identity where relevant.

### D1. Enter expanded (ordered)

1. Read current capability/enablement, display routing, scene readiness, `CUSTOM` status and existing accepted transition batch. Reject without writes if any is invalid.
2. Resolve active Edit transaction through its **existing** user-choice/Save/Cancel path. Preserve draft when the user cancels entry; do not silently Save or Cancel. This same requirement applies if the glyph is technically clicked while Edit chrome is present.
3. If a transition is active, wait for its accepted finalization edge or reject/defer **one latest intent** bounded by that existing edge. Do not steal its destination or start a timer to poll for completion.
4. Snapshot a small *transient* activation record (owning display identity, ordinary resolved rect, visible widget IDs/leases, visualizer activation/generation, current image/transition policy). Do **not** clone settings, scene objects or render payloads.
5. Resolve entire display logical viewport and mode camera/clip policy through the canonical presentation/config resolver; preflight render target size/DPR and resource budget before making overlay changes.
6. Fence/prepare per-display wallpaper policy (see E), then apply a display-local transient widget-visibility gate. Allow other displays and OSD to continue.
7. Apply one gently eased viewport transition and overlays through the retained Quick host. On completion, lazily retire **only those truly display-local service/presentation leases proven safe**; preserve a cheap re-admission snapshot for restoration.
8. Publish EXPANDED and persist requested intent with a narrow canonical Settings write *only after the action succeeds*. Failure restores ordinary layout and policy. Do not persist on each animation frame.

### D2. Exit expanded (ordered)

1. Fence current expanded generation/input and HUD animations; capture the latest intended restore target from canonical settings (not from a stale stored pixel rect).
2. Re-admit widgets and their required display leases **without starting a duplicate shared owner or blanking services still used elsewhere**. Honor original per-display routes and current Settings state.
3. Restore wallpaper eligibility with one coherent current source/image policy (E); if there is no ready wallpaper yet, preserve a non-black safe known frame and hand off at the existing readiness boundary. No replay backlog.
4. Apply short exit transition to ordinary visualizer geometry and restore its original clip/shell policy.
5. Commit ORDINARY; explicit user collapse persists `expanded_display_requested=False`. Automatic temporary collapse (e.g. Settings, edit start, monitor loss) does not necessarily erase intended future expansion.

### D3. Mode requests

- [ ] **Capable -> capable:** precompute new mode's expanded viewport and controller activation using existing request-completion edge; retain the takeover and wallpaper policy. Do not shrink to a card before a valid new frame. No controller duplication; failed activation keeps the previous mode and UI state.
- [ ] **Capable -> incapable:** hold mode activation until orderly collapse; use current `_request_quick_visualizer_mode` call and its existing `on_complete` after the collapse has committed. If target admission fails after that temporary collapse, **roll back by re-expanding the still-active capable source mode** (subject to its current eligibility), not by silently leaving the old mode miniaturized. Do not persist an inconsistent mode or lose user geometry.
- [ ] **Incapable -> capable:** select mode normally; do **not** silently reenter expansion unless persisted user intent is explicitly defined to reapply after capabilities become eligible. Make this decision deterministic and test it.
- [ ] Middle click/preset Previous/Next must not toggle expansion, destroy it, or reset playback; `replace_visualizer_runtime_preset_state` preserves the product-level intent and geometry.
- [ ] Request rejection vs preparation failure vs accepted completion has distinct outcomes; stale completion cannot resurrect an expanded state on another display.

### D4. Monitor transfer / loss

- [ ] Resolve true physical destination identity, participation, new DPR/size/refresh, display-local wallpaper status, OSD presence and whether the destination is already under any takeover.
- [ ] Perform a single **source collapse + target preparation + existing `transfer_visualizer_to`/manager transfer + target expand** transaction. No duplicate renderer or controller in the overlap. If target cannot be preflighted, preserve source intact rather than strand the visualizer.
- [ ] Existing `QuickDisplayUnit.attach_visualizer_owner/detach_visualizer_owner` and `DisplayManager._transfer_quick_visualizer_unit` retain exact retirement ownership; add rollback fences for *both* display takeover scopes.
- [ ] Source widgets/transition eligibility restore; target widgets/transition eligibility suppress. Other displays unaffected.
- [ ] New target viewport uses local real logical and physical geometry and camera reflow; no artificial scaling from the source display or writes to authored preset coordinates.
- [ ] Explicit route to an absent display stays absent until it returns. Topology loss retires the generation under existing barriers and re-evaluates intent after replacement; do not create invisible offscreen surfaces.

### D5. Startup / Settings / Edit / shutdown

- [ ] Initial scene admission resolves mode and monitor **first**, then expanded intent; reveal coordinator gates all new retained roots before exposure. A persisted expanded intent must never cause a cold ordinary-card flash.
- [ ] Settings opens using current `on_settings_requested`, complete teardown and destruction barrier. The *intent* persists in profile settings. On return, only the new generation may re-admit expanded state; no callbacks from prior QML objects.
- [ ] Edit entry from expanded collapses through the same transaction. **If Edit has an active unsaved draft when expansion is requested, prompt/resolve with the current session policy; no implicit discard.** Returning from Edit restores expanded intent only after editor exit and correct readiness, not during drag.
- [ ] Terminal exit releases HUD animations, every local lease, visualizer and GL resources with existing exact retirement; preserve settings but not runtime references.
- [ ] Restoration on startup/Settings and topology change is idempotent, bounded and has a documented safe state if eligible mode is no longer available.

## E. Per-display wallpaper/transition suppression: the critical architectural gate

**Problem proven by inspection:** `engine/screensaver_engine.py::_show_next_image` reserves the full image-change transaction before queue/history mutation; `DisplayManager` tracks an expected set of screens and completes only when every admitted destination is authoritative. `QuickDisplayRuntime.set_presentation_image` rejects replacing the image during an active transition. Therefore one display cannot simply ignore `start_transition`, drop completion, or unhook image events. Nor can a 'deferred' per-display FIFO grow behind a fullscreen view.

### E0. Required design proof **before** a suppression implementation

- [ ] Trace `_show_next_image`, `_prepare_next_transition`, `_load_and_display_image_async`, `DisplayManager` expected/published screen sets, `_present_quick_captured_image`, `transition_batch_idle`, `current_images`, the image queue/peek/history, source-speculative workers, monitor wake/replay, startup reveal and image-cache ownership. Draw an explicit source/destination/accounting state diagram for (a) one covered screen of two, (b) ALL covered if possible, (c) last uncovered screen removed mid-batch.
- [ ] Define **one authoritative per-display presentation admission policy** at the existing engine/manager seam: `normal`, `covered_committed_without_effect`, `covered_excluded_from_processing` (labels illustrative). This is NOT a second transition engine or separate image queue.
- [ ] Choose the strongest state actually safe. Prefer suppressing GPU effect work and any unnecessary image preparation on the covered display. The *global* queue and other displays keep their canonical semantics, including same-image/independent-image configuration. Distinguish logical image progression from physical pixel upload.
- [ ] Decide and test whether a covered display must still **commit a cheap destination identity/accounting receipt** for a global batch, or can be removed from that batch's expected set at admission. If excluded, recompute expected membership **before** queue mutation, and the actual completion contract must remain satisfiable. Do not later add it to an already running batch.
- [ ] Never suspend a shared source/prefetch worker solely because a single display is covered; only suppress work provably exclusive to it. If both screens are covered or none selected, apply documented zero-target/no-consumer behavior rather than infinite defer.
- [ ] Define exactly what the uncovered display receives on resume: current authoritative wallpaper at the engine's next admitted edge vs a single explicit re-seed without transition. No replay of skipped frames, no old/stale destination, no black flash.
- [ ] Classify performance honestly: hiding a visualizer's background under opaque pixels may avoid visible work but **does not itself stop render/GPU work**; measuring that distinction is part of the gate.

### E1. Implementation order and fallbacks

1. Implement **batch/accounting-safe no-effect covered display** in pure state tests first. It must send a completed/omitted receipt at the right boundary; never replace a live source/destination image without the accepted transition completion.
2. Prove cross-display ongoing effects by real Quick smoke and synthetic two-display completion sequences with source/history assertions.
3. Only then remove covered display's decode/process/prefetch participation if evidence shows that its work is separately identifiable, and the source queue history remains correct. This deeper optimization is separately gated and optional.
4. Test exit rejoin at image-idle, mid-transition on the *other* display, and source refresh/invalidation. Ensure the visualizer never sees a stale wallpaper reflection when expanded; if a mode consumes wallpaper, document whether it retains the pre-cover snapshot or the current global source intentionally.
5. If true suppression cannot be proved without violating batch semantics, **do not weaken the image transaction contract**. Permit a narrowly documented per-display low-cost presentation fallback (including Crossfade only as last resort) and keep one explicitly unresolved performance item. Crossfade is not evidence of dormancy and must not change other displays' transitions.

**Release gate:** no screenshot-only proof. Require batch-state traces of expected/published/covered display identities, image queue/history before/after, active transition counts, foreground/background processing submissions, first-frame identity on resume and zero pending work after collapse. Tests must fail if an expected display has no terminal receipt.

## F. Widget fading and service dormancy: two different contracts

- [ ] Add a **temporary display-local visual policy** separate from family activation and `widgets.<id>.enabled`. Suppressing a widget must not persist `enabled=False`, remove a capability, or alter a global saved layout slot.
- [ ] Fade admitted ordinary widget roots through the existing retained host and family `fadeOpacity`/startup gate *without hijacking family-owned fades*. The startup reveal is independent; a new takeover scalar must compose cleanly with authored family fade rather than overwrite it. Avoid treating visual opacity `0` as a lifetime signal.
- [ ] Preserve Media **state** even when its card paint is suppressed. If no local Media presentation is needed for source truth but another display's already-admitted model supplies it, bind the HUD to that model. Otherwise establish a narrowly justified neutral consumer lease rather than leaving an invisible full Media card or creating a duplicate controller. Preserve exact `MediaRuntimeService` generation/lease accounting.
- [ ] For nonessential display-local widgets, after fade completion use `OrdinaryFamilyPresentationBinder`/`WidgetRuntimeManager` service ownership. Existing binder `retire_widget` has no matching mid-generation targeted `admit_widget`: implement a symmetric *single-family, idempotent, exact-generation re-admission* if demanded by this feature. This is a **justified** new contract, not a general rerender system. Rebuild the widget exactly once from current canonical config, not stale pre-hide QObjects, and activate only after construction as the existing two-phase binding rule requires.
- [ ] If a widget service owns a generation-shared backend (Gmail, Media, Feeds, Steam), retiring the *display lease* must not stop the backend while other displays use it. On re-entry the new lease gets the newest published snapshot and does not trigger a burst of missed polling/requests.
- [ ] Preserve OSD rendering and endpoint consumer count; when it overlaps HUD, the HUD moves/fades/limits its footprint, not the OSD. OSD is a named exception to widget hiding and must remain in its existing foreground host.
- [ ] Other display retains current widgets and geometry, hover, input, Media actions, default fades and update cadence.
- [ ] Prevent stale callbacks into retired QML controls on re-admission, including `shiboken6.isValid` and generation fences on queued/coalesced actions. Repeated expansion cycles must not grow QObject, subscription or worker counts.
- [ ] Decide once what happens to a widget that is enabled/disabled by Settings while covered. On collapse, reconcile current committed intent, not a frozen widget list. No forced resurrection of a user-disabled family.

## G. Now-playing HUD: single data source and deterministic event windows

- [ ] HUD is presentation-only. Authoritative fields derive from **existing Media model** (`MediaPresentationModel`/`MediaRuntimeSnapshot`) and the canonical volume/OSD model as applicable. Reuse semantic theme colours, font/stroke/shadow rules and artwork image provider; no second GSMTC query, network request, decoder or artwork cache.
- [ ] Construct HUD lazily only for an expanded owning display (not all scenes, not imported backends); use one small retained QML item in the scene's current visualizer/foreground presentation hierarchy. No extra top-level window, render node or QObject model with duplicate business data.
- [ ] Trigger events: track identity changed, playback state changed, optional volume changed, and pointer moved/hovered within the expanded visualizer. Pointer movement is *event*-driven with bounded coalescing; no permanent hover poll or frame-request loop.
- [ ] Apply one semantic priority/visibility lease: OSD (higher priority) > collapse/camera/preset controls > HUD > decorative content. HUD must shrink/move or defer when its safe rect is not available. Different DPRs, portrait displays and very small geometry are measured.
- [ ] Define one-shot fade lifecycle from event time (Qt finite animation or already-owned one-shot visibility deadline), with latest-event-wins and a hard maximum display interval. No repeating QTimer; do not introduce new per-frame update to drive opacity.
- [ ] Volume bar semantics must match the actual volume type (app-specific vs system); do not show a fabricated per-app level if `supports_app_volume=False`. Reading a system endpoint for OSD does not imply app-volume control.
- [ ] Track title/artist/cover changes are identity-fenced and published atomically; stale old album art must not flash under the next track. Missing cover falls back to theme geometry.
- [ ] HUD does not steal focus, suppress visualizer drag/camera wheel or intercept double/middle clicks beyond its explicitly visible supported controls.
- [ ] Honour user-selected settings to suppress HUD, reduce motion/animations and font readability where applicable; no duplicate theme colour hardcodes in the policy layer.

## H. Milestones with live checklists and explicit completion gates

Entry and exit gates per milestone are bound in §0.2; the prerequisite phase P-A (AC-02) precedes M2.

**Milestone 0 | Pre-admission and baseline capture**

- [ ] Waveform Ribbon completed/accepted by operator; do not preempt current Waveform or other current work.
- [ ] Record active repository commit/heads and audit every source and guardrail above; note drift from this plan and deliberate contract amendments, not unreviewed legacy assumptions.
- [ ] Baseline EB idle/music dynamic traces and accepted presets on canonical, wide/tall, extreme screen-sized view, one/two monitors and representative GPU load. Capture CPU/GL/GUI, frame pacing p50/p95/p99, source age, visualizer audio-to-photo freshness, pool/lease counts, and startup/reflection behaviour.
- [ ] Identify all widget families on both real displays and their shared-owner leases; log baseline consumer counts without creating a polling diagnostic.
- [ ] **Gate 0:** written baseline receipts, unresolved risks labelled, no visualizer code changed yet.

**Milestone 1 | Capability + persistence + pure takeover state machine**

- [ ] Add registry capability default false; EB true only. Disabled/unregistered mode cannot force expansion.
- [ ] Add canonical default/model/normalization for persisted intent. Test preset and Custom replacement transaction preserving field/other widget subtree; reset/import/export/migration/MC profile isolation.
- [ ] Implement pure event/action reducer for enter/exit/mode/monitor/Settings/Edit/topology with generation and idempotency rules; no GL or extra resource owners.
- [ ] **Gate 1:** all pure tests pass including stale/duplicate input and immediate accept/reject permutations; no modules eagerly imported from dormant modes.

**Milestone 2 | Full display viewport with intact 3D rendering**

- [ ] Implement single resolved display-space presentation variant through scene controller/retained node. No new render path, no preset changes, no whole-widget final-pixel stretching.
- [ ] Add contextually admitted vector ↗/↙ glyph with safe hitboxes and event-bound hover fade; preserve existing reset/preset and semantic double/middle clicks.
- [ ] Prove viewport clips and camera on 16:9, 16:10, 21:9, portrait and mixed DPR, with screen/window-bound geometry and safe GL target resize/retirement.
- [ ] **Gate 2:** screenshot/production-host geometry is truly display-wide and reactivity/payload numerical identities remain untouched; ordinary view can round-trip pixel geometry.

**Milestone 3 | Display-local fading, HUD + safe widget suspension**

- [ ] Add composed takeover opacity outside authored fade; no flashing at startup or immediate toggles.
- [ ] Add exception/preservation for Media truth and OSD; implement consumer-accurate targeted retirement/re-admission (if safe), not global disable flags.
- [ ] Add theme-aligned event-driven HUD with no tooltips/hit overlap; test track/play/pause/volume/hover and unavailable app-volume provider.
- [ ] **Gate 3:** no service/backend orphaning, no duplicate worker/endpoint source, UI equal on untouched display, no opacity/binding warnings.

**Milestone 4 | Wallpaper transition policy and GPU savings**

- [ ] Complete E0 diagram. Implement batch-safe covered-display receipt/omission policy; test both screens with staggered, asynchronous transitions and image queue/history.
- [ ] Only after baseline receipt, suppress admitted GPU effect work on covered display; deeper source/decode/prefetch suppression optional and separately proven.
- [ ] **Gate 4:** another display still uses authored transition; covered display has no backlog or stalled batch; collapse re-enters safely. Record true GPU/CPU improvement vs original; no unmeasured 'dormant' claim.

**Milestone 5 | Mode/monitor/Settings/Editor transactional lifecycle**

- [ ] Test capable->capable (synthetic second capable descriptor fixture until another real mode opts in), capable->incapable, failed mode activation, mode-cycle double-click, context-menu mode and preset middle-click.
- [ ] Cross-display transfer at different DPI/size/refresh retains **one** controller, DSP lane, mode, authored state and exact owner retirement; source restored, target expanded.
- [ ] Cold launch expanded, repeat Settings open/close, active CUSTOM draft Save/Cancel, monitor hotplug/unplug/restart and terminal shutdown.
- [ ] **Gate 5:** deterministic event trace and resource-count proofs after multiple cycles; zero stale observer actions or leaking Qt/GL resources.

**Milestone 6 | Performance/fidelity and documented product admission**

- [ ] Run focused suite, native retained-QML tests, production replay captures and EB `tools/visualizer_live_check.py` at representative preset(s)/load, including other-display photo changes and real active music.
- [ ] Compare accepted EB BTF/reattack/settle/stream/drift, bead/particle appearance and GL/CPU frame-age tails to baseline. No new performance knob hiding source/renderer cost.
- [ ] Record closed risks with source and evidence, then update `Spec.md`, `Docs/Contracts.md`, `Docs/Reference/Visualizer_Reference.md`, `Docs/TestSuite.md`, and any focused 3D contract **only for proven new semantics**. Add historical-bug records only for rejected/faulty mechanisms. Avoid restating all source implementations in every doc.
- [ ] **Gate 6:** operator's only mandatory intervention is visual/physical acceptance of actual expanded appearance/controls and any installed build gate they personally choose to run. No agent product/installer build. Mark implementation accepted only after that evidence.

## I. Automated verification matrix (new test filenames are PROPOSED)

Plan test assets under `tests/` / `tools/`, align with `Docs/TestSuite.md` and current harness conventions. Do not create docs/defaults existence assertions or brittle text snapshots in place of functional tests. Never pin mutable visualizer presets. All synthetic config remains test-local. For Qt tests, use the real retained QML item when geometry/click delivery matters; no second QQuickWidget.

| Proposed focused test/harness | What it must prove | Failure is blocking? |
| --- | --- | --- |
| `test_visualizer_expansion_capability.py` | Registry opt-in EB only; disabled/unregistered mode inert; mode change policy and no import of dormant modes | Yes |
| `test_visualizer_expansion_persistence.py` | Normal/MC isolation, defaults, SST import/export/reset, mode-presets and Custom normalization across runtime transaction, no layout-slot corruption | Yes |
| `test_visualizer_expansion_reducer.py` | Ordered state transitions, idempotence, stale generation/activation reject, duplicate glyph, Edit cancel, topology/target failure rollback | Yes |
| `test_visualizer_expansion_geometry.py` | Exact display logical viewport, DPR conversion, aspect/camera and original rect restoration, clip/shell correctness, no unrequested settings writes | Yes |
| `test_visualizer_expansion_qml_native.py` | Real retained glyph hit/tooltip/fade, no action under menu/Edit, double/middle clicks unchanged, no HUD/OSD overlap or binding warnings | Yes |
| `test_visualizer_expansion_widget_leases.py` | Other-display lease survival, targeted retire/re-admit, no Media/OSD loss, deactivated family stays off, no Qt stale callback | Yes |
| `test_visualizer_expansion_transition_batch.py` | Whole batch never wedges; two-screen target change/status receipts, other-display effect, queue/history, no missed backlog, safe resume | **Critical** |
| `test_visualizer_expansion_transfer.py` | Old->new display owner transaction and rollback, mixed DPR/hotplug/absent display, no duplicate controller/pacer | Yes |
| `test_visualizer_expansion_lifecycle.py` | Cold expanded launch, Settings barrier, Edit Save/Cancel, warm replacement, terminal retirement, no resource/subscription growth | Yes |
| `test_visualizer_expansion_hud.py` | Event-only visibility, source identity/artwork, per-app volume vs system OSD, fade retirement, input priority | Yes |
| `tools/visualizer_live_check.py` with EB and real-music replay | No logical/render starvation, no source age/regression, accepted EB feel under game-shaped load | Yes for final acceptance |

**Execution rule:** focus new pure tests first; run only affected existing tests at each milestone; run `tests/run_chunked.py` at milestones, not after every source edit. Run project interpreter from `.venv`, no global installs. If PowerShell commands are supplied, keep each on one line with semicolons and no environment-variable setup. No GitHub Actions, no agent Nuitka/installer builds. Tests proving Qt/GL presentation must exercise real Quick consumers rather than drain bridge snapshots directly.

## J. Rollback, explicit non-goals, acceptance report

**Rollback:** each milestone can disable new capability admission via one canonical metadata gate and leave ordinary runtime unaffected. The gate must not leave orphan persistent `expanded_display_requested` values silently rewriting other settings; inactive intent remains harmless and explicit. Aborting an in-flight expansion restores the last accepted semantic state at a current-generation edge; do not blanket-cancel wallpaper runs or orphan resource generations. Any failed milestone stays unaccepted and cannot be 'fixed' by weakening BTF, switching to software/QWidget fallback, or recreating a second GL window.

**Not in this project:** SMP playback engine, library DB, playlists, new visualizer modes, Vulkan/FSR/DLSS, window pop-out, reworking Settings into live player mode, retuning EB presets/physics or expanding every mode without merit.

**End-of-gate report expected from implementing agent:** changed **complete files**, source/contract rationale, tests run with pass/fail summary (never claim unrun tests), artifact/trace locations, GPU/CPU timings compared to baseline, open issues, and a short **operator-only physical validation** list. Update durable contracts only after accepted implementation. Keep `Current_Plan.md` untouched until the operator explicitly admits the work.

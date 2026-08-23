# Qt Quick Migration — Completed Work Archive Through 2026-08-23

> **Historical record only.** This file is not an execution plan and must not be used as current
> implementation authority. Start with root `Current_Plan.md`; consult this archive only when a
> demonstrated regression reopens completed work or historical rationale/evidence is specifically
> required.

Archived against reviewed checkpoint:

```text
91e2b5471dab6b64a90039c7272eb6d6785b0601
```

This archive exists to keep completed/validated work out of `Current_Plan.md` without losing the useful
technical chronology, test rationale and checkpoint evidence.

---

# Closed Phases A–D

# 5. Phase A — bootstrap/render-node proof

Structurally complete for forward migration.

Settled:

- standalone QQuickWindow path;
- threaded scene graph;
- explicit OpenGL bootstrap;
- inline Python QSGRenderNode OpenGL proof;
- presentation pacer foundation;
- lifecycle/teardown proof.

Deferred A4 compiled smoke remains operator-scheduled after implementation unless explicitly
requested earlier.

Do not reopen Phase A merely to reconfirm the selected architecture.

---

# 6. Phase B — runtime-host decomposition

Structurally complete for forward migration.

Settled properties:

- one `QuickDisplayRuntime` per selected physical display;
- per-runtime window/scene/pacer/input ownership;
- generation-scoped lifecycle including generation 0;
- queued Qt/C++ meta-call teardown for hide/release/close rather than blocking Python
  render-thread inversion;
- hide/wake behavior;
- coordinated one-shot exit;
- deterministic destruction barriers;
- topology replacement harnesses;
- unexpected QWindow screen displacement does not silently adopt a fallback display;
- binding loss preserves original physical identity/pacer target, quiesces presentation/input, and
  emits one-shot topology/binding loss.

Production `DisplayManager -> QuickDisplayRuntime` ownership still waits for Phase H.

---

# 7. Phase C — base image + transitions

**Implementation status: complete. Deterministic test-hardening (Section 7.5, C-T1..C-T8) landed; only operator-scheduled real-GL/eyes-on sign-off remains.**

Read:

- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/Transition_Change_Checklist.md`
- `Docs/TestSuite.md`
- `Docs/Harness_Index.md`

## 7.1 Transition-neutral foundation

Completed:

- immutable/detached presentation image boundary;
- `TransitionRequest` / `TransitionRun` lifecycle;
- monotonic progress sampling;
- generation/run fencing;
- exactly-once completion/cancel;
- shared image texture ownership;
- common GL-state fence;
- lazy static implementation registry;
- GUI/runtime-side parameter/random/default resolution;
- permanent canonical-registry ↔ Quick-registry parity gate.

## 7.2 Canonical renderer inventory

All 12 canonical production transitions have Quick renderers:

- Crossfade
- Slide
- Wipe
- Warp Dissolve
- Block Puzzle Flip
- 3D Block Spins
- Blinds
- Diffuse
- Ripple / Raindrops
- Crumble
- Particle
- Burn

No Quick renderer depends on `GLCompositorWidget`.

Canonical transitions remain catalog-visible as appropriate while application-level deactivation keeps
implementation/shader/resource ownership dormant.

## 7.3 Critical preserved contracts

### Slide

Four cardinal product directions only. Source/destination sampling and pixel ownership derive from
one immutable eased sample in one draw, so missed physical frames may cause a larger positional jump
but never a seam/gap.

### 3D Block Spins

Real thin 36-vertex rectangular-prism slab, depth-tested front/back/sides, black void, four authored
axes/directions, correct destination UV orientation, cubic internal spin, dark sides, moving specular
band, white edge rim, context-local resource teardown. No flat fallback.

### Particle

Canonical shader preserved with Directional/Swirl/Converge, directional/random-placement modes,
trails, swirl settings/order, wobble, texture mapping, 3D shading, gloss/light controls, seed, and
physical-framebuffer resolution semantics.

### Burn

Canonical rich shader preserved: ignition, six directions, four-octave/domain-warped noise, jagged
front, heat distortion, glow, white-hot core, char/crackle/smoulder progression, sparks, smoke, ash,
densities/toggles, per-run seed, run-clock animation time, delayed destination tail.

## 7.4 Existing Phase-C acceptance debt

Real-GL sign-off was driven on real hardware 2026-08-21/22 (MSI G321Q + LG TV, OpenGL threaded,
`--size 480x270`), single- and two-display (`--windows 2`, both physical screens):

- ✅ focused deterministic Phase-C tests green in the capable Windows worktree;
- ✅ all 35 parameterized effect×case smokes green single- and two-display;
- ✅ Blinds Horizontal / Vertical / Diagonal green single- and two-display;
- ✅ mature transitions green two-display: Crossfade, Slide, Wipe, Warp, Block Flip and all six Block
  Spins directions;
- ✅ topology recreation green for Crossfade and Wipe;
- ✅ **full two-display closure sweep: 54/54**.

The two 3D-slab oracles (Block Spins and Block Flip) exposed timing fragility on the 60 Hz display.
Those were corrected as **harness-only robustness changes**: production transition renderers were not
changed, the precise geometry/UV fallbacks remain rejecting flat substitutes, and the shared sparse
5×5 geometry grid remained unchanged for unrelated geometry oracles.

Broad single-process real-GL runs can still show contention flakiness after hundreds of window
creations. Chunk those runs rather than attributing unrelated teardown contention to the active slice.

Remaining acceptance requiring the operator's own environment:

- eyes-on old-vs-Quick authored-effect comparison where still useful;
- mixed 60 Hz/high-refresh continuity and physical cadence only where it answers an unresolved
  question.

Phase D may proceed while those acceptance items remain explicit.

## 7.5 Phase-C test/harness strengthening — explicit test-only debt

**STATUS (2026-08-22): deterministic test-hardening C-T1..C-T8 is landed and the real-GL closure sweep is green 54/54 on two physical displays. Both 3D-slab harness timing defects were subsequently deflaked without production renderer changes. The C-T subsections remain durable rationale, not active unfinished work.**

Landed evidence (focused gate, capable Windows worktree, HEAD after the C-T checkpoints):

```text
python -m pytest tests/test_qtquick_transition_controller.py \
  tests/test_qtquick_transition_parameter_defaults.py \
  tests/test_qtquick_transition_implementations.py \
  tests/test_qtquick_transition_uniform_wiring.py \
  tests/test_qtquick_transition_state_fence.py \
  tests/test_qtquick_phase_c_registry_parity.py \
  tests/test_qtquick_phase_c_effect_smoke.py
```

- C-T1: real-GL midpoint oracles now reject a plain wipe (all six axes) and a uniform crossfade
  fallback; discriminators proven with deterministic synthetic fixtures.
  (`tools/qtquick_phase_c_effect_smoke.py`, `tests/test_qtquick_phase_c_effect_smoke.py`)
- C-T2: selected smoke cases proven to resolve to materially different request parameters
  (Ripple counts, Crumble weighting, Particle direction/mode, Burn smoke/ash). Pixel-level pairwise
  contrast remains the operator real-GL rerun.
- C-T3: request-parameter → shader-uniform wiring matrix (`tests/test_qtquick_transition_uniform_wiring.py`).
- C-T4: common GL-state fence + exception restoration (`tests/test_qtquick_transition_state_fence.py`).
- C-T5: Blinds + Ripple sparse canonical-default coverage (`tests/test_qtquick_transition_parameter_defaults.py`).
- C-T6: controller false-pass fixed (`tests/test_qtquick_transition_controller.py`).
- C-T8: `_ALL_QUICK_TRANSITION_IDS` derived from the catalog (`tests/test_qtquick_transition_implementations.py`).
- C-T7/C-T9: honoured (Crumble mosaic tested only as the optional uniform-upload contract; real-GL
  harnesses kept real, fakes used only for wiring/state-contract level evidence).

**If the operator says "continue from Phase C tests", Phase-C implementation/test hardening and the two-display real-GL closure sweep are complete; proceed to Phase D. Only operator-owned eyes-on/high-refresh acceptance remains.**

The Phase-C test audit found real coverage holes. Improve the tests/harnesses first. Do **not**
redesign transition implementation merely to satisfy the audit. If a stronger test exposes a real
implementation defect, record the failure, fix the smallest demonstrated implementation defect in a
separate bounded checkpoint, rerun the strengthened gate, then continue.

### C-T1 — make real-GL midpoint oracles effect-discriminative

The current Diffuse/Ripple/Crumble/Particle/Burn real-GL midpoint checks are too permissive. A generic
spatial reveal can satisfy several because a simple mix of source/destination/effect-colored pixels is
enough.

Strengthen the existing real-GL harnesses so each effect is meaningfully distinguishable from a plain
wipe/crossfade-style fallback.

Do not replace the real-GL harnesses with mocks. Keep the real renderer/window/OpenGL path and add
better discriminators.

Useful principles:

- use fixed synthetic source/destination patterns and deterministic seeds;
- compare effect-specific spatial signatures, not merely "both images appear";
- use paired/contrast cases from the same effect at the same progress where a parameter should change
  the result;
- prefer robust regional/statistical/geometry assertions over exact screenshot hashes.

### C-T2 — prove selected smoke parameters materially change behavior

Several smoke cases currently exercise settings without proving they alter rendering.

Add pairwise/contrast evidence for at least:

- Ripple `count1` vs `count3` vs `count8`;
- Crumble weighting modes;
- Particle directions and modes;
- Burn smoke/ash toggle cases.

The selected case must measurably change the intended output under fixed seed/input/progress.

Examples of suitable discriminators:

- Ripple: changed ring/front frequency or radial crossing structure;
- Crumble: changed deterministic piece/old-vs-new distribution for weighting modes;
- Particle: changed displacement centroid/orientation/radial-vs-angular behavior for
  direction/mode choices;
- Burn: smoke/ash toggles change their intended regions under the same seed/time without being the
  only evidence for the core burn front.

### C-T3 — direct request-parameter → shader-uniform wiring tests

Add direct renderer-boundary tests proving resolved immutable request parameters reach the intended
shader uniforms for:

- Diffuse;
- Ripple;
- Crumble;
- Particle;
- Burn.

A recording/fake GL uniform sink is appropriate for this **wiring** test, because the existing real-GL
harness remains separately required for actual rendering.

Particle must cover every authored control:

- mode;
- direction;
- radius;
- overlap;
- trails;
- swirl strength;
- swirl turns;
- swirl order;
- 3D shading;
- texture mapping;
- wobble;
- gloss;
- light direction;
- seed;
- physical framebuffer resolution.

Burn must cover all authored effect uniforms plus `u_time` derived from the immutable run clock.

Do not let renderer defaults hide missing request fields.

### C-T4 — direct common GL-state fence regression

Add a focused regression test that starts from deliberately non-default GL state, allows a transition
renderer to mutate it, and proves the host restores the previous values.

Cover at least:

- viewport;
- scissor state where the current fence promises it;
- current program;
- VAO;
- array buffer;
- active texture;
- texture units 0 and 1 bindings;
- blend;
- cull;
- depth enable;
- depth write mask;
- depth function;
- depth clear value;
- stencil.

Repeat the restoration assertion when `renderer.render()` raises. Exception cleanup is part of the
state-fence contract.

### C-T5 — complete sparse canonical-default coverage

Existing sparse/default tests already cover Diffuse/Crumble/Particle/Burn.

Add Blinds and Ripple so absent Settings values resolve from canonical defaults rather than renderer
magic numbers.

### C-T6 — remove the false-pass controller test shape

Fix:

```text
tests/test_qtquick_transition_controller.py
test_runs_require_explicit_interruption_and_are_generation_fenced
```

`cancel_current(...)` and the generation-mismatched `start(...)` must not sit in the same
`pytest.raises` block.

Only:

```text
start(_request(generation=8))
```

is the operation expected to raise.

The cancellation call must execute and be asserted independently so a premature exception cannot make
the generation-fence check falsely pass.

### C-T7 — Crumble `mosaic_mode` testing must match the authored shader

Do not invent a fake visual mosaic test.

The canonical fragment shader declares `u_mosaic_mode` but currently does not consume it.

Test only the renderer's optional uniform-upload contract when that uniform exists. Do not claim
current authored visual mosaic behavior unless the shader is deliberately changed in a separate
product decision.

### C-T8 — remove duplicate hard-coded transition inventory

`_ALL_QUICK_TRANSITION_IDS` duplicates canonical transition inventory in one test.

Registry parity is already the independent inventory gate. Remove/derive the duplicate where practical
so future canonical additions/removals do not require updating two supposedly authoritative lists.

### C-T9 — preserve environment fidelity

Do not weaken Windows/Qt/OpenGL/physical-display tests because another environment cannot run them.

Keep real-GL harnesses real. Use mocks/fakes only for isolated wiring/state-contract tests where they
are the correct level of evidence.

### C-T10 — suggested checkpoint order

Prefer bounded test-hardening checkpoints:

```text
controller false-pass + sparse defaults + duplicate inventory cleanup
-> request-to-uniform wiring matrix
-> GL-state fence + exception restoration
-> real-GL discriminator/parameter-sensitivity strengthening
-> rerun focused Phase-C gates and record exact evidence
```

If any strengthened test exposes a real renderer defect:

```text
record failing evidence
-> smallest implementation fix in separate commit
-> focused test + real-GL rerun
-> push
-> audit if high-risk
```

Do not broaden the repair into transition redesign.

---

# 8. Phase D — visualizer — COMPLETE

D1–D9 landed and Phase-D documentation closure is done (see Section 15). All five modes run on the Quick
visualizer boundary; only operator-scheduled physical cadence/eyes-on acceptance debt remains. The
decomposition below is retained as the durable contract; do not reopen it without contradictory
evidence.

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`

Phase D must preserve the current five visualizers **and** avoid baking the historical painted-card
assumption into the new architecture.

The final visualizer presentation is explicitly split into:

```text
mode/render state
        +
presentation shell policy
        +
content clip policy
        +
presentation geometry / viewport
```

All current five modes use the carded policy. No current visual result is intentionally changed by
this architectural split.

## D1 — presentation-neutral runtime/controller + mode presentation policy

Separate the non-pixel visualizer owner from QWidget presentation without rewriting provider/business
logic.

Retain settings/mode/preset activation, playback state, BeatEngine/source,
`VisualizerLogicalRuntime`, and latest logical publication.

Do not instantiate a hidden QWidget merely to keep those owners alive.

Extend the cheap canonical visualizer mode descriptor with presentation metadata rather than adding
mode-specific `if/elif` branches to scene owners.

Conceptually:

```text
VisualizerModePresentationPolicy
    shell_policy = CARD | FRAMELESS
    clip_policy  = CARD_INTERIOR | VIEWPORT_RECT
    viewport_resize_capable = bool
```

Current five modes:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode such as the post-migration deformable 3D sphere may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

`FRAMELESS` means no card fill, frame/border, or card shadow. It does **not** mean a second native
window or permission to draw arbitrarily across the display.

Checkpoint/push/audit this split.

## D2 — immutable latest-state render bridge

Publish bounded immutable current visualizer snapshots containing generation/activation identity,
mode/playback identity, logical timestamp, fade/style, mode-specific render data, and the resolved
presentation policy/geometry required for that committed frame.

No render-thread reads from live QWidget/QObject/provider/Settings state or live mode-registry state.

Latest state wins; no FIFO/catch-up replay. Protect short-lived authored edges explicitly.

Checkpoint/push/audit the bridge separately.

## D3 — Quick visualizer scene composition, clip owner, and card/frameless shell

Use one sub-rect custom Quick item/QSGRenderNode inside the display QQuickWindow.

Selected carded scene shape:

```text
VisualizerPresentationRoot  (one fade/visibility owner)
    |
    +-- retained card shadow        [CARD only]
    +-- retained card background    [CARD only]
    +-- visualizer content item
    |       |
    |       +-- QSGRenderNode / direct OpenGL
    |               |
    |               +-- one local SDF/stencil clip host
    +-- retained card frame/border  [CARD only, above content]
```

For `FRAMELESS`, omit the card shadow/background/frame while retaining the same presentation root,
content item, lifecycle, fade authority and display-scene ownership.

### D3.1 — clipping policy

The old architecture needed a rounded-card stencil because custom GL content had to remain above the
card fill and below the visible border without bleeding through rounded corners.

That **visual contract remains necessary for carded modes**. The old hand-written stencil mechanism
does not automatically remain the best owner.

The exact pinned PySide 6.9.1 proof is complete. The scene-graph clip-node handoff did not provide
usable accumulated clip state to the Python render node: rounded cases exposed stencil state whose
framebuffer contents did not match, while rectangular cases could expose an invalid sentinel scissor.
Do not reopen or retain that failed path.

The selected single Quick implementation is one render-node-local SDF/stencil clip host inside the
same `QQuickWindow`/`QSGRenderNode` architecture:

- `CARD_INTERIOR` uses rounded geometry matching the actual inner edge of retained Quick card chrome;
- `VIEWPORT_RECT` uses the same host with zero corner radius;
- shell, clip and custom GL derive from one immutable canonical geometry record and render-target
  viewport;
- the host nests above any incoming `RenderState` scissor/stencil value without clearing Qt's clip
  contents;
- the temporary stencil contents and every touched direct-GL state are restored before returning to
  Qt;
- there is no second selectable scene-graph clip implementation.

Never solve clipping by shrinking the visualizer render rect or scaling the authored content smaller.
Historical R-21 proved that changes mode geometry/amplitude/bar sizing rather than clipping pixels.

### D3.2 — Quick border semantics

Do not cargo-cult the old mask formula.

The historical mask compensated for a centred QPainter border (`border_width / 2`) plus painted-card
shadow tuning. Qt Quick `Rectangle` borders are rendered **inside** the rectangle bounds.

The new card-interior clip must therefore be derived from the actual retained Quick chrome contract:

```text
outer card shape
        ↓
inside border width
        ↓
inner content path / inner corner radius
```

Any additional inset must be an explicit authored Quick card/style value, not a copied magic
`1px + border/2` rule from the QWidget/QPainter era.

## D4 — canonical geometry: one baseline aspect, uniform scale, separate viewport extent

Create one committed presentation-neutral geometry record capable of expressing:

```text
outer_rect
content_rect
dpr
baseline_viewport_size
baseline_aspect_ratio
uniform_visual_scale
viewport_extent
current_aspect_ratio
shell_policy
clip_policy
```

### D4.1 — retire the legacy per-mode card-height/growth system from Quick

The old runtime carries per-mode presentation controls such as:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They change preferred **outer card height** while width remains media-relative. CUSTOM already bypasses
that preferred-height path once committed custom geometry owns the visualizer.

These are legacy presentation customization and are **not part of the Qt Quick visualizer contract**.
Do not port them into the Quick controller, immutable render snapshot, mode descriptor or retained
card geometry.

For the Quick-era normal/default layout:

- all current visualizer modes share one canonical baseline viewport aspect ratio;
- normal card width/placement may still follow the intended common layout owner, but height derives
  from that one baseline aspect rather than a mode-specific growth multiplier;
- switching Spectrum ↔ Oscilloscope ↔ Sine ↔ Bubble ↔ DevCurve does not resize the viewport merely
  because the mode changed;
- built-in presets may tune the mode's visual behavior but do not own viewport/card height;
- screen-bound clamping preserves the baseline aspect by uniform scale/downsize rather than chopping
  one axis independently.

Do **not** invent a new numerical aspect ratio from an arbitrary old mode-growth value. D3/D4 should
extract/freeze one explicit canonical ratio from the intended healthy CUSTOM/default visualizer
baseline and give it one named authority. Once chosen, every current mode uses that authority.

The destination should therefore behave like the clean part of current CUSTOM: legacy growth values
are irrelevant to visualizer shape.

The old settings/UI/preset keys may remain temporarily while the old presenter still exists, but the
Quick implementation ignores them. H0 resets them away and Phase I/J0 remove their remaining current
schema/UI/preset/default/tooling authority after caller proof.

### D4.2 — uniform scale preserves the baseline aspect

`uniform_visual_scale` is the ordinary whole-visualizer size control.

It scales shell + viewport + authored content coherently and **preserves the canonical baseline aspect
ratio**.

This is the semantic used by:

- existing/custom scroll-wheel resize;
- corner-handle resize;
- ordinary reset-to-size behavior.

It is not an X/Y stretch.

### D4.3 — viewport extent is a separate future operation

`viewport_extent` changes how much visualizer world/layout is available at the current visual scale.
It may intentionally produce a wide/tall aspect that differs from the baseline aspect.

That deviation is allowed **only** through the explicit viewport-extent operation planned for Phase G,
not through mode presets, legacy growth controls or ordinary corner/scroll resize.

Do not bake these assumptions into the five renderer ports:

- mode-specific preferred heights;
- one fixed historical card size hidden inside a renderer;
- non-uniform final-pixel stretching;
- card existence as a precondition for drawing.

Where logical simulation needs spatial bounds (Bubble in particular), viewport changes enter through a
presentation-neutral viewport-metrics update owned outside the render thread. That update is
configuration, not another clock.

## D5 — prove baseline aspect independence and future viewport compatibility

During the five mode ports, exercise at least:

```text
canonical baseline aspect at scale 1.0
canonical baseline aspect at another uniform scale
wide viewport extent at the same visual scale
tall viewport extent at the same visual scale
```

The first two are migration requirements. Wide/tall cases are architectural compatibility probes for
the later Phase-G QoL; Phase D does not ship the edit handles.

Expected semantics:

- Spectrum: redistribute bars/layout across available width; vertical limit follows content height;
- Bubble: spatial bounds/aspect change without anisotropically stretching circles, radii, velocities
  or trajectories;
- Oscilloscope/Sine/DevCurve: recompute available domain/placement while preserving stroke thickness
  and authored scale;
- future 3D sphere: aspect-correct camera/projection so the sphere remains round.

If one current mode cannot safely support free viewport extent without compromising authored behavior,
keep the D4 geometry seam and mark that mode `viewport_resize_capable = false` for the later QoL. Do
not block migration and do not fake support by stretching pixels.

## D6 — sole authored logical clock

`VisualizerLogicalRuntime` remains the sole mode-general authored logical clock.

Non-negotiable:

- every authored logical step survives;
- latest-state semantics;
- no FIFO/catch-up;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- render cadence never becomes simulation cadence;
- nonblocking media/GSMTC interaction;
- generation/stale fencing;
- clean worker join.

## D7 — five mode ports

Preserve all current authored **mode behavior** for the five modes below. The D4-retired per-mode card-height/growth presentation controls are explicitly excluded from parity:

1. Spectrum — bars/peaks/ghosting, paused idle visibility, source freshness;
2. Oscilloscope — waveform/line persistence/idle behavior;
3. Sine — authored idle/layers/reactivity, no separate timer;
4. Bubble — dedicated high-risk checkpoint with BTF, continuous positional evolution, collisions,
   trails/tails, ghosts/pop/transients/protected edges, authored logical Hz;
5. DevCurve — active layers/order/alpha/offsets/outline/ghosting/tuning.

All five current modes remain `CARD + CARD_INTERIOR`.

Do not retune modes to hide presentation problems.

The observation that unrelated widgets can materially change measured Bubble-era GPU load supports
retained-scene efficiency and true feature dormancy. It does not implicate Bubble collision logic by
itself.

## D8 — Pause/Play and lifecycle

Preserve warm-source/expected-state behavior without recreating the window/item or inventing a second
playback authority.

One presentation-root fade authority covers both carded and frameless modes.

Retirement must close publication, stop/join the logical runtime, invalidate activation/generation,
remove snapshot admission, release GL resources on the render owner, and destroy roots cleanly.

A background owner that prevents process/test shutdown is a defect.

## D9 — checkpoint cadence

Prefer pushed/audited checkpoints for:

1. runtime/controller split + presentation policy;
2. immutable bridge;
3. item/node + clip/shell/geometry foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF;
8. DevCurve;
9. all-five-mode lifecycle/source/pause + aspect-policy closure;
10. Phase-D documentation closure.

## D exit

All five modes use the Quick visualizer boundary with the authored logical runtime intact, immutable
latest-state publication, clean lifecycle/resources, and no old compositor/QWidget presentation
dependency inside the new renderer.

The renderer architecture must no longer assume every possible visualizer mode requires a card, and
its geometry contract must preserve a clean later seam for viewport-extent resizing.

Phase D does **not** need to ship the Phase-G freeform viewport-resize UI to exit.

After implementation exit, rewrite visualizer/preset authoring guidance against the landed Quick
contract. Explicit physical/eyes-on items may remain scheduled acceptance debt when they require the
operator's actual display/GPU environment.

---

---

# Completed Phase-E foundation before the current active queue

Landed E foundation slices (additive/inert at all-on defaults; no default runtime behaviour change):

- **presentation-neutral widget family catalog** — `WIDGET_FAMILY_DESCRIPTORS` in
  `core/settings/widget_family_catalog.py` is the single source of truth mapping stable `family_id` to
  canonical member runtime widget ids. Family-level environment availability is neutral there;
  `rendering/widget_descriptors.py` re-exports the catalog and retains member-level runtime
  availability/legacy descriptor details such as `get_active_member_widget_ids()` — it is not the
  membership source. (Visualizers was later added as a capability family requiring Media; see the E2
  second audit-correction notes below.) Pinned by `tests/test_widget_family_catalog.py`.
- **canonical capability-activation settings schema** — `widgets.family_activation.<family_id>` and
  `transitions.activation.<setting_name>` in canonical defaults (all `True`, so behaviour is unchanged
  until H0), plus `core/settings/capability_activation.py` presentation-neutral read/write/query and
  normalization helpers (`is_widget_family_activated` / `is_transition_activated` /
  `get_effective_random_pool` = activated ∩ pool-member / `is_random_mode_effective` /
  `resolve_manual_transition_selection` / `get_default_activated_transition` /
  `normalize_transition_capability_state`). Canonical normalization explicitly repairs all-false
  activation by persisting Crossfade reactivation and disables Random when its effective pool is empty
  while preserving saved pool preferences. Regenerated `defaults_snapshot.json` and both SST doc
  artifacts. Pinned by `tests/test_capability_activation.py`.
- **transition activation runtime foundation (admission fencing closed)** — engine Random preparation,
  C-key cycling, manual selection and factory-side Random candidate generation filter activation in
  their normal paths, and `normalize_transition_capability_state()` is the one canonical authority
  (consumed by engine prep, factory admission, and C-key). The final-admission foundation corrections
  are now landed and tested:
  - a stale/pre-resolved `transitions.random_choice` is revalidated at final factory admission
    (`TransitionFactory._is_admissible_random_choice`) and rejected if it became deactivated or
    hardware-invalid;
  - the engine, factory (`_pick_random_transition`), and C-key (`_resolve_cycle_fallback`)
    empty-candidate paths no longer run a literal deactivated Crossfade — they pick a deterministic
    activated hw-available transition, or perform the explicit canonical recovery repair
    (`ensure_recovery_transition_activated`, persisted) and admit the now-activated recovery normally;
  - zero-activated and empty-effective-Random-pool states are repaired by the one normalization
    authority (Crossfade reactivation / Random-off + deterministic manual + preserved pool prefs).
  Pinned by `tests/test_transition_activation_admission.py` (factory stale/hw-invalid/manual/never-run-
  deactivated-Crossfade; engine empty-pool + zero-activated repair; C-key never selects deactivated
  Crossfade) and `tests/test_capability_activation.py` (normalization / fallback / recovery units).
  **E2.6 is complete** (see the E2 audit-correction notes below): `random_always` is the single live
  Random authority; the factory and engine no longer treat legacy `type="Random"` as a live trigger.
- **presentation-neutral capability authority (import boundary closed)** — the family catalog was
  extracted to `core/settings/widget_family_catalog.py`; `core/settings/capability_activation.py` now
  imports only that neutral catalog and the (neutral) transition registry. Importing the activation
  authority no longer transitively pulls `PySide6.QtWidgets`, `rendering/widget_descriptors.py`,
  WidgetsTab/settings builders, widget implementations/providers, or Quick renderers. Pinned by
  `tests/test_capability_activation_neutrality.py` (subprocess import probe).
- **widget-family activation runtime consequence (creation-admission dormancy only)** —
  `_create_factory_widgets` skips a deactivated family before per-instance `enabled` handling and
  expected-overlay accounting, so a deactivated family creates no runtime widget at that seam. This
  proves **creation-admission dormancy only**; broader provider/model/service/timer/process/Quick-
  resource dormancy and last-consumer shared-service lifetime remain the **E1 `WidgetRuntimeManager`
  ownership responsibility**. Inert by default. Pinned by `tests/test_widget_manager_refresh.py`.

The activation foundation (neutral catalog + schema + canonical normalization + closed runtime admission
fencing) is landed and inert-by-default. E2 supplies the operator-facing toggle; its audit-correction
work (lazy transition pages, mutation-boundary normalization, E2.6, context-menu activation, responsive
layout) has landed and E2 remains at its audit gate.

---

# E2 implementation/correction chronology through `91e2b547`

- **E2** — Widgets and Transitions `SETUP` subtab UI + lazy navigation consuming the activation schema.
  **Operator decision (2026-08-22): rebuild the nav live** — deactivating a capability while Settings is
  open immediately removes its pill and reactivation re-adds it, matching doc 07 §5.3 literally (not a
  deferred grey-out); default landing is the SETUP page; family rows use theme-matched tooltips.
  - **Widgets SETUP — LANDED.** New always-present first `setup` section descriptor + `_build_setup_ui`
    in `ui/tabs/widgets_tab.py`: one circle-checkbox activation row per available family (from the
    neutral catalog) with description tooltips, `Enable All` / `Disable All` (activation only, never
    per-instance `enabled`), live pill show/hide on toggle, fall-back-to-SETUP when the current family is
    deactivated, activation persisted under `widgets.family_activation.*` through the normal save path
    (SETUP is bootstrap-built so it never depends on lazy hydration and cannot corrupt hidden family
    config). Pinned by `tests/test_widgets_tab_setup.py`; lazy-build index tests updated to stable ids.
  - **Transitions SETUP — LANDED.** Pill/subtab nav on the Transitions tab (`ui/tabs/transitions_tab.py`):
    a first `Setup` pill (default landing) + one pill per activated transition; the old visible dropdown
    is retained only as a passive compatibility mirror (not a selection authority) and the old
    per-transition "Include in Switch/Random
    Pool" checkbox is removed. SETUP page owns transition activation rows + `Enable All`/`Disable All`,
    `Use Random Transitions` (the single `random_always` authority), and a Random Pool list (only
    activated transitions shown; edits `transitions.pool`). Deactivating a transition hides its pill and
    pool row live and falls back to SETUP if it was the edited one; activation persists to
    `transitions.activation.*`; `_save_settings` now also writes `activation` + `random_always` and
    preserves engine-managed `random_choice`/`last_random_choice`. Pinned by
    `tests/test_transitions_tab_setup.py`.
  - **E2.6 `type="Random"` normalization — LANDED.** `normalize_transition_capability_state` now also
    converts a legacy manual `type="Random"` into `random_always=True` + a concrete activated manual
    type (invariants compose with the zero-activated and empty-effective-pool repairs). The Transitions
    tab runs the normalizer on load (persisting any repair). Pinned by `tests/test_capability_activation.py`
    and `tests/test_transitions_tab_setup.py`.

  **E2 audit correction (independent audit of `ae9b95b1` found substantive gaps; corrected — E2 has NOT
  self-promoted to complete).** The following corrective work landed on top of the earlier E2 slices:
  - **Transitions settings are now genuinely lazy.** `TransitionsTab` builds SETUP eagerly and each
    transition's specific-settings page only when its pill is first selected; a deactivated transition
    page is never built, deactivating a built page retires it, reactivation restores the pill without
    rebuilding, and selecting it later rebuilds + hydrates from preserved settings. The hidden legacy
    `transition_combo` is a passive mirror only — `_current_transition` is the authoritative
    manual/edited selection consumed by save/nav; unbuilt transition detail is preserved (not
    reconstructed) across unrelated saves.
  - **Invalid capability state is normalized at the E2 mutation boundary**, not deferred to a later
    load/runtime seam: Disable All / final deactivation reactivates Crossfade and reflects it live;
    Random-on with an empty effective pool disables Random + persists a deterministic activated manual
    type live; a deactivated current manual type resolves to an activated replacement.
  - **E2.6 completed:** `random_always` is the single live Random authority. `type="Random"` is migration
    input only (normalized once); the factory `_get_random_mode` and engine
    `_prepare_random_transition_if_needed` no longer treat `type="Random"` as a live trigger.
  - **Random state parity + activation-aware context menu:** the screensaver context menu rebuilds its
    transition submenu from current activation on show (only activated transitions; Random disabled when
    the effective pool is empty), fails admission on stale deactivated selections, normalizes before
    persist, and shares the single `transitions.random_always` state with Transitions SETUP; it never
    writes `type="Random"`.
  - **Responsive layout:** a shared `ui/flow_layout.py` (`FlowContainer`/`FlowLayout`) drives wrapping
    pill navigation, responsive module grids (Widget Modules, Transition Modules, Random Pool — ≥2
    columns at normal width, more when wider), and wrapping Enable/Disable All rows in BOTH tabs; Widget
    Modules now uses the styled `QGroupBox` + circle-checkbox grammar. Frames stay horizontally contained
    with no horizontal scrollbar.

  Pinned by `tests/test_transitions_tab_setup.py`, `tests/test_capability_activation.py`,
  `tests/test_context_menu_activation.py`, `tests/test_flow_layout.py`, `tests/test_widgets_tab_setup.py`,
  and the transition admission suite.

  **E2 second audit correction (independent audit of `ad2b0649` found five further substantive gaps;
  corrected — E2 still NOT self-promoted).** Landed on top of the above:
  - **Visualizers is now an application-level capability** (neutral catalog family `visualizers`, member
    `spotify_visualizer`, `settings_section_id="visualizers"`) with a neutral dependency
    `required_family_ids=("media",)`. Canonical default `widgets.family_activation.visualizers=True`;
    snapshot + SST regenerated. Runtime/render ownership stays the Phase-D subsystem (not Phase-F, not
    `WidgetRuntimeManager`).
  - **Media→Visualizers dependency** enforced by the one neutral authority
    `normalize_widget_capability_state` (`media=False` forces `visualizers=False`, never auto-reactivates
    Media/Visualizers). Widgets SETUP shows a Visualizers row that is disabled + "Requires Media" while
    Media is off, with the repair reflected live.
  - **Explicit visualizer runtime admission**: local `_setup_spotify_visualizer` and remote
    `_reconcile_remote_custom_visualizer` fence on `is_widget_family_effective(config, "visualizers")`
    (activated + Media activated), so a stale/reused Media object cannot bypass the capability gate.
  - **Context-menu visualizer admission**: the Change Visualizer submenu is hidden when Visualizers/Media
    is deactivated (refreshed on show), and a stale mode-selection request is rejected.
  - **Generic Widgets page retirement**: deactivating any family retires its built Settings section
    (container destroyed, built/hydrated ownership + control attrs cleared) so it is genuinely
    rebuildable; persisted per-family config is preserved; SETUP is never retired.
  - **Live Random link**: `TransitionsTab` subscribes to `SettingsManager.settings_changed` and reflects
    external `transitions` mutations (context-menu Random / concrete selection) into its live controls
    with a write-reentrancy guard, so it can no longer resurrect a stale `random_always`/`type`.
  - **Random can no longer escape the saved pool**: the engine random prep and factory
    `_pick_random_transition` FAIL CLOSED when `activated ∩ saved pool ∩ hardware` is empty (no
    broadening, no out-of-pool substitution, saved pool untouched); the context-menu Random availability
    uses the same bounded rule.
  - **Transitions programmatic-nav admission**: `_on_nav_selected` redirects a deactivated transition key
    to SETUP before any selection/mirror/build/save.

  Pinned by `tests/test_widget_family_catalog.py`, `tests/test_capability_activation.py`,
  `tests/test_widgets_tab_setup.py`, `tests/test_visualizer_capability_admission.py`,
  `tests/test_transitions_tab_setup.py`, `tests/test_transition_activation_admission.py`,
  `tests/test_transition_distribution.py`, and `tests/test_context_menu_activation.py`.

  **E2 third audit correction (independent audit of `4ac884f8` found three further contract gaps;
  corrected — E2 still NOT self-promoted).** Landed on top of the above:
  - **Final random admission revalidates the saved pool.** `TransitionFactory._is_admissible_random_choice`
    now verifies ALL current admission dimensions of a pre-resolved `transitions.random_choice` —
    activation, hardware, AND saved-pool membership — sharing one `_is_in_saved_pool` helper with
    `_pick_random_transition`. A choice that was pooled when prepared but later removed from the pool is
    rejected and re-resolved through the current bounded pool (or fails closed); it can no longer escape
    the pool merely because it stays activated + hw-runnable.
  - **Delayed remote CUSTOM visualizer rechecks capability.** The delayed fallback recheck
    (`_run_remote_custom_visualizer_fallback_recheck`) and the single final creation boundary
    (`_create_remote_custom_visualizer_on_target`) now re-read CURRENT canonical capability state via the
    live `SettingsManager` (`_visualizer_capability_admitted_now`, fail-closed) rather than trusting the
    config copied when the callback was scheduled. A Media/Visualizers deactivation during the delay is
    honoured; a stale Media object cannot re-open the gate.
  - **Persisted Media→Visualizers dependency repaired durably at load.** `SettingsManager.__init__` runs
    `_normalize_persisted_widget_capability_state` after defaults merge, driving the one authority
    (`normalize_widget_capability_state`) over the widgets root and persisting via the low-level store (no
    `settings_changed` emission → no signal/save recursion). An invalid persisted/migrated state
    (`media=False` with `visualizers` activated or its key missing) can no longer stay latent so a later
    Media reactivation silently re-enables Visualizers.
  - **Fail-closed capability checks:** the context-menu show path and `on_context_visualizer_selected`
    now force the visualizer submenu unavailable / reject the mode switch when the capability state
    cannot be resolved (an exception no longer becomes permission).
  - **Doc reconciliation:** doc 04 now names `core/settings/widget_family_catalog.py` (not
    `rendering/widget_descriptors.py`) as the membership authority; the catalog's
    `get_family_id_for_widget` docstring records the visualizer's owning family.

  Pinned additionally by `tests/test_remote_visualizer_capability_admission.py`,
  `tests/test_widget_capability_persist_repair.py`, and the extended
  `tests/test_transition_activation_admission.py` (stale out-of-pool random_choice cases).

  **E2 remains at its independent-audit gate — do NOT self-promote to complete.** This third correction
  (`4ac884f8` → the pushed checkpoint below) has not yet been independently audited, so operator eyes-on
  is NOT yet the only remaining item. After this correction is audited green, the remaining acceptance
  item is operator `python main.py --s` eyes-on confirmation of the responsive layout (already reported
  "much better") and the Visualizers dependency UX across widths. Checkpoint/push/audit E2 before Phase F.

## Independent audit note — 2026-08-23

The third E2 correction at `91e2b547` independently closed the three substantive blockers described in
its exit report:

- stale/pre-resolved Random choice now revalidates saved-pool membership at final admission;
- delayed remote CUSTOM Visualizer creation rechecks current Media + Visualizers capability state;
- invalid persisted Media→Visualizers dependency state is durably repaired at SettingsManager load.

One **narrow** remaining E2 issue was then identified in the context-menu caller: missing or malformed
current widgets state can be converted to `{}`, which the global backwards-compatibility rule treats as
active. That issue remains active in root `Current_Plan.md` and is intentionally not marked completed
here.

The same audit also reopened the historical R-26 monitor failover topic as a separate queued lifecycle
slice (E2.7): 30-second human-scale grace, temporary fallback ownership only, event-driven reclaim to
the configured CUSTOM display even much later, and no persistence of fallback monitor/geometry.

# SRPSS | Current Plan

Live work and genuine acceptance debt only. Exact source → `Spec.md` / `Docs/Contracts.md` → focused references.
Completed mechanisms and rejected approaches live in source control and `Docs/Historical_Bugs/`, not this checklist.
Do not duplicate the plan. `[ ]` means work remains; `[~]` means failed or unaccepted, never an implicit pass.
**Reading order: dependency-ordered EB execution queue first**, then full detailed EB failure records and independent work.
The G00–G33 execution gates govern sequencing; numbered implementation notes are evidence, not priorities. The existing 4A/4B/EB-D etc. section IDs stay stable because other project documents cite them;
those IDs are cross-references, not a priority ordering. No visual item is resolved until the operator or a capable local agent visually validates and accepts it.

## 0. Current scope, order and protected baseline

**Current mandate: repair and visually validate evidence-backed Extruded Bubble failures,
with bounded focused investigation and minimal/no subagents.** Preserve per-preset authoring and a real 3D scene observed by the camera: no lens-attached
cohorts or camera-driven spawning. Continue between verified checkpoints. Full diagnostic report: `Docs/Reference/Extruded_Bubble/Investigation.md`; EB images, lab, reports and evidence: `Docs/Reference/Extruded_Bubble/README.md`.
Durable target: `Docs/Reference/Extruded_Bubble/Target.md`. The report owns measurements/failed mechanisms;
§4B below owns the live recovery checklist. Earlier target/history findings remain accessible, not silently accepted.

**Accepted baseline:** original Bubble, Neon Lake, Oscilloscope, Spectrum/Rainbow Ghost, Sphere, source routing,
landed transitions and Foundry launch buttons stay accepted. Dev Curve has no present reproduced defect.
Typed Visualizer Settings and the shared G0/G1/FC/G3 substrate are available. Do not redo completed migrations or
reopen accepted modes as general work. EB's implementation exists. Operator now considers P1 generally good; its idle remains lacking and all specific
remaining fidelity/response defects stay actionable. Renamed `Targets/Originals/*Goal.png` files are current
parity references; they do not authorize preset overwrites or close other gates.

**Order:** use the single G00–G33 dependency queue below: strict lifecycle and evidence first, then
world/camera/lighting geometry, physical population/lifetime, response, material and acceptance.
Lifecycle correctness is a hard gate, not a cosmetic side task.
Do not interpret this as permission to ignore projection/fade confounds while measuring D. All fixes need actual
recorded input → stable identity → production instance/uniform → native pixels, plus operator acceptance.
Release/media, deferred graphics and builds are independent; they neither block investigation nor permit skipping evidence.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and sole Visualizer logical clock/source. No new floor,
capture/DSP, renderer simulation, timers/polling or camera-following replacement populations. Spectrum shaping stays
descriptor-owned. Preserve BTF, accepted timings, authored presets, parallel work and strict retirement barriers.
Use CLI/sidecars, not environment-variable configuration. Smallest meaningful focused falsifier; no full suite,
Nuitka/Build Runner/installer or product build unless requested. Audit dormancy, cost, churn and contradictions.
Checkpoint confirmed documentation or authorized changes narrowly, inspect the actual diff, and treat the provided working tree as the only source authority. Delivery mechanics live with the operator workflow, not this visual acceptance plan.

## Shared camera gestures and control hints

- [ ] **Held-left-drag orbit for bordered 3D visualizers:** after the camera/idle checkpoint, trace the existing
  press/drag/double-click/focus owners and add plain-left orbit inside the visible box only if existing click,
  double-click, child Edit and glyph behavior can be preserved. Reuse camera admission and cursor fade-out/in;
  confine control to the card while held, restore cursor on release/cancel/focus loss. Event-driven only: no
  polling, timers or extra motion owner. Verify cancellation, edges, DPI and interaction conflicts natively.
- [~] **3D framed control hint in progress:** use `images/bothcontrols.png` at the top right with small crisp
  viewport scaling. Fade gently with glyph admission, then out after five seconds even while still hovered.
  Default-on toggle beside Show Glyphs in Widgets → General; reuse shared settings/resource/presentation owners,
  event-triggered animation only. One reused Sol Medium agent implements; review native appearance, one-shot
  dwell/leave/re-enter, disabled state, frame/mode eligibility and existing glyph/input behavior before checkpoint.

## Settings hierarchy connector rails | parallel authorized UI work

- [~] **Hierarchy rails — Awaiting Validation:** shared bucket/Visualizer/Technical builders derive connectors
  from actual visible widget/layout geometry, skipping explanatory/status captions. Review operator theme and
  physical mixed-DPI movement; retain values, reopening/persistence, conditional/lazy alignment and last-child
  termination. Native Steam, Clock, Feeds three-level/scroll and EB Surface/Deep/light-theme captures at150% plus
  root-reviewed29 focused checks pass. No polling, new timers, observers, separate hierarchy or geometry writes.
  Native examples/receipt: `tmp/settings_tree_native/`; contract: `Docs/Architecture/Settings_Theme_Architecture.md`.
- [ ] **Adjacent isolation debt found during native capture:** Steam cache hydration bypasses
  `SettingsManager(storage_base_dir)` for credential metadata and reads the profile AppData path. Investigate the
  canonical storage resolver separately; do not add a silent fallback or weaken the isolated capture boundary.

## UI R41. Small glyph presentation remainder (operator accepts capture / glyph interaction / child Edit)

Operator visually confirmed that the manual `\` capture works and the hover glyph interaction,
slow fades, and child-edit handoff are useful. These completed pieces no longer occupy the
active plan; their source and R38–R40 reference reports remain available, not deleted.

- [~] **Glyph polish candidate:** ordinary hover chrome now follows the actual visible card,
  not an accessory-bearing outer host (Media screenshot), and Close uses a centred
  vector X inside its unchanged 24 px hit target. Native visual verification pending
  on Media, small cards, visualizer and high-DPR displays.
- [~] **Glyph-only tooltip candidate:** short themed text, after >= 1 second per individual
  glyph hover via QML animation (no polling/Timer/Python worker). Pointer-passive and
  interaction-gated. Verify actual dwell/leave/rapid glyph traversal, fade appearance,
  no input interception, Edit retirement and GPU/text-atlas cost. EB Settings tooltip
  wrapping is separate and uses Qt rich text, not the compositor glyph presenter.
- [~] **Native R39 test correction:** detached zero-size QQuickItem did not prove actual
  scene visibility. Attach to QQuickWindow for visibility assertion; do NOT weaken
  actual Lock/hover behavior checks. Native rerun pending.
- [ ] **Transfer/topology glyph parity** remains the one deliberately deferred extension:
  existing multi-display authority must determine eligibility. Hide Controls remains
  exclusively Edit-only. No additional runtime or geometry authority is authorized.

## 4. Graphics | active Extruded Bubble recovery

### 4A. Shared substrate and deferred demand

Use the existing framed-camera capability, SceneTarget attachments, depth-aware transparency, probe, traced-shell,
defocus and HDR facilities. Contracts/cost evidence: `Docs/Reference/Scene3D_Resources.md`. A source defect in EB's
use of them is not permission for a duplicate compositor, camera, resource owner or speculative full optics engine.
Generic G2/S25 shadows, later G4/S18 and G5 consumers, and S19–S27 character/world work are routed through
`Future_Work.md`; no accepted EB shadow receiver exists. **Anything required to reproduce EB's examples/lab scenes
is active EB scope**, including stream-source/emitter architecture, debris/gas/wisps or volume primitives and more
capable camera positioning/centring. Extend the shared substrate where needed, with opt-in ownership and measured
cost. The future-work router must not postpone an EB prerequisite. Trustworthy source timing, world-space geometry and a stable bubble population are prerequisites before judging reactivity.

### 4B. Extruded Bubble | operator-rejected behavior; every acceptance gate remains open

**Acceptance oracle:** start with `logs/visualizer_recordings/anything_mixed2.jsonl`: strong response immediately,
with accepted **2D Bubble as the minimum response-scale reference**. Also use Ragdoll quiet→loud, Heavy and
soft/acoustic recordings. EB remains its own simulation, Settings, frame runtime, renderer and authored art.
Existing source candidates, synthetic tests and compatibility shader links do not count as successful behavior.
Keep D/B/C/A and all original/additional failures in the target/history; no earlier failure is retired by this rewrite.

**Specific 2D→EB breathing oracle (operator 2026-10-22; OPEN, not visually accepted):** ideally EB (3D Bubble)
with **Dynamic Floor OFF** must match or exceed the *visually confirmed music-correlated breathing* of accepted
**2D Bubble with Dynamic Floor ON**, at normal Sensitivity and existing operator-authored settings on the same
recorded musical passages. Compare quiet contraction, onset expansion, meaningful size changes during continuous
playing, held loud with headroom, and smooth release, for representative large and small bubble identities.
Dynamic Floor can adapt to a song's changing dynamics and can **make that song react worse after it kicks in**;
EB must not depend on enabling it, and must not copy those bad adaptive-floor artifacts to meet the reference.
Use independent, explicitly recorded 2D-ON and EB-OFF capture configurations: this is a deliberately asymmetric
quality oracle, not a demand to force both modes onto the same technical floor or duplicate 2D mechanics.
2D-OFF is an optional diagnostic; EB-ON/high Sensitivity remains a negative-control/workaround check, **not**
a passing baseline. Verify from native synchronized video/pixels and music, not code-only traces. Details are
in the G13/G14/G25 acceptance runbook. All existing reactivity failures remain open.

**Idle contract (operator 2026-10-20):** every reactive aspect settles slowly into its collapsed/resting state,
leaving room for musical expansion. No periodic idle size-breathing target. Size, drift/sway, stream, water/ambient,
beads/wakes, rays and emission must all be gentle; nothing remotely fast while idle. No abrupt stop on release.

**Passage roles (latest operator clarification):** large bubbles breathe significantly in softer music, especially
downward. They carry sustained body specifically in sustained/loud passages. Small bubbles and emission/drift/
speed/rays must continue expressing changes inside those loud passages, without a shared bass/transient hold.
Presets and controls may be corrected where needed; prove meaningful controls rather than protect ineffective tuning.

**Additional operator evidence, 2026-10-20 evening (NOT ACCEPTED):** breathing is somewhat better in recent builds,
but small bubbles visibly *jump between size states* instead of continuously interpolating, and large bubbles
stay near maximum size much too often. Light rays show **no perceptible musical reaction at all**. Stream speed
and drift visibly change between stopped and playing, but changing song sections slow → fast → slow inside
continuous playback has no visible effect. Musical response must have fast ramps/attacks and slow decays,
including during sustained music rather than only at play-state edges. Use accepted 2D Bubble's BTF/R-105
and established size/stream followers as proven design references, but do not copy its REJECTED tiny-breath
microfilter. Operator requests approximately **10% more resting motion** for moving bubble/stream/bead/particle
actors and ray shimmer, explicitly **not** water/ocean-surface animation. No resolved items in this note.


### 4B-0. SINGLE ACTIVE EXECUTION QUEUE | architectural dependencies, all OPEN

**This is the reading and work order.** Each G-ID is defined in [the EB visual acceptance runbook](Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md), which provides its input fixture, minimum observable evidence and explicit failure criteria. The original EB-L/F/S/B/C/D/A/P checklists and the dated source-investigation sections **remain below at full detail**; they are evidence/constraint owners for these gates, not authorization to close them. A candidate fix remains `[~]` until native pixels or motion and an explicit operator/local visual-agent acceptance. A test pass is a prerequisite, not acceptance. No preset is protected against operator editing or automatically overwritten.

**Do NOT execute this in numeric chronology of implementation notes.** Stabilize Settings/ownership, get a trustworthy matched recording, establish world/lighting truth and stable physical identities, *then* tune audio response, optical appearance, native UI and performance. Skip a gate only if its dependency is demonstrably already satisfied for the exact reproduction; record the evidence. Do not turn completed unrelated mechanisms into active work. Preserve the accepted 2D Bubble, Neon Lake, unframed Spectrum/Sphere and Qt Quick delivery contracts.

#### P0 | Runtime safety and measurement authority (blocks claims from downstream gates)

- [ ] **G00 strict Settings/lifecycle** (EB-L/S): find the actual retained Python owner edge on failure. **Must see** owners retired and the real Settings transition completes repeatedly at the existing barrier; never extend/bypass the barrier.
  - [~] **Awaiting Validation:** latest MC source runs retain normal updates/all useful CLI diagnostics and pass three Settings request/close/full-restart cycles each. After camera/idle/SCENE changes, idle barriers remain within 8 seconds (`logs/run_matrix/2026-10-22_mc_after_idle_scene_fades/receipt.json`). Explicit play-state stimuli then start real loopback capture four times, with all six Settings barriers completing in 0.70–4.97 seconds and normal CLI exit 0 (`2026-10-22_mc_controlled_active/receipt.json`). Canonical paused Media overrides those brief stimuli; this proves controlled capture/DSP activation plus retirement, not continuous music/preset acceptance or reproduction of the retained-owner failure. Exercise sustained active processing and preset changes locally; inspect exact owner edges on recurrence.
- [ ] **G01 lazy Settings/persistence** (EB-S): exercise every bucket and physical editor with real native Qt. **Must see** single build/hydration, no callback exceptions, values/Custom/presets intact after reopening.
  - [~] Native lazy-bucket/control tests pass on this Windows tree, including unopened-value hydration, cross-bucket conditions, every bucket, Aim, Deep ray source and emission choice. **Awaiting Validation:** repeated actual Settings reopen/Custom/save/reset, partial-build exception cleanup and visual/editor interaction; this is not G00 retirement evidence. Use a fresh workspace `--basetemp` with the no-env fixture if sandbox temp admission fails.
  - [ ] Reconcile the old blanket FOV-in-preset text assertion with the operator's parallel P1 authoring: the current edited JSON includes Camera FOV in its controls, so `test_custom_reset_has_canonical_pose_and_lens_not_an_artwork_override` fails its file-wide ban. Preserve that preset and the parallel goal-image renames; determine intended camera/artwork ownership before changing the file or oracle. This is separate from camera-bound regression checks.
  - [ ] Attribute the earlier Settings `QFont::setPointSize(-1)` and startup `QUnifiedTimer::stopAnimationDriver` warnings if they recur during native bucket/editor coverage. The latest three-reopen idle and controlled-capture MC sessions each have **zero Qt messages** with valid session start/end receipts, so do not report old appended warnings as current failures. Shared combo QSS already uses positive point sizes per `Docs/Architecture/Settings_Theme_Architecture.md`; unopened/editor-specific paths remain unproved. Earlier receipt: `logs/run_matrix/2026-10-22_mc_settings_full_cli_retry/receipt.json`.
- [ ] **G02 256-vs-512 source-to-pixel temporal evidence** (EB-F/D): same recording and visual conditions for 2D/EB, with per-ID radius and logical/presentation timestamps. **Must see** where judder first enters; no smoothing/cadence guess counted as proof.

#### P1 | Physical geometry and camera/lighting source-of-truth

- [ ] **G03 camera world-to-pixel parity** (EB-B): project the same fixed 3D targets into real frames during orbit, flight, zoom, pan, Aim and reset. **Must see** correct eye/world position, perspective/parallax and unchanged FOV under movement.
  - [~] **Finite-world camera boundary candidate — Awaiting Validation:** operator authorizes camera movement bounds when open populated water cannot retain fixed physical populations. One pure resolver admits the actual world eye with 3 units of tank clearance, returning the effective existing offset to runtime, saved-pose hydration and every special 3D editor. Native Qt checks cover all four camera markers, out-of-range positions, Aim in place, keyboard wall/reversal and pre-save FOV/Light Type normalization. Analytic long-held yaw/travel removes hidden overshoot; simultaneous orbit/pan/dolly rebases the same immutable gesture. **Next:** actual compositor drag/flight/preset-reopen and high-refresh cost inspection. Native latest-Custom active cutoff is removed with identical ordinary world records; sparse views/idle readability are not accepted. `Investigation.md` §51.
  - [~] **Measurement gate repaired; native interaction still Awaiting Validation:** the full-silhouette GPU test now keeps its sphere inside the 45-degree sensor and retains the analytic oracle/tolerance. World-probe estimates use the actual physical eye, FOV, pan, offset and Surface/Deep bound, including correct grazing-sphere side-plane margins. Use its retained native P1/P7 views as a baseline, not proof of per-ID loss or interactive camera parity.
- [ ] **G04 visible surface and bubble breach** (EB-B; R37/R42/R43): synchronized XYZ/radius/alpha/cause vs *rendered* ceiling at many camera angles. **Must see** no early invisible exit; controlled near-surface fade; no fake ceiling or world-boundary surprise.
  - [~] **Deep exit authority — Awaiting Validation:** the water-plane outside check is now Surface-only; Deep BEAM/SCENE retain physical world bounds and BEAM's authored End. Verify a stable Deep identity above Y=9 against native pixels, then its real exit/fade, including upward/lateral/oblique tracks. This source repair does not establish the cause of the operator's apparent early Surface disappearance or resolve mode-switch cohort policy (G07/G09).
- [ ] **G05 Light/Ray/Camera source authority** (EB-B/C; R34/R41): move one light or ray node at a time. **Must see** Deep Light visible emitter/glint/shaft origin coincide; Surface light direction and finite shaft path explicitly distinguished.
  - [~] **Surface analytic direction candidate — Awaiting Validation:** ordinary/fused/near glass now sees the same refracted sunlight direction as particles and probe glints, replacing a fixed world-up emitter. Native reflected/transmitted diagnostics cross authored nodes→uniforms→pixels, including a small ordinary shell; frozen P1/P7 comparisons are retained in `Evidence/2026-10-22_surface_light_direction/`. Inspect all-angle moving highlights, ordinary idle readability and the separate Deep positional-light debt. No count, radius, source path, pass or preset change; whole-SCENE coverage is still failed.
  - [~] **Emitter highlight intensity — Awaiting Validation:** existing Light Strength now governs analytic reflected/transmitted lobes and glint-proxy radiance; strength 1 preserves former intensity. Native isolated pre-bloom shell pixels and production HDR probe captures verify 0/0.5/1 scaling over unchanged ambient in Surface/Deep, with identical proxy positions/radii/counts. Review authored P1/P7 highlights, probe/self-reflection and bloom; Deep physical direction, positional attenuation and shaft authority remain open. `Investigation.md` §43–44 records the scope.
  - [~] **Deep analytic source-point candidate — Awaiting Validation:** glass now computes Source direction at each traced interface or matching homogeneous lens exit, including fused tangent surfaces and near/sub-ray paths. Native pixels prove fixed-Source End invariance, Source response and rigid translation/rotation covariance; CPU/GPU optics mirror actual path points, including inside/TIR. Frozen P1 Surface control is byte-identical; P7 highlights change. Review moving close-source/union/near art and shader storage/register cost, then resolve shared finite-emitter attenuation and the shaft field. No claim of full secondary-ray transport. Local producer: `Evidence/2026-10-22_deep_shading_points/`.
- [ ] **G06 all-angle physical rays** (EB-C; Investigation §38): hold lighting constant, look up/down/side near surface. **Must see** genuinely descending shafts through the same physical region; angular fan and look-toward-light gain may NOT hide/reverse a real down-view volume.

**G05/G06 lighting-authority sub-order, 22 October audit (NEW OPEN work, not a second queue):**

- [ ] **G05a audit/repair one physical light authority before adding coverage:** trace Light Type, world Light Source/End, Ray Source/End, Sunlit directional versus Deep positional semantics into water illumination, visible glow, glints, ray origin, attenuation and final HDR/bloom. Existing Deep glow is mainly view-angular despite a real world source; Surface's positional light marker has misleading semantics. Make physical emission and scattering agree without deleting existing art controls. **Must see** shared world geometry and honest UI at fixed light/camera during individual node moves. Evidence/design: [`Lighting_Authority_Repair.md`](Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md).
- [ ] **G06a world-space beam extent / all-angle repair:** Surface `shaft_fan=1.0` selects a dominant camera-ray angular fan; `beamExtent` currently gates only axial distance between planes without lateral radius. Replace camera-anchored *placement* with bounded physical beam/scene scattering, real transverse beam width, and Surface-depth / Deep-distance falloff. Camera-dependent scattering gain is fine; physical beam placement must not move when looking up/down/side/along the light. Keep the half-resolution bounded pipeline initially; verify per-bubble/particle shadow proxies and measured GL4.6 cost. **Must see** consistent illuminated region and no fake slab/camera-facing fan.
- [ ] **G05/G27/G30 proposed Lighting Coverage (NOT implemented):** only after physical authority/optics acceptance, add separate **Lighting Coverage BEAM / SCENE** beneath existing **Light Type Sunlit Surface / Deep Light**. BEAM is bounded shafts/spotlight; SCENE is broad coherent environmental light. This setting is **independent of Motion → Emission Geometry BEAM / SCENE**; never automatically couple them. Existing current authored presets and Custom/settings/defaults remain intact. Four Light Type × Coverage combinations need native visual/cost checks with both physical emission geometries. Do not advertise it as an existing control or mark complete until implemented and accepted.

#### P2 | Source, stable lifetimes, contact and near-camera geometry

- [ ] **G07 bubble source/birth/spread** (EB-C/B; R42/R43): record source positions, actual reacted shell clearance and birth times during startup and song peaks. **Must see** wide spread without clustered bands, clamped-edge piles, overlap or interior births.
  - [~] **Whole-SCENE coverage repair remains unaccepted:** the latest saved-pose failure is reproduced (§49); the authorized finite-world camera candidate now admits its eye from `(8.1487,-7.7674,49.0063)` to `(8.1487,-5,15)`. Native active pixels extend below the former cutoff with identical world records/counts/source nodes. Eleven frozen-world Surface/Deep views and a pose/lens/corner matrix verify positive domain path in every direction. **Next:** inspect actual moving whole-tank distribution and sparse outward views; do not infer adequate density from geometry. Idle remains visibly failed. No camera-based actor placement, count increase, preset reset or new wall. Producers/limits: `Investigation.md` §51; `Evidence/2026-10-22_operator_active_idle_rejection/camera_bounded/` and `camera_bounds_all_angles/`.
  - [~] **SCENE physical-fade candidate — Awaiting Validation:** retained-pose native isolation proves broad entry/lateral-wall masks suppress valid interior particles. Specks/snow/free chains now fade over their physical footprint at entry/exit/wall crossing, retaining finite containment; BEAM native pixels remain identical on the frozen parity fixture. Check high-speed moving births/exits and near-wall chains. The larger empty swath remains open: reconcile saved camera/tank intersections with the water backdrop and ordinary coverage. Local logs, ray-box maps, flat occupancy and before/after pixels: `Docs/Reference/Extruded_Bubble/Evidence/2026-10-22_SCENE_retained_pose/` and `2026-10-22_SCENE_physical_fades/`; full method/limits: `Investigation.md` §42.
  - [~] **SCENE emission candidate (unaccepted):** BEAM remains the default; the new Motion → Emission Geometry choice can select SCENE. In SCENE the authored Source chooses entire inward-facing world-box inlet faces (floor, wall, adjoining corner faces), while Source→End sets physical travel direction. Each bubble takes its individual outgoing physical face; the camera never spawns or redirects it. Startup only pre-ages a deterministically seeded bounded tank; subsequent musical admissions happen at real upstream faces. Check G07/G08/G09/G32 together. **Must see:** face-wide, distributed ordinary large/small bubbles entering and leaving continuously, correct corner selection, no startup row or newly appeared interior cohorts, no sideways pop or camera-dependent regeneration. Check occupancy against the same cap; do not raise counts merely to fill the frame. A sparse-looking tank and wrong apparent density remain possible.

  - [~] **SCENE R45 face-distribution diagnosis (unaccepted, 22 Oct):** operator's two synchronized SCENE captures show narrow speck/particle clusters and apparently premature high-altitude bubble loss even with SCENE selected; the native 9/9 gate verified Settings/control wiring, **not** camera-space distribution or bubble identity lifetimes. Settings log confirms SCENE with a near-floor upward Source→End path; this is not a wrong-mode selection. GPU `sceneInlet` previously correlated the two free face coordinates via a `fract` mixture; R45 candidate maps independent face UVs. SCENE specks previously kept the old BEAM cloud-shaped *instance rejection*, hiding most of the full floor and making separated patches; R45 candidate makes their admission spatially uniform while using the authored cloud shape for intensity variation. BEAM remains identical. This is not proof of adequate full-tank bubble density: large/small population endpoints are still global, and the existing capacity is unmodified. **Must see** whole-floor physical birth distributions and reasonably uniform particle coverage from fixed camera poses, preserving BEAM presets and measured GPU cost. **Reject** shader syntax success or uniform source samples alone as visual acceptance. The dying-bubble complaint is a separate open gate G04/G09. Do **not** attribute it primarily to collision without per-ID collision/retirement evidence; a bubble exiting the camera frame is also not proof of physical death.

  - [~] **22 Oct subsequent operator screenshot: SCENE STILL visibly clustered (REJECTED).** Evidence archived at `Docs/Reference/Extruded_Bubble/Evidence/2026-10-22_SCENE_operator_rejected_clustering.png`. New visual evidence after the R45 handoff shows bright groups concentrated in localized lower-water areas with wide unoccupied gaps; sparse larger shells and earlier apparent surface disappearance are separately open. This is a **failed visual result**, not a task merely awaiting an initial inspection. Screenshot/run-revision linkage and exact actor IDs are not recorded, so inspect native build provenance and physical vs shader-space populations before blaming a particular cause. R45 uniform inlet samples / speck reject-mask fix **did not earn acceptance**. Distinguish specks, chains, snow, attached fizz and ordinary shells, fixed-camera HDR vs post-bloom, cold SCENE versus live BEAM→SCENE, and natural cohort retirement. Low counts may cause sparse coverage but **do not explain narrow groups when positions are truly distributed**; retract population size as an explanation for clustering. See [`Lighting_Authority_Repair.md`](Docs/Reference/Extruded_Bubble/Lighting_Authority_Repair.md#separate-and-higher-confidence-scene-cluster-evidence-g07g08g09g32) for full falsifiers. Preserve current count endpoints and cap. Do not conflate this with G04 surface EOL.
  - [ ] **G07/G08 emission-mode handoff and inherited bubble-cohort test (new, unproven cause):** switching BEAM→SCENE selects SCENE only for **new** admissions; old live BEAM identities are not redistributed. Compare cold SCENE, switched SCENE, and SCENE→BEAM→SCENE at identical authored state while logging per-ID birth mode, birth/retire time, world path, screen projection and luminosity. If persistent old cohorts contribute to grouping, design a **natural continuity-preserving takeover**, not teleport, delete, hidden reseed or camera-driven population replacement. Native pixels and operator acceptance decide the result; cold SCENE clustering disproves a universal switched-cohort explanation.

- [ ] **G08 population demand/admission/retirement** (EB-D/C): graph target versus actual stable IDs for both populations. **Must see** physically paced source admission and no midstream deletion on quieting or easy count-maximum saturation.
- [ ] **G09 speck/free-chain/marine-snow/attached-fizz EOL parity** (EB-C): track identities/opacity when populations rise and fall. **Must see** correct Source→End or parent-owned motion/fades, no opaque halfway birth or abrupt disappearance.
  - [~] In SCENE, existing GPU specks, free bead chains and marine snow now take world-space upstream-face paths using the **same face weights** as CPU bubbles; parent-attached fizz stays parent-owned. **Must see:** all actors spread over the selected true inlet faces and fade at the individual physical exit, with no static clouds and no opaque instance-count pop. Shader link checks alone do not validate alpha at cohort changes.

- [ ] **G10 Fuse / Pop / Bounce physical outcomes** (EB-B/C): capture actual contact and resulting separation. **Must see** readable action and strong smooth Bounce impulse with no overlap vibration or positional teleport.
- [ ] **G11 giant near-lens / fused DoF and culling** (EB-B/A): move the real camera through very large shells and the 1.5 px CoC threshold. **Must see** smooth near/far transition, no dot lattice/viewport-covering hard wall or erased valid population.
  - [~] **Mixed-circle sampling — Awaiting Validation:** the fine gather now covers circles below the wide mip's texel width. Native 5–10 px transition/energy and existing small-circle strip gates pass without wider tolerances; inspect real mixed-size near glass and highlights at both viewport sizes. This corrects a sampling gap, not G11's footprint/admission/culling failure.
  - [~] **Footprint protection candidate — Awaiting Validation:** the shared ordinary/fused render policy now strengthens blur toward half-viewport size even at zero aperture, then smoothly fades/culls near-full-viewport shells. It uses sensor-clipped projected footprint, continuous off-axis near-crossing bounds and per-member union opacity/CoC within the existing blur budget. Native diagnostics establish softness, fade/cull, eye-inside suppression, sparse-union survival, off-axis continuity and framebuffer/aspect scaling. Inspect actual authored P1/P7 glass in approach/retreat motion, mixed near/far overlap, both cards/DPRs and dual-display cost; the operator's sharp-screen-eating failure remains unaccepted until that review. Physical IDs, contacts, motion and wakes must remain intact; no simulation death or camera-relative respawn. Diagnostic comparison and producer: `Docs/Reference/Extruded_Bubble/Evidence/2026-10-22_near_lens/`.

#### P3 | Musical reactivity, temporal fidelity and exact Range endpoints

- [ ] **G12 visual-only Smoothing** (EB-D): compare 0/0.5/1 on one recording. **Must see** unchanged DSP/physical state and smooth per-ID display radii that still express attacks.
- [ ] **G13 large radius, sustained body and crest headroom** (EB-D): synchronized 2D/EB on quiet/held/changing loud. **Must see** actual rise/fall *inside* music, rather than inflated plateau or startup yank-down.
  - [ ] Repair actual-large recorded contraction/excursion: corrected admission-class instrumentation measures
    minimum median 1.976× nominal (required <.8) and active 4–8s span 1.398× (required >1.8). Preserve these failing
    bars; do not classify paced BEAM IDs by number. The current small span is 1.820×, not large-body acceptance.
- [ ] **G14 small radius and 512/256 judder** (EB-D): frame-by-frame per-ID 2D/EB, match song sample time. **Must see** smooth, expressive small-bubble radius, no shared size-state snapping or spawn/pop confusion.
  - [~] **Tiny material-state candidate — Awaiting Validation:** the sub-2.5px ordinary sparkle choice now uses stable identity alone, removing a changing-radius hash that caused native brightness jumps for negligible geometry changes. Native threshold regression fails before repair and passes with identical physical state policy; inspect recorded moving/sizing identities. This is a material discontinuity fix, not evidence of corrected radius followers, temporal sampling or 2D breathing parity.
- [ ] **G15 startup, pause, rest and event transients** (EB-D): tagged and untagged ramps/preset swaps. **Must see** gentle non-pulsing idle, no false hot-start peak, and real post-start musical hits.
  - [ ] **G09/G15/G18/G21/G25 idle-population contract:** verify settled idle and active→idle→active against `Target.md` and the runbook: particles remain visible, much smaller and without glow; ordinary/fused bubbles remain minimum-size without breathing and continue slow source birth→travel→breach/exit; free bead chains fade out and smoothly return with activity. Trace each owning scalar/opacity before repair; preserve zero authored amounts, physical IDs and existing near-lens/lifetime visibility rules. Collect local source/native evidence rather than waiting for operator logs.
  - [~] **Class-rest/Amount candidate — partial, idle still FAILED:** native Custom/P7 and 2D-ON recorded→pause60s→resume captures show retained ordinary rings and dust, quarter-radius/no-glow particles, and disappearing/returning chains. Custom remains too faint versus 2D; P7 active glare remains unaccepted. Quiet/loud size handles now have separate endpoint authority and class calibrations; Amount now controls squared density at fixed per-point radiance, an explicit semantic change. Zero particles and settled chains produce background-identical isolated pixels. **Next:** improve actual ordinary/particle readability without a new lighting floor or camera-based populations; verify native long lifecycle and active art. CPU one-hour idle runs prove source births and retirement, not their visible appearance. Complete measurements, prior failures and scoped producers: `Investigation.md` §52; `Evidence/2026-10-22_idle_class_transfer/`.
- [ ] **G16 Large Bubbles Range** (R33/R34): both handles separately control count targets; **must see** sustained-band breadth requirements and physically paced actual count.
- [ ] **G17 Small Bubbles Range** (R33/R34): both handles separately control targets; **must see** no easy saturation, no apparent radius snap from count churn.
- [ ] **G18 Bead Chains Range** (R33/R34): low/high and single-versus-broad band playback. **Must see** controllable visible count with smooth source/lifetime; not upper limit from any loud band.
- [ ] **G19 Stream Speed Range** (EB-C; R33/R41): one stable cohort, slow→fast→slow *while playing*, record actual XYZ/s and px/s. **Must see** unmistakable velocity change and authored low/high influence.
- [ ] **G20 Drift Range** (EB-C; R33/R41): track lateral XYZ and px displacement, not just general level. **Must see** perceivable within-song sway against steady main stream, calm idle.
- [ ] **G21 Particles Range / optional glow** (EB-C/A; R33/R34): independent count vs intensity vs spatial travel. **Must see** visible effect, smooth fades, preservation of P7 attractive debris without pinned glare.
  - [~] **Modest release extension — Awaiting Validation:** existing EB ray/particle followers now add
    min(150ms, 20% of their previous release). Review matched native release/return and live musical transitions;
    45 focused checks pass, ordinary records are unchanged and settled idle pixels are identical. No new state,
    timer, clock or DSP change. Evidence/limits: `Investigation.md` §53.
- [ ] **G22 Large Breathing Range** (EB-D; R33/R34): move quiet/high handles independently. **Must see** resting size not covertly driven by high handle and meaningful smooth loud expansion.
- [ ] **G23 Small Bubble Pulse Range** (EB-D; R33/R34): independently sweep endpoints. **Must see** smooth, high-value small reactivity versus same-time 2D Bubble, no binary peaks.
- [ ] **G24 Ray Strength Range** (EB-C; R33/R34): record driver→shaft uniform→HDR pixels in continuous songs. **Must see** reachable range, repeated transient-linked gentle brightening/slow dimming without flicker or pinning.
- [ ] **G25 role separation/sensitivity/idle motion** (EB-D/C): source-to-pixel lane breakdown at quiet/loud/fast/silence. **Must see** large body versus small details/rays/flow remain musically distinct; the +10% resting-motion candidate excludes water.
- [ ] **G13/G14/G25 asymmetrical breathing parity gate (operator 2026-10-22, still OPEN):** pair visually approved 2D Bubble **Dynamic Floor ON** against EB **Dynamic Floor OFF** at the same recording timestamps, normal sensitivities, current mutable presets, and annotated settings. Large and small EB bubbles must show at least comparable expressive per-ID radius excursions, attacks, downward contractions and releases through contrasting passages *within a song*, not only start/stop. Distinguish the dynamic floor's song-dependent deterioration in 2D from acceptable musical response: do not force EB to inherit it. EB Dynamic Floor ON/maximum sensitivity is a diagnostic negative control only. Native operator/visual-agent acceptance required; no source candidate can close this item.

#### P4 | Optical/material fidelity after underlying world and motion truth

- [ ] **G26 full water-surface coverage** (EB-B/A): views far from and directly under sun. **Must see** continuous, dimmer surface outside the brilliant local light without a floating bright island.
- [ ] **G27 ray softness, source reach, glints and attenuation** (EB-C/A): move bubble/particles through fixed shafts, compare bloom and final pixels. **Must see** coherent physical direction/soft occlusion with controls effective and bounded cost. **NEW dependency:** demonstrate true finite lateral beam width (not merely a Source→End axial slab), consistent physical light/glow/glints/medium sampling, appropriate Deep attenuation and the existing four-bubble proxy limits before any separate Lighting Coverage BEAM/SCENE can claim visual success; compare pre/post bloom, view angles, P1/P7, and current music/range controls. Reference: `Lighting_Authority_Repair.md`.
- [ ] **G28 glass material and rounded geometry** (EB-A): same-camera reference crops/video across presets/near/far. **Must see** true round shells, double rim and specular/refraction, no flat coins, thin disconnected lines or wrong light scaling.
  - [~] **Authored small-shell wall candidate — Awaiting Validation:** tracing now retains the authored 3% wall instead of thickening it to 1.5 pixels. Native ordinary/union tests fail under the former substitution and pass with material thickness authority restored; a fixed-world idle P1 camera sweep gives clearer small rings across subpixel movement. **Next:** inspect radius-changing musical identities, latest Custom after camera repair and Deep/near art. Whole idle remains failed. No physical radius/count/pass change; initial full-frame GPU queries show a small median increase and variable tails, so cost neutrality is unproved. Producer/limits: `Investigation.md` §50; `Evidence/2026-10-22_authored_wall_motion/`. The separate identity-hash correction stays at G14.
- [ ] **G29 P7 and seven-preset art registry** (EB-A): compare moving full-resolution targets and current mutable artwork. **Must see** lively controlled specks, gas/debris/film and correct orientation, without deleting requested effects or treating presets as frozen.

#### P5 | Native presentation, bounded costs, operator acceptance

- [ ] **G30 three-quarter editor/tooltip native parity** (EB-S): drag Camera/Aim/Start/End, save/reopen, switch Surface/Deep. **Must see** real scene movement from the existing state owner, readable labels and honest direction semantics.
- [ ] **G31 small glyph/UI remainder only** (UI R41; R42/R43): validate remaining transfer/topology, position/sizing and native test edge. **Must see** glyphs inside actual cards and exactly one Edit authority. Already accepted capture/hover/child editing is **not** reopened.
- [ ] **G32 GPU/CPU/dormancy/dual-display** (EB-P/F): bounded before/after p99, age and memory on multiple sizes and displays. **Must see** acceptable cost with no extra frame pump, worker, polling or owner leak. **New comparison:** same actual native P1/P7 authored frames and GPU p50/p95/p99 before/after lighting-authority + finite-volume correction and, only later, Light Type × Lighting Coverage; keep half-res shaft pipeline as baseline, prove any extra pass/occlusion earns its measured cost. G07 SCENE clustering and G04 surface EOL remain independently open.
  - [ ] **Deep point-metadata cost gate:** compare actual glass/bead/near pass cost against the true `05321d13` shader/optics baseline. Surface skips unused point metadata, but single-card frozen-frame queries vary and do not establish neutrality; the quiet sample still has higher P1 median despite lower p99. Preserve `Evidence/2026-10-22_deep_shading_points/timing*.json`; measure representative counts/motion and both displays before accepting register/storage cost. No extra program variants/passes/owners were introduced.
  - [ ] **SCENE cost/LOD acceptance:** native test equal authored counts in BEAM and SCENE at identical camera/card size/DPR, at common levels and worst-case 192 shells; compare logical tick cost, actual instance count, GPU p95/p99, memory and dual-display churn. SCENE introduces GPU inlet math, not a new draw pass; no extra bubbles are allocated by default. Only pursue frustum/size LOD if native cost or density actually warrants it. Renderer-only culling must never delete or reseed physical identities.

- [ ] **G33 complete P1–P7 visual acceptance** (all): annotated synced music clips/screenshots at actual authored settings, signed item-specific judgments. **Must see** all physical, musical, lighting and artistic gates working *together*; no inferred blanket approval from a few improved frames.

**Per-item minimum record:** exact audio/source and timestamp, preset and current Settings (including camera/light and block size), **single change**, numerical stage trace where available, native captured frames or short motion comparison, focused test result, specific pass/fail reason and who visually accepted it. A still cannot validate motion; a passing shader cannot validate pixels; FPS alone cannot validate flow. Missing native assets remain missing evidence, not permission to invent it. See [Acceptance_Runbook.md](Docs/Reference/Extruded_Bubble/Acceptance_Runbook.md) for the *specific observation and falsifier* of G00–G33.


### 4B-1. Detailed unaccepted implementation and failure records (retain all original checklists)

The following entries are the detailed failure/attempt and source-contract registry. Their dates and numbering DO NOT set priority. Follow the G00–G33 queue above for execution and consult these complete entries before touching their owners. All existing `[ ]` and `[~]` observations remain open.

### 4B-2. Durable failure inventories by architectural owner (all still OPEN)

#### EB-L — Strict Settings handoff and native lifecycle | independent correctness gate

- [ ] Reproduce the retained `QuickDisplayVisualizerOwner` during repeated actual MC Settings handoffs,
  using normal provider updates and the bounded CLI capture in `Docs/Guides/Logging_Guide.md`.
  Collect local logs directly; the idle pass above is not active-audio/preset/repeat coverage.
- [ ] On recurrence, attribute the exact surviving strong edge. Available archives contain no
  `[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS*]` receipt; existing MC flags do not enable this Diagnostic-only
  capture. Use MC lifecycle identities first and establish any remaining attribution gap explicitly;
  do not silently switch product flavour. The typed builder is not a proved retaining root. Do not soften,
  lengthen, retry through or bypass the barrier.
- [ ] Once an exact strong edge is proved and source work authorized, sever it at its actual owner, then exercise
  repeated cold/warm EB→Settings handoffs and preset changes. Preserve complete generation retirement, no orphan
  owner, stopped logical runtime and clean scenegraph/context resource release, including failed first build.
- [ ] Expand native admission/retirement beyond the captured P1/P7 paths to every preset, small/large card, resize,
  mixed DPR, dual displays, near clipping and `sceneGraphInvalidated`. Shader compilation is only admission proof.

#### EB-F — Evidence fidelity and remaining attribution

- [~] **Portable graphics investigation is possible, but not native product proof.** This analysis environment
  has a successfully initialized **Mesa llvmpipe OpenGL 4.5 core offscreen context** (EGL). The shipped
  `#version 460 core` shader stack and Qt Quick compositor cannot run unmodified in that context; GPU
  shader/primitive A/B with an explicitly adapted shader version is nevertheless feasible, as are exact
  source-driven CPU geometric projections. Label llvmpipe/translated GLSL versus native Windows OpenGL 4.6
  clearly; do not use missing PySide6 as a blanket excuse to avoid meaningful GPU diagnostics. Need native
  full-card frame evidence to close camera shape, judder, near DoF and actual music reaction.
- [ ] Extend the existing bounded forensic tools only where an unresolved competing explanation requires it.
  Preserve exact source hashes, resolved preset/Settings, playback/generation/activation and source timestamps;
  read actual band tuples/onsets and typed Ranges once, stable-ID base/radius/swell/alpha/pop/cluster, packed
  instance/view depth and actual captured output. Never identify a bubble by a changing compacted slot.
- [ ] Use the native `anything_mixed2` 2D/EB comparison and report §6 as the measured baseline. When measuring
  pixels, use the full-card 2D comparator and canonical CUSTOM/presentation resolver. First-order projected radii
  are estimates; add actual silhouette/ROI measurements where optics/DoF can alter the apparent result. Whole-frame
  zero-swell differences prove delivery but do not isolate individual boundaries or prove musical fidelity.
- [ ] Resolve the **live input** question with synchronized actual source values if needed after the measured
  response mapping is specified. Existing binary trace proves publications/draws, not band quality. Ordinary
  replay holds recorded post-DSP bands: Sensitivity/Floor overrides cannot test live DSP there. The optional PCM
  reanalysis is explicitly hybrid (requested PCM tails plus recorded events/loudness/sampled cadence), not proof
  of the failing live tuples; do not change accepted/shared DSP based on its plateaus alone.
- [ ] Measure source-band read/logical-tick CPU cost without introducing a permanent observer. The auxiliary
  `extruded_bubble_traces.py` plot supplies real bands and classifies by identity, but its default-control population
  means are not per-ID radius or native-pixel acceptance. Use forensic custody for those claims.

#### EB-S — Exposed Settings lazy construction, size ownership and preset fidelity (unaccepted source candidate)

- [~] **Partial source implementation — genuine section/bucket lazy loading.** Previously only the
  whole EB visualizer mode was lazy: all ~EB bucket controls/widgets/signals were constructed when
  its page opened, even for closed buckets. The current Settings builder creates the EB accordion
  hosts first, and only constructs/hydrates controls/signals on the FIRST open of each bucket.
  Settings collection merges live controls from built buckets and canonical cached values for
  unopened buckets; loading another preset hydrates both without implicit Custom/save, with
  live cross-bucket dependency conditions re-evaluated as controls appear. Existing expanded
  buckets are never discarded/recreated on collapse. A further source reduction now hydrates ONLY
  the newly opened bucket, not every previously opened bucket; full preset reload still hydrates all.
  This saves redundant widget writes but is NOT proof of a shorter Settings/barrier lifetime.
  **Qt UI tests, real Settings open/close, preset swaps, Reset, Custom, save/reload,
  signal and lifecycle barriers MUST pass on Windows.**
  A compile check alone is NOT UI acceptance; failed Settings startup remains actionable.
- [~] **Lazy build vs strict lifecycle barrier is an unproven causal link, NOT a reason to extend
  the barrier.** Current failure evidence from report §6.6: at the timed-out Settings handoff,
  every other QObject/resource category had retired but exactly one `QuickDisplayVisualizerOwner`
  remained. That is evidence of a retaining owner, not proof that EB control creation ran
  too long. Measure separately: mode shell build, per-first-open bucket widget/signal cost,
  per-open hydration/condition pass, Settings open→ready, live instance deactivation→all
  barrier categories retired, and Python owner referrer receipts on **failure only**. Include
  previously reopened buckets, Settings close during first-open, preset swaps with mixed
  built/unbuilt buckets, repeated reopen, and FOV/size edits. Never add timers, weaken
  the barrier, or claim the builder is the proven retaining root. Investigate exception
  midway through first-open (partially constructed Qt widgets plus no built marker):
  fail-closed cleanup and retry without duplicate rows/signals is still unverified.
- [~] **Independent large/small/bead physical sizes are authorable but unaccepted.** The Bubbles
  bucket now has distinct `Large Size`, `Small Size` and `Bead/Wake Size` sliders (0.5–2.0,
  1.0 defaults), separate from population counts and Size Variety. Large and small physical
  sizes are consumed at the simulation owner for new and existing stable IDs, contacts and wakes;
  bead/wake size is consumed by the real procedural bead shader, not a cosmetic screen zoom.
  Fuse-member type remains the underlying large/small owner. Verify actual large/small/fused,
  chain/attached-wake sizes, 0.5 and 2.0 endpoints, Custom/preset persistence and no repeated
  scale on each tick or abrupt transitions while editing. Never silently rewrite authored presets.
- [~] **Camera FOV bucket control** added with canonical 45° default; distinct from orbit/zoom,
  no scene-geometry mutation. Prove Settings value → saved Custom → runtime lens → 2D native
  shape, at both card sizes. The existence of a control does not close the camera rejection.

#### EB-B — Real world, camera, entry/death and near field

- [~] **NEW candidate: reset camera from R or hover glyph; gesture sign corrected, unaccepted.**
  `R` is captured once (no auto-repeat) by the same app-wide 3D runtime input owner that owns
  W/A/S/D, from any active display, and the bottom-right on-card `↺` glyph (EB only; revealed
  on pointer hover during admitted interaction/Ctrl) requests exactly the same display-manager
  reset. The authoritative mode/preset live pose is read from `starting_view` metadata for the
  seven curated EB presets; Custom uses canonical home; no preset file/artwork is overwritten.
  Active W/A/S/D/Alt-orbit intent, inertia, auto-rotate, pan/dolly gesture and pending commits
  are cancelled, and the single settings/presentation owner persists the one reset. EB lens
  additionally resets explicitly to canonical 45° (FOV is a separate lens control, not preset
  `starting_view` geometry). None of the seven on-disk EB preset JSONs contains historical FOV;
  all seven starting poses are valid, including intentional nonzero/downward tilts, and MUST
  remain editable. Runtime user-saved FOV could still be 62° before reset.
  **User rejected reversed Scene Pan:** historical `lens_shift` showed positive pan X right,
  positive pan Y down, matching Alt+right drag deltas. The physical-camera sign is now
  `dx=-2*d*tanX*panX` and `dy=+2*d*tanY*panY`; screen follow and near/far parallax have
  Qt-free projection tests, but still require actual Windows mouse, rotated camera, drag
  direction, bounds, viewport, Mode/Custom/Settings persistence, and glyph hit-target checks.
  Ensure the glyph does not conflict with Edit overlays, actions or screen exit gesture;
  don't make the rest of the visualizer card catch clicks. Verify deferred lazy root creation,
  runtime replacement, multi-display routing, FOV reset, held-key interruption and preset
  switch before calling it accepted. See Investigation §24.


- [~] **COMPLETELY FAILED live — stretched/elongated bubbles and wrongly coupled camera controls;
  physical world-camera SOURCE candidate now implemented, NOT visually accepted.** The earlier 62°
  rectilinear lens/off-axis Scene Pan produced objectionable distortion. The first 45°/centred
  candidate fixed the sensor shift but mistakenly changed Scene Pan into ANOTHER yaw/pitch rotation
  alongside existing Alt+left orbit. **Operator 2026-10-20 explicitly rejected that semantic mistake.**
  CURRENT CANDIDATE: default 45° vertical FOV with mutable 35–62° camera control, and a real
  pivot/eye rig in `extruded_bubble_scene.physical_camera`. Existing Alt+left `turn`/`tilt`
  orbits the eye around a fixed world pivot; Scene Pan moves camera eye + target together
  in the camera plane without changing orientation; Scene Scale dollies eye/pivot distance,
  rather than zooming by shrinking FOV. The renderer feeds ONE physical eye to ordinary
  shells, fused clusters, bead/wake/snow/speck particles, world water-plane sampling,
  shaft marching and probe glint positions. Legacy `camera_look_pan` and `lens_shift`
  product paths removed. Near-circle strength is no longer spuriously multiplied by
  old virtual scale. The underwater eye has a physical clearance limit from the surface.
  All positions/populations remain simulation world-owned, not camera-relative.
  **This repairs control semantics and represents actual camera translation/dolly in source;
  it DOES NOT mathematically eliminate rectilinear edge stretching, certify refraction,
  or prove good framing.** At 45° and 75% horizontal half-width the analytic projected sphere
  remains ~1.143:1 versus ~1.282:1 under the old 62° lens; operator's still-unaccepted
  1.155:1 at 30°/1.306:1 at 40° off-axis requires a separate projection/shading decision.
  Compare identical world bubble IDs/radii at fixed turn/tilt and controlled pan/zoom/orbit
  in native frames; require front/edge silhouettes, near/far parallax, defocus, probe,
  sun shafts, water coverage, 3D viewport gestures and actual P1/P7 authoring. Do not
  conflate historical temporal judder with near-focus switching; do not close on unit tests.
  Source evidence: report §23; historical rejected first candidate retained in §22.4.

- [ ] **Awaiting Validation — fixed physical world and real perspective.** Inspect the candidate against report §15:
  the simulation owns physical xyz/radius in a fixed water domain; shells/wakes/unions pack those values directly,
  and GPU chains/snow/specks use fixed world positions and a common world stream. Camera pose, zoom and aspect
  must never choose births, relocate identities or resize physical geometry. Check the full orbit at authored
  sparse/dense settings, source entry/exit and real-music movement at both resolutions. Global count ceilings stay
  global: no hidden sector copies or multipliers, and sparse views may legitimately remain sparse. Uniform/pixel
  tests and frozen real-snapshot views establish bounded mechanism proof, not camera/art acceptance.
- [~] **Unaccepted camera placement/centering and pose coverage.** A genuine translated eye,
  15-world-unit fixed orbit pivot and dolly source now exist. The pivot is NOT independently
  user-authored, camera reach/ceiling and the current gesture-to-scene sign/range remain
  unvalidated, and there is no proof the P1/P7/diagonal/abyss views are framed usefully.
  Confirm Alt+left remains orbit; regular Scene Pan translates, not rotates; wheel scale
  dolly changes near/far perspective instead of FOV; none change widget card position.
  Reuse the shared pose/input owner (do not add a second orbit gesture), and compare both
  card sizes, user pan extremes, tilt ceiling, reset, preset persist, and fixed-world IDs.
  The fixed pivot or limit may require geometry-informed adjustment following screenshots,
  but must never drive bubble births or an artificial camera-wrapped population.
- [ ] **Awaiting Validation — reacted physical contacts and continuous unions.** Verify ordinary/union/big/small
  contacts with the same current radii used by snapshots and wakes, including large extents across grid cells.
  Fusion stores the admitted connected edge layout and follows the existing smoothed radii; it must not snap
  centers or disconnect on contraction. Bounce continues gradually after a once-per-contact event choice and
  moves existing clusters as a group. Check repeated grazing contacts, third-member admission/removal, collision
  mixes/scopes, stable mass center, dense cost and absence of jitter in actual motion, not only numeric fixtures.
- [ ] **Water-boundary clearance and retirement.** The fixed center domain's top is below the water plane, but
  expanded shells can still cross that plane: current exit checks wait for the whole sphere to pass above it.
  Admit physical sources with current-radius clearance and define gentle retirement on actual surface breach;
  test rising/downward/diagonal streams, initial fill and musical expansion near the surface. Keep the world
  domain/source independent of the camera; do not fix this by hiding a lens region or scaling geometry.
- [ ] Establish **readable depth before view-aware overlap intervention**. Preserve convincing projected crossings
  like the copper mock; competing sharp rims/bright interiors and weak attenuation remain fidelity failures.
  Review world/source placement, perspective, transparency, near softness and distance attenuation together.
  Then design stable-pair join/pop/bounce handling for persistent unreadable crossings, including separated depth
  layers where justified. Use the existing live camera's derived projection; never fuse distant surfaces into a
  disconnected union, teleport geometry or automatically react to every projected intersection. Prefer continuous
  steering/approach and extremely gentle opacity retirement according to authored collision mix. An explicit
  opt-in is allowed if justified after demonstration. Fixed-camera proof precedes the much later Auto Rotate
  challenge, which must distinguish camera-induced crossings from bubble motion and remain bounded in cost.
- [ ] **Awaiting Validation — material lifetime and gentle pops.** Current ordinary/union instances carry opacity
  independently of radius; unions blend member opacity with their surface weights. Pops use a 2.4 s smooth
  opacity retirement with no pop-only radius expansion, retaining musical size separately. Inspect actual birth,
  pop, exit and cluster-member removal: no opacity brightening, shell resurrection, neck snap, geometric implosion,
  parent/bead size violation or detached/rebound wake. The removed `sqrt(alpha)` sizing must not return.
- [ ] **Awaiting Validation — one projection and shared near DoF.** Ordinary/fused shells now use the same pinhole
  rays/bounds/depth, with finite near-plane/eye-inside handling. Fused near surfaces use the existing DefocusLayer
  and one depth-selected route. Verify normal/reflected/transmitted output, center/edge/near-plane views, partial
  member fades and focus/aperture changes in real scenes. Native checks cover common silhouette conventions and
  exclusive layer admission; true pinhole off-axis elongation is not by itself a new refraction defect or accepted
  art. Focus/aperture and resolution-scaled lens budgets require visual review at both resolutions. Preserve
  prepared allocation/state restoration through camera gestures; no new lens-attached population.
- [ ] **FAILED live — close bubbles become pixel-like or miss proper DoF.** Record actual near-layer admission,
  front depth, CoC, budget/mip and material opacity through approach/retreat and breathing. A native shared-DoF
  strip falsifier already reproduces 2px circles becoming separated 8px-grid discs under the 54px budget; fix
  mixed small/large CoC sampling with preserved light and prepared resource ownership, not larger fake geometry
  or reduced specks. Properly defocus close forms wherever feasible; if too close to represent, use coherent
  gentle occlusion/retirement as justified by the camera/scene, without hard pops or teleportation. See report §19.

#### EB-C — Stream, drift, beads, wakes, rays and emission

- [~] **Operator-requested +10% idle motion, source candidate (not verified visually).**
  Keep audio bands, presence and the ocean/water surface's `_motion_phase` unchanged. A
  `rest_motion_boost = 1 + 0.10*quiet` multiplies only non-surface rest contributions:
  physical speed/drift admission (and downstream bead/snow/speck travel), sway amplitude,
  and ray shimmer's idle phase. It collapses to 1.0 at normal musical intensity; no
  artificial periodic bubble breathing, no extra clock. The quiet-end emission floor
  (`max(0.25, activity)`) can still mask this small activity increase in emissions;
  verify idle motes and wakes and don't claim an exact +10% optical-flow increase.
  Qt-free test proves exact 1.10 speed/shimmer scaling in silence and unchanged
  `_motion_phase`, NOT 10% measured native optical flow. Check no ocean change at P1/P7.
- [ ] **FAILED live: no useful intra-song drift/stream acceleration or deceleration.**
  Play-state idle→active is obvious, but within uninterrupted slow→fast→slow passages
  the motion apparently sticks. The current `activity = min(1, idle_rate + 1.6*level)`
  is saturated for level around 0.59+; `_soft_top(change_drive)` and successive followers
  can further compress/hide sectional changes. Yet a Qt-free artificial high-bass,
  low-mid→high-mid→low-mid sweep gives stream ~1.21→1.79→1.39 world units/s
  and drift ~0.605→0.818→0.628 after 2-second segments. Thus the *logical* stream
  CAN respond; the user's native visual rejection is not disproved by this synthetic
  test. Trace actual recorded bands and target/current, travel slope/particle world
  displacement, projected pixels/s and viewport/camera/DoF on matching IDs. Test
  0/1 ranges plus peak speed and return latency through several changes *within*
  loud passages, not just play/pause; correct saturation or weak pixel gain at its owner.
- [ ] **FAILED live: rays do not perceptibly react AT ALL.**
  Existing wiring is source bands→`_body_small_envelope`/`_level`→`_rays`
  (0.08s attack / 0.22–0.65s release)→`ray_strength` Range mapping→`uRays`
  →backdrop shaft texture + cutoff/focus/color, with separate onset shimmer/flicker.
  A synthetic P1 constant-high-bass low-mid→high-mid→low-mid sweep produces ray
  driver ~0.332→0.688→0.341 after two-second stages; **source scalar motion
  exists but does NOT establish visible rays**. Debug P1/P7 with isolated shaft-only
  ROI and 0/1 strength, log per-frame `_rays`, `uRays`, fan texture mean/95th,
  cutoff-surviving pixels, contrast after water/HDR/bloom, and audio-correlated
  optical difference (not source-only or low-fps screenshots). Distinguish not
  changing the shaft map from moving/brightening rays too weakly to be seen.
  No statement that ray response is fixed until native operator/agent visual signoff.


- [~] **COMPLETELY UNACCEPTED — other reaction lanes need real passage attribution, not a common amplitude claim.**
  Source path `ExtrudedBubbleSimulation.advance`: `level=max(bass, vocal_body)` and a shared `_soft_top`
  drive feed population, motion, stream, drift, rays and emission; `activity=min(1, idle_rate + 1.6*level)`
  can saturate *before* the input reaches its maximum. `change_drive` is also a shared aggregate, despite the
  declared requirement to remain expressive during sustained bass with changing vocals. `emission_target`
  retains `max(0.25, activity)` and `ray_motion` retains 30% of authored flicker scale at zero driver;
  whether the actual idle pixels are excessive needs measurement. Do **not** infer any rendered behavioral
  correction or that these expressions explain all failed lanes. On identical real-recorded sections trace
  pre/post `_soft_top` signals, target/current stream speed, drift, emission, ray strength/phase and rendered
  optical flow/luminance on quiet/soft/onset/held bass+vocal changes/release. Verify authored Range endpoints,
  time constants, stable IDs, real pixels and costs independently. The latest native rejection governs.
- [ ] Establish **proper world-space stream sources**: simulation-owned source points/regions, direction/spread,
  birth distribution, advection and lifetime for the applicable bubble/chain/particle families. The candidate has
  actual fixed-volume upstream faces and world procedural paths; expose the point/region controls and localized
  authored streams needed by the examples rather than treating a global box inflow as full target parity.
  Make needed source controls authorable through canonical Settings, preserving one logical clock and stable
  emitters. Prove source location/direction during orbit, musical acceleration and collapsed slow idle.
- [ ] Give stream speed and drift a demonstrably broad, smooth musical response through quiet and saturated
  passages. Trace displacement of stable IDs, direction and optical flow; source values alone are insufficient.
  Audit the retained response followers and world-unit conversion in actual pixels without adding another clock.
- [ ] Prove free chains' complete birth/death fade, curved **15% wider** paths and common world stream direction.
  Preserve the existing ceil/fractional-opacity allocation; inspect its actual entry/exit and lifetime pixels.
  Diagnose heading divergence under camera motion separately from intended curvature. Keep chains distinct
  from bubble-attached wakes.
- [ ] Include every bubble family in the **minimum-size/response audit**: ordinary large/mid, fused members,
  free beads and parent-attached wake beads. Beads are already tiny and use only modest size reaction; speed,
  drift and emission should carry much of their response. Keep non-bubble dust/snow distinct. A count reduction
  or disappearance does not prove contraction; parent attachment and retiring-tail continuity need native proof.
- [ ] **Awaiting Validation — per-feature Range ownership and tier-stable wake allocation.** The candidate resolves
  Bead Chains independently from normalized musical level, and snow/fizz consume the already-resolved Particles
  emission. Fractional allocation opacity reaches the actual snow fragment; every stable wake receives a per-owner
  quality budget, including retirement. Native tests cover zero emission, fractional snow opacity, both wake owners
  at reduced quality and bead size bounds. Review real quiet/live/release at P1/P7, especially high-density retained
  settings; changed budgets alone do not establish musical birth/lifetime or acceptable density. Preserve fractional
  chain opacity; do not reopen the disproved blanket integer-chain-pop diagnosis. Report §13 owns bounded evidence.
  Bead Chains currently means 12 generated chains per displayed unit: reconcile user-facing density semantics
  against lab/preset art at the later mapping audit without silently rewriting authored values.
- [ ] **Awaiting Validation — bounded bead sizing / visible slow rest.** The candidate now carries nominal and
  reacted parent radii separately: attachment follows the parent, while bead dimensions/trail extent remain
  nominal with at most roughly −10%/+10% musical size variation. GPU tests enforce strictly smaller beads than
  current parents, including fading tiny parents and raster-size limits. Inspect actual pop/fuse/retirement,
  depth and changing parents in P1/P7, preserving stable identities and source-to-tail retirement. The candidate
  raises nonzero resting motion and separates emission activity from motion attenuation (the latter was then
  squared into almost no particles). Verify visibly very slow stream/emission/surface-water without a fast
  idle or oscillator; native/CPU/GPU evidence is in report §9, not a physical acceptance claim.
- [ ] **Awaiting Validation — Ray Softness.** The candidate now connects the authored setting to the depth-marched
  shaft threshold as well as the fan; native endpoints differ where Deep Light previously ignored the setting.
  Review broad softness in actual P1/P7 passages, measuring angular/pixel units at both
  resolutions; fixed blur taps alone are not a resolution-independent appearance contract.
- [ ] **Awaiting Validation — ray reaction range and slow idle dimming.** The candidate retains 3% resting activity,
  then opens the authored Range with the continuous musical driver. Verify useful native contrast through real
  quiet/onset/sustained/release, including P1's strong quiet handle and P7's low-light art. Retain the single
  ray Range owner, motion phase continuity and independent light/surface art. Prove actual ray ROI and profile
  changes on real passages, not merely a changed uniform or shimmer clock. See report §7 for the native probe.
- [ ] Validate stable live/retiring wake emitters at the physical surface, pop, fusion, parent exit and slot compaction.
  Require the travel-front-to-tail dissolve with no detached/falling fizz or new-parent attachment. The dedicated
  wake SSBO/source candidate is unaccepted; shader/source tests do not demonstrate visual continuity.
- [ ] Measure bead/wake shimmer and glints at small/large card, DPR and oblique camera motion. Keep scene/probe-lit
  micro-glass; do not mask aliasing by disabling environment lighting. Separate lifetime/coverage from brightness.
- [ ] Measure **rays alone**: actual range→driver→uniform→shaft area/intensity, spread/flicker and sustained changes.
  Diagnose background-light dominance and shared-level compression without substituting an unmusical time effect.
- [ ] Measure **emission populations separately**: speck count/brightness, free chain count/opacity and attached
  fizz/wake density/lifetime. Preserve one Particles Range mapping; its removed duplicate mapping did not fix the
  visible failure. Fizz now has a musical per-owner budget, but that is not an independently proved musical birth rate.
  Include quiet/live/release and the high-density authored settings seen in retained logs.

#### EB-D — Musical size, attack/release and collapsed rest (first recovery priority)

- [ ] **NEW visual rejection: SMALL size snaps between states instead of gliding.** User directly reports
  frame-to-frame size-state switching in newer builds, even though bulk breathing improved. Same-ID
  measurements must distinguish `small_body`→reference delta→`_body_small_envelope`→
  `_reaction_scale`→`b.current_radius` against source/logical/render cadence, near-layer 1.5px
  membership and native full-alpha pixels. The current code has no distinct per-ID displayed-radius
  convergence and directly publishes a class-shared envelope; that is a *mechanism to investigate*,
  not proof of the symptom or permission to reintroduce the failed R-105 micro-breath hold.
  Plot raw/target/drawn radius, frame-to-frame reversals, 10–90% attack, post-peak release and
  same-ID depth/CoC membership for the SAME song passage, and compare to accepted 2D release gating.
  A smoothing change is disallowed if it muffles the first attack or loses expected downward size motion.
- [ ] **NEW visual rejection: LARGE bubbles pinned at maximum too often.** Do NOT mistake sustained
  body for a permanent peak. Track percentage of each selected large ID's time spent within
  90%/95% of its own attainable upper excursion, number/duration of flat runs, and time below
  half-scale during softer changes. `_reaction_scale` couples its baseline and expansion to the
  same `drive`, with `_body_big_envelope` fed a held `(0.25 + 0.75*sustain)*big_body` component
  and slow nonquiet release; test whether these together prevent receding between distinct phrases.
  Contrast a constant-hot segment, slow→fast→slow inside playback, soft/acoustic gaps and pause.
  Never solve pinning by lowering peak amplitude or squeezing the entire dynamic range.


- [ ] **FAILED live — activation/preset-swap size overshoot and yank-down.** Latest operator reports large
  bubbles overinflate on start/swap, then get pulled down. Establish the actual producer/settings from latest
  logs. Trace first-ready bands, onset serials, zero-seeded change references, sustain, target/current radius,
  activation/source reset and reveal. Reproduce quiet→music separately from joining already-playing music and
  swapping presets while loud. Seed/retain the correct authorities at their owner; do not suppress real soft
  breathing or add a startup workaround/timer. Preserve gentle birth/reveal and source-generation fencing.
  **Historical source-level reproducer (`Investigation.md` §20):** original P1/P7 input with already-hot
  music made ~3.37× peak vs ~1.24× final nominal radius; a one-second quadratic playback ramp also
  produced ~2.71× peak/final. Priming zero references alone did not address that separate ramp.
  **CURRENT IMPLEMENTATION CANDIDATE / NOT ACCEPTED (`Investigation.md` §22):** activation primes the
  large-body reference; the existing producer's `play_ramping` flag suppresses fictitious ramp changes,
  and gradual unflagged ramps use a fast follower with bounded change; a genuine sudden musical step
  retains its strong attack via a short edge follower. Synthetic P1/P7 hot start: ~1.253×/1.253×;
  source-tagged quadratic ramp ~1.238×/~1.238× (ratio 1.00); unflagged ~1.517×/~1.238× (1.23); quiet→genuine musical step remains strongly
  reactive. Existing soft-breathing and full-dynamic Qt-free tests continue passing;
  numerical checks do not certify musical fidelity. **Small-bubble hot-start/warmup now also has an unaccepted source-ramp candidate:** its first playing reference is primed and actual engine warmup changes are excluded as artificial; P1/P7 flagged 1-second ramp yields ~0.251× peak/final and already-hot ~0.251×/0.251×. The unflagged quadratic ramp STILL gives ~3.381× peak vs 0.263× final for small bubbles, a real sensitivity requiring source-ramp metadata on every delivery. Direct quiet→musical step remains large in both lanes (~3.315× large and ~3.373× small peaks), and is NOT proof of appropriate musical amplitude. Unaccepted until recorded audio/visual validation. Actual play/pause,
  preset switch while loud, source-generation fencing, changing recorded tracks and native pixels
  MUST falsify/accept the candidate. No `[x]` by numerical gate or this note.

- [~] **UNACCEPTED — near-defocus switching is a SECONDARY, separately measurable effect, NOT the
  explanation for most live bubble judder.**
  `ExtrudedBubbleSimulation.advance` calculates ONE common big/small envelope for the full population and assigns
  `b.current_radius = b.radius * scale` on every logical tick, without a separate per-ID displayed-radius filter.
  A changing source drives every like-class silhouette together; **this is not by itself proof of oscillatory
  chatter**. Additionally, `BUBBLE_VERTEX` / `CLUSTER_VERTEX` switch exclusively between ordinary glass and the
  shared near-defocus layer at `sceneNearCircle(...) > 1.5px` (strict; no overlap/hysteresis). The Qt-free
  P1/P7 probe establishes that a small smooth ±2% radius variation can cross this branch at
  fixed centre depth. That creates the *opportunity* for appearance switching, not proof of user-reported
  judder. Measure exact per-ID radius/centre/alpha, near-layer branch, CoC, composited pixel silhouette and
  Qt presentation intervals on the same real recorded passage before choosing a smoothing or layer fix.
  `tools/visualizer_replay/extruded_bubble_projection_gate_probe.py`; ledger §21. Historical BTF,
  `R-105` and the accepted 2D render-size release gate remain primary causal leads for 1–2px
  temporal vibration. Do not blindly import the rejected tiny-breath filter, dull musical dynamics,
  or use a second frame clock.
- [ ] **FAILED live — large and small judder/vibration between sizes.** Use latest logs/traces and identical
  recorded passages to distinguish actual target/radius chatter, pass/DoF switching and display cadence. Inspect
  accepted 2D's **Bubble Temporal Fidelity** and `R-105`: accepted render-loudness/hero rise +
  `RENDER_SIZE_RELEASE_S` decay, and the REJECTED tiny-breath directional filter which worsened
  recorded comparisons. Measure SAME-ID
  target/current world radius, projected/segmented size and optical flow at logical/native cadence; current
  amplitude/continuity fixtures did not falsify this failure. Repair smooth transitions at the canonical logical
  owner with current radius shared by contacts/wakes; no renderer simulation, extra clock, arbitrary clamp or
  loss of strong downward soft breathing. Add a real-input jitter regression that fails this producer.
- [ ] **Awaiting Validation — candidate musical radius transfer.** Use report §7 and the current simulation as the
  implementation reference. Verify real large/small SAME-ID minima as well as excursion/peaks, without treating
  birth/pop/fade as contraction. Normal reaction strengths must let even the big population settle near 0.13× nominal
  radius, comparable to accepted 2D's low range, then expand strongly with music. Measure full-alpha projected and
  actual silhouette size at fixed depth; preserve deliberate zero-strength disabling and independent Range handles.
  Reject a large percentage excursion that still leaves the minimum inflated or makes musical peaks too small.
- [ ] **Awaiting Validation — Sustained Response.** The band-path consumer now supports body size and motion;
  prove 0/1 endpoints in actual pixels on sustained real passages without inventing a periodic pulse on held input.
- [ ] **Awaiting Validation — passage-role separation (report §18).** Check 2D's separate
  mid/high reference, clean delta, bounded hot/body support and release; it is not literally bass-free. Give large
  bubbles significant downward breathing in soft/changing music and held body in sustained loud music. Avoid
  ordinary small size being held by transients or bass; retain changing-vocal/high response during loud passages.
  Audit the shared `max`-level consumers for pinned stream/drift/emission/rays under held bass with changing vocals.
  Verify the corrected Sustained Response/Range consumers; revise preset values through canonical Settings where
  needed. Validate quiet/change/held-loud/changes-within-loud/release
  at multiple control endpoints on the same recorded sections as 2D. The latest native screenshots are rejected.
- [ ] **Awaiting Validation — clean-body phrase response.** Use report §§16/18 and the paired comparison tool to
  compare the same actual body tuples/cadence in 2D/EB. The candidate removes event tails from size, restores
  vocal contribution under bass and gives changing small-body energy more authority. Verify absolute span,
  minimum, peak, relative excursion and onset/release timing independently: the first-window large minimum and
  relative excursion still miss 2D, despite a larger peak. Do not close this using tiny opening-rest percentages.
  Inspect high-pass small peaks for long ceiling-like holds, additive-mixture clipping, apparent overcrowding and
  pauses. Include actual native ordinary silhouettes at fixed depth and label raster/near-layer transitions.
- [ ] **Awaiting Validation — small/large separation and count limits.** Verify the normalized population driver
  and retiring-slot admission against the Range endpoints; mechanisms/history are in report §10. The small lane
  separates changing vocal energy from restrained held support. Verify real sustained passages and transient peaks remain
  expressive without turning the entire small field into large-looking shells. Classify by stable owner ID,
  never current radius. Distinguish active count targets, still-visible retirement and fused groups; confirm
  current user's [0,4] large / [20,50] small values at the logical/GPU seam. See report §10, including the rejected
  repeated-event hold; do not use that failed probe as evidence of steady body support.
- [ ] **Awaiting Validation — idle settling across every reactive lane.** The candidate contracts size and reduces
  integrated resting phases, stream, drift and emission. Inspect gentle release over seconds, raw-time bypasses,
  water phase, bead travel, ray shimmer and emission in pixels, including pause→resume without a reset or jump.
  Trace why the operator perceived idle faster than playback; this inversion is still unattributed, not disproved
  by a slower numerical phase. Compare matched optical flow on pause/release/resume with the same scene/camera.
- [ ] Compare effective multi-stage latency and excursion on quiet, onset, changing body, saturated music and release.
  Large and small SAME-ID radius changes must visibly approach the accepted 2D response scale on `anything_mixed2`
  at normal controls. Dynamic Floor on/extreme Sensitivity are negative controls, never required workarounds.
  Reject small rapid nonmusical pulses, held inflation, dead small bubbles, judder and sudden stops.
- [ ] **Explicit positive/negative comparator settings:** 2D Bubble with Dynamic Floor **ON** is the accepted *visually observed* positive reference; EB with Dynamic Floor **OFF** is the desired normal-settings target. Document floor state independently for each capture; compare passages before and after any floor adaptation. Do not mistake 2D Dynamic Floor ON for an EB requirement or mark a visual parity pass from the 2D/EB source traces alone.
- [ ] Accept the **reactivity baseline** only on the same opening 12 seconds of `anything_mixed2`
  used in the native positive comparison, with unchanged authored presets and normal technical controls. Compare
  large/small SAME-ID radius/base, music-correlated excursions, onset-to-pixel delay and release against accepted
  2D; include the 1.507–3.147 s window where old EB only reached 1.038–1.131× base against 2D's 0.707–2.782×.
  Show genuine contracted rest and strong expansion throughout representative populations, not a single selected
  giant. Capture short passages at source logical cadence/high temporal resolution with synchronized recorded
  sound where native history permits verified reconstruction; low-fps contact sheets alone cannot prove attack,
  judder or musical connection. Validate quiet→onset→sustained→pause→resume, Range endpoints and the restored
  Sustained consumer with production-band-path tests plus native pixels. Then repeat on Ragdoll, heavy and soft
  clips, both target resolutions and P1/P7 before extending to every preset. Measure timing independently of
  diagnostic readback/encoding; keep source/dormancy/retirement checks and an operator physical check as distinct gates.

#### EB-A — Glass/material, mock fidelity and authoring

- [ ] Verify the centralized preset→example→lab registry in `Docs/Reference/Extruded_Bubble/README.md` against actual
  resolved Settings and camera/source composition. P7→ExBubble6Diagonal is operator-confirmed; other associations
  remain candidates. Use the original/annotated targets, full historical lab material and failed native evidence
  now housed together there; record parity gaps, owning architecture and proof at that single home. Do not create
  another image collection or postpone needed EB architecture as optional graphics work.
- [ ] Confirm/fix the P7 dot lattice at the existing near-defocus owner: Astra's audit finds the 1440p highlight
  sampler's 8-pixel grid matches the native dot rows/columns. Freeze the current snapshot and A/B that split with
  all particles/geometry preserved. Do not reduce specks to conceal a near-highlight sampling defect. Then isolate
  conflicting background/light lens models, missing rear-population refraction, probe/self-proxy blobs and the
  analytic specular consumer ignoring Light Strength. Exact source leads/falsifiers: the centralized Visual Audit.
- [ ] Isolate coin-like/edge-on clear shells, especially Preset 7, with native normal/coverage/reflected/transmitted
  diagnostic views and SAME-ID samples. Inspect screen-facing-ray, refraction, film/rim, interior blur and DoF
  separately; analytical sphere intersections do not establish believable spherical glass.
- [ ] **FAILED visual parity — active speck glow is roughly 50% too strong (operator estimate).** Preserve important
  specks and separate glow from density, refraction/proxy duplication, exposure and near-defocus artifacts. Measure
  matched active/quiet P1/P7 crops and meaningful control endpoints before retuning; spherical glass and readable
  overlap depth take priority over this glow adjustment. Keep the source/preset correction in the central registry.
- [ ] Complete the remaining target §7 material recovery in bounded steps: C01 edge-soft smear, C03 smoothstep,
  C05 cluster normal, C06 depth, then inset highlights/specular, double rim/roundness and shafts in isolation.
  Use already-proven shared optics/OIT/HDR and keep visible depth/translucency at overlap. No hard shadows without
  an approved receiver; no ocean floor. Do not restore rejected ribbon/sperm-like trails or synthetic foreground giants.
- [ ] Compare all seven mutable presets and all supplied mocks at full resolution, with crops and motion: discrete
  bead rain, source-following tiny-bubble wakes, volume glints, natural soft close passes, copper/abyss art,
  smoky/glowing detail and broad soft light. Every scene must remain authorable through canonical typed controls
  alone. Audit collisions (Fuse/Pop/Bounce and Big/Small/All), Range handles, Direction midpoint guide and FC Auto
  Rotate through their existing shared owners, including native DPR/keyboard behavior and real-body persistence.
- [ ] Reproduce the fiery/diagonal example's **ember debris and gas/smoky flow**, including source placement,
  depth/occlusion, glow, coherent advection and musical/idle response. Inventory the lab's `ExBubble6Diagonal`
  and current production consumers to distinguish a matched still from working runtime architecture. Add the
  particle/emitter/wisp/volume facilities actually needed for parity; do not treat these as optional future art or
  substitute a static haze/dust overlay. Compare mock | lab | production motion and close crops, then measure
  quality-tier GPU/CPU/memory cost and dormant teardown. Reactivity baseline precedes this implementation.

#### EB-P — Cost, dormancy and acceptance

- [ ] Benchmark the scene-lit micro-glass branch against the **pre-micro-glass** source with identical recorded
  frames, Settings, density, camera and quality. Cover Presets 1/7 and dense chains at 1672×941 and 2560×1440;
  warmed per-pass GPU timings, independent total-frame median/p90, GL/Python calls, source-read/tick CPU and memory.
  Current single-tree samples and serial per-draw queries are evidence, not comparative performance clearance.
- [ ] Prove inactive import/resources/CPU remain dormant; no live diagnostic polling or persistent capture work.
  Preserve one source/clock and single retained presentation; no accepted 2D/Neon behavior or preset mutations.
- [~] **Awaiting Validation after actual repairs:** operator accepts strong immediate real-music response,
  gently collapsed slow idle, camera/world/fades, beads/wakes, rays/emission, glass/near DoF and seven-preset art.
  A capable agent may supply native captured pixel/motion evidence, but no existing failed status is closed merely
  by a numeric test or this investigation. Release showcases wait until musical/rendered behavior is stable.


### 4B-3. Detailed source candidates, recorded evidence and unresolved investigations (all still OPEN)

**22 October additional independent source audit, evidence only:** [`Additional_Source_Audit_2026-10-22.md`](Docs/Reference/Extruded_Bubble/Additional_Source_Audit_2026-10-22.md) confirms the current Breathing/Pulse high-handle→silent-size coupling (G22/G23), Deep water-plane EOL leak (G04/G09), SCENE→BEAM inherited-cohort End-plane retirement (G07/G09), camera/light-sensitive speck visibility separate from world placement (G07/G21), stacked quiet-range compression (G19–G21), disabled-ray shader work without measured cost (G27/G32), unreachable exact ray high setting from the clamped logical driver (G24/G27), and a uniform synthetic CPU floor inlet that does **not** explain the still-rejected pixels (G07). Existing G00–G33 gates and complete failures govern all repairs. **Source-proof is not native visual verification; [ ]/[~] stay open.**

#### EB-R43 — 2026-10-21 surface breach and physically paced inlet (ALL UNACCEPTED)

**Operator evidence:** three R42 captured frames at 23:39:53, 23:40:00, 23:40:26 show tight/banded large bubbles and apparent early loss below the visibly rendered ceiling. The supplied `logsbae635b676.zip` archives end at **2026-10-20 20:13**, BEFORE these images; they are **not** synchronized with this report and cannot be used to claim a measured disappearing ID or camera depth. Keep R41's **Sunlit Light/Ray source-authority and editor-to-pixel projection audit** fully open.

- [~] **P1/P3 physical inlet-spacing candidate:** R42's 1.8-world-unit capped birth gap did not use reacted physical radii; two visibly large shells could spawn overlapping. R43 samples the prospective bubble radius once, calculates its current music-owned physical radius and rejects candidates that overlap any existing nonretiring physical shell, with a small inlet margin. The candidate must **not** use display Smoothing, move existing IDs, spawn midway, or force a crowded birth. Check at startup AND in sustained/changed music that 3D separations, screen projections and actual visible groups are acceptably distributed with high Bubble Spread. Note that later reactive radius expansion or fusion can still create groups; distinguish admission clumping from collision/size effects.
- [~] **P1/P3 count-deficit burst candidate:** R42 accrued spawn credit at ~target-count-scaled rate even when stream transport was slow, so a large missing population could be born in a short interval. R43 caps logical admission at one source bubble per population per capture and uses existing travel speed, authored path length and requested occupancy to pace births; it discards credit if Source is crowded. The count target remains a **ceiling**, not an instruction to instantly populate. Native recorded passage + timestamps must show no cohorts launched together, no hidden backlog, and still sufficient *eventual* occupancy and visible variety at both idle and loud settings. A slow or stationary stream may now remain below requested occupancy; measure before any tuning. **Do not solve startup emptiness by materializing middle-of-stream births.** Review accepted 2D temporal seeding separately if needed, preserving source-only entry.
- [~] **P1/P3 premature surface death candidate:** renderer's water uses the actual shared `WATER_SURFACE_Y=9` ray/plane, not an independently rendered fake ceiling. R42 started the full time-based .9 s opacity fade when the bubble's *upper rim* reached near that plane, which may empty the bubble far below it at slow flow. R43 starts that fade only when the **centre crosses Y=9**, retaining the authored Deep Light endpoint contract. Test a stable named bubble against rendered surface pixels in an animated capture at known camera pose; check whether it genuinely breaches before fading (including changing bubble sizes). Distinguish this from `Pop` collision, x/z world-boundary exit, DoF/culling or camera-projected separation. No visual acceptance yet.
- [~] **Small glyph tweak:** shift general hover row +2 px inward from card left; reduce only Lock and Close X drawings an additional 5%, leaving 24 px hit boxes, row height, bottom margin, Edit authority and established glyph timing untouched. Native card/Media/mixed-DPR eye-check pending.
- [~] **Visual acceptance procedure awaiting execution:** the new G00–G33 queue and runbook specify matched recorded 2D/EB, time-coded motion, world/pixel projection, bubble exit causes and failure-only owner-retention evidence. This is documentation organization, **not** evidence that any unresolved behavior improved. Every original failure item stays open; native and operator validation remain required.

Source detail and exact local diagnostic coverage: `Docs/Reference/R43_EB_Breach_Inlet_And_Glyph_Checkpoint.md`.

#### EB-R42 — 2026-10-21 surface EOL, grouped births, weak Bounce and native glyph gates (ALL UNACCEPTED)

**New operator evidence:** paired EB underwater screenshots show a large bubble disappearing while visibly below the water surface and numerous tightly grouped birth bands despite high Bubble Spread, both during startup and music. Camera Position screenshot is supporting geometry context but **does not prove world height from image pixels**. Operator also reports repeated barely separating Bounce contacts. Do not remove the Sunlit Surface vs Deep Light source/shaft interface-authority audit from R41/P4: these are different problems.

- [~] **P3 high-priority premature surface fade, source candidate:** R37 faded ordinary bubbles on `dot(position-End,direction)>=0`, regardless of visible surface. In Sunlit Surface with an upward stream this could fade the bubble at an authored End below the water plane. R42 passes the existing Light Type through the logical control admission; a *surface/upward* bubble now starts 0.9 s EOL opacity release only when its visible upper radius is within 0.05 world units (in WORLD_UNIT multiples) of `WATER_SURFACE_Y`. Deep Light, lateral/descending streams and absent paths retain their former authored End/bounds semantics. Compare actual world camera projection and moving surface pixels across P1, oblique streams, P7, and varying sizes. Do NOT mark accepted because logical height tests passed. Confirm no new lifetime leak in low-speed flows or false plane breach on huge visual radii.
- [~] **P3 grouped birth bands, source candidate:** the old Source-spread sampler froze any coordinate whose Source was exactly on a world boundary, and clamped other outlying high-Spread samples to ±WORLD_HALF. Thus high Spread could **increase exact-face pileups** and closely spaced linear stacks. R42 rejection-samples actual in-volume transverse births with no coordinate clamp; when the bounded inlet is crowded, it defers admission and drops that tick's credit rather than introducing a coincident new ID or queuing a burst. Author-authored Columns remain purposeful and untouched. This fixes a clear placement defect but **does not prove that all synchronized bands are gone**, especially where music asks for high counts faster than a narrow source can physically pass. Required: startup vs mid-song separate snapshots, per-ID birth timestamps, source/end projected positions, spacing distribution, Compare Columns 0 vs >0 and Spread 0/1/4, source on floor/ceiling/walls and oblique paths; prove bounded population does not permanently starve and camera doesn't relocate births.
- [ ] **P5 Bounce motion still unacceptable:** `_bounce()` moves each pair by `min(overlap*(1-exp(-dt/.35)), WORLD_UNIT*.2*dt)`; at 90 Hz this caps total separation correction at ~0.02 world units per frame, has **no persisted outward collision velocity**, and re-applies after relative stream motion, consistent with operator-described jittering recontacts. Do NOT merely turn the position cap up: that can teleport/interpenetrate clusters and cause visual popping. Next source slice: stable-ID/cluster-aware bounded separating impulse + sustained, smoothly damped physical recoil on the EXISTING logical clock (no timers, no render physics), retained only for Bounce (not Fuse/Pop); test finite penetration, post-collision minimum separation, rebound impulse, no rapid re-hit, symmetric near/far mass response, 30/60/90 Hz invariance, physical target vs visually eased radius, and existing cluster/wake parity. Keep collision-scope and share authoring unchanged.
- [~] **UI two native failure gates:** R41 Windows yielded `F........F..` (2 failed, 10 passed). Test 1: `WidgetHoverEditGlyphs.qml` top-level item becomes visible, but `findChild(QQuickItem,'hoverEditGlyph-lock')` reports none. R42 gives the four eligible delegates stable string-model identities and retains real QQuick child visibility assertion via recursive `childItems()` (not a weaker metadata-only check). Test 2: EB native Settings control tooltip expected raw `control.tooltip` after R41 deliberately wrapped it in HTML. R42 compares Qt-rendered, whitespace-normalized `QTextDocument.toPlainText()` against the authoritative spec text for both widget and row; does not discard the tooltip wrapping or any `[NEEDS AUDIT]` warning. Both native tests still need Windows rerun.
- [~] **Glyph polish:** bottom-left geometry retained. Close X artwork ~10% smaller, Lock ~10% smaller and Restore ~10% larger, with unchanged 24 px circular hit targets and centres. Glyph-only tooltips ALL CAPS and accurate close semantics **CLOSE & DISABLE WIDGET**; >1000 ms delayed event-driven fade stays. Interaction/child Edit, screenshot capture and glyph fade already operator-accepted; do not regress or crowd main EB priority with finished work.

**R42 focused source gates:** `tests/test_extruded_bubble_r42_source_surface_candidates.py` (surface/deep lifetime split, edge distribution, crowded admission and Settings light mode), previous EB lifetime/simulation/stream tests and glyph source tests. **Windows targeted native**: `tests/test_r39_hover_edit_qml_native.py`, `tests/test_extruded_bubble_lazy_bucket_ui.py` with `.venv\Scripts\python.exe --noconftest -p tools.pytest_qt_noenv`. See `Docs/Reference/R42_EB_Surface_Birth_Glyph_Test_Audit.md` for source/geometry rationale and limits. **No EB visual item, bounce collision or native test is accepted.**

#### EB-R37 — 2026-10-21 three-log Settings failures, finite population transport, dolly/surface candidates (ALL UNACCEPTED)

**Priority-ordered next work (the older EB-R36...D/B/C/A checklists remain authoritative and MUST NOT be removed, condensed, or checked off):**

1. - [ ] **P0 Settings lifecycle barrier, strict and fail-closed.** `logs814d70270a.zip`, `...a2.zip`, `...a3.zip` are CUMULATIVE snapshots, **not three independent full histories**. The final snapshot contains **four distinct** `reason=settings` timeouts (~01:38:41, 02:48:48, 02:50:37, 02:55:10), while other Settings retirements apparently complete. Each failure reaches `qobjects={}`, `resources=[]`, `thread_work=[]`, `global_subscriptions=[]` but retains exactly `QuickDisplayUnit:1`, `QuickDisplayVisualizerOwner:1`. Presentation owner retires, so do not call it a control-builder time-budget failure. Attribute surviving strong referrers with the already available failure-only diagnostic ownership snapshot (diagnostic product; no `[PYTHON_OWNER_REFS]` in supplied normal logs); inspect the retirement-completed signal, manager's `_retiring_quick_units`, retained callback/signal closures, and visualizer owner lifetime **per generation**, comparing EB/Neon Lake and lightweight scenes. A code repair needs a recorded retaining edge and native rerun; do not extend eight seconds, force GC on a healthy frame, detach a live owner, bypass barrier, or add a second cleanup poll.
2. - [~] **P1 audio/timing and per-ID radius/energy.** Current log has 512-sample loopback frames, e.g. 02:55:01 `samples=512`; no parallel controlled 256-sample capture or per-bubble body/visual-radius telemetry is supplied, so the previously reported ~80% judder reduction at 256 remains useful OPERATOR evidence, not numerically isolated proof. Restore exact BTF/R-105 temporal contract with actual music and trace each stable ID's body target/visual radius/capture timestamps; reproduce continuous slow→fast→slow transitions, distinguish 512 block admission from compositor cadence, and verify visual Smoothing=1.0 affects only pixels not musical AGC.
3. - [~] **P2 stream/drift/musical range authority.** Existing `speed_target`, `drift_target`, `emission_target` multiply interpolation by a separate `activity`; slow→fast→slow remains visually flat and the authored low/high handles are not literal endpoints. Quantify music→logical targets→world velocity and pixel displacement without adding capture DSP/timers. Preserve idle +10% exception (not ocean surface), fast attack and slow decay. Check all nine ranges from EB-R33/R34 (including ray, small and large size/occupancy and bead counts).
   **New operator capture (2026-10-21, 512 audio block):** Stream and Drift remain
   perceptually motionless across music passages, changing obviously only idle→playing.
   Confirmed source route: `extruded_bubble_simulation.advance()` computes
   `change_drive`, applies `activity = min(1, idle_rate*1.10 + 1.6*level)`,
   follows speed with 0.68 s attack and much slower decay, follows drift with
   0.20 s attack / slower decay, then moves ordinary IDs by `speed*dt` and
   small lateral sine wander. Both ranges are logically connected but endpoint
   semantics are disputed. **Action:** record timestamped 10–15 s slow→fast→slow
   with `change_drive`, `activity`, `speed_target`, `self._speed`, `state.stream_speed`,
   `state.travel`, `drift_target`, `self._drift`, stable-ID XYZ and projected px/sec.
   Test whether motion plateau is (a) normalized-band saturation, (b) gate multiplication,
   (c) slow 0.68 s attack/held high, (d) tiny world-unit lateral displacement,
   (e) projection/camera angle or (f) slow transport through the view. Compare 2D
   Bubble acceptance with no additional AGC/polling. Do not proclaim fixed on a
   logical speed test or increase random gain without evidence.

4. - [~] **P3 emission/admission/retirement physical parity.** **R37 candidate**: musical count reductions now stop admitting bubbles at Source instead of marking downstream live IDs `leaving` midstream. Authored Source→End sets an EOL fade trigger for ordinary large/small IDs, preserving .9-second opacity release and wake retirement; absent path retains legacy physical bounds. No existing target count, GL geometry or authored preset changed. This can temporarily leave more live bubbles than their musical target, especially if stream velocity approaches zero; residence remains bounded by per-population limits/MAX_BUBBLES. **Native falsifiers:** target reversal before End, intermittent silence, constant very-low speed, diagonal/end-inside-volume stream, boundary exits before End, path edits while IDs are in flight, clusters and popped IDs, no popping/teleporting at source/end. Requires measuring whether 0.9-second fade after crossing End is perceptually late; do not call it a completed source/end lifecycle. GPU free chains/specks still have the documented persistent-birth ambiguity.
5. - [~] **P4 physical camera limits, water surface and lens/DoF.** **R37 candidate** increases EB-only `scene_scale` admitted range from 0.5–2.0 to **0.2–5.0**, giving nominal orbit-pivot dolly distances 75→3 world units, no FOV change, no Spectrum/Sphere/Neon modification and no preset rewrite. Surface-only Y clamp remains in `physical_camera`; verify no hidden held-key travel above the plane and no penetration. At near or inside a large sphere, original `coc > 1.5` near-layer switch and lens circles still operate; no explicit giant-covering-lens cull or comprehensive near DoF is proven. Compare on-screen near focus, covering >50% of the viewport, behind-eye cases, fused clusters and occlusion, especially where enlarged dolly allows the lens inside geometry. No camera-relative spawning allowed.
   **R41 photographic geometry comparison (Sunlit Surface):** operator provided
   Light, Ray and Stream 3/4 editors showing distinct physical paths, a camera
   outside the normalized source volume, and one native underwater screenshot
   looking up at a broad luminous surface. These alone do not prove source→pixel
   alignment: editor is an oblique WORLD projection, not the camera render, and
   perspective plus lens/eye position change where the same 3D point lands.
   **Action:** add a DEV-only static world-axis/source/end/camera/aim marker projection
   using the *production* `physical_camera` matrices to both editor and image,
   compare precise 2D pixel coordinates at one captured snapshot, verify handedness,
   scene origin, normalization, camera offset and surface-bound eye, never use
   visual guesses or alter FOV to align a view. Screenshot currently shows a
   pleasing broad surface and clear shafts, not a geometric proof or acceptance.
   **Sunlit Surface authority distinction:** `scene_knobs` derives a distant sun
   direction from `light_direction`; independent `ray_path` gates a finite beam
   region. `light_on_screen` uses sun direction, not the local Light Source marker;
   hence the two editors need truthful labels and an explicit choice whether
   Surface rays should inherit the sun axis or remain independently spatial.
   Deep Light is intentionally different: Ray Source is linked to Light Source,
   Ray End stays independent. Prove both modes' visible rays/glow against actual
   camera projection and any translucent-object attenuation before claiming parity.

6. - [~] **P5 collision Fuse/Pop/Bounce visual force/rarity.** `_collide()` creates contacts only when **physical** `distance < sum(current_radius)` and `alpha >= .6`; the `Pop` action does exist but fades alpha over **2.4 seconds**, with no clearly independent visual pop/impulse. `_bounce()` caps correction per step by `min(overlap*(1-exp(-dt/.35)), WORLD_UNIT*.2*dt)`, a deliberately weak overlap-only response that can remain imperceptible until meshes interpenetrate. Do not infer 2D screen overlap equals 3D contact. Capture pair ID, 3D separation/overlap, action chosen, alpha trajectory and screen-space contrast. Provide optional diagnostic per-action forced scene, not a production per-frame logger; no unrequested violence or strong spring action. Popped/fused wakes must keep exact emitter identity and fade.
7. - [~] **P6 Sunlit Surface coverage.** GLSL `basinWater` previously multiplied the *entire* sky/surface by `window = smoothstep(.56,.7,ray.y)`, which makes oblique upward views largely resemble plain water and only a narrow near-vertical patch read as a surface. **R37 candidate** keeps a low continuous 30% window with a wider raised-angle shoulder (0.12→0.68) while preserving higher sun/refraction highlights. GLSL source edited, NOT compiled here; must inspect a moving camera from many angles, all surface presets, horizon/waterline, physically plausible total reflection, colour consistency, GPU cost and no global blowout. Does not alter Deep Light. Mark [~] even if code compiles.
8. - [ ] **P7 visual/fidelity regression backlog remains:** P1/P7 glass specular/double rim/roundness and excessive speckles; ray intra-song modulation vs source/shaft/clamping, particle direction/lifetime and optional glow, cluster DoF, near pixelation, frame-time and 3D projection distortion, size-dependent overlap and wake fidelity. Existing authored presets remain editable and untouched. No source test or operator note closes these failures.

**R37 test ownership:** `tests/test_extruded_bubble_r37_lifetime_zoom.py` exercises inward physical zoom independent of FOV, individual identity retention on count reduction, and fade at the authored End; `tests/test_extruded_bubble_simulation.py` updates its old *midstream-retirement* assertion to the new desired no-midstream-drop contract while preserving population cap/identity checks. 31 focused Qt-free tests passed here. The R37 surface GLSL edit and native camera, Physics/GL, lifecycle, and recorded-audio acceptance remain unexecuted. Focused Windows run only, from the extracted tree using `& '.\.venv\Scripts\python.exe' -m pytest --noconftest -p tools.pytest_qt_noenv ...`; no environment variables, builds, or chunked suite. Do not equate numerical/syntax results to visual success.

#### EB-R36 — Extruded Bubble Settings tooltip coverage and operator-facing audit warnings (ALL UNACCEPTED)

- [~] **Every exposed control now explains its intended effect.** Audited `core/settings/visualizer_mode_settings.py` EB spec: 57 bucket controls, 36 had no tooltip and 21 had one. Added or refined all 57 (including toggles and colour swatches) without changing their identities, limits, music curves, runtime, canonical defaults, or seven authored presets. The generic Settings builder now also sets the EB row tooltip, so moving over its label as well as the actual editor/swatch can reveal the description; other modes are untouched. Native PySide6 hover/lazy construction is NOT verified.
- [~] **23 controls visibly carry `[NEEDS AUDIT]`, AFTER a description of what the control is INTENDED to do.** This is a discoverable warning, not an indication of automatic failure or permission to change the preset. Preserve the marker until the affected source → logical output → renderer uniform → native pixels or real recorded-music behavior is demonstrated and the operator or a capable local agent visually accepts the result. Do not remove it merely because a Qt-free test passes or a new source candidate was implemented.
- [ ] **All nine music-linked quiet→loud ranges must be audited individually**, as already listed in EB-R33/R34: Ray Strength, Large Bubbles, Small Bubbles, Bead Chains, Stream Speed, Drift, Breathing, Small Bubble Pulse, and Particles. The tooltip tells the intended meaning of both handles first, then `[NEEDS AUDIT]` explains the present mismatch or visually rejected response. Never state that an endpoint is literally reached at the pixel layer without verifying the intervening musical followers, activity scalars, spatial admission/retirement, shader gain and actual displayed values.
- [ ] **Additional tooltip-marked authority/visual checks remain open:** Deep Light Source and Light Strength, Ray Source/End and Flicker, Stream Source/End, Sustained Response, visual-only Smoothing, Camera Position/aim/surface bounds, Clarity, Rim Glow, Sparkle, particle Glow Reactivity, Focus and Aperture. These connect to existing EB failures, not new acceptance gates or superseding checklist owners. Audit musical attack/decay without flicker; stream endpoint fade and native pixel parity; optical edge/stretch/DoF; and the actual lifecycle-safe Settings/editor interactions. Preserve all operator rejections and previously documented numeric evidence.
- [~] **Focused checks only:** `tests/test_extruded_bubble_tooltips_contract.py` checks all 57 texts and markers without Qt; `tests/test_extruded_bubble_lazy_bucket_ui.py::test_every_eb_bucket_constructs_and_hydrates_in_real_settings_page` now also checks visible widget and row tooltips after lazy construction. Run Windows tests using `.\.venv\Scripts\python.exe`, `--noconftest -p tools.pytest_qt_noenv`, and no env-var changes. The latter native gate is pending. Avoid builds and the chunked suite.
- [ ] **No closure/retune from this copy pass.** EB temporal fidelity, lifecycle barrier, rays, camera, bubbles, particles, stream lifetime, glass, lens, range response, performance and all other open operator issues remain exactly as before. Do not downgrade or mark visual items `[x]` for a tooltip change.

#### EB-R35 — documentation/guardrail audit and R34 two-test repair (NATIVE VERIFICATION PENDING; NO VISUAL ACCEPTANCE)

- [~] **Operator focused Windows result (2026-10-21):** 15 passed, 2 failed in 3.64 s: `test_extruded_bubble_lazy_bucket_ui.py::test_r34_volume_aim_edits_existing_pose_without_touching_lens` and `test_extruded_bubble_r34_alignment_candidate.py::test_camera_editor_retains_shared_mapper_and_uses_existing_yaw_pitch_not_fov`; console also printed `encodings/cp1252.py:23 UnicodeDecodeError`. No full failure trace was supplied, so assignment of the decode error to a particular assertion was initially an inference; same-tree Qt-free source-contract checks independently pass here. **No native result is inferred** from that fact.
- [~] **Windows source read fixed:** the R34 contract test read two UTF-8 source files using bare `Path.read_text()`. On a cp1252 Windows locale, that can fail during decoding before reaching any assertion. Specify `encoding='utf-8'` for both reads; future text-source probes must name UTF-8 explicitly. No source contract assertions were weakened.
- [~] **Camera Aim physical-eye precision candidate:** `SceneCameraPosition.admit()` rounded offset to 4 decimal places, while the native test demands eye invariance to 0.0001 world units. Direct simulation of the test input gives ~0.000516 unit drift at 4 digits; 6 digits lowers maximum error below 0.000006. Change only offset serialization precision (4→6), preserve all clamps, lens, orbit, pan, preset and visual authority. Add a Qt-free camera-eye numerical regression. Native Test `test_r34_volume_aim_edits_existing_pose_without_touching_lens` still **must be rerun**; a failure at any other assertion needs its full traceback, not test relaxation.
- [ ] **Operator rerun, focused only, from the actual running working tree** using repo-root `.venv\Scripts\python.exe` and no env-variable changes. Prefer `--noconftest -p tools.pytest_qt_noenv` for the three affected files: native lazy Settings, Qt-free R34, and source/end. Do not request another chunked suite or frozen build. No full Qt acceptance, live pixels, lifecycle or QML ownership can be inferred from this slice.
- [~] **Handoff hazards documented:** references to operator-held EB Lab/Evidence assets are external evidence pointers, not missing project source; `README.md` had obsolete `Q` exit wording; `Index.md` named optional, absent checkpoint files; the plan used bare `py -3.14` despite the operator's `.venv` rule and assumed unrelated repository writes; default Qt `tests/conftest.py` mutates `APPDATA`/`LOCALAPPDATA` against the standing no-env test rule. Do not silently alter the test fixture or point tests at real settings. Use the opt-in no-env fixture for this narrow gate, and schedule harness-isolation refactor separately if it affects other suites.
- [ ] **Existing EB failure inventory UNCHANGED:** Settings open/lifecycle barrier, camera/input and view, 256/512 temporal judder, big/small breathing and count saturation, ray intensity, streams, particle/wake lifetime, glass/DoF, spread, deep light positioning, all range slider semantics, all native performance/visual gates remain open. No checkbox may move to `[x]` solely from this documentation or focused regression repair.

#### EB-R34 — Deep Light emitter alignment, real camera look target, spread and actionable range audit (ALL UNACCEPTED)

- [~] **Operator observation, not acceptance:** with the physical camera, untouched Preset 1 now looks appreciably better than early EB builds. This is encouraging visual evidence for camera fidelity, **not a pass** for any camera, ray, breathing, material, temporal or life-cycle failure. User subsequently discovered zoom worked but had reached its travel limit; do not call zoom broken solely from that episode.
- [~] **Deep Light source mismatch candidate:** operator screenshot shows a luminous orb on one side and a dim shaft/light mass elsewhere. Root wiring used **different Source positions** (`light_direction[:3]` for the visible Deep Light/core glints and `ray_path[:3]` for shafts), while some effects followed only a directional vector. In Deep Light ONLY, renderer now takes the physical Light Source as the actual ray origin, retains independently authored Ray End/fan shaping, and points deep-water directional terms at the emitter from the actual eye; reflections/glint proxies still take the same physical emitter position. The EB oblique Ray editor shows the effective linked source, and dragging it updates Light Source via the existing lazy Settings/persistence owner. Surface mode retains independent light/ray paths. **Falsifiers:** move Light Source and Ray End separately in a moving camera; inspect visible core, shafts, glints and frame pixels from front/behind/off-axis; confirm exposure/attenuation after bubbles and particle fog; no inverted source/endpoint, hidden stale Ray Source control or broken preset/preset-switch behavior. Candidate [~] even if source coordinate tests pass.
- [~] **EB oblique volume control refinements:** retain shared `ScenePathMapper` and authored six-coordinate paths; EB `SceneVolumeMapper` now paints two subdued forward-view guide rays from actual camera marker, a central line and a draggable **Aim** dot. The aim gesture computes camera yaw/pitch from eye→target using current world units and writes the EXISTING `extruded_bubble_turn`/`extruded_bubble_tilt` pose on final commit, not a second camera or FOV control. First-open/preset hydration and the lazy cache continue to own widget creation; preview changes are local until commit. Hide the verbose adjacent source-coordinate label and on-widget keyboard instructions (accessible description retained); legend colour the **whole words**, not just the dot: cyan Start, amber End, violet Camera, pale-violet Aim. New controls remain world-coordinate independent of lens angle. **Native mandatory:** drag Aim from each of Light/Stream/Rays/Camera, change camera position midway, save/reopen Custom, switch presets and reset R; compare heading on card, no unwanted FOV/zoom shift, no duplicate signals, false Custom conversions, lifecycle stalls or broken tab-key interaction. The screenshot's cramped 3/4 cage and off-volume camera projection still warrant operator review.
- [~] **Separate BUBBLE and PARTICLE spread:** previous `Columns` only quantized bubble lanes and was NOT an overall spread control. Bubbles were emitted from a small fixed transverse patch; procedural specks, free bead chains and marine snow each had other hardcoded path widths. New `Bubble Spread` in Bubbles and `Particle Spread` in Particles are independent 0..4 physical-width multipliers, **default 1.0** (exact original widths absent source edits) and neither changes musical gain/count/stream speed. Ordinary bubbles keep their authentic Source births, physical world bounds and stable identities. Particle spread affects free chains, snow and specks, not attached fizz, and preserves source/end fading and original cloud pattern; broader widths may be clipped at world boundaries. **Visual acceptance:** narrow/wide diagonals, floor/ceiling paths, Preset 7 and P1, banded particle visibility, camera travel through near stream, spreading along each axis, birth/fade at volume limits, renderer cost and absence of interior teleports. No preset snapshot changed; operators may author spread per preset.
- [~] **Surface-only camera boundary:** previous world camera applied underwater eye Y clamp even in Deep Light, despite no water-surface scene. `physical_camera(...surface_bound=...)` now retains the ceiling only in Sunlit Surface and permits Deep Light physical travel above it; no FOV/dolly expression changes. Renderer and Settings preview both follow Light Type. **Native checks:** continuous WASD, Aim, position drag, reset, switching Light Type and all near-surface views. Verify the underlying flight position itself doesn't accumulate hidden beyond-ceiling coordinates when the renderer clamps its visible eye; prevent collision with the real surface in surface scenes, and preserve Neon Lake's separate terrain-underneath limit. Not accepted.
- [ ] **Turn each EB-R33 Range audit finding into an explicit repair-and-falsifier task; no curve retunes in R34:**
  - [ ] **Large Bubbles count:** distinguish target count vs visible per-ID admitted/retiring count; slow/fast/soft recorded passages, breadth/saturation and cap evidence; full right endpoint only at meaningful broad energy, no burst. [~] population candidate remains unaccepted.
  - [ ] **Small Bubbles count:** same separate saturation/admission trace plus persistent small-radius judder at 512 vs 256; no count pop disguised as size snap; independent left/right reach.
  - [ ] **Bead Chains count:** replace/justify max-band `state.level` reaching the upper handle too easily; per-ID birth/retirement opacity, continuous count and source/parity under quiet→sustained→fast→soft music.
  - [ ] **Stream Speed:** determine whether left/right sliders should be literal physical speed bounds once idle energy is separately owned. Remove/reinterpret compounded `activity` without losing fast attack/slow release; record physical velocity and actual pixels, not just onset/play edges.
  - [ ] **Drift:** similarly audit activity/soft-top/held response against authored bounds and 2D BTF; quantify lateral distance per bubble through intra-song changes and real resting motion.
  - [ ] **Particles:** separate emission/count vs luminosity and optional glow reaction; make left/right visible-intensity semantics explicit, verify not pinned in P7, preserve attractive warm/cool balance and no new birth pops.
  - [ ] **Large Breathing:** low handle must control its own quiet contraction/response rather than only the high handle setting silent radius; soft ceiling and held-body crest must allow meaningful dynamic headroom without size snapping.
  - [ ] **Small Bubble Pulse:** independent low/high meaning and smoothed per-ID visual radius; compare 512/256 capture and original 2D follower on the same recording, no shared state-step impression.
  - [ ] **Ray Strength:** a separate silence baseline and reachable loud endpoint; resolve 0.90 driver cap plus post-interpolation `0.03 + 0.97*drive` suppression. Prove meaningful within-song ray intensity in final HDR/bloom pixels without unpleasant flicker; keep transient fast-ramp/slow-decay, authored limits and attenuation through objects.
- [ ] **Independent gate remains:** sporadic strict Settings lifecycle `QuickDisplayUnit`/`QuickDisplayVisualizerOwner` survivor, near-field defocus switching, specular/roundness/double rim, 256/512 judder, stream/drift, fading emission, glass, P7 glow, GPU shader registration, scene cost and all previously preserved EB-D/B/C/A checklist items. No items close automatically on Qt-free tests, shader link or subjective before/after impressions.

#### EB-R33 — EB quiet→loud Range authority audit (DIAGNOSTIC ONLY; ALL UNACCEPTED)

- [~] **Audited all NINE EB dual-handle `Range` controls** from `core/settings/visualizer_mode_settings.py` through actual simulation/renderer consumers. They are not dead controls, but the apparently uniform "quiet → loud" UI currently disguises **multiple different musical authorities and nonliteral endpoints**. Do not retune authored preset values or declare musical response accepted from this wiring audit. New reproducible Qt-free `tools/visualizer_replay/extruded_bubble_range_energy_audit.py`, with accompanying fast wiring regression, reports 10-second synthetic steady-band results; actual recorded music, onset-rich passages, rendered pixels and operator approval are still required.
- [~] **Large Bubbles / Small Bubbles (count ranges):** `frame_runtime.controls_from_parameters` → `simulation._population_drive` (band *breadth* raised to power 1.8, 0.28 s attack/1.05 s release) → interpolated targets → bounded spawn/retire. At zero bands, target equals left count; all bass/mid/high at 1.0 eventually requests right count. **Targets are not immediately visible counts** because admission, fades, physical world/source and population caps still apply. Operator previously rejected excessive live saturation; no validated result.
- [~] **Bead Chains (count range):** separate render-side `_procedural_fill`: left + (right−left) × `state.level`, multiplied by 12 chains/step and detail share, then rounded to instanced procedural population. `state.level` is a max-band-based intensity follower and can saturate early on one band. This range is **not** controlled by `_population_drive` and can appear pinned/stepwise independently of big/small counts. Source/end and lifetime parity remain [~].
- [~] **Stream Speed / Drift / Particles (amount ranges):** each first interpolates against `change_drive` (a composite of `level`, small-body envelope and flash), then uses extra sustain/flash lifts, `_soft_top` (Drift/Particles), and a separate `activity` multiplier (Particles `max(0.25, activity)`). Consequently **the left handle is not the actual silence output**, nor is the upper handle guaranteed at maximal steady music; some lifts may also exceed an authored high control target. Their independent attack/release followers are still present. A quiet→loud slider cannot currently promise a literal quiet-to-loud output span, and no visual song-section fidelity has been accepted.
- [~] **Large Breathing / Small Bubble Pulse (reaction-strength ranges):** both feed `_reaction_scale(pair, independent_body_envelope, expansion)`. Critically, **rest is calculated from `max(pair)` alone**, including when musical drive is ZERO, while the actual low handle participates only in the drive-dependent expansion term. Thus the left handle **does not independently define resting bubble size**; moving the high handle can change silent/rest radius. This is a concrete UI/behavior mismatch worth separating from max-Smoothing judder, radius plateau and the earlier reduced held-body coefficient. Do not flip those production curves without a recorded visual A/B.
- [~] **Ray Strength (brightness range):** `state.rays` has its own phrase/onset follower and is capped at **0.90**; then `ray_strength` computes `(left + (right-left)*driver) * (0.03 + 0.97*driver)`. Thus at silent driver=0 the *left* handle contributes **only 3%**, not its literal setting, and because the driver cannot reach 1 the *right* endpoint is mathematically inaccessible. There is no independent stable-intensity → full-authorable-ray-brightness span. This directly strengthens the operator's reported strong idle→play but pinned intra-song appearance; compare before/after HDR composition and bloom, not logical brightness alone.
- [~] **Quantitative synthetic illustration, 90 Hz/10s, controls 20%→80%** (NOT P7 or actual Ragdoll): silent outputs normalized stream=0.0132, drift=0.0132, particle emission=0.0500, ray brightness=0.0060; all-bands steady=1.0 gives stream=0.6571, drift=0.6691, emission=0.6211 and ray brightness=0.1266. In the same run, counts reach requested 16/48 and bead chains 8/8 before detail tier. Large/small reaction radius multipliers are ~0.13x in silence and 1.54x/0.43x on sustained full bands, respectively, reflecting **response dynamics** rather than exact low/high radius guarantees. No onsets in this probe: a transient can raise these targets further. **Next candidate direction** (not implemented): give every Range an explicitly documented, shared quiet/live interpretation without conflating different energy bands; retain BTF/AGC separation, soft attack/slow release and operator-authored endpoints. The Ray and breathing contracts deserve priority once native R32 Settings is accessible.
- [ ] **Narrow native check, NOT another chunked suite**: `& '.\.venv\Scripts\python.exe' -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_extruded_bubble_flight_keyboard_native.py tests/test_extruded_bubble_lazy_bucket_ui.py tests/test_extruded_bubble_range_energy_audit.py`. The first two exercise real Qt Settings and Shift+WASD; the third is Qt-free source/simulation wiring. Run the audit with `& '.\.venv\Scripts\python.exe' tools/visualizer_replay/extruded_bubble_range_energy_audit.py` if numbers are useful. Everything visual, including ray variation, count/pulse peaks, audio-block temporal fidelity, Settings construction, frame time and lifecycle remains unaccepted.

#### EB-R32 — Shift+WASD rotation and Settings-builder native crash gate (ALL UNACCEPTED)

- [~] **EB framed-camera keyboard candidate:** plain WASD travels relative to camera heading; Shift+W/S pitches up/down; **Shift+A/D yaws left/right**, functionally equivalent to existing Q/E yaw left/right. Q/E remain valid alternatives and remain removed from global exit. Switching Shift while a travel key is held immediately changes its role; releasing Shift restores ordinary strafe/travel. Combined Q+Shift+A and E+Shift+D are additive, key repeat cannot accumulate intent, and all motion uses the existing logical frame clock and single owner. No FOV, zoom, Scene Scale, new timer, new presentation authority or per-frame Settings persistence. Free-form Spectrum and Sphere keep their legacy keys, Neon Lake remains only an audit note. **Native multi-key, dual-display and focus/lifecycle behavior unaccepted.**
- [~] **Repeated blocker `UnboundLocalError: describe` upon entering EB Settings:** operator supplied the identical traceback from `ui/tabs/media/spec_mode_builder.py` **line 361**. The previous R31 source candidate has `label = QLabel(describe(widget.value()))` at **line 363**, with a branch-local formatter already assigned; the earlier source snapshot has it at **line 361**, with missing volume-branch initialization. **Traceback line numbers match R30 rather than R31, but the operator has reported unusual Foundry selection behavior; do not presume which copy actually launched or blame operator deployment. Check the runtime source/build fingerprint before concluding anything.** R32 strengthens construction by assigning `describe = control.text` *unconditionally* before the mapper branches, retaining all initialization, lazy buckets, and authored values. A new unique `EB-R32` source marker distinguishes deployment. The issue remains [~] until the operator can actually enter the native EB Settings builder from the launched application.
- [~] **New narrow native tests, no whole chunked suite:** `& '.\.venv\Scripts\python.exe' -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_extruded_bubble_flight_keyboard_native.py tests/test_extruded_bubble_lazy_bucket_ui.py` exercises native QKeyEvent routing, all currently registered visual control classes and every EB lazy-bucket expansion through the actual `VisualizersTab`/SettingsManager page. It explicitly requires the lazy-built-set membership after each expanded bucket to catch Qt signal-slot exceptions that can be printed without failing a test call. Can be run from the active working tree; it does not build the app. Source-only/Qt-free regressions are **not** proof of Settings construction, nor of a deployed EXE/source version. Run the test using the **same on-disk tree the application launches**; if the program's traceback still has line 361, audit the actual launch/build and source copy first. Avoid environment-variable setup and preserve the strict lifecycle barrier. Qt native result and application Settings entry both [~] until observed.
- [ ] **Independent failures unchanged:** recurrent `QuickDisplayUnit`/`QuickDisplayVisualizerOwner` barrier timeout, 256-vs-512 temporal judder, small-bubble radius snapping, extended large peak, stream/draw disparity, light-ray intra-track reaction, particle lifetime/source parity, camera parallax and projection, visual/GL performance, and full 3D volume editor visual/drag semantics. The QFont point-size warning is not tied to the UnboundLocalError by this evidence. Keep every preexisting operator-authored failure/checklist and preset unclosed.

#### EB-R31 — Framed physical-flight controls + blocked Settings construction (ALL UNACCEPTED)

- [~] **EB-only keyboard candidate, no change to freeform Spectrum/Sphere:** Q yaw left, E yaw right, Shift+W pitch up, Shift+S pitch down, unmodified WASD flies relative to the CURRENT view (W forward along view including pitch, S backward, A/D strafe). Both yaw and travel derive from the same physical `camera()` basis; flight translates `extruded_bubble_camera_position` directly, not Scene Scale/zoom, off-axis projection, FOV or simulated world entities. Mouse Alt+left orbit, Alt+right scene pan, Alt+wheel card sizing and R/glyph camera reset retain their separate owners. Keyboard motion is held on the existing logical capture timestamp in an immutable `FramedFlightMotion`; no OS-repeat stepping, new timer, per-frame Settings write, preset authoring or freeform mode key binding change. Key releases settle the one camera position before final once-per-gesture Settings persistence; preset activation rebases, R clears, and mode admission refuses non-EB consumption. Native flight, both displays, no-stuck keys on focus/mode swaps, all axis signs and physical approach remain [~] pending visual validation.
- [~] **Q unbound from global exit:** `RuntimeInputOwner` no longer treats Q as an explicit exit key (including outside EB). ESC remains exit, as do the ordinary product exit policies. Mode-admitted EB Q is always consumed for yaw while held; its release and repeat do not cause exit. This change is intentional and global. Other modes still have the old WASD view-orbit bindings; do not mistake their lack of Q navigation for a broken new camera.
- [~] **Critical EB Settings page exception candidate:** operator cannot enter EB Settings, repeated `UnboundLocalError: cannot access local variable 'describe'` from `ui/tabs/media/spec_mode_builder.py:_build_visual_control` for the new `SceneVolumePath`/`SceneCameraPosition` branch. Its constructor assigned neither `describe=control.text` nor the admitted `widget.setValue(value)` before `label = QLabel(describe(widget.value()))`. Add both without disabling lazy buckets or removing widgets. Qt-free source regression and a focused native `QWidget` constructor regression added; native first-open Settings, alternate bucket orders and lifecycle barrier remain unaccepted. The adjacent QFont invalid-point-size warning is not established as the cause, and is independently open if repeated.
- [ ] **Neon Lake later camera-controls audit, deliberately NOT implemented in this slice:** assess whether framed Neon Lake uses flight at all and how the shared framed-cam capability could provide Q/E yaw, Shift+W/S pitch and WASD scene travel without breaking its accepted geometry, bounded framed view, water/horizon clipping or controls. A Neon Lake camera must NEVER rotate below its terrain/geometry underside on the vertical orbit axis. Do not accidentally apply EB's ±8-unit underwater translation or open volume movement to the landscape. No change to freeform Sphere or Extruded Spectrum.
- [ ] **All earlier failures still open:** 256-vs-512 block-size judder and 2D BTF comparison, breath release/pinning, population admission peaks, particle/chain/fizz origin/end and birth/fade, ray phrase brightness/material attenuation, projection edge stretch, deep light, GPU/frame-time and Settings lifecycle owners. A successful synthetic flight or Settings source fix is not operator visual acceptance. See Investigation §31 for explicit native gates. Avoid requesting another chunked suite; use targeted tests only.

#### EB-R30 — Operator camera reach, oblique shared-volume authoring, and native chunk evidence (ALL UNACCEPTED)

- [~] **Operator cannot reach the particles with the camera:** `logsbae635b6766.zip` has camera pose writes at 2026-10-21 00:02:19, :24, :36, :50 with `extruded_bubble_scene_scale=2.0` (the actual upper limit in the Settings spec). Camera orbit was hardwired around one pivot 15 units away, pan limited to ±0.5, and physical position bounded by a ceiling; it offered no independently editable XYZ eye coordinate. This verifies zoom exhaustion, not the exact unseen distance from the nearest speck. **Candidate:** new `extruded_bubble_camera_position` (normalized physical-world offset) composes with the one renderer `physical_camera` and translates its real `eye` for every downstream shaft, bubble, reflection/probe and particle render pass. User can position the eye inside the ±18 x/z, ±8 y authored source volume even when the starting orbit is distant, while unchanged centred perspective/FOV remains the same. Pan now uses a viewport-aspect-independent real-world translation (direction preserved; its screen magnitude may change); the ocean ceiling remains enforced. R/glyph Home also clears XYZ translation to canonical [0,0,0]. This is source-candidate, **not validated visual camera arrival, near-field quality, clipping or gesture behavior**. Test near/far depth and all pose extrema before acceptance.
- [~] **EB-specific oblique 3D source editor candidate:** `SceneVolumeMapper` gives tilted perspective-free 3/4 cylinder/volume with draggable coloured source/end points, camera diamond, and faint actual Light/Stream/Rays references in the other panels. Use same normalized XYZ coordinates and persisted six-value paths as before; no second scene/world owner, no FOV-affecting preview camera, no preset JSON rewrite. Left drag adjusts XY holding Z; Shift+drag or right drag adjusts Z; PageUp/PageDown adjust selected depth; Tab toggles node. Camera diamond is draggable inside any of these controls and through the Camera bucket. A new live `SceneCameraPosition` descriptor stores three physical offset numbers; marker is calculated by the renderer's own camera function from current Settings view. The older shared `ScenePathMapper` remains in shared controls unmodified, available to all other modes. **Native geometry/hit-test and lifecycle validation mandatory:** drag value parity for all three axes, depth visibility, camera outside-volume indication, migration of legacy two-angle paths, independent path overlay updating when presets change and buckets open in any order, keyboard support, UI styling/hitboxes and correct persist/Custom semantics. Opening closed buckets may create cost; measure rather than relaxing barrier.
- [ ] **Current supplied log also repeats the prior uniform crash 693 times** at render node: `ValueError: uniform uBlock* unsupported value (x,y,z,radius)`. The supplied run captured the pre-fix failure; R29 contains the `glProgramUniform4f` candidate. A native retest of that **exact bug only** is needed. Repeated occurrences are not hundreds of independent errors. No visual before/after claims should be made from a continuously failing renderer.
- [ ] **Chunked suite 2026-10-20 22:17–23:55; do NOT require rerun as routine.** Collection passed. Four chunks: 40/13/18/31 failures, 1,984/2,011/2,006/1,992 passes, one skipped; totals **102 failed, 7,993 passed, 1 skipped** across >20 minutes. Many historical contract expectations concern retired Shockwave/Grid or Neon rendering, but **not all red is stale**. `test_extruded_bubble_recorded_reactivity::test_active_recorded_phrase_has_large_absolute_excursion_in_each_class`: recorded median ~1.7506, expected >1.8; `test_pause_releases_radius_and_every_motion_phase_into_slow_rest`: early displayed-radius release violated continuity condition; `test_extruded_bubble_world_gpu::test_ordinary_and_fused_coverage_share_true_pinhole_projection`: observed ~1.698 vs expected ~1.269 for off-axis coverage (projection/expected-reference discrepancy); `test_qtquick_visualizer_all_modes...extruded_bubble` and native Settings tests also red. Builder spec tests still expect eager control construction and legacy two-value direction equals default, inconsistent with section-lazy/new endpoints; rewrite assertions to prove the NEW contract, not to hide actual bugs. Other failures affect Qt6 shader admission, Neon transparency, clip smoke, scene3D quality and mode defaults. Triage independently from EB rather than sweeping all under stale.
- [ ] **Two separate lifecycle timeouts confirmed in same log:** 2026-10-20 22:42:58 `reason=settings` and 2026-10-21 00:03:21 `reason=application_exit`: both `qobjects={}`, `resources=[]`, `thread_work=[]`, `global_subscriptions=[]` but Python owners `QuickDisplayUnit:1`, `QuickDisplayVisualizerOwner:1`. Do not extend timeout, skip owner retirement or assume UI control construction explains the retained owners. Target residual holder/referrer evidence, scene/runtime weakref and generation-specific disconnect; compare successful lightweight-mode Settings barrier.
- [ ] **All prior reactivity/visual debt explicitly retains priority:** 256/512 audio-block judder (operator reports ~80% better at 256 but still bad; do not equate with pass), small snap and inadequate visual-only Smoothing at 1.0, too-long large inflation and near-peak population, streams drifting insensitive to slow→fast→slow phrases, ray transient lift/pinned brightness, weak or overly bright glass, camera peripheral stretch/near-focus lens quality, free procedural lifetime pops, particle direction and glow tuning. Do not mark any old failure `[x]`. P7 particles are desired artwork, not an instruction to remove them. New camera path must not move particles or stream targets relative to the world.

#### EB-R29 — Crash after ray shadow proxy, procedural source/lifetime parity (ALL UNACCEPTED)

- [~] **NEW operator-confirmed production crash at 23:40:27, render node / shaft uniforms:** `ValueError: uniform uBlock0: unsupported value (-10.840106010437012, 1.3623005151748657, -17.55120849609375, 0.052287131547927856)` at `implementations/extruded_bubble.py:_Uniforms.set` while setting `programs["shafts"]`. New ray occlusion uploads four world-space `vec4` (bubble xyz/radius) values, but the uniform dispatcher only supported length 2, 3, 9 and 16. **Candidate fix:** dispatch four-component tuples with `glProgramUniform4f`, and cache values only after accepted upload (including inactive uniforms). Exact operator tuple is covered by a focused Qt-free mock-GL execution of the real uploader class; GLSL shader link checks do not cover host Python uploads. **Native launch and Preset 7/P1 render immediately**, validate no `uBlock[0..3]` exceptions at active/no-bubble/cluster transitions, no GL errors or new hitch, and capture ray attenuation. Remains [~] until operator/local agent visual check, even if crash no longer reproduces synthetically.
- [~] **NEW source/end parity candidate for free chains and marine snow:** ordinary bubbles and decorative GPU specks already consumed authored `Stream Source -> End`; free bead chains and marine snow still seeded/wrapped through the fixed world volume. The shared GPU bead path now consumes *the same* `stream_source` / `stream_end` world coordinates as specks, advances deterministic free-chain positions and marine snow along that finite line using existing integrated `state.travel` and their previous independent speed factors, fades each near source/end and physical box boundaries, and preserves seeded chain curvature / a wide finite transverse section. No new clock, DSP, buffers, presets or artist-authored control value changes. **Attached fizz is intentionally sourced at its stable bubble's wake emitter**, fading along each parent trail; forcing fizz to originate at global Source would violate the parent-attachment requirement. Check all three procedural families independently under vertical, inverted, short, diagonal, angled-depth and rapidly edited two-node paths, camera orbit/pan, slow/fast music and idle; validate no new half-volume spawning, clipping, scene emptiness or sudden wrap.
- [~] **Pops are not proven eliminated.** Decorative specks use a fixed instance count for each detail tier (music varies `uSpecks` brightness, not their `glDrawArraysInstanced` count), seeded stable paths and near-zero intensity at physical endpoints. However, procedural free-chain/marine-snow populations use `ceil` counts with fractional opacity; if the driven count crosses more than one instance in a capture, **newly admitted IDs can appear at nonzero progress without an individual birth timestamp**. A gentle spatial endpoint fade protects only old identities crossing that endpoint, not an instantly admitted mid-path identity. Attached fizz similarly needs native fade and parent-retirement parity testing. Compare per-ID world path, opacity and actual raster/pixel light at count changes and on fixed-level recycling; if popping remains, consider *persistent birth age on the existing single logical simulation owner*, or bounded seeded cohort admission, not a new independent particle update loop. Leave all parent/wake, bubble, emission and temporal-fidelity rejections intact.
- [~] **Verification only:** Qt-free exact four-float uploader + retry cache tests and shared-path contract checks pass; previous ray/particle, population, source/end and Smoothing standalone probes pass. Legacy native speck GPU fixture updated for the new finite path but **not run** here. Mesa GL4.5 diagnostic links shaft, speck and bead shader stages, with `#version` substitution and an additional unused fragment-only derivative in the bead vertex shim replaced by constant 0 *only in the diagnostic*, not product source. No Windows GL4.6 draw, Qt Settings, material, 256/512 recorded replay, frame-time or visual parity is established. **The ray phrase-range problem, sporadic lifecycle owner survivors, small-bubble judder and all original art failures retain their previous live statuses.**

#### EB-R28 — 256-vs-512 cadence, ray phrase, procedural specks, lifecycle (ALL UNACCEPTED)

- [ ] **NEW operator evidence / BTF:** Ragdoll at audio block **512** retained severe small-bubble temporal judder; block **256** reduced operator-perceived judder by about **80%**, but MAX visual-only Smoothing still feels weak. The supplied `logsbae635b6764.zip` confirms Windows loopback negotiated 512 then 256 at 22:40:34 and the 256 session ran through 22:42:50. This is operator comparison, NOT a proved causal attribution, no firmware/audio-default change, no visual acceptance. Shared BeatEngine source/capture freshness, logical-step spacing, result admission, stable-ID target/display radii and displayed-frame deltas must be measured side by side at 512 and 256 on the SAME Ragdoll passage; read BTF and R-105 before changing time cadence or smoothing. The last 256 session ended `steps=12451 skipped_deadlines=8 slow_steps=1 failures=0 joined=True`: an aggregate success counter cannot rule out 1–2 frame holes. Add a cheap targeted trace before changing AGC or a display smoothing ceiling. Test 2D Bubble side by side. Avoid rejected dead-band/tiny-breath filters. Do not make 256 a mandatory global default without source/pacing evidence.
- [~] **Rays musically pegged within playback (new candidate):** The one-shared-ray driver previously accumulated `0.35*level + 0.45*small_envelope + 0.05*sustain` and could settle near high baseline even when a track had musical changes; onset lift mostly moved cosmetic shimmer. Existing `Ray Strength` range resolves separately in `ray_strength`; no fixed flicker should be introduced. Candidate adds a **ray-only** fast-rise/slow-release mid/bass/high phrase-relative follower, lowers the held contribution to leave crest headroom, and uses each real onset once for brightness (decays continuously, without double-smoothing the flash) as well as shimmer, without adding audio analysis, AGC, timers or per-pixel noise. Synthetic uninterrupted soft→strong→mid→fast→soft probe now makes new changes visible in `snapshot.rays` without playback toggles. **NOT visual success**: compare actual shader luminance before and after bloom across the same recorded clip, multiple authored ray ranges/softness, and with surface/deep sources, avoiding distracting flicker. The earlier finite Source→End shaft and four-bubble attenuation remain [~] as in R27.
- [~] **Procedural particle stream candidates (new):** `SPECK_VERTEX` was already moving seeded particles in the same general `uStreamWorld` direction via integrated `state.travel`; NOT genuinely static. But its world-volume `fract(seed + ...)` admission was independent of the two-node Stream Source/End. Candidate reads that one existing parameter/path, draws a broad seeded cross-section distributed along the actual segment, advects it by **0.30 × the integrated stream distance** (including inherited idle movement), fades in near Source and fades out near End / box boundaries, then recycles; no new clock or CPU per-particle updates. This may alter the attractive P7 speck cloud distribution, especially around tilted surface/floor paths and shallow segment lengths. **Mandatory native comparison** P1/P7 and other presets, scene camera poses, density, clustering, costs, wrapping seams and glow. Particle stream is NOT a new emitter authority; bead snow/fizz origin/lifetime parity, user-authored Source/End constraints and soft passage speed variation remain OPEN.
- [~] **Optional speck glow reactivity:** new typed `Glow Reactivity` slider in lazy Particles bucket, canonical **0.0 OFF**; existing `Particle Glow` and presets remain untouched. With nonzero values, multiplicative bloom lift reads current simulation ray/flash state, not a new DSP/clock; user must verify that this is gentle/transient-linked and P7 never flashes unpleasantly or brightens permanently. No native Qt bucket/load/save/reset or visuals passed yet.
- [ ] **NEW reproducible Settings lifetime failure:** Oct 20 **22:42:50–22:42:58**, `reason=settings retiring_generation=1`: 948 QObjects were initially watched and all retired, but `QuickDisplayUnit:1` and `QuickDisplayVisualizerOwner:1` remained weak-reachable at the eight-second deadline, with `qobjects={}`, `resources=[]`, `thread_work=[]`, `global_subscriptions=[]`. A separate **18:35:58–18:36:06** run shows the same two survivors. Other Settings transitions completed in ~455–785 ms. This is **Python owner lifetime**, not evidence to enlarge/remove the strict barrier or blame lazy controls. Trace **specific reference holders / retention edges** across `DisplayManager`, selected `QuickDisplayUnit._visualizer_owner`, owner `retire()` and delayed callbacks, comparing Neon Lake/EB, empty/ordinary mode, 1 vs 2 screens. Instrument weak owner identity + `is_retired` + generation and trusted GC root diagnostic only when barrier stalls, never add a timer/poll or forcibly forget live owners to appease the barrier. No lifecycle implementation fix in this slice.
- [ ] **Previous open failures all remain:** per-ID small-bubble judder, large-radius crest pinning, population saturation candidate, stream/drift relative-to-song flatness, visual-only Smoothing weakness, startup untagged ramp, early/faded object appearance, camera/peripheral lens distortion, ray transport shadows, materials, wakes, procedural source parity, Qt Settings lifetime, and size/DPR mismatch. Do not close or reduce earlier checklist detail because this slice compiles or synthetic tests pass. See detailed Investigation §28. Visual acceptance remains operator-owned.

#### EB-R27 — Physical source/end controls and bounded shaft attenuation candidate (ALL UNACCEPTED)

- [~] **Two-node 3D direction tool, not a cosmetic extra handle.** In the lazy EB Settings buckets, Stream Source → End, Light Source → End, and Ray Source → End use a shared `ScenePathMapper`: independently draggable S/E screen coordinates and independently editable depth rails, with keyboard targeting and one persistence commit per gesture. The circular UI maps the WHOLE XY world square without truncating corners. Physical coordinates are normalized to the fixed 3D world box; `core/constants/extruded_bubble_world.py` is the new pure geometry constant owner imported by both Settings and logical/render consumers. Original EB light/stream `[around,height]` values from all seven operator-authored presets are admitted to six physical coordinates and recover their original vector directions to rounding precision; preset files are untouched. **Native Qt builder/preset round-trip, lazy lifecycle, accessibility, drag hitboxes and visual appearance are not validated.**
- [~] **Stream physical source/end candidate, still visually unaccepted.** The scene receives `stream_path` from its single Settings authority; the direction is derived from the world-space endpoints, and ordinary new large/small bubbles spawn in a narrow jittered *transverse source patch* rather than a random halfway-up point. Floor/surface/side face axes are held on their authored boundary. On a newly initialized path-enabled activation the old immediate random full-volume preload is bypassed in favor of ordinary bounded/fading admission from Source. This may introduce an undesired initial sparse interval, clustering or perceived underpopulation; visually compare before considering it successful. Existing Qt-free legacy-only callers retain their old admission path. Test free chains, marine snow and fizz origins separately: they are still procedural and not automatically anchored at the ordinary-bubble source, so **whole-scene source parity remains OPEN**.
- [~] **Physical light placement candidate, partial.** `Light Source → End` drives lighting direction and supplies world-space deep-light source to the scene's visible deep light plus each bubble's procedural glint proxy. The remaining environment/probe directional lobe is still only direction-aware, so a translated light does NOT yet behave as a true finite-area positional emitter in every reflection. Surface sunlight is naturally directional. Validate both P1 and P7 and never advertise full per-object positional lighting parity before comparison.
- [~] **Finite 3D ray line and shadow proxy, NOT verified optics.** New independent Ray Source → End supplies physical endpoints to the *production* half-resolution shaft shader. Marched samples and angular fan are tapered to the authored finite segment. The old `Ray Reach` slider remains as **Ray Fan Spread** pending user acceptance, because its former consumer changes angular spread rather than literal shaft length. No preset rewrite. The shaft pass attenuates at most four dominant ordinary bubble proxies (up to 16% each, softness around the source) and a bounded 0–8% aggregate particle term. There is no accurate per-particle ray blocking, cluster/near/cohort shadowing, true multiple scattering, or measured performance guarantee. Full-resolution P1/P7 ray-only before/after, tilted camera, surface vs deep, large/small card and shader/GPU duration are mandatory gates. GLSL 4.5 Mesa offscreen compile AND link passed with 4.6→4.5 diagnostic substitution, **not native GL 4.6 validation**.
- [ ] **Music → ray brightness still appears pinned inside playback.** This pass does NOT declare ray reactivity corrected and does not introduce arbitrary shader flicker. Follow `body_bands → state.rays/_ray_lift → Ray Strength Range → uRays → shaft texture → HDR bloom/composite pixels` on a sustained slow→fast→slow section. Test smooth onset-lift/decay and independent ray fall when the music settles, under both the low/high Range endpoints. Controlled shader compile and connected uniform names cannot demonstrate the requested visible changes.
- [ ] **All previous size/occupancy/judder/camera and lifecycle rejections remain open.** Display-only Smoothing, per-ID radii, harder bubble count peaks and large held-body reduction from EB-R26 remain unaccepted candidates; do not rewrite approved presets, relax the retirement barrier, revert proven 2D Bubble mechanisms or mark an item `[x]` on synthetics. Also retain the explicit preexisting red on untagged playback ramp. See `Docs/Reference/Extruded_Bubble/Investigation.md` §27 for exact owner/read paths and native acceptance matrix.

#### EB-R26 — Interrupted source candidate, first superseding checkpoint (ALL UNACCEPTED)

- [~] **Display-only Smoothing candidate wired in simulation:** `controls.smoothing` now changes only per-stable-ID `visual_radius` attack/release, not music reference/AGC followers, source-body envelopes, onset flash, rays, motion, speed/drift, emission or physical contact `current_radius`. No additional simulation owner, clock or deadband. Rendered shells and wake emitters consume `visual_radius` from one logical owner; contacts/cluster resolution use the instantaneous physical target. Qt-free 390-tick test exercises smoothing extremes and asserts identical music, positions, collisions, clusters, movement and only different displayed radii. Visual surface/wake correspondence, release feel, size-gate and Qt cadence remain to be checked.
- [~] **Large held-body coefficient candidate** lowered from `(0.25+0.75*sustain)` to `(0.22+0.70*sustain)` without lowering authored `breathing` controls or changing presets. This is **not** the accepted 2D solution: 2D uses separate drawn-loud/hero envelope, soft-ceiling and per-ID visual follow. Operator explicitly prefers making the top harder to reach while keeping smooth rises/releases. Keep the candidate available for A/B and measure local peak dwell; do not mistake a lower overall radius for solving pinning, or close the issue.
- [~] **Flow slew after decoupling:** fixed musical flow attack 0.68 s, no dependence on displayed-radius Smoothing. Retain 2D temporal-fidelity checks and verify live phrase acceleration and decay.
- [ ] **NEW operator rejection: counts saturate too easily for both size populations.** Almost any audible music reaches near-max *Large Bubbles* / *Small Bubbles* emission/occupancy; high bubble counts persist across long songs. `_level` is a fast-followed `max(bass, vocal_body)` and `targets` map it linearly into both count ranges, with no separate count transfer curve. Record per-frame source band, level, target/live/retiring population, emission admission credit, and 2D occupancy on matched recordings. Compare monotonic nonlinear transfer, time-in-crest eligibility, and separate fast-attack/slow-decay count smoothing; avoid merely slowing admissions or suppressing the intended maximum. Keep the authored quiet/loud endpoints and exact preset data intact until acceptance.
- [~] **Count saturation source candidate (separate from shell breathing):** added a 0.52 fast-band / 0.48 weighted all-band `breadth` and a monotonic `breadth**1.8` population drive; fixed 0.28 s attack/1.05 s release (same logical tick, no new timer) affects only `large_count`/`mid_count` quiet→loud interpolation. Authored endpoints, admission limits, stable IDs and retirement remain unchanged. The old 2D Bubble maintains fixed authored counts and therefore does not supply this musical count mapping; this is an EB-specific candidate. A single full bass lane now yields fewer than the maximum authored count, while full strength in all bands still reaches the exact maximum. Added Qt-free population curve/regression gates. **[~] is an implementation state only: operator must validate real song occupancy and transitions.**
- [ ] **NEW operator clarification on rays:** idle→playing ray intensity grows strongly but appears visually pegged throughout playback, regardless of Ray Strength range. Need smooth transient-linked lifts and graceful fades, not random flicker, maintaining inter-phrase volume articulation even in loud music. Test `rays` simulation, emitted uniforms, shader pixel luminance after bloom, and verify whether bubbles/particles attenuate rays (currently not confirmed).
- [ ] **Two-node source/end widgets and actual ray start/end rendering are still outstanding IN THIS CHECKPOINT.** Existing single-marker Stream Direction/Light Direction and Ray Reach are unchanged here. Source must be configurable to surface or floor, with bubbles born at real upstream boundary rather than mid-volume; ray source/end must affect the real shaft path before Ray Reach is considered redundant. Do not declare it implemented based on the earlier interrupted progress narrative.
- [ ] **Remaining known red:** untagged synthetic play-ramp still fails the prior startup threshold. Tagged real BeatEngine play-ramp is tracked separately; native playback, source swaps and operator visual acceptance still required.

#### EB-R25 — New source-confirmed smoothing/speck diagnosis (UNACCEPTED; preserve all live failures)

- [ ] **Smoothing is NOT currently visual-only, contrary to operator intent.** In
  `widgets/spotify_visualizer/extruded_bubble_simulation.py`, `soft = 0.5 + 1.5 *
  controls.smoothing` scales the musical-level follower, big/small body references and
  envelopes, their release, movement/emission followers, and more. 0→1 changes
  those time constants by up to **4×**, not just the presentation of per-ID radii.
  Especially for small bubbles, `small_change = max(0,small_body-reference)` is
  multiplied by `(6+2*sustain)` without a bounded transient contribution; the
  *musical reference* becomes slower as the operator turns up purported visual
  smoothing. Controlled P7 90-Hz stepped-band probe: after 2.67 seconds of the
  **same** hot segment following a soft section, small radius was ~0.394× nominal
  with smoothing 0, ~0.683× with 0.5 and ~2.066× with 1.0. These are synthetic
  logical source ratios, NOT native pixels or a proof of actual recorded judder.
  Stop coupling audio reference estimation to visual smoothing. Preserve fast
  attacks and slow, continuous drawn-radius release, actual source-band freshness
  and discrete onset semantics. See Investigation §25; retain **R-105 rejection**
  of tiny-breath holding/threshold tricks. Never claim restored size fidelity by
  merely changing the global follower constants.
- [ ] **No per-ID visual radius evolution currently exists for EB ordinary large
  or small bubbles.** Both populations get ONE shared lane envelope and every
  stable-ID `current_radius` is directly reassigned `nominal_radius × lane_scale`
  on each logical capture. Source variations are therefore synchronized class-wide,
  and this is distinct from 2D Bubble's separated raw pulse, instant-rise/0.10-s
  render-size release authority, and per-hero display-radius follower. Design an
  owner-local, frame-rate-independent, identity-stable *presentation-size* follower
  that does NOT alter audio feed/control semantics; ensure visible shells, wakes,
  contacts and fused members remain physically coherent from one canonical radius
  owner. No shader-only substitute, extra clock, hard hold band, threshold switching
  or suppression of downward soft breathing. Falsify against same-ID raw target,
  current/drawn world radius, native projected radius and real audio from 2D/EB.
- [ ] **Large near-max pinning has an independent source lead.** `_body_big_envelope`
  continuously incorporates `(0.25+0.75*sustain)*big_body` and `_reaction_scale`
  folds the held envelope into BOTH baseline contraction recovery and positive
  expansion, across every large ID. A steady synthetic P7 high-body segment
  maintained ~1.87× nominal large radius after 4 seconds, and another, audibly
  different synthetic high-body segment still ended at ~1.87×. This is NOT proof
  of literal renderer clamp/max or every real song. Compare local-phrase 90%/95%
  occupancy, high-body plateaus, soft→hot→soft and individual musical attacks
  before changing the ceiling, range or held support. Retain high peaks without
  long inactive holds. Distinguish population count and depth changes from size.
- [ ] **P7's ember/debris field is existing `Particles`, not a separate debris
  emitter setting.** In `presets/visualizer_modes/extruded_bubble/preset_7_ember_drift.json`,
  particles=[0.85,1.0], size=1.6, colour=[255,64,5,255], warmth=.9,
  glow=.6, particle_bands=True, band_contrast=1.0. P1–4: particles=[.1,.35],
  size=1, glow=0, bands=False. P5 and P6 have denser particles but no bands/glow.
  This Range drives the shared smoothed emission for independently drawn scene
  specks and procedural snow/fizz; Bead Chains has a separate count control.
  `speck_amount` squares the resolved emission for instance density and applies
  2.4× for brightness, so full-detail P7 can issue very many lit instances.
  Controlled constant-hot input gave ~175k *submitted* speck instances P7 vs
  ~13k P1 (GPU cloud discard/visibility not measured). Do not add another
  particle system or silently retune operator presets. When tuning visibility,
  isolate Particles, Glow, Size and Bands endpoints individually.

### 4C. Shared Settings UX audit | after EB body acceptance, not current implementation scope

- [ ] Audit every Visualizer/Transition/widget page for shared Angle/Direction, Range and Triangle controls,
  stronger `when` conditionals and nested bucketing. Keep stored meaning and canonical keys; migrate inputs if
  necessary, prove each changed real-body round-trip and render the body offscreen. No per-page owner clones.
- [ ] Prototype the gradient direction mapper on original Bubble: around = direction, distance from centre =
  strength/gradualness (centre even, rim hard). EB uses its Water/Depth/light controls, not another gradient owner.
- [ ] Make Advanced more prominent with the existing larger bucket; move Technical controls under Advanced and
  EB Camera there. Add curved parent→child bucket connection lines only at the shared owner if absent.
- [ ] Expose canonical overall/per-mode 3D quality in Visualizer bodies as views of the existing 3D tab keys;
  assess per-mode AA/Bloom via `resolve_scene_quality` as for transitions, never duplicated persisted settings.
  The speculative Settings live-preview feature belongs to `Future_Work.md`.

## 6. Reddit cache durability | active, independently actionable

- [ ] **Persistent Reddit candidate reservoir.** Retain a deduplicated, subreddit-isolated pool of every valid
  previously retrieved post independently of the displayed 5–25-post window. Valid historical posts must not
  expire merely because they are old; a blocked, empty or sparse fetch must never shrink the retained pool.
  Reuse existing cache persistence and refresh ownership.
- [ ] **Merge before display selection for every Reddit provider.** Merge incoming RSS and HTML results with
  retained candidates before selecting the display window, regardless of incoming count or source. Successive
  small batches must accumulate rather than overwrite one another; HTTP 403/429, empty results and partial
  responses retain prior usable posts. Keep subreddit identities separate, and preserve generation fencing.
  Focused tests: successive three-post batches, a one-post RSS response, fetch failures, restart persistence
  and a 25-post cache surviving a three-post fallback. **Why:** provider instability must not reduce an otherwise
  full widget to three posts. This is an active source-integrity repair, not a low-priority watchlist item.

## 2A. Focused pre-existing regression triage | independent of EB acceptance

- [ ] Reproduce each relevant red at the exact tree before changing it; distinguish stale oracle from actual product
  defect, and repair at its owner. Keep this bounded, not an implicit full-suite campaign. Remaining recorded areas:
  `test_3d_curated_preset_ownership`, `test_defaults_schema_authority`, `test_default_settings_editor`
  (`ast.literal_eval` versus `basin_profile()`), `test_defaults_projection`, `test_engine_lifecycle`,
  `test_image_prefetch_transport`, `test_qt611_shader_admission`, `test_scene3d_foundation`,
  `test_scene3d_quality_settings`, `test_sphere_shared_scene3d_projection`, `test_theme_defaults_authority`,
  `test_transition_distribution`, `test_visualizer_3d_reach`, `test_visualizer_custom_route_contract`,
  `test_visualizer_edit_content_envelope`, `test_visualizer_presentation_orientation`,
  `test_visualizer_runtime_controller`, `test_visualizer_settings_body_transaction_contract`, and the stale
  rear/translucent-body/depth cases in `test_neon_scene_materials` with no visible Sun/Moon in the reference render.

- [ ] **Nonblocking tooling housekeeping:** investigate the repeated `.venv` launcher warning
  `Failed to find real location of ...pythoncore-3.14-64\\python.exe`. The forensic commands still completed with
  exit 0 and native captures; do not conflate this warning with EB behavior or introduce an environment-variable workaround.

## 3. Release media and bounded source cleanup | Independent, nonblocking work

This section is **not** a dependency of Extruded Bubble investigation/recovery in §4; perform it at a
stable checkpoint or when separately authorized, without delaying or bypassing the explicit §0 order.
The release capture tool is already landed. `Docs/Reference/Release_Media.md` is the single source for input paths,
encoding and manifest policy: genuine UsuScene1–4 originals, transition loops at 480 px wide / 24 fps / authored speed,
high quality and no arbitrary 10 MB cap. Outputs remain outside runtime QRCs.

- [ ] **RM1 — Reconcile the catalogue at a stable checkpoint.** Enumerate the current registry/meaningful appearance
  variants and compare existing manifest/source hashes. Generate missing or stale entries only; preserve the accepted
  exclusions (Warp Dissolve, Particle, Blinds Flat) unless changed by the operator. Review each new/visually changed
  transition WebP before closing its implementation. Do not fabricate missing local originals or recapture merely
  because the Git revision changed when source inputs did not.
- [ ] **RM2 — Visualizer showcases.** Once the migration/geometry source is stable, capture registered modes' curated
  presets with canonical schema-2 real-music clips through production replay/capture/render ownership. Keep the authored
  reaction, photograph backdrop and reflection inputs; fail loudly for unavailable inputs.
- [ ] **RM3 — Catalogue proof.** Inspect motion/endpoints, loop seams, dimensions, metadata and quality; retain outputs
  and manifests. Verify unchanged inputs skip regeneration, changed source/preset/clip inputs regenerate appropriately,
  and mixed-revision captures are rejected. This is media proof, not another product visual acceptance gate.
- [ ] **SC1 — Retire unused root transitions.direction.** Confirm current caller absence, then forward-strip the root key
  without changing each transition's own direction setting. This changes the operator's defaults: undertake only with
  explicit defaults-change authorization. Prove import/default merge/save cannot resurrect it.
- [ ] **SC2 — Blinds Flat endpoint discrepancy, nonblocking.** Reproduce the prior capture endpoint mismatch at the exact
  production endpoint before deciding whether the defect is in capture or rendering. Landed transitions are accepted;
  do not reopen broad appearance work, change authored behavior or demand another build absent a reproduced defect.
- [ ] **SC3 — Retire unused Spectrum fill/border-link state.** Current source finds `spectrum_link_fill_border` only in
  defaults/model serialization and authored preset/fixture payloads, with no UI or renderer consumer. After the Settings
  migration, confirm current caller absence and forward-strip it at canonical input/save boundaries without linking
  the independent fill/border controls. Preserve frozen historical fixtures; prove current import/save cannot resurrect it.


### SC4. Just Make It Work Pools | provider selection, independently scoped

**Do not infer completion from discovery:** The existing Just Make It Work action currently replaces the wallpaper
feed URL list with four fixed entries and Guided Setup calls that same action. Pool UI, provider rotation and new NASA
selection have not yet been implemented. Technical design, site validation and acceptance gates live in
`Docs/Reference/Wallpaper_Pool_Selection.md`. Scope as separately authorized source work, not an implicit blocker
of §0 Neon Lake → Bubble migration → shared 3D → Extruded Bubble. Retain SC1–SC3 and the §5 wallpaper-RSS
runtime-replacement audit as independent work.

- [ ] **SC4.1 — Source eligibility and exact resolution.** Verify current public listing, metadata and original-image
  access with bounded live requests for each candidate. Wallhaven's public JSON API is already the implemented
  feed. Group NASA Sun/Mars/Solar System/Universe behind one `Space` choice, rather than exposing each as an
  individual consumer-facing NASA checkbox; replace the current NASA-wide Image of the Day and legacy JPL listing
  in the curated choice. NASA's Solar System is a *group* of several official Photojournal topic feeds, not an
  assumed single URL. Keep Minitokyo experimental until anonymous original access, site availability, permission
  and respectful request costs can actually be demonstrated. Consider Konachan.net (wallpaper-oriented SFW), then
  Safebooru/Zerochan with stricter admission; include Yande.re and E-Shuushuu in comparison with stronger SFW,
  wallpaper and API-access caveats. Distinguish published API documentation from **actual, authorized, successful
  original-image retrieval**; no board is a public default until bounded live probes pass.
- [ ] **SC4.2 — One provider-selection authority, no new shuffle.** Create a canonical typed selection for named
  Just Make It Work Pools, including **named Wallhaven thematic search pools** rather than its three coarse
  General/Anime/People flags as user-facing choices. Give the entire popup **one global discovery-order preference**
  (Random, Latest, Popular, Today/Week/Month/Year), translated only for providers with real support; unsupported
  providers keep their native discovery order with no simulated ranking or second shuffle. Define stable, validated
  provider query templates and a bounded number of distinct feed documents **per acquisition pass**, rather than
  fetching a document for every checked search. Existing wallpaper coordinator,
  conditional-request/backoff, image-attempt, per-host pacing, session-replacement, cache and display-size header
  admission remain owners. Source sorting filters what the RSS wallpaper pool may discover; the final wallpaper
  rotation and display shuffle remain entirely in the existing engine. Persist fair pool rotation/retry without
  creating a scheduler, timer, competing shuffle or per-feed continuous worker. Prove behavior with pool=full,
  offline source, 429/backoff, settings restart and zero active displays.
- [ ] **SC4.3 — Shared themed popup and Guided Setup.** Existing **Just Make It Work** buttons in Sources Settings and
  Guided Setup invoke the *same* popup, Save/Cancel and settings owner. Popup title `Just Make It Work Pools`;
  source-family groups with **Wallhaven themed-search checkboxes** (Nature & Landscapes, Space, Cities &
  Architecture, Fantasy, Science Fiction, Cyberpunk, Abstract, Minimalism, Anime Scenery, Dark Wallpapers),
  one NASA Space checkbox (the four subject families), and optional approved board pools. Offer **one discovery-order
  selector at popup level**, not per Wallhaven/source group. Keep `purity=100` and coarse category bits as adapter
  internals only, and keep provider-specific ranking semantics out of the wallpaper shuffle. Use the
  established StyledPopup/shared dark-glass theme, sizing, keyboard, scrolling and bucket components. Guided Setup
  must keep its draft/Finish/Skip lifecycle and readiness authoritative and must not silently overwrite custom feed
  authoring when toggling pool availability. Validate fresh, existing-custom, empty and disabled-feed states, and
  source-list add/remove/edit across both surfaces.
- [ ] **SC4.4 — Safe migration, metadata and physical acceptance.** Migrate the existing curated NASA/Wallhaven URL
  entries into selected pool identities at canonical persisted-input boundaries once, without repeated legacy
  branches; never misclassify user-authored custom URLs as curated. Preserve independently authored RSS/Atom/JSON
  feeds, folders, source ratio, cache and nonblocking 3D roadmap. Use test-owned configs for persistence/selection
  and fake feed documents for fair per-pass admission, backed by opt-in provider probes and operator review.

## 5. Nonblocking watchlist and operator-owned evidence

Observe during normal use or an operator-chosen build/capture. Do not turn these into a request for a costly build,
polling, or a full suite. Reopen accepted behavior only on concrete new evidence; use explicit Awaiting Logs/Validation.

- [ ] **Monitor power/wake — Awaiting Validation when convenient.** Either display off, >30 s on one display,
  rapid off/on, reordered return and both selected displays absent. Widgets must keep physical assignments and
  CUSTOM geometry, restore on their own display and never spill/duplicate/freeze. Include Settings reassignment,
  Arrange/Edit/Reset if exercised. On recurrence record timestamps, remaining physical screen, flavor, Interaction
  Mode and exact wake/exit input. Legacy numeric first binding requires intended displays or a unique saved home.
  Prior evidence/failed methods live in R-79; no general wake-exit cause was established.
- [ ] **Refresh contention — Awaiting Logs on recurrence.** Correlate accepted/queued/claimed/published/retired
  FEEDS/Gmail/Reddit work and transition delays in a naturally available dual-display trace. Check fairness,
  no post-transition stampede, retained last-good content and busy throughout queued work. Steam/Weather/Friend
  Pulse/startup cache readers need publication/retirement audit before joining any common gate. Existing R163/R164
  evidence is background, not proof of a current stranded FEEDS request.
- [ ] **Wallpaper RSS after runtime replacement — source audit required.** `engine_lifecycle.stop(exit_app=False)`
  permanently sets the reused RSSCoordinator stop event and replacement does not restore its timer. Audit Settings,
  CUSTOM and topology generation ownership/pending IO before deciding resume versus rebuild. Prove one refresh
  owner resumes, no stale publication/session rotation and no acquisition with zero selected displays; separate
  this from FEEDS widgets.
- [ ] **Display Settings capacity — deferred UI work.** Replace four fixed monitor checkboxes with current-screen
  rows before claiming explicit authoring beyond four displays. Preserve unavailable choices/physical bindings
  through canonical resolver/persistence; no runtime/provider rewrite.
- [ ] **Cross-display Media shortcuts — Awaiting Validation when exercised.** Each shortcut on the other display
  is delivered once. Do not build solely for this check.
- [ ] **Music recorder — Awaiting Validation when recording is needed.** Capture a named 60-second real clip;
  verify signal/history, result file, cancel and mixed-DPR UI. Full-history/schema-2 commands live in Harness Index.
- [ ] **Frozen release gate — operator scheduled.** Standard/Diagnostic from the same compile, MC and Reddit
  Helper: installed startup/exit, Settings/widgets/cache/audio and installer behavior. Analyze supplied evidence
  and exact failures; no speculative builds or automatic four-chunk run. Accepted Python/Qt and Ban Image cutovers
  are not reopened absent a regression.
- [ ] **Conditional evidence only:** original Bubble tiny-radius judder needs new music/scale/DPR reproduction
  (R-105); dual-display reboot-dependent recovery needs pre-reboot DWM/driver/swap evidence (R-134–R-145), not an
  attribution to an unproved patch. Long-duration CUSTOM/Extruded lifecycle reopens on a concrete symptom.
  The unrelated 90 Hz versus 60 Hz investigation remains off limits.

## Handoff rules

Use direct-copy, single-line PowerShell commands with explicit `.venv\Scripts\python.exe` for the operator.
Keep details/evidence at their focused owner, this checklist actionable, and Index/Spec navigation current.
No memory updates without an explicit user request.


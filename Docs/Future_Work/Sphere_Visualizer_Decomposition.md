# Deformable Sphere visualizer

Status: implemented and automatic/visual prototype checks passed; operator acceptance remains below. Live sequencing: `FWPlan.md`.
Pre-implementation comparison/rollback HEAD: `f8def8ee8cbd99527b513494bb2068417144452c`.
The operator explicitly requested an ambitious 3D item after Glow and Slide. This is a new experiment;
it does not claim to reconstruct the lost historical Blob.

## Current foundation

The canonical mode descriptor owns default dormancy, lazy runtime/capture/renderer/builder resolution and
FRAMELESS + VIEWPORT_RECT policy. The existing Quick display owner owns the shared BeatEngine lease and
activation lifecycle. Capture publishes compact immutable Sphere state through the normal render bridge;
no other mode is instantiated to support Sphere. Settings and curated presets use the shared normalization
and Custom persistence path. The existing render host owns the GL fence and context retirement, with
Sphere restoring its additional depth/scissor/cull state locally.

## State, cadence and lifetime

Sphere is one canonical `sphere` descriptor, display name `Sphere (Experimental)`, independently disabled by default.
Enable it deliberately through existing mode Setup; family activation and enabled-mode selection remain distinct.
Its policy is FRAMELESS + VIEWPORT_RECT and supports the existing viewport resize/whole-scale contract.

`SphereFrameRuntime` owns activation-relative authored time and latest frozen Sphere state, driven only by the
existing logical clock/capture callback. Common analysis supplies bass/mid/high/overall plus transient energy;
stale generation/activation data cannot become fresh response. No FFT, source subscription, worker or timer is added.
The renderer consumes immutable time/energy/configuration and never advances simulation or reads the engine.

Payload interface: `SphereFrame(authored_time: float, parameters: FrozenFields)` under `logical.mode_state`;
reactive inputs are `logical.common.energy` and `logical.common.transient`. Generation/source/fades stay on the enclosing established snapshot.
Sphere parameters are bounded `sphere_*` values: material (Chrome/Obsidian/Magma/Silver/Water), deformation strength,
rotation speed, gloss/specular and key-light direction. Initial defaults are feature-local and do not alter existing
mode defaults, presets, shared colour controls or logical parameters.

One modest static sphere mesh is generated/uploaded only at first admitted render/context creation. CPU topology
is never rebuilt per frame. One vertex deformation pass and one lit fragment pass form a real three-dimensional
surface; finite tangent samples reconstruct deformed normals. Broad bass breathing, low-order mid lobes and
restrained high ripples remain independent and do not form an audio hedgehog. Arbitrary-axis rotation derives
from authored time. Bounded specular/Fresnel/material treatment makes surface deformation readable.

Perspective uses a fixed camera distance in sphere-local units and scales into current content pixel geometry with
one common X/Y pixel scale based on the shorter current content axis. Uniform resize changes object size;
viewport-edge resize changes object size when it changes that shorter axis, otherwise framing/playroom,
without ellipse distortion or viewport-dependent audio damping. Clip to the existing assigned viewport.

Depth/cull/function/clear state is restored through the existing fence plus narrowly scoped Sphere-local state where
needed. Clear depth only inside the admitted content scissor; never clear colour, overwrite stencil or create a
second depth/window owner. Program, VAO and VBO retire through renderer `release_resources`, including allocation
failure and context recreation. No meaningful 3D work survives retirement/deactivation.

## Primitive classification

- **Feature-local:** Sphere mesh generator, deformation/normal equations, audio mappings, material palette,
  perspective constants, settings controls and immutable mode frame/runtime.
- **Justified reusable infrastructure:** cheap descriptor default-enabled and lazy-capture metadata needed by this
  real sixth consumer; preserve existing mode behavior while replacing closed central dispatch where necessary.
- **Reuse existing:** run/generation clock, source bands, immutable transport, presentation geometry/fades,
  shader compilation, context release, GL fence, eight-way direction vocabulary and lazy Settings body host.
- **Speculative reuse deferred:** general camera/MVP library, mesh/resource framework, lighting/material hierarchy,
  scene graph, physics, 3D object manager. Extract only after a second real consumer proves identical requirements.

## Resumable checkpoints

- [x] Inventory current owners and commit decomposition before substantial coding.
- [x] **S1 — admission/state:** descriptor default-enabled policy, frozen Sphere payload, lazy runtime/capture,
  configure-owned immutable parameters, current playing source identity and independent dormancy tests.
- [x] **S2 — geometry/render:** vectorized static 5,120-triangle icosphere, analytic deformation/deformed normals,
  arbitrary-axis rotation, perspective, five materials, surface-gradient bump mapping and filtered microdetail.
  Depth clears intersect projected viewport/inherited scissor; depth/cull/scissor state and partial resources restore.
- [x] **S3 — real Quick prototype:** inspected five-material capture and separate 1080p/4K fixtures; all modes draw
  and retire on the same legal context. Hidden items release mode resources before scene invalidation.
- [x] **S4 — Settings:** isolated lazy body, material/lighting/motion/detail controls, five real curated presets,
  Custom restore and zero-value/unbuilt-body preservation. Mode body hides/shows correctly after first construction.
- [x] **S5 — integration:** focused contract gates and destination run completed; new-mode fixture closure and real
  lifecycle fault fixed. Remaining unrelated destination failures are actionable in `Future_Cleanup.md`.

## Implementation evidence and boundaries

`tools/qtquick_sphere_smoke.py` drives bounded fixture frames from swap events, captures asynchronously and checks
inactive GL release before invalidation. `logs/evidence_chest/fw_sphere/materials_final.png` is the inspected capture
(Chrome, Obsidian, Magma / Silver, Water). Probe callbacks are measurements, not physical-refresh acceptance. A fixed-size capture subtree preserves
projection when Windows clamps an oversized native window; the report records actual native size/DPR separately.
The corrected 4K Water capture is `logs/evidence_chest/fw_sphere/water_4k_final.png`.
The only probe timer is a failure deadline; production adds no timer, poller, source lane or per-frame mesh upload.

The nominal radius is 0.245 of the shorter actual content axis, with fixed camera distance 4.6.
This reserves the maximum combined size pulse/deformation envelope. The original canonical-height *
uniform-scale defect produced ~13px radius inside the operator's ~1400x268 viewport; the resolved-content
radius is now ~66px before musical expansion. Uniform resize enlarges the object independently of saved
extent encoding. Real GL tests exercise that exact geometry and every mode's live edit projection.

Chrome/Silver have restrained metal microdetail, Obsidian has fractured stone relief, Magma has recessed emissive
fissures with authored-time flow, and Water has animated ripple bump, caustic accents and Fresnel transparency.
Bump Strength controls base relief; Bump Reactivity controls added musical relief. These are procedural materials and studio reflections; Water does not sample
or refract the live background. Its visible surface alone blends, with back-face culling and the existing depth target.

## E2 material and reactivity contract

Sphere consumes existing immutable bands, decaying transient envelopes and activation-relative authored time.
It receives no waveform, audio job or source subscription. Current playing source identity gates both bands
and transients, including valid generation/activation zero. Stale or stopped sources cannot retain a size pulse.

- Deformation (0..2) controls local musical displacement, independent of Idle Motion (0..1).
- Bass/Mid/High Response (0..2 each) shape independent bands. Vocal Response (0..2, default 1.4) adds
  broad low-order lobes from the established 0.62 mid / 0.38 high frequency blend; it does not isolate voices.
- Energy Curve (0.2..2, default 0.60) makes ordinary low bands visible without flattening combined lobes.
- Size Response (0..2, default 1.5) adds uniform whole-body breathing independently of Deformation.
  Drive is the maximum of the existing decaying transient bands, 0.25 overall energy and 0.35 bass energy,
  clamped to 0..1. Radius addition is `0.10 * size_response * drive ** energy_curve`, at most 0.20.
  TransientBus already owns decay; the renderer adds no mutable filter or clock. Zero disables size response.
- Bump Strength (0..2, default 1.15) controls base material relief. Bump Reactivity (0..2, default 0.65)
  adds energy-driven relief without changing the silhouette; zero retains the configured base relief.
- Material Effects (0..2) controls the bounded Magma/Water secondary geometry; zero omits its draws.

The vertex shader applies `1-exp(-2.8*pow(band, curve)*response)` per independent field. Absolute displacement
coefficients sum to 0.27 before the 0..2 Deformation control, without clipping the combined moving field.
Maximum radius is `1 + 0.20 + 0.10 + 2 * 0.27 = 1.84`. At camera distance 4.6 and 0.245 shorter-axis radius,
its canonical 280px projection remains below 138px. This fixed reserve does not damp audio at extreme extents.

Magma and Water lazily create a 320-triangle effect mesh once per GL context; Magma additionally creates one immutable
six-vertex fire quad. Their positions are deterministic shader functions of `gl_InstanceID`, immutable energy and
authored time. Magma has lit falling teardrops with a hot core, cooling skin and highlight; their standard alpha
composition preserves finite-life and global fades while their visible front surface owns depth. A separate additive
soft-alpha fire pass rises from the body. Water has rounded, irregular 3D blobs with shape-derived normals,
Fresnel/specular light and a transmitted cyan tint. Each finite life fades to zero before its mathematical cycle wraps,
so it retires and condenses without a visible teleport. Water has no pointed drip neck; Magma retains one. Water lanes are deliberately separated, then use ordinary alpha
blending with no overlap-order claim; no live-background refraction is claimed. There is no texture, CPU particle state,
per-frame upload, timer, worker or source subscription. Partial lazy effect allocation is discarded before a clean retry.
Magma reuses its one fire quad for four filtered procedural smoke wisps and six ash/ember flakes, drawn with ordinary
alpha blending before the additive flame pass. Closed lava and Water meshes retain back-face culling; only the
camera-facing quad passes disable it. The renderer restores blend factors/enabled state, depth-write and cull state
before returning.

At FX=2, the final warm-cloud world-Y bound is 1.526, smoke 1.588 and ash 1.287. With camera-Z at
most 0.42, their projected upper extent is at most 1.747 base-radius units; maximum projected lateral
extent is 1.339. Falling lava and rounded Water blobs remain within the same conservative 1.90 projected
reserve. This fits the 0.245 shorter-axis framing without FBO clipping. The upper clouds were moved above
the active growing body after actual preset captures exposed depth occlusion at the original positions.
Real GL samples their finite lives at FX=2, compares against effects disabled, and checks visible pixels,
colour, finite bounds, global fade/depth and unchanged upload count.

E2 evidence: `e2_presets_effects_raised.png` and `e2_presets_quiet.png` under
`logs/evidence_chest/fw_sphere/` use actual normalized presets and a retained checkerboard. The background
is visibly transmitted through Water and its rounded blobs; Magma's smoke/ash/fire blend over it. The 4K
Water and exact 8240x1579 saved-world Magma captures also pass context retirement. Current local capture
DPR is 1.5; physical mixed-DPR/60/165Hz checks remain open. Warm callback medians in the bounded single-mode
fixtures were 2.47ms (4K Water) and 3.41ms (extreme Magma); these include Python/GL submission and are neither
GPU-time measurements nor physical cadence acceptance. Captures ran alongside test work.

215 focused rendering/settings/defaults/dormancy/preset tests passed. The silhouette test isolates size
response from surface deformation: a maximum pure transient grows diameter by over 17%, intermediate
transient decay gives an intermediate size, and zero returns exactly to rest. Vocal-range deformation
and bump reactivity have separate pixel assertions. Canonical regeneration also corrected three preexisting
missing defaults-snapshot fields (Spectrum rainbow fill and Sphere rainbow enable/speed).

Inactive resources retire on one-shot `beforeRendering` events, with invalidation as the context completion edge.
Window rebind detaches the old node and leaves cleanup on its old window. Ordinary sync never schedules cleanup.
A Qt-owned QRunnable prototype caused a reproducible native heap failure on the pinned binding; it was removed.
The event equivalent is documented by [Qt's QQuickWindow contract](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/QQuickWindow.html#PySide6.QtQuick.QQuickWindow.scheduleRenderJob).
Real runtime-reality (4 tests), hotkey (12 tests), and retirement/item/runtime (18 tests) pass after that correction.
The mesh/source/Settings/dormancy/packaging focused group passed 64 tests. The initial destination run executed all
115 targets; new-feature fixture failures and native retirement faults were corrected with focused reruns. Nine
unrelated existing targets remain red (see cleanup ledger); do not report the entire profile as green.

## Acceptance bars

- **Deterministic/source:** unit sphere topology/finite outward normals/real Z; same time+bands gives same payload;
  distinct bass/mid/high influence; exact immutable generation identity; renderer cannot advance authored time.
- **Lifecycle/resource:** disabled old/default profiles import no Sphere runtime/builder/renderer; first enable resolves
  only Sphere; disable/mode switch/recreation retires its program/buffers; failure cleanup preserves recoverability.
- **Geometry:** fixed pixel metric on both axes across wide/tall extents; whole-scale uniformity; viewport clipping;
  no card fill/border/shadow. Preserve the five established modes' R-69/BTF behavior exactly.
- **Performance:** one body upload plus lazily bounded effect-mesh/fire-quad uploads per renderer/context lifetime,
  constant bounded uniform transport and no per-frame topology/upload/source jobs. Measure 1080p/4K/extents separately;
  callbacks are not physical cadence proof.
- **Eyes-on/operator:** it reads as a deforming 3D body with normals/specular following dents/bulges; materials differ
  meaningfully, no clipping surprises, responsive real music/idle, 60/165 Hz and mixed-DPR/recreation acceptance.
  Retain this checklist as Awaiting Validation when automation cannot honestly close it.

## Awaiting operator validation

- [ ] Inspect real music response and the five material presets at representative display sizes.
- [ ] Verify physical 60/165 Hz, mixed-DPR transfer and installed/frozen context recreation.

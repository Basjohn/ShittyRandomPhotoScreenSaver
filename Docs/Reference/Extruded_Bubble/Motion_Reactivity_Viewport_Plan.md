# Extruded Bubble: drift, flow, framing and reliable musical response

Assessment and execution contract, 2026-10-28. **The operator approved implementation after reviewing the assessment.**
`Current_Plan.md` owns admission and sequencing; this document owns the detailed assessment and proposed gates.
The operator requires checkpointed slices audited by one Sol 6.1 High agent. Resizing must retain the authored lens,
physical world and camera, with no aspect stretching or automatic FOV retuning, and preserve the original rectangle.
The operator reopened these five specific issues after the 2026-10-25 acceptance. This is not a reopening of the
entire historical EB recovery or permission to retune accepted materials, populations, lighting coverage or presets.

## Evidence and its limits

Source baseline: `71049610896c63a8568b1045df201410397ed1b4`. No product code, settings or presets changed during assessment.
One Sol High read-only audit independently traced free-chain visibility and ray response. Findings below distinguish
source-established behavior, measured replay and hypotheses requiring further reproduction.

Recorded baseline: `logs/visualizer_recordings/dontyouseemetrying_mixed.jsonl`, SHA256
`92408f4f995713eb23ce426b94b614b27eedbe89326056636047805e5337fc01`.
Preset 8 was resolved from its current authored file, SHA256
`85c687867e8cd3b2b5e794634bf6e955eacd55a0f1f06c6e6b301f675c5a2e09`.
These identify historical evidence, not test oracles for mutable authored presets.

Evidence under `tmp/eb_assessment_20261028/`:

- `p8_recorded/`: production recorded-feature replay, including pre-roll, with measurements over 3–6 seconds;
  per-ID positions, nominal radii, classes, state scalars, exact resolved settings and source custody are retained.
- `p8_no_contacts/`: same recording/settings with only collision scope set to Off in memory; no saved changes.
- `motion_summary.json`: stream-axis displacement divided by the current snapshot's physical stream speed;
  fully visible, ordinary stable IDs exclude cluster members, leaving/popping identities and discontinuous births.
  Forming cohorts are reported separately. Samples are consecutive ID/time observations, not independent actors.
- `projection_summary.json`: current production camera calculations across five aspect ratios.
- `p8_pixels/`: 12 production-host offscreen frames at 960×540 over 3–5 seconds, contact sheet and silent GIF.
  This establishes current captured pixels; 6 fps is **not** a gentle-fade, native cadence or performance acceptance gate.

Replay used existing recorded post-DSP features. It is not a new live capture or PCM sensitivity reanalysis.
The three-second motion sample cannot establish response over all songs, pause/resume or extended held passages.
Offscreen jobs were externally bounded over their Windows process trees and retired their GL resources.
No performance optimization audit was performed; capture-tool timing output is incidental diagnostic metadata.

## 1.1 Drift ownership and proposed controls

### Confirmed current paths

`widgets/spotify_visualizer/extruded_bubble_simulation.py` owns logical motion. Its shared musical drift target is
range interpolation driven by passage/flow/body/sustain, multiplied by activity, followed over time and accented by
the bounded onset surge. `_drift_steer()` supplies directional motion; ordinary bubbles add wander/depth components.
All existing and forming ordinary bubbles use the current value every tick, irrespective of their opacity.
Fused members skip that loop: the cluster centre owns their common motion.

`extruded_bubble_frame_runtime.py:controls_from_parameters()` projects the persisted controls. The Settings surface
is generated from `core/settings/visualizer_mode_settings.py`; the EB builder and binding are delegates, not owners.

The procedural shader populations do not consume this Drift Direction field. Free bead chains use integrated stream
travel plus a fixed seeded arc/scatter shape. Snow and decorative specks use their own stream-carry coefficients.
Therefore Preset 8's ordinary-bubble spiral/free-chain mismatch is a **confirmed missing coupling**, not evidence that
the operator needs a larger Drift value.

Bead Scatter and Particle Spread already expose static plume/width geometry; neither is a substitute for musical
advection. Reuse existing motion variables only where their actual meaning matches the new control.

| Consumer | Current direct coupling to authored Drift | Proposed new gain range / important qualification |
| --- | --- | --- |
| Ordinary large bubbles, including forming | Yes: wander, depth and selected steering | `[1,1]`; normalize the existing contribution, preserving its calibration |
| Ordinary small bubbles, including forming | Yes: same owner with per-ID phase | `[1,1]` |
| Fused groups | Yes: one centre, its own wander calibration and shared steering | `[1,1]`; apply once to the centre, never again to each member |
| Free microbubbles / bead chains / scattered bead plumes | No; these are presentations of one population | `[0,0]`; highest-priority new consumer |
| Parent-attached wake microbubbles/fizz | Inherit parent/path motion; no direct shared-field coupling | `[0,0]` **additional** drift; preserve inherited attachment and avoid double application |
| Wake veils/strands and their retained water | Inherit parent history/entrainment; have independent coherent water flow | `[0,0]` additional shared-field drift; preserve existing water motion |
| Marine snow | No; existing stream travel only | `[0,0]` |
| Decorative particles/bands | No; existing stream travel only | `[0,0]` |

“Currently affected” must distinguish direct control coupling from movement inherited from a parent. Wake water
already has `ENTRAIN=0.45`, a decaying carry and `water_flow()` with `FLOW=0.012*WORLD_UNIT`; those are not equivalent
to authored Drift and must not be multiplied twice. Sway is already an exposed independent motion variable. Preserve
and clearly label that independence rather than claiming Drift 0 removes Sway. Physical lights/camera and water-wave
authoring retain their existing owners; adding unrelated drift controls to them needs an explicit scope decision.

### Proposed UX and numerical contract

- Add a **Drift** bucket using the existing spec/shared controls. Move the current Drift range, Drift Direction and
  related Sway control there. Leave Stream Source/End, Emission Geometry and Stream Speed in Motion.
- Add signed, dimensionless per-consumer two-handle gains, each endpoint clamped to `[-1,+2]`, displayed as multipliers.
  `1×` preserves that consumer's existing drift contribution, `0×` adds none, negative reverses it and `2×` doubles it.
  Newly introduced fields use flat `[1,1]` or `[0,0]` defaults from the inventory, not an inferred preset rewrite.
- A quiet/loud gain interpolates on one documented normalized logical drift response. It modulates the existing master
  drift field. With both ranges varying, the combined response is multiplicative, not a second linear absolute-speed
  range. Label gains honestly; do not hide this by adding another audio normalizer or per-renderer follower.
- Flat `[1,1]` is a parity gate. Flat `[0,0]` must remove only the added drift contribution. Apply signed gain after
  resolving the field; do not accidentally clamp negative motion away or clamp a doubled contribution back to 1.
- Resolve gains for current identities on every logical update. Never latch them only at birth, alter population
  counts, reseed IDs, teleport actors or use opacity/visual radius to suppress newly forming actors' motion.
- Zero defaults preserve existing unconnected populations. Demonstrating the requested Preset 8 spiral therefore
  requires a captured-copy/in-memory microbubble gain override; it must not silently rewrite the operator's preset.

### Architecture decision before coding

Adding UI rows alone is insufficient. CPU ordinary motion is integrated, while free GPU populations currently derive
position from seeds and integrated stream travel. `time * current_drift` would make existing beads jump when the music
changes; moving every procedural bead into a CPU simulation would add substantial work.

First choose a bounded logical advection representation for procedural cohorts/history, projected through the existing
snapshot and GPU instance path. Compare a small cohort/path representation against analytic integrated carriers for
the admitted directional fields. Constant-tangential-speed spirals are radius-dependent: a single rigid rotation is
not automatically equivalent. Keep one drift-field definition and verify CPU/GPU agreement; do not clone independent
direction semantics. Retained wakes must receive only additional water drift after their existing parent/history motion.
This decision is unresolved by the present source audit and is an explicit pre-implementation design gate.

### Drift acceptance

Test every directional mode with equal, varying, zero, negative, doubled and sign-crossing gain endpoints. Include
existing and newly forming IDs, fused groups, free chains, attached wakes, BEAM/SCENE and both light types.
Trace raw/EB bands, passage, normalized drift response, target/follower/surge, resolved consumer gains and physical
displacement. Test quiet→loud→held→quiet repeatedly, without requiring fresh onsets to restore response.
An upper endpoint during genuinely loud input is legitimate; failure to release after energy falls is not.
No hard saturation or hidden activity factor may make an endpoint misleading. Idle behavior must be explicitly
distinguished from the quiet-playing endpoint. Preserve the original global audio/DSP and size response.

## 1.2 Stream speed: measured attenuation and remaining question

The displayed Stream Speed range is multiplied by `STREAM_SPEED_FULL=0.25` during control projection, then by
`WORLD_UNIT=9` in simulation. Full authored speed corresponds to 2.25 world units/s **before** the musical envelope
and per-actor factors. This is a unit calibration, not proof of an error.

Historical baseline ordinary forward velocity before the correction:

`stream_speed * (0.65 + 0.6 * clamp((nominal_radius - MID_MIN)/(LARGE_MAX - MID_MIN), 0, 1))`

Fused centres receive `0.9 * stream_speed`. Nominal size controls can therefore change travel speed too.
New/forming ordinary bubbles use the same formula as mature ones; there is no birth-opacity speed multiplier.
The global stream itself includes range interpolation, activity, smoothing and bounded onset surge.

Preset 8, recorded passage 3–6 seconds, contacts disabled:

| Quantity | p05 | Median | p95 |
| --- | ---: | ---: | ---: |
| Global physical stream speed, world units/s | 1.958 | 2.076 | 2.130 |
| Mature large forward speed / global stream | 0.965 | 1.192 | 1.250 |
| Mature small forward speed / global stream | 0.650 | 0.654 | 0.728 |
| Forming large forward speed / global stream | 1.016 | 1.044 | 1.073 |
| Forming small forward speed / global stream | 0.650 | 0.656 | 0.731 |

The no-contact sample has 3,197 mature large and 29,369 mature small consecutive observations. Predictions from the
nominal-radius formula agree with measured world motion. Original-contact medians are approximately 1.191/0.654.
Different forming/mature distributions are different size cohorts, not proof of an age-dependent speed change.

Thus small bubbles really are attenuated here; large bubbles are generally faster than the global stream. The global
speed is already near its 2.25 ceiling in this particular loud passage. Increasing the whole stream blindly would
conceal the class difference and accelerate procedural populations as well.

Before choosing a correction, measure more passages and separate global-envelope responsiveness, per-class transfer,
contact/fusion corrections and projected pixels/s. Compare drift/sway-off and original controls at the same camera.
The approved correction makes Stream Speed literal shared forward transport for ordinary and fused bubbles,
independent of nominal size and birth opacity. Drift, sway and contact pushes remain additive; the global stream
envelope and procedural layer calibrations are unchanged. Recorded P8 no-contact verification gives1x forward/global
speed for mature large/small and forming large/small across34,000+ consecutive measurements. The broader contact,
passage and pixel matrix remains part of the combined gate.

## 1.3 Framed viewport behavior

The registered framed modes are currently EB and Neon Lake; free-form Sphere/Extruded Spectrum are separate.
The shared camera authority is `core/settings/framed_camera.py`, with per-mode specifications.

**EB:** `physical_camera()` uses a fixed tank and an eye independent of aspect. The projection holds **vertical FOV**
constant and changes horizontal FOV with `tanX = tanY * width/height`. The central horizontal/vertical focal scale in
pixels agrees; the equations do not squeeze spheres by independently scaling X/Y. A wider card sees more sideways.
Increasing height at fixed width, however, grows focal scale in pixels while keeping vertical angular coverage fixed:
it looks like a zoom/crop change rather than revealing more above/below. Very wide rectilinear views also create genuine
peripheral perspective stretching. These are different from an incorrect aspect matrix.

For the captured P8 lens of 62°, the eye is identical at every tested aspect. Horizontal FOV is 93.78° at16:9,
62° at1:1, 37.35° at9:16, 134.82° at4:1 and17.09° at1:4. At fixed 540-pixel height, both focal axes remain449.36px.

**Neon Lake:** `half_width(aspect) = 0.8*max(1,aspect)+0.9` also changes actual terrain/world width. Half-width is
2.322 at16:9 and4.1 at4:1. Authored terrain, event/celestial X coordinates and the terrain floor used to re-bound
the rendered eye consume that width. Resizing can therefore change scene geometry and, where floor clearance binds,
the admitted eye. This is not purely a crop of one fixed scene.

**Proposed policy decision:** interpret resizing as changing the observed region of a fixed world, preserving the
physical eye, orientation, scene scale and authored landmark coordinates. To make taller and wider windows reveal
more independently, define a shared **reference-window/focal-scale** policy using the existing canonical presentation
reference, rather than silently retaining constant-vertical-FOV behavior. Current FOV is defined against the current
viewport, so changing that interpretation requires an explicit migration/parity decision. No new per-mode camera owner.
If constant vertical FOV is retained, document its height/edge consequences instead of promising aperture-window behavior.

Before implementation, approve the reference framing and extreme-FOV policy. A finite fixed world may expose its
limits; do not hide them by moving the camera, stretching terrain or creating camera-following populations.
For Neon, audit terrain continuation and floor admission before changing its accepted world mapping.

**Gates:** freeze one recorded snapshot, pose, seed and world state; vary16:9,1:1,9:16,32:9,4:1,1:4, matched
width/height/area and DPR separately. Check central calibration shapes, known world landmarks, off-axis projection,
camera-eye invariance, near-plane/depth, rounded clipping, rays, reflections, particles and culling. CPU equations alone
do not close this issue: compare actual offscreen production pixels, then native resize/Settings behavior.

## 1.4 Microbubble visibility on restart

Free chains multiply opacity by `_idle_activity(level)`, a smoothstep of `level/0.1`. The logical level follows audio
with80ms attack/450ms release. For an illustrative warm-resume target0.5, it crosses0.1 in approximately18ms: opacity
can reach full within a few frames. Warm capture resumes intentionally skip the BeatEngine cold play ramp, so cold
starts can mask the asymmetry. Lifetime/population fades remain separate. Attached wake beads have different opacity
ownership and must be checked independently, not “fixed” by applying every free-chain gate to them.

The logical simulation now publishes `chain_activity`: its rise follows the existing quiet-band target with a
0.35s exponential attack; its fall is bounded by the original quiet-band visibility target. This preserves the prior
fade-out and stable travel/IDs while making warm return gradual. The immutable capture projects this value directly
to `uChainActivity`; snow/specks and attached wakes retain their prior response. Legitimate source/activation retirement
still resets the generation. No shared audio level, size response or BeatEngine warmup is slowed.

Use recorded music with warm pause/resume, cold resume, short interruptions, repeated toggles and quiet playing.
Render at least60fps around transitions and retain every logical sample; the current6fps assessment GIF cannot judge
an18ms attack. Compare layer-isolated opacity and final composited pixels. Verify no first-frame flash, integer cohort
pop, position jump or new visibility gate on attached wakes/snow/specks.

## 1.5 Rays: sustained response and control semantics

`_ray_body_reference` follows current body energy; positive differences and onset lifts decay during a held passage.
A dip/recovery creates another positive difference. This supports the reported **enter → diminish → recover** pattern.
However, `ray_target = soft_top(passage*(0.6+0.7*ray_beats))` retains a sustained base. The source does not establish
that a constant positive passage must decay to zero. Shared PassageIntensity is fixed-scale, not a learned chorus
normalizer. Do not attribute the report to adaptive loudness without evidence.

Current `ray_strength()` interpolates the strength range, then applies a resting multiplier **only below drive0.15**:
`rest=clamp(drive/0.15)`, multiplier=`0.03+0.97*smoothstep(rest)`.
At drive>=0.15 it is ordinary authored interpolation; at drive0 the left handle is reduced to3%. Older linear-factor
comments/evidence must not be mistaken for the current equation. In the short recorded P8 sample, driver p05/median/p95
is0.778/0.848/0.872, strength before global light is0.456/0.470/0.474 and passage intensity is1 throughout. The resting
multiplier cannot explain disappearance in that sample; a longer reproduction is needed.

Flicker0 currently disables an extra cosmetic shimmer multiplier. It does not disable musical brightness, resting
suppression, sustained reach changes or ordinary time-driven shaft-pattern motion. Global Light Strength, coverage,
blockers, camera and composition can also change visible rays. Trace these separately before retuning audio.

### Recommended control model for approval

Use explicit strength endpoints and a single primary **Ray Modulation** amount (`0=steady at upper strength`,
`1=full musical range`). This replaces the misleading expectation attached to the name Flicker. If independent
cosmetic control is retained, expose it separately as **Shimmer**, not as another brightness gate.

One continuous brightness rule, before global physical light/coverage, is:

`strength = lerp(high, lerp(low, high, musical_drive), modulation)`

| Strength range / modulation | Meaning |
| --- | --- |
| `[0,H]`, modulation0 | SteadyH; music cannot extinguish rays |
| `[0,H]`, modulation1 | Quiet endpoint can legitimately be0 |
| `[L,H]`, modulation1 | L is the actual quiet strength, without an undisclosed collapse multiplier |
| `[L,L]` | Fixed authored strength |
| `[0,0]` or Light Rays disabled | Explicitly off |

At modulation0 the lower handle is retained but inactive; explain this in the existing shared control tooltip/status.
Intermediate modulation narrows musical excursions toward the upper handle. Do not invent an invisible nonzero floor
to reconcile two contradictory zero contracts. “Always on” still respects disabled rays, global Light Strength0,
physical visibility/occlusion and an entirely zero authored range.

Alternative: retain Flicker strictly as shimmer and add a separate Music Response control with those brightness
semantics. This is mathematically clean but does not make old Flicker0 alone mean constant rays. The control naming,
zero contract and migration must be approved together. Existing authored flicker values represent cosmetic depth;
do not silently reinterpret them as music-response amounts. Preserve/map them explicitly and document intended
behavior changes; no wholesale preset overwrite. Pause behavior is part of this decision: steady mode remains steady,
reactive mode approaches its honest quiet endpoint rather than another hidden blackout factor.

**Ray gates:** hold input long enough for transient references to settle; sustained brightness must not require new
onsets. Run recorded held passages, dips/recoveries and pause/resume, tracing body bands, passage, source-ramp flag,
phrase/lift, target/follower, range output, light multiplier and final shader uniforms. Isolate rays with fixed camera,
light, blockers and pattern phase; inspect linear shaft buffers and final composed pixels before/after bloom.
Test off/zero/flat ranges, modulation0/1, shimmer independently, both light types and BEAM/SCENE. Separately release
camera/pattern motion so a beam moving out of view is not misdiagnosed as lost audio response.

## Execution order after authorization

1. **Freeze evidence and approve semantics.** Capture current editable presets as immutable evidence inputs; review
   the drift consumer inventory, procedural advection representation, literal stream-speed meaning, viewport policy
   and ray zero/migration contract. Make current probes enumerate actual preset files: forensics/world-probe CLI
   guards still cap presets at1–7. Assessment P8 logical replay used the existing Python API; the standard production
   capture CLI already accepts8. Do not introduce a parallel renderer to work around those stale guards.
2. **Logical drift/stream behavior, then Settings projection.** Establish the bounded field/gain contracts, prove
   existing/forming/cluster motion and endpoint release, then wire the Drift bucket through canonical defaults,
   model/spec, preset/import admission, immutable capture and production uniforms. No extra setting authority.
3. **Framed-view contract.** Prove the chosen policy independently on both framed modes before changing common
   projection or Neon geometry. Preserve existing reset/flight/orbit/pan/eye-clearance and per-preset camera ownership.
4. **Visibility and rays.** Repair the dedicated chain-presence transition and held ray response using the approved
   independent semantics, with no global audio/size retune. Verify all controls reach their actual consumers.
5. **Combined behavior gate.** Recorded quiet/loud/held/dip/resume passages; current P8 and representative other
   resolved presets; extreme aspects; both coverage/light types; fusion, source births, existing identities and
   zero/max/negative controls. Use production replay and offscreen renders, not lab-only art or formula-only passes.
   Review motion plus source traces; native Settings layout/runtime confirmation remain separate evidence.
6. **Only after all five requested behaviors pass: performance audit.** Then inspect CPU allocation/churn, uploads,
   actor/contact/wake work, pass/resource dormancy, overdraw and conservative culling/occlusion opportunities.

Performance changes need matched before/after source, input, seed, pose, dimensions and quality. Compare HDR/layer
outputs and final pixels across reveal/occlusion, near-field blur, fused shapes, glass/reflection, rays and moving
cameras. An actor hidden from the main camera may still affect another optical pass or wake. Keep its logical
lifecycle/audio current, prove any culling bound conservatively and reject speedups obtained by dropping detail,
reducing populations/cadence or making a non-equivalent image. No optimization is accepted merely because it is faster.

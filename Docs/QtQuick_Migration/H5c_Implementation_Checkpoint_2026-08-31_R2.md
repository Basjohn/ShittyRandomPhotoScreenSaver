# H5c Implementation Checkpoint R2 — Physical-log driven reactivity repairs

Date: 2026-08-31  
Behavioral oracle: `3fe5df687387b6b6a121142372c43a7719442386`  
Input physical trace: post-R1 source-mode logs supplied 2026-08-31  
Execution authority: `Current_Plan.md`

> **SUPERSEDED CHECKPOINT / PROVENANCE ONLY.** Do not use this file as live repair or status authority. `Current_Plan.md` owns sequence; R6 native-`QCursor` Halo and R7 image/prefetch/seam work supersede the pointer/image-pipeline portions. Preserve only findings explicitly carried forward by current living docs.

## 1. Purpose

This checkpoint follows the first preset/source ownership repair and is deliberately a new safety point before another physical run. It does **not** declare H5c complete. It contains only repairs justified by historical source comparison plus the first post-repair physical trace, and bounded diagnostics needed to classify the remaining seams.

The governing architecture remains unchanged:

```text
one product visualizer owner
-> one VisualizerRuntimeController
-> one BeatEngine / audio worker
-> one authored logical runtime (~90 Hz)
-> latest immutable state mailbox / bridge
-> one retained Qt Quick render item/node
```

No second timer, replay queue, duplicate source, duplicate logical owner, renderer-side settings polling, or legacy QWidget/GL presenter is introduced.

## 2. Physical R1 result

### Spectrum

- [x] Spectrum is physically **dramatically improved** after restoring topology translation, shared source shaping and the historical `0.55` renderer transfer.
- [x] It is again recognizable as the historical Spectrum rather than the saturated segmented failure.
- [x] The steady paused idle hump exists and the logical runtime authors it correctly (observed max around `0.24`).
- [ ] One pause-transition flaw remains: live bars briefly appear to reach zero before the already-correct idle-floor frame becomes visible.

### Bubble

The new trace strongly relocates Bubble's remaining failure downstream:

- [x] source identity is current (`source_ready=True`);
- [x] real-music energies are large, not idle-sized (representative overall ~0.57-0.65, bass ~0.54-0.75, mid ~0.79-0.80 in the supplied run);
- [x] Bubble authored integration is healthy at about 90 Hz;
- [x] integration accounting showed essentially one integrated step per requested authored step;
- [x] therefore the remaining visually-dead response is **not** explained by FFT gain, restored notch routing, source readiness, or authored cadence.

The next Bubble seam is simulation-result transport / immutable snapshot / retained Quick expression.

### Sine

- [x] Sine paused idle motion is physically present.
- [x] The prior "missing entirely" hypothesis is closed.
- [x] Operator asks for a modest ~20% stronger paused idle motion.
- [x] Live/music gain should remain unchanged.

### DevCurve

- [x] Most of DevCurve is physically strong after the shared source repair.
- [ ] Outlines appear jagged/doubled relative to historical smooth appearance.
- [ ] In basic preset, the bottom/transient layer no longer visibly reacts to heavy hits as expected.

### Play/Pause resume

- [ ] Long visual reactivity startup from a true idle pause remains.
- [x] App startup and visualizer hotswap do not exhibit the same long delay, so this is not treated as a generic Quick startup cost.

## 3. Corrected Play/Pause trace interpretation

The first R1 diagnostics could make T3 appear at ~1.5 s for some modes. Source audit found that this was partly **instrumentation error**:

```text
maybe_log_reactivity_boundary()
-> periodic 1.5 s sample throttle returned early
-> only then attempted T3/T4 edge detection
```

Bubble happened to emit an identity/readiness transition and proved a genuinely fresh source could arrive around ~73 ms after Play. Therefore the old ~1500 ms T3 lines cannot be used as proof that capture waited 1.5 s.

R2 changes:

- [x] T3/T4 edge milestones are evaluated **before** ordinary periodic reactivity sampling.
- [x] T5 on a Play edge now requires a post-edge source timestamp, so a retained idle scene cannot masquerade as "first reactive logical publication".
- [x] T7 now reports `energy_level`, `bars_level`, and `waveform_level` actually consumed by the retained Quick item.
- [x] Spectrum gets four bounded `[VIS_SPECTRUM_HANDOFF]` samples immediately after the retained item observes Pause.
- [x] Diagnostics still own no timer/cadence and dump no full arrays.

## 4. Resume lifecycle repair

Historical pause->play committed this sequence:

```text
engine.wake()
-> engine.set_playback_state(True)
```

The Quick owner had dropped `wake()`.

R2:

- [x] restore `wake()` on a real False->True edge before playback-state commit;
- [x] do not wake when the same `playing=True` truth is merely re-applied;
- [x] `wake()` retains its existing safety behavior: restart only a capture that the backend reports stale/unhealthy, otherwise just ensure the sole worker remains running and reset smoothing timestamp;
- [x] no duplicate capture/source is created.

### Cold reactivity ramp

The old 1.5 s ramp is not a stale-frame fence. Current generation/activation identities already fence stale results, and the physical trace demonstrates fresh capture data can exist in tens of milliseconds.

R2 intentionally changes only the **cold** visual reactivity ramp:

```text
1.5 s -> 1.0 s
```

- [x] warm keepalive resume remains ramp-free;
- [x] source generation/activation admission is unchanged;
- [x] AGC/floor/source math is unchanged;
- [x] the quadratic ramp shape is unchanged;
- [x] focused test protects cold 1.0 s versus warm immediate behavior.

This is a bounded parity/latency adjustment, not a global gain change.

## 5. Bubble latest-state repair

### Proven transport defect

R1 source + physical evidence exposed a contradiction with the intended Qt Quick latest-state architecture.

`BubbleFrameRuntime` produced a protected consume-once edge named `bubble_visible_result`. The edge copied:

- every Bubble position;
- every Bubble extra/radius/alpha value;
- every trail value;
- Bubble count;
- event metadata.

`VisualizerSnapshotBridge` correctly coalesces protected edges by kind so a consume-once event can survive a latest-state slot replacement. However `resolve_quick_bubble_payload()` then **preferred the protected edge's full arrays over the ordinary newest `BubbleFrame`**.

That means:

```text
newer Bubble geometry arrives in latest-state snapshot
+ older protected event edge survives coalescing
-> Quick renderer chooses older protected geometry
```

This defeats the exact latest-state behavior Qt Quick migration was intended to provide and copies large arrays unnecessarily.

### R2 repair

- [x] newest immutable `BubbleFrame` is now the **only geometry authority**;
- [x] protected Bubble edge retains only compact consume-once metadata/identity/timestamps/event kinds;
- [x] event consequences remain safe because Bubble integrates every authored step and kick/vocal/snare consequences are forward-carried in the simulation's subsequent geometry/state;
- [x] the bridge may still protect/coalesce the consume-once event metadata;
- [x] the renderer never lets that metadata replace positions/radii/trails;
- [x] large protected-array copies and repeated render-boundary uploads of stale event frames are removed.

This repair is expected to improve both correctness and overhead.

### R2 physical Bubble gate

- [ ] Does live music finally produce obvious radius/position/trail response?
- [ ] If yes, quantify remaining parity rather than retuning the shared engine.
- [ ] If no, continue B6-B9: latest `BubbleFrame` arrays -> adapter -> bridge -> renderer payload -> shader-visible geometry/alpha.

## 6. DevCurve historical ghost deviation

This was found while following the jagged-outline / missing-bottom-hit observation.

The saved historical presets contain:

```text
devcurve_ghosting_enabled=true
devcurve_ghost_alpha=0.65
devcurve_ghost_decay=0.4
```

but source comparison proves the known-good historical renderer did **not** visually implement that setting:

- historical shader declared `u_ghost_alpha` but never consumed it;
- historical shader had no ghost curve arrays;
- historical renderer never supplied a delayed second set of curve samples.

Quick added a new behavior during migration:

```text
logical runtime stores a delayed ghost curve ring
-> renderer uploads 4 additional arrays of 96 floats
-> shader draws four extra stale filled + outlined layers
```

With the basic preset's 65% ghost alpha, this is a material visual redesign. It can create doubled/stair-stepped outline appearance and can visually mask a short movement in the transient/bottom layer.

R2:

- [x] keep persisted ghost settings so settings/preset compatibility is not damaged;
- [x] stop authoring a DevCurve ghost curve ring;
- [x] stop uploading four 96-float ghost arrays;
- [x] remove the Quick-only ghost draws from the shader;
- [x] retain current adjustable viewport geometry/scaling;
- [x] retain the real DevCurve solver, layer ordering, shadow, specular and curve fields.

This is both historical parity and a performance simplification.

### DevCurve transient diagnostics

If the bottom layer is still weak after removing the visual mask, R2 adds a bounded event-driven line:

```text
[VIS_DEVCURVE_TRANSIENT]
raw_b/raw_m/raw_h
smooth_t
curve_span
ready
```

It emits only when a meaningful raw transient exists and is rate-limited. This directly compares the source bass transient used historically to the solver's smoothed transient lane and resulting transient-curve excursion.

## 7. Sine paused idle adjustment

The physical run proves idle motion exists. The requested change is therefore deliberately mode-local and paused-only:

```text
paused speed gate: 0.14 -> 0.168
paused idle phase:  0.22 -> 0.264
```

Both are exactly +20%.

- [x] live `u_playing == 1` path remains at `1.0`;
- [x] BeatEngine/source energy is untouched;
- [x] no QML timer or second animation owner is added;
- [x] existing Sine authored/runtime idle state remains the authority.

## 8. Spectrum pause handoff

Do **not** change the steady idle floor in R2.

Source and R1 logs agree:

- paused logical runtime authors the intentional hump immediately once the paused logical frame exists;
- steady max is approximately `0.24` before the historical renderer transfer;
- user physically sees the correct hump after the short zero interval.

Therefore the remaining question is a transition seam, not floor amplitude.

R2 adds evidence, not a speculative gain/floor workaround:

```text
last live frame
-> playback edge
-> first paused logical frame
-> T6 bridge publication
-> T7 Quick consume with bars_level
-> next 3 [VIS_SPECTRUM_HANDOFF] retained states
```

Next repair rule:

- [ ] if T5/T6 already contain floor but T7 reports zero -> bridge/item/node bug;
- [ ] if T7 contains floor but pixels still zero -> Spectrum renderer/shader draw bug;
- [ ] if pre-pause logical bars become zero while canonical state is still Play -> classify Media/source-to-Pause handoff and fix without contaminating quiet music passages;
- [ ] never increase `_IDLE_BASELINE_MAX` merely to hide the gap.

## 9. Settings/source controls reconfirmed

The R2 work does not reopen controls already proven correct:

- [x] per-mode bar count;
- [x] audio block size;
- [x] dynamic/manual floor;
- [x] adaptive/manual sensitivity;
- [x] dynamic-range/energy boost mapping;
- [x] input gain;
- [x] `AGC=0.0` exact no-AGC/raw-output bypass.

The earlier enormous defect was the adjacent shared notch/shaping source family that the split owner omitted, not these technical controls.

## 10. Tests changed in R2

Only tests whose contract changed or that protect a new repair should be included in the handoff ZIP.

- `tests/test_qtquick_visualizer_reactivity_config_parity.py`
  - historical wake order;
  - 1.0 s cold ramp;
  - warm-resume no-ramp remains;
  - prior source/preset parity bars remain.
- `tests/test_qtquick_visualizer_bubble.py`
  - protected edge is compact metadata;
  - latest `BubbleFrame` geometry wins even with a protected event edge.
- `tests/test_bubble_btf_coalescing.py`
  - forward-carried event consequence is proved in the ordinary latest frame rather than a protected geometry duplicate.
- `tests/test_qtquick_visualizer_sine.py`
  - paused-only +20% shader constants.
- `tests/test_qtquick_visualizer_devcurve.py`
  - historical ghost controls remain visually inert;
  - Quick shader no longer invents ghost-curve uniforms.

No unchanged test tree is needed in the superseding ZIP.

## 11. H3/H3b/H4 plan cleanup

Operator has validated these slices.

- [x] H3 Reddit product action — closed.
- [x] H3b Clock mode/CUSTOM persistence — closed.
- [x] H4 Media Play/Pause/seek semantics — closed.

`Current_Plan.md` removes their rows and detailed active checklists entirely. Durable historical evidence remains in the migration docs / operator ledger.

## 12. Physical run requested from this checkpoint

Use real music and leave visualizer diagnostics enabled.

### Bubble

1. pause long enough to see idle behavior;
2. Play a track with obvious kick/body variation;
3. leave Bubble visible for at least ~15 s;
4. include a pause -> Play edge;
5. report whether Bubble visibly changes size/motion now.

Relevant log tags:

```text
[VIS_REACTIVITY] mode=bubble
[BUBBLE_CADENCE]
[VIS_PLAYBACK_EDGE]
```

### Spectrum

1. run active music for several seconds;
2. Pause once and watch specifically for zero -> idle-hump transition;
3. Play again.

Relevant tags:

```text
[VIS_PLAYBACK_EDGE]
[VIS_REACTIVITY] mode=spectrum
[VIS_SPECTRUM_HANDOFF]
```

### DevCurve

1. use basic Deep Blue preset;
2. observe whether outline jaggedness/doubling improves;
3. play material with strong kicks/heavy impacts and watch the bottom transient layer.

Relevant tags:

```text
[VIS_REACTIVITY] mode=devcurve
[VIS_DEVCURVE_TRANSIENT]
[SPOTIFY_VIS][DEVCURVE]
```

### Sine

Verify paused idle looks roughly 20% more alive while live music response remains unchanged.

### Resume latency

Capture at least one long-idle Pause -> Play. Corrected T3/T4/T5/T6/T7 now distinguish fresh-source latency, ramped logical response, bridge handoff and retained consumption.

## 13. Unrelated J observation recorded at this checkpoint

- [ ] Context-menu theme colours do not follow the active theme and appear stuck on one palette. This is recorded as J presentation/theme parity in `Current_Plan.md` / the operator ledger. It must use the canonical theme authority; do not introduce a context-menu-specific palette owner.

## 14. Still open after packaging

- [ ] Bubble B9 final visual-only smoothing/elasticity validation after the physically successful nonbaseline radius correction.
- [ ] Spectrum brief zero-before-floor seam after corrected trace.
- [ ] DevCurve physical validation after historical ghost no-op, bass-only transient diagnostics and logical-pixel AA restoration.
- [ ] Oscilloscope final presentation parity control.
- [ ] H5a/H6/H8/H7 according to `Current_Plan.md`.

## 15. Post-R2 physical continuation

### 15.1 Bubble remains visibly compressed; source and edge transport are prompt

The next two operator runs still report wildly weak Bubble response that never approaches the expected maximum size. The operator then quantified the gap as **at least about 3x weaker than the genuine old architecture**; the old goldens were known to be incomplete and are not accepted as physical closure. Stop decay improved slightly, while the most recent Pause -> Play ramp looked worse. The new trace does **not** support retuning the shared source or inserting an edge timer:

- [x] sustained live samples remain strong (`bass` commonly about `0.60-0.77`, `mid` up to about `0.97`);
- [x] Bubble remains fresh/ready and authored integration remains near 90 Hz / one step per request;
- [x] cold Play reaches fresh ready input and its first current logical publication at `93.8 ms`;
- [x] warm Play reaches a current logical publication at `20.0 ms`;
- [x] the retained item initially observes the already-published pre-Play idle snapshot: on the warm edge T7 reported about `2527 ms` source age, followed by the current logical frame at `20.0 ms`.

That immediate retained-old observation is a real handoff detail, but its tens-of-milliseconds lifetime cannot explain the full perceived slow radius ramp. Historical/current radius projection then exposes the exact magnitude loss:

```text
historical snapshot/shader: pos.z = authored_radius
current nonbaseline path:   pos.z = authored_radius / domain_h
active domain_h:            772.8311688311688 / 280 = 2.760111317...
```

The historical renderer interpreted `pos.z` as a fraction of the actual card inner height. Quick uploaded the already-divided value unchanged, and its shader applied no compensating multiplier. Depending on border accounting, this is a source-proven **2.72-2.76x physical radius loss**, matching the operator's 3x-class observation.

Correction:

- [x] keep expanded-world X/Y and trail normalization;
- [x] keep shader aspect correction so bubbles remain round;
- [x] restore final authored radius unchanged as a fraction of actual card height;
- [x] inverse-map rendered radius, collision-only gaps and positional correction caps by `domain_h` inside collision/spawn geometry so visually enlarged bubbles do not overlap at the old attenuated spacing; canonical 1x1 behavior remains exact;
- [x] do not alter source gain, pulse formulas, smoothing, contraction, cadence, DPR, or retired `bubble_growth`;
- [x] add compact `[VIS_BUBBLE_GEOMETRY] stage=B6_B7` final-simulation/frozen-big summaries and `stage=B8` retained logical/device-pixel summaries, with bounded extra samples around playback edges and no new clock;
- [x] pin the active-profile 2.760x correction, expanded-world collision/spawn conversion and shown-Quick round/tall projection in focused tests;
- [ ] physically validate old-architecture magnitude and the Play/Pause radius trajectory (B9).

If ramp shape remains wrong after the magnitude restoration, the new B6-B8 samples now identify whether final simulation radius or retained projection is discontinuous before any smoothing/contraction change is considered.

### 15.1.1 First corrected B9 trace: magnitude restored, visual-only settling remains

The first operator run with the corrected radius projection reports Bubble as **dramatically better and almost close-worthy**. The compact trace confirms that the corrected magnitude reaches retained Quick without a new transport defect:

- [x] Play reaches current source/logical state in `105.7 ms`, with the first current frame only `6 ms` old;
- [x] authored service remains about `88-90 Hz` and requested/integrated Bubble steps remain `1.000`;
- [x] B6 final, B7 frozen and B8 retained radii agree;
- [x] retained radius reaches about `75.95` logical px / `113.92` device px at DPR `1.5` in the short run;
- [x] the operator physically confirms the magnitude correction;
- [ ] the remaining visual complaint is limited to size smoothing/elasticity shape.

The active preset authors `bubble_big_visual_smoothing=1.0`. At that setting, the display-only filter's hard hold band could retain an unchanged radius until target error reached roughly 13-19% of the current hero radius, then switch to a much faster correction rate. That mechanism made Play/Pause settling look held-then-released even though source, cadence, publication and retained magnitude were current.

The bounded correction removes only that hard early-return band. The existing micro rise/drop rates now converge continuously for sub-settle changes; large-delta attack, hot-energy smoothing blend, pulse/contraction/clamp authority and the authored cadence are unchanged. A same-bubble 90 Hz rise/drop oracle pins nonzero monotonic settling at smoothing `1.0`, and B6/B7 now reports target maximum plus maximum display lag for the next physical run. Final Play/Pause visual validation remains open because the confirming short trace contained Play but no new Play -> Pause edge.

### 15.1.2 Latest B9 trace: edge response improved; rate switching still flickers

The next short operator run accepts the magnitude and reports Play/Pause as much better, but rejects the remaining elasticity/hero smoothing: contractions rapidly flicker rather than breathe. Source age remains about `5.5-46.9 ms`, authored service remains about `89.8 Hz`, requested/integrated remains `1.000`, and the enlarged radius does not contact its clamp. The failure is therefore inside the display-only settling shape, not source freshness, cadence, transport, magnitude or clamp authority.

Source inspection finds a second discontinuity after removal of the hard hold: a target hovering around the settle band can alternate between the micro rate and the much faster macro rate on adjacent frames. The bounded correction now:

- [x] replaces that threshold switch with a continuous smooth interpolation over target error;
- [x] continuously blends drop-ratio and soft/sharp-drop thresholds as well;
- [x] preserves exact large-edge `40 Hz` rise and `22 Hz` drop endpoints so the newly-good Play/Pause path is not weakened;
- [x] tracks one stable live big Bubble until retirement and publishes its target/display radius, delta, applied step, effective rate and blend through the existing bounded B6/B7/B8 cadence;
- [x] adds same-bubble threshold-hover and tracked-identity runtime oracles;
- [x] focused Bubble/Quick gates pass `85/85` and the maintained `h-destination` profile passes `78/78`;
- [ ] requires another physical B9 run to accept breathing contraction/elasticity.

The same operator run also reports that stream speed and drift speed/amount do not react perceptibly to transients. Existing source shows stream motion dominated by smoothed mid/high plus a weak vocal/snare envelope, while drift is dominated by sustained/body energy and authored static controls. That is the next separate bounded correction: add a decaying transient contribution to the existing motion drive and prove visible short-window displacement without changing authored settings, source gain, radius response, cadence or adding a clock.

### 15.1.3 Bounded transient-motion continuation

The separate motion correction is now implemented at the existing `BubbleSimulation` owner:

- [x] kick, snare and vocal-swell events remain consume-once and combine into one bounded motion-event scalar;
- [x] an event immediately lifts the existing stream-burst envelope, whose existing `7 Hz` release forward-carries the positional consequence without another state owner or clock;
- [x] stream burst receives a bounded direct event contribution and drift receives an independently capped `0.18` transient lift;
- [x] authored stream/drift amount, speed, frequency and direction remain unchanged;
- [x] Bubble pulse, radius, smoothing, clamp, source gain and cadence paths are untouched;
- [x] a manual-one-big-Bubble same-body A/B oracle proves greater short-window stream and drift path length after one snare while requiring identical pulse and rendered-radius sequences;
- [x] B6/B7/B8 and `[SPOTIFY_VIS][BUBBLE][DRIFT]` expose event, envelope, burst, capped drift and mean stream/drift motion-stage steps at existing bounded cadence; these steps are measured before impulse/collision correction and are not final trajectory distance;
- [x] focused Bubble/Quick gates pass `87/87`, BTF/cadence/renderer transport gates pass `15/15`, the maintained `h-destination` profile passes `78/78`, and an independent read-only audit is GREEN;
- [ ] operator validation must confirm that transient stream/drift response is perceptible but not overdriven.

### 15.2 DevCurve AA and transient-diagnostic corrections

The second physical report says DevCurve edges remain jagged after removal of migration-invented ghost layers. Source comparison now disproves the remaining AA mapping:

```text
historical / logical-pixel width: 1.15 / inner_h
Quick before correction:          1.15 * visual_scale / inner_h
observed CUSTOM visual_scale:     0.75
```

Quick coordinates are already logical pixels, so multiplying coverage width by the independent content scale narrowed the edge a second time. R2 continuation restores the historical logical-pixel AA width while preserving current content-rect/viewport sizing.

The supplied `[VIS_DEVCURVE_TRANSIENT]` samples were also misleading: they were triggered by `max(bass, mid, high)` even though the historical/current solver intentionally feeds the bottom transient layer from **bass transient only**. In the observed package all 51 diagnostic samples had zero raw bass, so `smooth_t=0` was correct. The trigger and event summary now use the bass lane; no DevCurve energy/gain formula changed.

- [x] remove the second AA scale factor and its now-unused uniform;
- [x] pin historical logical-pixel AA width in a shader contract test;
- [x] pin bass-only transient-layer behavior;
- [x] correct the real-Quick ghost test to require pixel identity for an historically inert control;
- [x] focused logical/shader and shown-Quick DevCurve gates pass;
- [ ] operator re-measure edge smoothness and capture a genuine bass-transient event if bottom-layer response is still suspect.

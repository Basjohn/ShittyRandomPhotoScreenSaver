# H5c Implementation Checkpoint R2 — Physical-log driven reactivity repairs

Date: 2026-08-31  
Behavioral oracle: `3fe5df687387b6b6a121142372c43a7719442386`  
Input physical trace: post-R1 source-mode logs supplied 2026-08-31  
Execution authority: `Current_Plan.md`

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

- [ ] Bubble B6-B9 if latest-geometry repair is insufficient.
- [ ] Spectrum brief zero-before-floor seam after corrected trace.
- [ ] DevCurve bottom transient lane if removal of invented ghosts does not restore visibility.
- [ ] DevCurve AA only if jaggedness persists after ghost removal; preserve adjustable viewport scaling unless its coordinate math is specifically disproven.
- [ ] Oscilloscope final presentation parity control.
- [ ] H5a/H6/H8/H7 according to `Current_Plan.md`.


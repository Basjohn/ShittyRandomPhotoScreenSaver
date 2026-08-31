# Visualizer Reactivity Audit — Historical vs Current Source Evidence Matrix

Date: 2026-08-31  
Historical tree: `3fe5df687387b6b6a121142372c43a7719442386`  
Baseline current tree: user-supplied current worktree, 2026-08-31  
Implementation status: first bounded H5b/H5c repair applied in the superseding worktree; this matrix preserves **baseline deviation evidence** and separately records the repaired destination.
Execution/decomposition: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`

## 0. Purpose

This file is the detailed evidence companion to H5c. It records **what was compared, what is source-proven, what remains inference, and the exact source seams to inspect next** so `Current_Plan.md` can stay compact.

Evidence labels:

- **IDENTICAL** — byte-for-byte supplied historical/current match.
- **SEMANTIC MATCH** — source moved/changed structurally but compared behavior is equivalent.
- **PROVEN DEVIATION** — historical behavior and current behavior differ at an identified source seam.
- **OPEN** — comparison/physical classification incomplete; do not assert cause.

## 1. Evidence-tree identity

- [x] Historical source came from the user-supplied trimmed snapshot for exactly `3fe5df687387b6b6a121142372c43a7719442386`.
- [x] Current source came from the user-supplied current worktree ZIP.
- [x] The ZIPs, not GitHub, are the primary comparison evidence for this pass.
- [x] Historical code is treated as the behavior oracle only; current Quick architecture remains destination authority.

## 2. Upstream audio/analysis comparison

| Source file | Result | Audit meaning |
|---|---|---|
| `widgets/spotify_visualizer/audio_worker.py` | **IDENTICAL** | capture worker algorithms did not migrate |
| `widgets/spotify_visualizer/beat_engine.py` | **IDENTICAL** | BeatEngine energy/FFT/floor/Play-ramp implementation did not migrate |
| `widgets/spotify_visualizer/energy_bands.py` | **IDENTICAL** | band-energy contract did not migrate |
| `widgets/spotify_visualizer/feature_frame.py` | **IDENTICAL** | feature/source frame contract did not migrate |
| `widgets/spotify_visualizer/signal_contract.py` | **IDENTICAL** | signal contract did not migrate |
| `widgets/spotify_visualizer/oscilloscope_contract.py` | **IDENTICAL** | waveform contract did not migrate |
| `widgets/spotify_visualizer/technical_config.py` | **IDENTICAL** | canonical technical resolution algorithms did not migrate |
| `widgets/spotify_visualizer/transient_bus.py` | **IDENTICAL** | transient bus implementation did not migrate |
| `widgets/spotify_visualizer/bar_computation.py` | **SEMANTIC MATCH** | only type-only import path changed; computation is unchanged |

### Initial conclusion

- [x] No source basis for a first move that globally retunes FFT normalization, input gain, AGC, floor math, bar math or transient extraction.
- [x] Configuration **reaching** the unchanged engine is still in scope and produced a source-proven shared-input defect: the historical full-model Spectrum notch/shaping block stopped reaching the one BeatEngine under Quick ownership.

## 3. Current owner split — the critical migration boundary

### Construction

`engine/display_manager.py::_construct_quick_visualizer_owner_on()` resolves activation/model/technical cache and supplies the model to the new Quick visualizer owner.

Current data flow:

```text
resolve_visualizer_activation_payload(section)
-> SpotifyVisualizerSettings.from_mapping(...)
-> build_technical_cache(None, model)
-> QuickDisplayVisualizerOwner.configure(
     logical_kwargs=asdict(model),
     presentation_kwargs=asdict(model),
     technical_config=technical_cache.get(mode),
   )
```

### Application — baseline vs repaired destination

The baseline Quick owner called:

```text
apply_logical_vis_mode_kwargs(logical_tick_state, logical_kwargs)
apply_presentation_vis_mode_kwargs(presentation_state, presentation_kwargs)
apply_controller_technical_config(controller, resolved_technical)
```

and intentionally did **not** call the old mixed `apply_vis_mode_kwargs()`. That architecture is correct, but the source-owned preset block had no new owner.

The repaired destination now adds exactly one configuration-time source owner:

```text
apply_logical_vis_mode_kwargs(...)
apply_presentation_vis_mode_kwargs(...)
apply_engine_vis_mode_kwargs(one_existing_BeatEngine, canonical_full_model)
apply_controller_technical_config(...)
```

`apply_engine_vis_mode_kwargs()` owns no timer, cadence, polling loop, renderer or duplicate engine.

### Audit implication

- [x] The split is architecturally desirable; do not revive the mixed QWidget façade.
- [x] Every historical key with a live current consumer requires an explicit logical/presentation/source/technical destination.
- [x] Mechanical live-consumer coverage audit completed.
- [x] Direct stranded set repaired: three Bubble logical controls, two historical Spectrum creator translations, and the Spectrum/shared-source shaping block.
- [x] Oscillo/Sine/DevCurve generated line/style/layer mappings and the shared technical family already have explicit owners.
- [x] Retired `*_growth` sizing controls remain excluded.

## 4. Spectrum evidence matrix

### 4.1 Topology identity

| Layer | Historical | Baseline Quick | Repaired destination | Result |
|---|---|---|---|---|
| canonical model | `spectrum_render_mode` | `spectrum_render_mode` | same canonical key | semantic input preserved |
| creator/config adaptation | creator derives `spectrum_single_piece = render_mode != "segment"` | preset layer removes legacy boolean; logical applier ignored canonical render mode | logical owner derives `_spectrum_single_piece` directly from canonical mode; legacy boolean fallback-only | **PROVEN DEVIATION -> REPAIRED** |
| color topology translation | creator derives `spectrum_rainbow_per_bar = spectrum_unique_colors` | presentation applier listened only for legacy alias | presentation owner consumes canonical `spectrum_unique_colors` | **PROVEN DEVIATION -> REPAIRED** |
| visible consequence | `bars` selects continuous columns | canonical `bars` could fall to segmented default | source now selects historical topology family | physical proof pending |

Exact source seams:

- historical `rendering/spotify_widget_creators.py::apply_spotify_vis_model_config()`;
- current `core/settings/visualizer_presets.py` Spectrum canonicalization;
- current `widgets/spotify_visualizer/config_applier.py::apply_logical_vis_mode_kwargs()`;
- current `widgets/spotify_visualizer/logical_tick_state.py` default;
- current `widgets/spotify_visualizer/tick_pipeline.py` Spectrum runtime call.

### 4.2 Engine shape configuration

Historical/current legacy catch-all `apply_vis_mode_kwargs()` contains live BeatEngine setters for:

| Canonical input | Existing consumer | Baseline Quick | Repaired destination |
|---|---|---|---|
| `spectrum_mirrored` | `BeatEngine.set_spectrum_mirrored` | missing | `source_config_applier` -> existing setter |
| `spectrum_shape_nodes` | `BeatEngine.set_spectrum_shape_nodes` | missing | `source_config_applier` -> existing setter |
| `spectrum_notch_positions_mirrored` | selected -> `BeatEngine.set_notch_positions` | missing | selected active notch family -> existing setter |
| `spectrum_notch_positions_linear` | selected -> `BeatEngine.set_notch_positions` | missing | selected active notch family -> existing setter |
| `spectrum_wave_amplitude` | `SpectrumShapeConfig` -> BeatEngine | missing | one `SpectrumShapeConfig` transaction |
| `spectrum_profile_floor` | `SpectrumShapeConfig` -> BeatEngine | missing | one `SpectrumShapeConfig` transaction |
| `spectrum_lane_strengths_mirrored` | `SpectrumShapeConfig` -> BeatEngine | missing | one `SpectrumShapeConfig` transaction |
| `spectrum_lane_strengths_linear` | `SpectrumShapeConfig` -> BeatEngine | missing | one `SpectrumShapeConfig` transaction |
| `spectrum_drop_speed` | `BeatEngine.set_drop_speed` | missing | `source_config_applier` -> existing setter |

Result for every row: **PROVEN DEVIATION -> REPAIRED IN SOURCE; PHYSICAL EFFECT PENDING**.

`build_technical_cache()` / `quick_technical_config` remain the authority for the separate shared technical family; the full-model source-shaping block now has its own narrow owner rather than being misclassified as renderer state.

#### Why this block is shared-reactivity relevant

The historical full-model activation applied these Spectrum-named source settings regardless of which visualizer mode was visible. That matters because unchanged `bar_computation.py` reads `_spectrum_notch_positions` **before mode-specific state** to select raw bass/mid/treble boundaries. If the source block is absent it falls back to fixed split indices `4` and `10`. With the default mirrored preset notches (`0.30`, `0.65`) the intended approximate splits are:

| Mode / bar domain | Baseline missing-config fallback | Configured preset split (approx.) |
|---|---:|---:|
| Spectrum / 33 | `4 / 10` | `9 / 21` |
| Bubble / 48 | `4 / 10` | `14 / 31` |
| Oscilloscope / 32 | `4 / 10` | `9 / 20` |
| Sine / 40 | `4 / 10` | `12 / 26` |
| DevCurve / 32 | `4 / 10` | `9 / 20` |

Those raw lanes then feed noise-floor/expansion, transient state, AGC zones and the mode feeds. The omission is therefore a **source-proven common migration deviation capable of affecting every mode**, not merely a Spectrum appearance bug. The repair restores historical source ownership; physical remeasurement will quantify how much of each symptom it explains.

### 4.3 Final renderer transfer

Historical `widgets/spotify_visualizer/renderers/spectrum.py`:

```text
bar upload  = bar * 0.55
peak upload = peak * 0.55
```

Baseline `rendering/quick/visualizer/implementations/spectrum.py` uploaded raw bar/peak values.

The repair exports `SPECTRUM_SHADER_INPUT_SCALE = 0.55` from `spectrum_solid_hysteresis.py` and applies it exactly once in `prepare_spectrum_shader_levels()` at the Quick shader-input boundary, including peak fallback/padding. Logical/snapshot bars remain canonical.

Result: **PROVEN DEVIATION -> REPAIRED IN SOURCE; PHYSICAL S6/S7 PROOF PENDING**.

### 4.4 Spectrum next-source path after known fixes

The known topology/source/transfer deviations are repaired in source. Do not continue speculative tuning; remeasure the exact S0-S7 path in order:

```text
S0 selected preset/model values
S1 resolved Quick engine configuration
S2 BeatEngine configured mirror/shape/notch/drop state
S3 FeatureFrame/bar input before Spectrum frame runtime
S4 SpectrumFrameRuntime source_ready + bars/peaks
S5 captured SpectrumFrame bars/peaks
S6 Quick renderer values after canonical 0.55 transfer
S7 shader/topology result
```

- [ ] If S3 is already saturated after configuration parity, inspect unchanged engine inputs/config values rather than global Quick gain.
- [ ] If S3 is healthy and S4 saturates, inspect Spectrum frame-runtime smoothing/peak logic.
- [ ] If S5 is healthy and S6/S7 saturates, presentation remains at fault.

## 5. Bubble evidence matrix

### 5.1 Configuration ownership

| Input | Historical/legacy applier | Current Bubble consumer | Baseline Quick | Repaired destination |
|---|---|---|---|---|
| `bubble_group_drift` | applies to `_bubble_group_drift` | `tick_pipeline.py` | missing | logical owner; **repaired** |
| `bubble_collision_pop_mode` | applies to `_bubble_collision_pop_mode` | `tick_pipeline.py` | missing | logical owner; **repaired** |
| `bubble_big_visual_smoothing` | applies to `_bubble_big_visual_smoothing` | `tick_pipeline.py` | missing | logical owner; **repaired** |

Current fallbacks:

```text
group drift          False
collision pop        "off"
big visual smoothing 0.5
```

Current shipped Bubble presets include non-fallback values, so these omissions are behaviorally real.

### 5.2 Source-readiness behavior

Current Bubble flow:

```text
latest authoritative source metadata
-> tick_pipeline source_ready exact identity decision
-> BubbleFrameRuntime.advance(... source_ready=...)
```

If `playing=True` and `source_ready=False`, current Bubble runtime zeros energy/pulses/events but continues simulation.

Result: **OPEN high-priority shared suspect**, because this can exactly resemble smooth intentional idle energy under real music.

It is not yet proven wrong because historical code also fenced stale generations/activations.

### 5.3 Bubble renderer dead-end already eliminated

Historical Bubble renderer uploaded overall/bass/mid/high energy uniforms that the historical Bubble shader did not actually consume.

- [x] Do not restore these uploads.
- [x] Bubble visible reactivity is authored into simulation state (positions/radii/alpha/etc.) before rendering.

### 5.4 Bubble next exact source path

```text
BeatEngine latest FeatureFrame
-> tick_pipeline captured energy/pulse/source identity
-> source_ready
-> BubbleFrameRuntime
-> BubbleSimulation.tick
-> snapshot positions/extras/trails
-> render_state BubbleFrame
-> Quick bridge
-> Quick Bubble renderer radius/alpha/position mapping
```

For every layer record a compact numeric summary, not large arrays.

## 6. Source-readiness matrix across modes

| Mode | Current not-ready consequence | Can cadence continue? | Classification |
|---|---|---:|---|
| Bubble | energy/pulse/events zeroed; simulation continues | yes | **OPEN common suspect** |
| Oscilloscope | waveform not accepted; energy + kick/snare targets zero | yes | **OPEN common suspect** |
| Sine | energy + kick/snare + base heartbeat suppressed; idle logic separate | yes | **OPEN common suspect** |
| DevCurve | energy/transient replaced by zero state | yes | **OPEN common suspect** |
| Spectrum | current reactive bars not admitted; holds/non-reactive behavior | yes | **OPEN common suspect** |

### Required evidence before modifying the gate

Instrumentation is now implemented at each actual mode admission boundary:

- [x] current runtime generation;
- [x] current engine generation;
- [x] current engine activation;
- [x] source generation;
- [x] source activation;
- [x] source age;
- [x] readiness state/transition with compact raw -> resolved magnitude;
- [x] playback-edge correlation through T0-T7.
- [ ] collect the physical traces and prove whether the gate actually rejects/delays a valid current frame.

Do not remove stale-source safety merely to increase movement.

## 7. Play/Pause timing evidence

Current source route:

```text
Media model.stateChanged
-> DisplayManager._sync_quick_visualizer_playback
-> QuickDisplayVisualizerOwner.set_playing
-> controller.playing
-> BeatEngine.set_playback_state
```

`beat_engine.py` is identical between trees, including a 1.5 s cold Play ramp and 6.0 s capture keepalive grace.

Therefore:

- [x] no evidence of a deliberate new Quick debounce;
- [x] historical cold-start ramp is not itself a migration defect;
- [x] bounded T0-T7 markers are implemented across the existing Media -> owner -> source -> authored -> bridge -> retained-item chain; no workaround timer was added;
- [ ] physical delay still needs warm/cold edge classification;
- [ ] H4 Media canonical-truth timing must be distinguished from visualizer timing.

### T0-T7 seam map

| Edge | Source owner / evidence point | What failure means |
|---|---|---|
| T0 | retained Media model playbackState change | late here -> H4/provider truth |
| T1 | `QuickDisplayVisualizerOwner.set_playing` | late T0->T1 -> route/signal |
| T2 | `BeatEngine.set_playback_state` | late T1->T2 -> owner/engine call |
| T3 | first current authoritative FeatureFrame | late T2->T3 -> source/capture/warm state |
| T4 | first mode `reactive_source_ready=True` | late T3->T4 -> identity/readiness |
| T5 | first materially reactive authored mode frame | late T4->T5 -> mode logic |
| T6 | corresponding Quick snapshot publication | late T5->T6 -> adapter/bridge |
| T7 | retained renderer consumes revision | late T6->T7 -> presentation scheduling |

## 8. Sine idle evidence

Current `SineFrameRuntime` still has explicit paused behavior:

```text
minimum line speed >= 0.22
non-zero travel selection
idle shift phase += bounded authored dt * (0.12 * speed)
line shifts adjusted by travel direction
animation_time += dt
```

This means the physical missing-idle report is **not explained by a deleted Python idle formula**.

Next exact files/objects:

- [ ] `widgets/spotify_visualizer/sine_frame_runtime.py`
- [ ] `widgets/spotify_visualizer/tick_pipeline.py`
- [ ] `widgets/spotify_visualizer/render_state.py`
- [ ] snapshot adapter/publication path under `widgets/spotify_visualizer/`
- [ ] retained Quick visualizer synchronization under `rendering/quick/visualizer/`
- [ ] `rendering/quick/visualizer/implementations/sine.py`
- [ ] Sine fragment shader loaded through `widgets/spotify_visualizer/shaders.py`
- [ ] scene-controller present request while paused

Test the transport first; only compare shader visuals after proving changed idle values reach the renderer.

## 9. Oscilloscope/Sine smoothing evidence

Historical compositor-side line-mode energy smoothing used an approximately 60 ms attack / 120 ms release.

Current Oscilloscope/Sine mode-owned runtimes preserve that treatment at authored time.

Result: **SEMANTIC MATCH for the compared smoothing seam**.

Still open:

- [ ] exact waveform/source normalization at mode runtime;
- [ ] exact transient/heartbeat assistance;
- [ ] exact final amplitude/glow/intensity mapping in Quick;
- [ ] paused idle transport.

## 10. Configuration completeness audit — field worklist

The historical-live-consumer configuration audit is complete. This checklist distinguishes **ownership coverage** from still-open renderer/behavior comparison.

### Shared/technical ownership

- [x] bar count
- [x] dynamic/manual floor
- [x] adaptive/manual sensitivity
- [x] audio block size
- [x] dynamic-range/energy boost
- [x] AGC
- [x] input gain
- [x] kick lane gain
- [x] transient pulse gain / clamp
- [x] mode transient mixes

These remain in the existing technical owner; no duplicate source applier was added for them. Direct historical/current comparison also verified the behaviorally sharp values rather than merely key presence:

- [x] `agc_strength=0.0` survives resolution/clamping as exact zero and the unchanged worker exits AGC before normalization (`< 0.01`), so zero still means **no AGC**;
- [x] `dynamic_floor=False` remains false and preserves manual-floor operation;
- [x] explicit `audio_block_size` reaches `set_audio_block_size(...)`;
- [x] per-mode `bar_count` reconfigures the existing BeatEngine/controller bar domain;
- [x] `dynamic_range_enabled` retains historical `1.18`/`0.85` energy-boost semantics;
- [x] adaptive-sensitivity false, manual sensitivity and input gain retain their resolved values.

A focused parity test now locks the zero/false case because these controls can change preset response dramatically. This technical subset was already correct in baseline Quick; the H5c source-config repair is intentionally adjacent rather than duplicative.

### Spectrum ownership

- [x] canonical `spectrum_render_mode` translation restored
- [x] canonical `spectrum_unique_colors` translation restored
- [x] mirror/shape/notch/wave/profile/lane/drop shared-source block restored
- [x] visual smoothing fields already owned by logical state
- [x] Spectrum ghosting/decay already owned
- [x] colors/border/rainbow presentation already owned (with unique-colors translation repaired)
- [x] historical `0.55` final transfer restored
- [ ] physical peak behavior and S3-S7 response after repair

### Bubble ownership

- [x] group drift repaired
- [x] collision-pop mode repaired
- [x] big visual smoothing repaired
- [x] bounce/frequency/size/speed ranges already owned
- [x] transient mix inputs already owned
- [x] ghost/trail behavior already owned
- [x] specular/alpha/color presentation already owned
- [x] protected Bubble event path no longer carries/overrides full geometry; newest ordinary `BubbleFrame` is geometry authority
- [ ] B6-B9 physical snapshot->Quick magnitude comparison after latest-geometry repair

### Oscilloscope ownership

- [x] speed
- [x] line amplitude
- [x] waveform smoothing
- [x] line count/ghost lines
- [x] ghost decay/intensity
- [x] glow + reactive glow
- [x] transient width mix
- [ ] final line width/amplitude renderer comparison

### Sine ownership

- [x] speed
- [x] line count
- [x] travel per line
- [x] phase/shift per line
- [x] reactivity parameters
- [x] ghosting
- [x] heartbeat/transient assistance
- [x] paused idle transport physically confirmed present
- [x] paused-only shader motion increased 20% without changing live gain
- [ ] final live uniform/intensity parity comparison

### DevCurve ownership

- [x] layer enabled/order
- [x] energy/transient mapping
- [x] alpha/outline
- [x] offsets/domain
- [x] tuning/specular parameters
- [x] ghost settings remain parseable/persisted, but historical rendering is now source-proven to have treated them as a visual no-op
- [x] migration-invented delayed ghost-curve rendering removed from Quick; current-frame geometry remains authoritative
- [x] logical-pixel AA coverage restored to historical `1.15 / inner_h`; the Quick-only `* visual_scale` term narrowed edges a second time at nonbaseline scale
- [x] transient diagnostic/solver contract pinned to the historical bass-transient lane; mid/high-only activity must not be classified as a failed bottom transient
- [ ] re-measure bottom transient-layer response after ghost removal
- [ ] re-measure outline smoothness after AA restoration; adjustable-viewport geometry remains unchanged

### Explicitly retired

- [x] old per-mode `*_growth` card-sizing authority is not a parity target.

## 11. Historical interaction scan worklist

- [x] middle-click same-mode preset hotswap/cycle known and separately tracked H8.
- [ ] scan historical mouse/semantic actions around Visualizer host.
- [ ] scan mode-change/preset-change reset semantics.
- [ ] scan Pause/Play behavior for source-state preservation.
- [ ] scan any per-mode Custom snapshot restoration.
- [ ] scan settings refresh for engine setter calls omitted by new owner split.

### 11.1 Golden coverage boundary — why GREEN did not prove live preset reachability

Historical deterministic replay accepts `FeatureFrame` records that already contain energy lanes, raw bars and waveform state, then executes the real logical tick path. The presentation goldens sample downstream completed state. This gives strong protection for mode evolution, cadence independence and presentation sampling **after feature state exists**, but it bypasses the production seam that H5c found broken:

```text
preset/settings model -> Quick owner split -> BeatEngine/audio-worker setters -> live FFT shaping
```

Consequently a migration can keep goldens GREEN while production audio is shaped with fallback notches/default engine state. The correct response is targeted reachability/configuration tests, not golden regeneration.

- [x] no golden baseline was regenerated for this repair;
- [x] focused owner/source routing test added;
- [x] focused technical `0.0`/`False`/explicit block-size/bar-count test added;
- [ ] future H8 same-mode preset hotswap must prove the same existing engine receives new source config without recreation.

## 12. Implementation / validation status — 2026-08-31

- [x] `source_config_applier.py` added as the sole new source-settings routing seam.
- [x] Quick owner applies source config only at existing configuration/mode-activation edges.
- [x] Bubble stranded logical controls repaired.
- [x] Spectrum render-mode + unique-colors translations repaired.
- [x] Spectrum historical shader-input transfer repaired exactly once.
- [x] `[VIS_SOURCE_CONFIG]`, `[VIS_TECH_CONFIG]`, `[VIS_REACTIVITY]` and T0-T7 playback diagnostics added at existing boundaries with compact/rate-limited data only.
- [x] One new focused test file added: `tests/test_qtquick_visualizer_reactivity_config_parity.py`; it now covers shared-source routing, Bubble controls, Spectrum translations/transfer, plus the already-correct technical zero/false contract (`bar_count`, explicit block size, manual floor, `AGC=0.0`, etc.).
- [x] Changed Python sources and the new test syntax-compile successfully in the audit container.
- [x] Existing replay/presentation goldens intentionally left unchanged; their downstream boundary does not prove live preset -> source configuration reachability.
- [ ] Pytest execution pending because this Linux audit container does not provide PySide6; do not report GREEN until run in the normal project environment.
- [ ] Physical all-mode reactivity + warm/cold Play/Pause traces pending.

## 13. Evidence rules for the continuation

- [ ] A historical/current source diff outranks a stale test expectation.
- [ ] A live consumer with no current configuration route is a defect even if its fallback looks plausible.
- [ ] A fallback/default is not parity proof.
- [ ] A healthy ~90 Hz authored cadence is not proof of healthy live-source reactivity.
- [ ] Intentional idle energy is not evidence that real music magnitude is reaching the mode.
- [ ] Spectrum's mode-specific failures cannot justify a global gain change.
- [ ] A source-readiness fence is not removed until identity evidence proves it rejects valid current data.
- [ ] Current sizing/viewport architecture remains authoritative; historical `*_growth` sizing does not return.


## 14. R2 physical-log evidence and bounded continuation — 2026-08-31

The first post-repair physical trace materially narrows the remaining defects.

### 14.1 Bubble: source/cadence exonerated, retained payload seam repaired

Observed under real music:

- [x] `source_ready=True`;
- [x] strong non-idle energy reaches Bubble (representative overall ~0.57-0.65, mid ~0.79-0.80, bass pulse ~0.55+);
- [x] authored Bubble integration remains ~90 Hz with essentially 1:1 requested/integrated steps;
- [x] a genuinely current post-Play Bubble source frame can arrive in tens of milliseconds, so a universal 1.5 s capture delay is disproved.

Therefore the remaining nearly-dead visible Bubble response is downstream of source admission and authored cadence. Source inspection then found a migration-only contradiction with the intended latest-state Quick design:

```text
newest ordinary BubbleFrame geometry
        +
older protected consume-once event edge carrying a full geometry copy
        -> renderer preferred protected full geometry
        -> older event snapshot could override newer authored geometry
```

Repair:

- [x] protected Bubble edge carries compact event identity/timestamp/kind metadata only;
- [x] newest ordinary `BubbleFrame` owns positions/extras/trails/count at Quick;
- [x] existing consume-once/coalescing metadata semantics remain;
- [x] temporal harness now models the real Bubble invariant: event consequences are forward-carried in persistent simulation state into the next latest authored frame;
- [x] no replay queue, duplicate cadence, per-frame configuration poll or extra presenter was introduced.

Next physical gate:

- [ ] verify Bubble now visibly expands/contracts/travels in proportion to the already-proven live magnitude;
- [ ] if still weak, compare immutable `BubbleFrame` radius/position summaries to T7/renderer payload rather than changing BeatEngine gain.

### 14.2 Play resume: historical wake restored; cold ramp bounded to 1.0 s

The first T3 trace for some modes was misleading because the diagnostic checked the 1.5 s periodic sampler before checking edge milestones. Bubble happened to expose the error by logging a true fresh source around ~73 ms.

Source comparison also found a real lifecycle omission:

- historical pause->play called `engine.wake()` before playback-state commit;
- migrated Quick pause->play had omitted that wake.

R2 repair:

- [x] restore existing `engine.wake()` on a real False->True edge only;
- [x] preserve one BeatEngine and its existing stale-capture test/restart semantics;
- [x] shorten **cold** reactivity ramp from 1.5 s to **1.0 s**;
- [x] warm resumes remain unramped;
- [x] generation/activation freshness fencing remains unchanged;
- [x] T3/T4 edge milestones are checked independently of periodic diagnostic sampling;
- [x] T5 Play publication requires a post-edge source timestamp;
- [x] T7 records actual bars/energy/waveform magnitude consumed by retained Quick.

The 1.0 s change is a bounded parity/usability adjustment, not a workaround for stale data: current-generation fencing still decides whether data is admissible, while `wake()` handles stale capture ownership.

### 14.3 Spectrum: steady pause floor is correct; only the handoff gap is open

Physical clarification:

- [x] Spectrum is again visually recognizable and strongly reactive after R1 repairs;
- [x] steady paused state reaches the intended authored idle hump (~0.24 max in the observed trace);
- [ ] immediately after Pause there is a brief **zero-bars gap before the correct floor appears**.

Do **not** raise the idle floor. R2 adds bounded post-Pause retained-consumption markers so the next trace can classify:

```text
last live frame -> canonical Pause edge -> first paused logical floor frame -> bridge -> T7 retained draw
```

- [x] `[VIS_SPECTRUM_HANDOFF]` emits only a few post-edge retained samples;
- [ ] fix the discontinuity at the source-proven failing seam after that trace.

### 14.4 Sine: idle exists; paused-only motion raised 20%

The physical run disproves the earlier "missing idle" report. Idle transport works, but is slightly too weak.

- [x] preserve live/music reactivity coefficients;
- [x] increase only paused idle gate/phase motion by 20%;
- [ ] operator re-measure.

### 14.5 DevCurve: migration invented rendered ghost curves

Historical source comparison found a stronger explanation for the new jagged/doubled-looking outlines than adjustable viewport scaling:

- the historical preset exposed DevCurve ghost settings;
- the historical fragment shader declared `u_ghost_alpha` but did not use it and rendered **no ghost curves**;
- Quick introduced four stale ghost-curve layers, including outlines/fills and four additional curve-array uploads.

This was a migration-era visual redesign, not historical parity. It can both roughen outlines and visually bury the short bottom/transient layer.

R2 repair:

- [x] remove Quick-only ghost curve history/draws/uniform uploads;
- [x] retain ghost settings in model/persistence compatibility;
- [x] leave current adjustable viewport scaling intact;
- [x] leave the historical/current-near-identical DevCurve solver intact;
- [x] add bounded transient-layer diagnostics when a real transient is present;
- [ ] re-measure bottom heavy-hit line and outline smoothness before touching AA scaling.

### 14.6 Next log package should answer, not rediscover

- [ ] Bubble latest geometry: visible response versus strong `[VIS_REACTIVITY]` input.
- [ ] Play: corrected T0-T7 cold/warm edge timing after wake + 1.0 s cold ramp.
- [ ] Spectrum: `[VIS_SPECTRUM_HANDOFF]` around the zero-before-floor gap.
- [ ] DevCurve: `[VIS_DEVCURVE_TRANSIENT]` plus physical bottom-line and outline result after ghost removal.
- [ ] Sine: paused idle strength after +20%.

## 15. Post-R2 evidence update — second Bubble run and DevCurve edge source proof

### 15.1 Bubble edge timing versus visible ramp

- [x] latest run still looks severely under-reactive and never reaches expected maximum radius;
- [x] stop decay is slightly improved, but operator reports the next Play ramp looks worse;
- [x] cold Play current source/ready/logical publication arrives in `93.8 ms`;
- [x] warm Play current logical publication arrives in `20.0 ms`;
- [x] retained Quick first observes the pre-edge idle snapshot (warm source age about `2527 ms`) before the current frame;
- [x] sustained current source remains strong (`bass` about `0.60-0.77`, `mid` up to about `0.97`) and Bubble cadence remains healthy;
- [x] operator quantifies visible magnitude as at least ~3x weaker than genuine old architecture; incomplete old goldens do not overrule the physical observation;
- [x] source comparison finds exact 2.72-2.76x nonbaseline loss: current snapshot divided final radius by `domain_h=772.831/280=2.760111...`, while historical snapshot/shader used the authored radius directly against actual card height;
- [x] restore card-height-normalized radius while position/trail world coordinates remain normalized and circles remain aspect-correct;
- [x] inverse-map that radius plus collision-only gap/correction distances by `domain_h` for collision/spawn coherence, preserving canonical 1x1 behavior;
- [x] add B6/B7 final-simulation/frozen-big radius-alpha plus B8 retained logical/device-pixel diagnostics around steady music and Play/Pause;
- [x] first corrected B9 run reports dramatically better / almost close-worthy magnitude; B6/B7/B8 agree, the source is current by `105.7 ms`, cadence remains ~89 Hz / 1.000 integration, and B8 reaches about `75.95` logical px / `113.92` device px radius at DPR `1.5`;
- [x] remove the display-only hard hold band at smoothing `1.0`, preserve existing micro rise/drop and attack paths, pin continuous same-bubble 90 Hz settling, and add target/lag scalars to B6/B7;
- [x] next B9 run accepts much better Play/Pause and magnitude but rejects elasticity: contractions rapidly flicker rather than breathe; source is fresh, cadence is about `89.8 Hz`, integration is `1.000`, and the enlarged radius does not contact its clamp;
- [x] localize the residual flicker to discontinuous micro/macro rate selection around the settle/drop thresholds; replace it with continuous interpolation while preserving exact `40 Hz` rise / `22 Hz` large-drop endpoints;
- [x] add one stable tracked-bubble target/display/delta/step/rate/mix diagnostic to the existing bounded B6-B8 samples so aggregate maxima no longer hide same-bubble threshold switching;
- [ ] final B9 gate is physical acceptance of breathing contraction/elasticity after rate interpolation;
- [ ] stream/drift transient motion remains visibly imperceptible; add and falsify one bounded decaying transient contribution at the existing motion owner without changing authored settings, source gain, radius or cadence.

Classification: source/config/cadence and long Play transport delay are exonerated. The retained-old first observation is real but too brief to explain the full physical ramp. Final nonbaseline radius normalization was the magnitude defect and is physically validated as dramatically better. Removing the hard hold improved Play/Pause but did not close elasticity because the remaining two-rate threshold still toggled under a moving target. The display-only correction rate now varies continuously, with stable per-bubble evidence added at existing cadence. No gain, cadence, timer, pulse, contraction or latest-state contract changed; physical elasticity validation and a separate transient-motion correction remain open.

### 15.2 DevCurve source-proven continuation

- [x] post-ghost-removal physical report still identifies jagged edges;
- [x] historical and current coordinate paths both operate in logical pixels at the AA calculation;
- [x] Quick alone multiplied the one-pixel coverage width by independent `visual_scale`, producing 25% narrower AA at the observed `0.75` scale;
- [x] restore `1.15 / inner_h` and remove the unused scale uniform without changing content geometry;
- [x] all 51 prior transient diagnostics had zero raw bass and were triggered only by mid/high activity; correct the diagnostic to match the historically bass-only solver input;
- [ ] operator re-measure decides whether any further DevCurve presentation work remains.

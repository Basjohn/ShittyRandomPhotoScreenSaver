# Visualizer Reactivity Audit — Historical vs Current Source Evidence Matrix

Date: 2026-08-31  
Historical tree: `3fe5df687387b6b6a121142372c43a7719442386`  
Current tree: user-supplied current worktree, 2026-08-31  
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
- [x] Configuration **reaching** the unchanged engine is still in scope and has already produced one Spectrum defect.

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

### Application

`widgets/spotify_visualizer/quick_display_visualizer_owner.py::_apply_configuration()` currently calls:

```text
apply_logical_vis_mode_kwargs(logical_tick_state, logical_kwargs)
apply_presentation_vis_mode_kwargs(presentation_state, presentation_kwargs)
apply_controller_technical_config(controller, resolved_technical)
```

It intentionally does **not** call the old mixed `apply_vis_mode_kwargs()`.

### Audit implication

- [x] This split is architecturally desirable.
- [x] Every historical key with a live current consumer now requires an explicit destination mapping.
- [x] Spectrum and Bubble already prove that the split is incomplete.
- [ ] Complete mechanical field coverage before declaring the split finished.

## 4. Spectrum evidence matrix

### 4.1 Topology identity

| Layer | Historical | Current | Result |
|---|---|---|---|
| canonical model | `spectrum_render_mode` | `spectrum_render_mode` | same semantic input |
| creator/config adaptation | creator derives `spectrum_single_piece = render_mode != "segment"` | preset layer removes legacy boolean; Quick logical applier ignores canonical render mode | **PROVEN DEVIATION** |
| logical default | historical creator explicitly sends selected value | `_spectrum_single_piece = False` | current falls to segmented when canonical key ignored |
| visible consequence | `bars` can select continuous columns | `bars` can still resolve segmented | matches physical wrong topology |

Exact source seams:

- historical `rendering/spotify_widget_creators.py::apply_spotify_vis_model_config()`;
- current `core/settings/visualizer_presets.py` Spectrum canonicalization;
- current `widgets/spotify_visualizer/config_applier.py::apply_logical_vis_mode_kwargs()`;
- current `widgets/spotify_visualizer/logical_tick_state.py` default;
- current `widgets/spotify_visualizer/tick_pipeline.py` Spectrum runtime call.

### 4.2 Engine shape configuration

Historical/current legacy catch-all `apply_vis_mode_kwargs()` contains live BeatEngine setters for:

| Canonical input | Current consumer | Quick owner currently applies? | Result |
|---|---|---:|---|
| `spectrum_mirrored` | `BeatEngine.set_spectrum_mirrored` | no | **PROVEN DEVIATION** |
| `spectrum_shape_nodes` | `BeatEngine.set_spectrum_shape_nodes` | no | **PROVEN DEVIATION** |
| `spectrum_notch_positions_mirrored` | selected -> `BeatEngine.set_notch_positions` | no | **PROVEN DEVIATION** |
| `spectrum_notch_positions_linear` | selected -> `BeatEngine.set_notch_positions` | no | **PROVEN DEVIATION** |
| `spectrum_wave_amplitude` | `SpectrumShapeConfig` -> BeatEngine | no | **PROVEN DEVIATION** |
| `spectrum_profile_floor` | `SpectrumShapeConfig` -> BeatEngine | no | **PROVEN DEVIATION** |
| `spectrum_lane_strengths_mirrored` | `SpectrumShapeConfig` -> BeatEngine | no | **PROVEN DEVIATION** |
| `spectrum_lane_strengths_linear` | `SpectrumShapeConfig` -> BeatEngine | no | **PROVEN DEVIATION** |
| `spectrum_drop_speed` | `BeatEngine.set_drop_speed` | no | **PROVEN DEVIATION** |

Current `build_technical_cache()` and `quick_technical_config.apply_controller_technical_config()` cover shared technical values but not this Spectrum shape family.

### 4.3 Final renderer transfer

Historical `widgets/spotify_visualizer/renderers/spectrum.py`:

```text
bar upload  = bar * 0.55
peak upload = peak * 0.55
```

Current `rendering/quick/visualizer/implementations/spectrum.py` uploads raw bar/peak values.

Current `widgets/spotify_visualizer/spectrum_solid_hysteresis.py` still owns `_SPECTRUM_UPLOAD_SCALE = 0.55` and uses it in its bar-domain conversion.

Result: **PROVEN DEVIATION** at final renderer input.

### 4.4 Spectrum next-source path after known fixes

Do not continue speculative saturation work until the three known deviations are repaired and retested.

Then inspect, in order:

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

| Input | Historical/legacy applier | Current Bubble consumer | New Quick logical applier | Result |
|---|---|---|---|---|
| `bubble_group_drift` | applies to `_bubble_group_drift` | `tick_pipeline.py` | missing | **PROVEN DEVIATION** |
| `bubble_collision_pop_mode` | applies to `_bubble_collision_pop_mode` | `tick_pipeline.py` | missing | **PROVEN DEVIATION** |
| `bubble_big_visual_smoothing` | applies to `_bubble_big_visual_smoothing` | `tick_pipeline.py` | missing | **PROVEN DEVIATION** |

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

- [ ] current runtime generation;
- [ ] current engine generation;
- [ ] current engine activation;
- [ ] source generation;
- [ ] source activation;
- [ ] source age;
- [ ] readiness transition timestamp;
- [ ] whether upstream freshness fence already admitted the frame.

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

The next source comparison should be systematic rather than symptom-led.

### Shared/technical

- [ ] `bar_count`
- [ ] dynamic/manual floor
- [ ] adaptive/manual sensitivity
- [ ] audio block size
- [ ] dynamic-range/energy boost
- [ ] AGC
- [ ] input gain
- [ ] kick lane gain
- [ ] transient pulse gain / clamp
- [ ] mode transient mixes

### Spectrum

- [x] `spectrum_render_mode` gap found
- [x] mirror/shape/notch/wave/profile/lane/drop engine gap found
- [ ] visual smoothing fields
- [ ] ghosting/decay
- [ ] peak behavior
- [ ] colors/border/rainbow presentation
- [ ] segment count/topology parameters

### Bubble

- [x] group drift gap found
- [x] collision-pop mode gap found
- [x] big visual smoothing gap found
- [ ] all bounce/frequency/size/speed ranges
- [ ] transient mix inputs
- [ ] ghost/trail behavior
- [ ] specular/alpha/color presentation
- [ ] protected visible event path

### Oscilloscope

- [ ] speed
- [ ] line amplitude
- [ ] waveform smoothing
- [ ] line count/ghost lines
- [ ] ghost decay/intensity
- [ ] glow + reactive glow
- [ ] transient width mix
- [ ] final line width/amplitude transfer

### Sine

- [ ] speed
- [ ] line count
- [ ] travel per line
- [ ] phase/shift per line
- [ ] reactivity parameters
- [ ] ghosting
- [ ] heartbeat/transient assistance
- [ ] final uniform transfer

### DevCurve

- [ ] layer enabled/order
- [ ] energy/transient mapping
- [ ] alpha/outline
- [ ] offsets/domain
- [ ] tuning/specular parameters
- [ ] ghosting
- [ ] final geometry/intensity transfer

### Explicitly retired

- [x] old per-mode `*_growth` card-sizing authority is not a parity target.

## 11. Historical interaction scan worklist

- [x] middle-click same-mode preset hotswap/cycle known and separately tracked H8.
- [ ] scan historical mouse/semantic actions around Visualizer host.
- [ ] scan mode-change/preset-change reset semantics.
- [ ] scan Pause/Play behavior for source-state preservation.
- [ ] scan any per-mode Custom snapshot restoration.
- [ ] scan settings refresh for engine setter calls omitted by new owner split.

## 12. Evidence rules for the continuation

- [ ] A historical/current source diff outranks a stale test expectation.
- [ ] A live consumer with no current configuration route is a defect even if its fallback looks plausible.
- [ ] A fallback/default is not parity proof.
- [ ] A healthy ~90 Hz authored cadence is not proof of healthy live-source reactivity.
- [ ] Intentional idle energy is not evidence that real music magnitude is reaching the mode.
- [ ] Spectrum's mode-specific failures cannot justify a global gain change.
- [ ] A source-readiness fence is not removed until identity evidence proves it rejects valid current data.
- [ ] Current sizing/viewport architecture remains authoritative; historical `*_growth` sizing does not return.

# H5c Technical Decomposition — End-to-End Visualizer Reactivity Parity Audit

Date: 2026-08-31  
Historical behavioral oracle: `3fe5df687387b6b6a121142372c43a7719442386`  
Current evidence tree: user-supplied current worktree ZIP, 2026-08-31  
Execution authority: `Current_Plan.md`

## 0. Purpose and non-negotiable premise

This audit exists because the visualizer was already behaviorally correct before the Qt Quick migration. The migration target was **performance and presentation architecture**, not a redesign of audio response, mode shaping, beat semantics, idle motion, or preset behavior.

Therefore:

> Historical behavior from `3fe5df687387b6b6a121142372c43a7719442386` is the behavioral oracle. Current Qt Quick architecture remains binding. When the two disagree, first find the migration deviation; do not tune around it.

The old source is **not** an architectural template. It is a behavior/semantic oracle only.

The accepted production architecture remains:

```text
selected physical display
-> DisplayManager
-> one QuickDisplayUnit
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> display-owned runtime owners
-> zero-or-one visualizer edge per display
-> one product-level visualizer owner across participating displays
```

Never restore `DisplayWidget`, QRhiWidget/GLCompositor presentation, `QQuickWidget`, a compatibility presenter facade, a hidden QWidget presenter, a second accelerated surface, a duplicate BeatEngine/source/logical owner, or another cadence/pacer.

### 0A. Retired growth controls are explicitly outside the parity target

The old per-mode `*_growth` controls were presentation/card-sizing debris even before the migration. Current scale + viewport-extent contracts are the accepted sizing model.

- [x] Do **not** restore `spectrum_growth`, `osc_growth`, `sin_wave_growth`/`sine_wave_growth`, `devcurve_growth`, or equivalent obsolete card-sizing authority.
- [x] Keep the canonical authored viewport / uniform visual scale / viewport extent split.
- [ ] If a retired growth value is found inside an actual historical **reactivity formula**, document that exact use before deciding whether it represents real authored behavior or accidental coupling.
- [ ] Never use a retired growth value as a convenient global gain knob.

## 1. H/J classification used by this audit

**H / functional migration defect** means the migration changed or lost what state exists, when it exists, or which owner receives it:

- setting not routed to its current consumer;
- source identity/currentness rejected incorrectly;
- mode field omitted/replaced;
- historical formula/transfer removed or changed;
- wrong timing / `dt` semantics;
- wrong data/domain/normalization;
- lost or coalesced state that changes authored semantics;
- wrong mode/topology selected;
- controller/bridge/presentation mismatch.

**J / visual parity issue** means correct state arrives at the right time but the retained Quick renderer expresses it materially differently.

A renderer-side numerical transfer mismatch may be J-shaped in isolation while still being required for an H functional closure when the result is unusable, as with the current Spectrum saturation.

## 2. First-pass audit status — live checklist

### Source comparison completed

- [x] Identified exact historical tree `3fe5df687387b6b6a121142372c43a7719442386`.
- [x] Identified exact current worktree supplied alongside it.
- [x] Compared the core capture / BeatEngine / feature-state files directly rather than from memory.
- [x] Compared Spectrum preset canonicalization, logical configuration, engine configuration, frame runtime and Quick renderer seams.
- [x] Compared Bubble logical configuration consumption and source-readiness gate.
- [x] Compared Oscilloscope/Sine smoothing ownership enough to establish that their principal historical attack/release formulas survived.
- [x] Located the current direct Media playback-truth -> visualizer owner -> BeatEngine route.
- [ ] Complete exact historical-vs-current field coverage for every mode setting with a live consumer.
- [ ] Complete exact historical-vs-current final renderer-input comparison for Oscilloscope, Sine and DevCurve.
- [ ] Complete Bubble end-to-end magnitude trace under real source state.
- [ ] Complete Sine paused-idle presentation trace.
- [ ] Complete warm/cold Play/Pause edge trace.

### Source-proven defects found

- [x] Spectrum canonical `spectrum_render_mode` no longer reaches the runtime topology boolean.
- [x] Spectrum BeatEngine shaping values retained in presets/settings are not applied by the Quick owner path.
- [x] Spectrum historical final `0.55` bar/peak upload transfer is absent from the Quick renderer.
- [x] Bubble `bubble_group_drift`, `bubble_collision_pop_mode` and `bubble_big_visual_smoothing` were left behind in the old catch-all configuration owner while the Quick logical simulation still consumes them.

### Important open suspects — not yet declared defects

- [ ] Prove whether the per-mode `source_ready` identity fence remains false or arrives late during real playback.
- [ ] Prove whether visible Play/Pause delay occurs before Media canonical truth, inside BeatEngine/source freshness, at mode readiness, at snapshot publication, or at retained draw.
- [ ] Prove why Sine's historical paused idle motion is not physically visible although current Python-side idle state still advances.
- [ ] Prove whether any remaining common Bubble/Oscillo/Curve/Sine weakness occurs before mode runtime, inside mode runtime, or only in Quick presentation.

## 3. Pipeline maps

### 3.1 Historical behavioral pipeline

```text
OS/audio capture
-> SpotifyVisualizerAudioWorker
-> BeatEngine
-> FeatureFrame / energy bands / transients / FFT bars
-> historical settings/preset application
   -> BeatEngine technical + Spectrum shaping setters
   -> widget-authored mode fields
-> authored visualizer tick / mode-specific logical state
-> old render-state/compositor handoff
-> mode renderer
-> historical GL shader inputs / geometry
-> visible result
```

The historical widget/compositor types are not destination architecture. Their **data transformations and mode contracts** are the oracle.

### 3.2 Current Quick pipeline

```text
OS/audio capture
-> SpotifyVisualizerAudioWorker
-> BeatEngine
-> FeatureFrame / energy bands / transients / FFT bars
-> DisplayManager resolves Visualizer activation + SpotifyVisualizerSettings
-> QuickDisplayVisualizerOwner.configure(...)
   -> apply_logical_vis_mode_kwargs(logical_tick_state, asdict(model))
   -> apply_presentation_vis_mode_kwargs(presentation_state, asdict(model))
   -> apply_controller_technical_config(controller, resolved technical cache)
-> VisualizerLogicalRuntime sole authored cadence
-> mode-owned frame runtime
   Spectrum / Bubble / Oscilloscope / Sine / DevCurve
-> immutable captured mode state
-> ResolvedVisualizerPresentation + VisualizerRenderSnapshot
-> latest-state Quick bridge
-> retained Quick visualizer item / render node
-> Quick mode renderer + shader
-> visible result
```

This ownership split is desirable **provided every old semantic input has a new explicit owner**. The audit has already found several inputs stranded in the retired mixed owner.

## 4. What stayed semantically identical

### 4.1 Upstream capture/analysis is source-identical

The following files are byte-for-byte identical between the supplied historical and current trees:

- [x] `widgets/spotify_visualizer/audio_worker.py`
- [x] `widgets/spotify_visualizer/beat_engine.py`
- [x] `widgets/spotify_visualizer/energy_bands.py`
- [x] `widgets/spotify_visualizer/feature_frame.py`
- [x] `widgets/spotify_visualizer/signal_contract.py`
- [x] `widgets/spotify_visualizer/oscilloscope_contract.py`
- [x] `widgets/spotify_visualizer/technical_config.py`
- [x] `widgets/spotify_visualizer/transient_bus.py`

`widgets/spotify_visualizer/bar_computation.py` is behaviorally identical; its only meaningful historical/current diff is a type-only import path:

```text
historical: widgets.spotify_visualizer_widget.SpotifyVisualizerAudioWorker
current:    widgets.spotify_visualizer.audio_worker.SpotifyVisualizerAudioWorker
```

Therefore the first-pass evidence does **not** support beginning with global changes to:

- FFT/sample ranges;
- input gain;
- AGC;
- dynamic/manual floor math;
- adaptive sensitivity math;
- band aggregation;
- transient extraction;
- BeatEngine energy generation;
- generic bar-computation formulas.

Any later evidence may reopen a specific value **because configuration reaching the unchanged engine differs**, not because these algorithms were rewritten.

### 4.2 BeatEngine Play ramp itself is historical

Current and historical `beat_engine.py` are identical, including:

```text
_play_ramp_duration = 1.5 s
_capture_keepalive_grace = 6.0 s
```

The historical engine distinguishes a cold Play ramp from a warm resume. The current visible Play/Pause delay must therefore be traced before changing these constants.

### 4.3 Oscilloscope/Sine smoothing ownership moved but core formulas survived

The old presentation/compositor path applied approximately:

```text
energy attack  = 60 ms
energy release = 120 ms
```

Current Oscilloscope/Sine frame runtimes preserve the same basic attack/release treatment at authored time. Sine's stronger beat-assist/reactivity formulas likewise remain present.

- [x] Do not retune these values merely because the physical result is weak.
- [ ] Finish exact renderer-input equivalence before declaring line modes fully parity-clean.

### 4.4 Bubble core integration is not obviously retuned

The core Bubble energy shaping/integration survived substantially intact. The major migration differences are **ownership/execution location**, readiness admission, configuration completeness, and Quick presentation.

- [x] Do not treat ~90 Hz smooth idle movement as evidence that live reactivity is healthy.
- [x] Do not retune Bubble physics as the first move.
- [ ] Trace real music magnitude through every Bubble seam listed in section 15.

## 5. Intentional Quick changes that currently look architecturally valid

These differences are not defects by themselves:

- [x] One controller-owned logical clock instead of compositor/render callbacks advancing authored state.
- [x] Immutable latest-state publication instead of renderer access to mutable widget internals.
- [x] Controller-owned per-mode frame runtimes.
- [x] Canonical authored viewport + uniform scale + independent viewport extent instead of old `*_growth` card sizing.
- [x] Bubble direct integration on the sole authored logical cadence instead of an additional bounded compute-lane ownership seam.
- [x] Retained Quick presentation requests rather than QWidget/GL repaint ownership.

The audit must test semantic equivalence **inside** these replacements rather than reversing them.

## 6. Proven H defect — Spectrum topology canonicalization was lost

### 6.1 Historical behavior

`rendering/spotify_widget_creators.py::apply_spotify_vis_model_config()` explicitly canonicalized:

```python
spectrum_render_mode = str(getattr(model, "spectrum_render_mode", "bars") or "bars").lower()
spectrum_single_piece = spectrum_render_mode != "segment"
```

and passed `spectrum_single_piece` into the live visualizer configuration.

So the semantic contract was:

```text
spectrum_render_mode == "bars"    -> runtime single-piece/continuous columns
spectrum_render_mode == "segment" -> segmented presentation
```

### 6.2 Current mismatch

Current `core/settings/visualizer_presets.py` makes `spectrum_render_mode` canonical and deliberately removes the legacy key:

```text
legacy spectrum_single_piece
-> canonical spectrum_render_mode
-> pop("spectrum_single_piece")
```

Current `DisplayManager` then supplies `asdict(model)` to `QuickDisplayVisualizerOwner`.

But `apply_logical_vis_mode_kwargs()` currently only recognizes:

```text
spectrum_single_piece
```

not:

```text
spectrum_render_mode
```

and `logical_tick_state.py` defaults:

```text
_spectrum_single_piece = False
```

### 6.3 Consequence

A canonical Spectrum preset requesting `bars` can reach the Quick owner while the actual logical topology remains the default **segmented** mode.

This is a direct source-proven **H functional migration defect** and exactly explains why the current physical Spectrum can present as a dense segmented matrix when the preset requests continuous columns.

### 6.4 Performance-safe repair method

Do not revive the historical creator.

- [ ] Make `apply_logical_vis_mode_kwargs()` consume canonical `spectrum_render_mode`.
- [ ] Normalize with the existing preset/settings canonicalizer/helper.
- [ ] Derive `_spectrum_single_piece = render_mode != "segment"` at configuration time.
- [ ] Keep `spectrum_single_piece` only as a narrowly tested compatibility fallback if any real caller still supplies it.
- [ ] Add canonical `bars` and `segment` tests through **Quick owner configuration**, not only the helper.
- [ ] Prove mode switch and owner recreation preserve the selected topology.

No extra timer, allocation loop, source owner, render owner, or frame work is required.

## 7. Proven H defect — Spectrum BeatEngine shaping configuration is stranded

### 7.1 Historical/current legacy catch-all behavior

`widgets/spotify_visualizer/config_applier.py::apply_vis_mode_kwargs()` contains the engine-facing Spectrum configuration contract, including:

- `spectrum_mirrored` -> `engine.set_spectrum_mirrored(...)`;
- `spectrum_shape_nodes` -> `engine.set_spectrum_shape_nodes(...)`;
- mirrored/linear notch position selection -> `engine.set_notch_positions(...)`;
- `spectrum_wave_amplitude`;
- `spectrum_profile_floor`;
- mirrored/linear lane strengths -> `SpectrumShapeConfig(...)` -> `engine.set_spectrum_shape_config(...)`;
- `spectrum_drop_speed` -> `engine.set_drop_speed(...)`.

These values shape what the unchanged BeatEngine/bar-computation pipeline produces. They are not merely old QWidget styling.

### 7.2 Current Quick mismatch

`QuickDisplayVisualizerOwner._apply_configuration()` intentionally calls only:

```text
apply_logical_vis_mode_kwargs(...)
apply_presentation_vis_mode_kwargs(...)
apply_controller_technical_config(...)
```

It does **not** call the broad legacy `apply_vis_mode_kwargs()`. That architectural decision is correct.

However, `build_technical_cache()` / `apply_controller_technical_config()` currently covers values such as:

```text
bar_count
floor/adaptive sensitivity
input_gain / AGC / dynamic range
worker block size / kick gain
transient gain/clamp/mixes
```

but does not carry the Spectrum shaping/mirror/notch/drop controls listed above.

Therefore the current Quick path can resolve the correct preset/model while the one shared BeatEngine remains at defaults or stale shaping for these fields.

### 7.3 Classification and likely consequence

This is a source-proven **H configuration-ownership migration defect**.

It is directly relevant to Spectrum's broken reactivity because it changes the intended per-preset engine shaping despite identical upstream algorithms. The audit must still measure the post-repair vector before assigning every observed `1.00` saturation frame to this one omission.

### 7.4 Performance-safe repair method

The repair belongs on the **configuration edge**, not the authored/render hot path.

Preferred shape:

```text
canonical model/preset
-> resolved per-mode engine configuration
-> one narrow controller-owned engine applier
-> existing BeatEngine setters
```

Acceptable implementation choices:

1. extend the existing resolved technical/engine mapping with these Spectrum-specific engine-consumed keys; or
2. introduce a small presentation-neutral `apply_controller_mode_engine_config(...)` seam if keeping shape controls separate makes ownership clearer.

Whichever is selected:

- [ ] one BeatEngine remains;
- [ ] configuration applies only on initial configure / mode change / preset/settings refresh;
- [ ] no per-frame SettingsManager reads;
- [ ] no legacy widget mirror is recreated;
- [ ] notch selection follows the resolved mirrored state atomically;
- [ ] tests prove preset A -> B updates the existing engine without recreation.

## 8. Proven presentation transfer defect — Spectrum historical `0.55` upload scale disappeared

### 8.1 Historical renderer

`widgets/spotify_visualizer/renderers/spectrum.py` multiplied both live bars and peak bars by `0.55` immediately before shader upload:

```text
shader_bar  = authored_bar  * 0.55
shader_peak = authored_peak * 0.55
```

### 8.2 Current Quick renderer

`rendering/quick/visualizer/implementations/spectrum.py` uploads the authored bar and peak arrays directly, without that transfer.

Thus for the same authored `1.0` value:

```text
historical shader input = 0.55
current Quick input      = 1.00
```

Current input is roughly **1.82x** the historical shader-side magnitude before subsequent nonlinear presentation.

### 8.3 Supporting current-source evidence

`widgets/spotify_visualizer/spectrum_solid_hysteresis.py` still defines:

```text
_SPECTRUM_UPLOAD_SCALE = 0.55
```

and uses it when mapping a logical bar to the boosted/segment domain. That surviving constant is strong evidence that the historical transfer remains part of the intended Spectrum presentation math rather than an obsolete GL artifact.

### 8.4 Classification and repair method

This is renderer-side numerical parity loss — J-shaped by the strict underlying-state/render distinction — but it is part of **H5b functional closure** because current Spectrum is physically saturated/unusable.

- [ ] Centralize/expose the existing `0.55` transfer rather than duplicating a magic literal.
- [ ] Apply it consistently to Quick live bars and peak bars at the renderer-input boundary.
- [ ] Keep logical/bridge bar values canonical; do not globally attenuate BeatEngine output.
- [ ] Add focused tests proving the historical transfer exactly once.
- [ ] Verify continuous and segmented topology both consume the same canonical transfer.

This touches at most the existing bounded bar arrays and has negligible performance consequence.

## 9. Proven H defect — Bubble logical configuration split is incomplete

### 9.1 Stranded values

The legacy catch-all `apply_vis_mode_kwargs()` still applies:

```text
bubble_group_drift
bubble_collision_pop_mode
bubble_big_visual_smoothing
```

but `apply_logical_vis_mode_kwargs()` does not.

Current Bubble authored code still consumes them from logical state through `tick_pipeline.py` with fallback values:

```text
bubble_group_drift            fallback False
bubble_collision_pop_mode     fallback "off"
bubble_big_visual_smoothing   fallback 0.5
```

The shipped presets contain real non-fallback values, including `bubble_big_visual_smoothing` around `0.95–1.0`, `bubble_group_drift=True` in at least one preset, and collision-pop modes such as `"one"`.

### 9.2 Classification

This is a direct **H configuration-ownership migration defect**: the current simulation consumes these fields, but the Quick owner path never populates them.

`bubble_big_visual_smoothing` is visibly reactivity-related, but its omission alone is **not yet a complete explanation** for the dramatically weak music response. Do not claim it is.

### 9.3 Repair method

- [ ] Move/duplicate these three mappings into `apply_logical_vis_mode_kwargs()` because the authored simulation is their current consumer.
- [ ] Remove redundant legacy writes later only if doing so cannot break historical/non-production tests; exact source ownership wins over cleanup aesthetics.
- [ ] Add a Quick-owner configuration test asserting all three resolved preset values reach logical state.
- [ ] Add a preset-cycle/reconfigure test proving values change in-place without a second runtime.
- [ ] Re-run Bubble deterministic/BTF tests.
- [ ] Do **not** tune sensitivity, energy gain, bubble size or physics to compensate.

## 10. Shared high-priority suspect — per-mode `source_ready` identity gating

This is the strongest current **common** seam capable of producing the reported symptom:

> authored cadence remains healthy (~90 Hz), idle motion remains smooth, but real music energy appears absent/weak because the mode runtime receives or accepts no current reactive source.

It is **not yet proven wrong** and must not be weakened blindly.

### 10.1 Current Bubble behavior

`tick_pipeline.py` computes current runtime/engine/activation identity and source identity, then passes `source_ready` into `BubbleFrameRuntime.advance()`.

When `playing` but `source_ready == False`, `BubbleFrameRuntime` deliberately:

- zeros every energy value;
- zeros bass and mid/high pulse;
- replaces event scheduling with a no-event scheduler;
- erases source identity for the resolved frame;
- still advances the Bubble simulation.

That can produce exactly **healthy moving idle-like Bubble at ~90 Hz under real music** if readiness remains false or is repeatedly reset.

### 10.2 Other modes use the same contract

**Oscilloscope**

- accepts waveform only when source identity is current;
- otherwise targets zero energy;
- zeros kick/snare targets;
- then attack/release smoothing decays toward non-reactive state.

**Sine**

- targets zero energy when source is not ready;
- zeros kick/snare targets;
- suppresses base heartbeat when source is not ready;
- preserves independent idle motion logic.

**DevCurve**

- replaces energy and transient state with zero values when source is not ready.

**Spectrum**

- refuses current reactive input when identity is not ready and instead holds/uses non-reactive state according to its runtime rules.

### 10.3 Why this is not automatically a bug

Historical code already contained source freshness, generation/activation fencing and “wait for fresh engine frame” behavior. Stale audio from a retired/reconfigured source must never leak into a new mode/generation.

The possible migration defect is therefore **not “there is a source gate.”** It is one of:

```text
new second-stage gate duplicates an earlier fence incorrectly
identity values do not converge
identity resets too often
valid latest source loses metadata in capture/publication
playback activation changes one side but not the other
fresh state arrives but a later adapter strips/replaces it
```

### 10.4 Diagnostic contract — bounded and performance-safe

Add event/transition telemetry, never a 90 Hz log stream:

```text
[VIS_REACTIVITY]
mode=
runtime_generation=
engine_generation=
engine_activation=
source_generation=
source_activation=
source_age_ms=
source_ready=
playing=
raw_energy=(overall,bass,mid,high or compact equivalent)
raw_event=(kick,snare/transient compact summary)
resolved_reactivity=(compact mode-specific summary)
logical_revision=
reason=edge|first_current|not_ready_persisted|identity_change
```

Rules:

- [ ] emit when `playing` changes;
- [ ] emit when `source_ready` changes;
- [ ] emit when generation/activation identity changes;
- [ ] emit the first accepted current source after Play/activation;
- [ ] optionally emit one bounded low-rate warning if `playing && !source_ready` persists beyond a sensible diagnostic threshold;
- [ ] never log full waveform/bubble arrays every tick;
- [ ] never create a timer solely for diagnostics.

### 10.5 Decision tree

- [ ] If raw current source is healthy and `source_ready=True`, move downstream; do not touch the gate.
- [ ] If source metadata is current upstream but the mode sees mismatched identity, repair metadata/adaptation at the first mismatch.
- [ ] If identity only becomes current after an avoidable second reset, remove/fix the duplicate transition — not the stale-frame fence.
- [ ] If readiness is prompt but resolved energy is weak, compare exact mode formulas/fields against historical source.
- [ ] If resolved state is healthy but Quick looks weak, classify the remaining issue at bridge/renderer as J/H presentation parity as appropriate.

## 11. Play/Pause visible startup/stop delay — edge decomposition

The operator reports a visible delay on Play/Pause. This is a first-class H5c timing symptom even though the historical BeatEngine cold-start ramp exists.

### 11.1 Current route found

Current Quick product routing is direct:

```text
retained Media presentation model.stateChanged
-> DisplayManager._sync_quick_visualizer_playback()
-> QuickDisplayVisualizerOwner.set_playing()
-> controller.playing = bool
-> existing BeatEngine.set_playback_state(bool)
```

There is no deliberate Quick visualizer debounce in that route.

### 11.2 Historical constants that must not be blamed without proof

Because `beat_engine.py` is byte-identical, both trees share:

```text
cold Play reactivity ramp: 1.5 s
capture keepalive grace:  6.0 s
```

Warm resume is intended to bypass the cold ramp while capture remains warm.

### 11.3 Required one-edge telemetry

Instrument one Play/Pause transition as timestamps/latencies, not continuous logs:

```text
T0 canonical Media playbackState observed
T1 QuickDisplayVisualizerOwner.set_playing entered
T2 BeatEngine.set_playback_state entered/committed
T3 first authoritative current source frame after edge
T4 first mode frame with reactive_source_ready=True
T5 first materially reactive logical publication
T6 corresponding Quick snapshot published/admitted
T7 retained render node consumes/draws that revision
```

For each edge record:

```text
warm vs cold
runtime/engine/activation identity
source age
mode
logical revision
snapshot revision
```

### 11.4 Decision tree

- [ ] `T0` late -> H4 / Media canonical truth reconciliation, not visualizer tuning.
- [ ] `T0->T2` late -> product/owner route defect.
- [ ] `T2->T3` late on supposed warm resume -> BeatEngine capture/warm-state transition investigation.
- [ ] `T3->T4` late -> source identity/readiness defect.
- [ ] `T4->T5` late -> mode runtime/authoring defect.
- [ ] `T5->T6` late -> publication/adaptation defect.
- [ ] `T6->T7` late -> retained presentation scheduling defect.
- [ ] All timestamps prompt but amplitude visually emerges slowly -> compare historical cold/warm shaping and renderer transfer before tuning.

Do not add a new Play timer, reveal timer, or renderer animation as a workaround.

## 12. Sine missing paused idle motion — comparative evidence

Historical Sine has intentional idle motion. The current physical report is that Sine apparently does not.

### 12.1 What survived in current Python source

`SineFrameRuntime` still:

- advances `_animation_time`;
- forces a minimum paused speed (`>= 0.22`);
- ensures non-zero travel direction while paused;
- advances `_idle_shift_phase` from `dt`;
- applies line shifts according to travel direction;
- emits resolved speed/travels/shifts/animation time even without reactive source.

Therefore “idle motion field was simply deleted from Python” is **not** supported.

### 12.2 Next exact chain to trace

```text
SineFrameRuntime.resolve/advance
-> SineResolvedFrame
-> tick_pipeline capture
-> render_state.SineFrame
-> visualizer snapshot adapter/bridge
-> Quick retained synchronizer
-> rendering/quick/visualizer/implementations/sine.py
-> u_time / u_playing / speed / travel / shifts
-> sine shader
-> retained dirty/present request while paused
```

### 12.3 Live checklist

- [ ] Deterministic paused/no-source runtime test: animation time and at least one phase/shift advance over authored ticks.
- [ ] Snapshot test: those changed values survive capture/adaptation.
- [ ] Quick renderer test: the expected uniforms are generated from changed snapshot values.
- [ ] Verify retained item requests/presents subsequent idle revisions while paused.
- [ ] Verify `u_playing` branch does not accidentally suppress the shader variables that represent idle motion.
- [ ] Verify no equality/dirty optimization treats Sine's changing paused state as settled.
- [ ] Compare exact historical shader inputs if the above are healthy.
- [ ] Never add a QML animation timer to make idle motion visible.

This mode is valuable because it separates **idle authored motion** from **live-source reactivity**: both need to work, and they can fail at different seams.

## 13. Oscilloscope and DevCurve comparative audit

The earlier broad smoke described Oscilloscope/Sine/DevCurve as looking good, but the newly reported Sine idle failure reopens that blanket conclusion. Oscilloscope and DevCurve remain useful controls.

### Oscilloscope

- [ ] Compare historical waveform source selection and normalization.
- [ ] Compare line amplitude/smoothing values after preset resolution.
- [ ] Compare energy/transient target before and after `source_ready` gate.
- [ ] Compare final line amplitude/glow/reactive uniforms historical vs Quick.
- [ ] Verify idle waveform evolves without live source where historically expected.

### DevCurve

- [ ] Compare historical layer parameter ownership against current resolved parameter map.
- [ ] Compare energy/transient admission around `source_ready`.
- [ ] Compare layer enabled/order/alpha/offset/specular/tuning fields for omissions.
- [ ] Compare final geometry/intensity transfer historical vs Quick.
- [ ] Keep retired `devcurve_growth` out of field amplitude unless exact historical source proves otherwise.

A common mismatch across Bubble/Oscillo/Sine/DevCurve should be fixed once at its shared owner. Mode-specific transfer differences stay mode-specific.

## 14. Bubble remaining end-to-end magnitude trace

The Bubble core simulation remains the clearest physical canary. Complete this trace before any reactive tuning.

```text
B0 BeatEngine current FeatureFrame energies/transients
B1 logical tick's captured energy/pulse values
B2 source generation/activation metadata
B3 source_ready decision
B4 Bubble settings payload (including newly restored stranded fields)
B5 BubbleFrameRuntime energy/pulse after readiness admission
B6 BubbleSimulation.tick() inputs and target size/velocity consequences
B7 frozen positions/extras/trails + compact radius/alpha summary
B8 Quick Bubble renderer consumes exactly those radii/alpha/positions
B9 visible result
```

### Required checks

- [ ] Compare `B0/B1` with the historical implementation on representative music ranges.
- [ ] Confirm active music does not spend meaningful time at the idle-energy baseline after startup.
- [ ] Confirm no normalization/domain conversion occurs between captured energy and Bubble simulation input.
- [ ] Confirm `dt` is authored-step `dt`, not render `dt`, and no integration happens twice.
- [ ] Confirm latest-state coalescing does not remove required protected visible events.
- [ ] Confirm Quick does not rescale Bubble radius/alpha reactively compared with historical visible semantics.
- [ ] Confirm Bubble's old renderer energy uniforms are not reintroduced: historical shader declared them but did not consume them.

## 15. Revised Spectrum H5b causal decomposition

Spectrum must be treated as **visually and reactively broken**, with at least three independent proven migration deviations.

### H5b-A — topology identity

- [x] Root source seam found: canonical `spectrum_render_mode` lost before `_spectrum_single_piece`.
- [ ] Repair canonical mapping.
- [ ] Test `bars` -> continuous and `segment` -> segmented.

### H5b-B — engine shaping / reactivity

- [x] Root ownership gap found: preset/model Spectrum shape controls not routed to BeatEngine in Quick owner path.
- [ ] Route the exact engine-consumed values through a narrow controller-owned configuration seam.
- [ ] Re-measure D0-D6 only after configuration parity is restored.
- [ ] If output still pins at the upper bound, locate the first saturating transformation from unchanged engine inputs onward.

### H5b-C — final presentation transfer

- [x] Historical bar/peak `* 0.55` transfer found missing in Quick.
- [ ] Apply the existing canonical transfer exactly once at Quick Spectrum renderer input.
- [ ] Verify peak and live-bar parity.

### H5b-D — physical acceptance

- [ ] Real music produces non-degenerate, visibly reactive Spectrum response.
- [ ] Organ/default continuous preset is continuous columns rather than dense segmented cells.
- [ ] Segmented presets remain intentionally segmented.
- [ ] Heights no longer pin visually because of missing historical transfer.
- [ ] Mode switch/recreation/preset swap preserves topology + shaping.
- [ ] No shared/global visualizer gain changed.
- [ ] Bubble and other modes unchanged except separately justified H5c repairs.

## 16. Systematic configuration-ownership completeness audit

The Spectrum and Bubble defects came from the same migration class: the historical broad widget applier was split, but not every live consumer received a new owner.

This class must now be audited mechanically across **all five modes**, not fixed ad hoc one field at a time.

### 16.1 Method

For each historical key accepted by `apply_vis_mode_kwargs()` or the historical creator:

1. identify whether the key is still canonical/resolvable from `SpotifyVisualizerSettings`/preset;
2. locate every current read/consumer;
3. classify consumer:
   - BeatEngine/audio worker;
   - authored logical state/mode frame runtime;
   - presentation state/Quick renderer;
   - retired/no current consumer;
4. prove the current Quick owner routes the resolved value to that consumer;
5. add a test for keys with live consumers;
6. explicitly mark obsolete keys as retired instead of silently relying on fallbacks.

### 16.2 Live per-mode checklist

- [ ] Spectrum — complete field matrix; topology + shaping gaps already found.
- [ ] Bubble — complete field matrix; three logical gaps already found.
- [ ] Oscilloscope — complete field matrix.
- [ ] Sine — complete field matrix.
- [ ] DevCurve — complete field matrix.
- [ ] Shared technical/audio controls — prove one current owner each.
- [ ] Presentation-only style controls — prove Quick consumes them; do not mirror into logical state.
- [ ] Retired growth/card-sizing keys — explicitly mark no-current-consumer.

### 16.3 Guardrail

Never solve this by copying every legacy widget attribute into `VisualizerRuntimeController`. Consumer-driven ownership is the migration destination; missing mappings are fixed narrowly.

## 17. Historical interaction-contract scan

The historical source is also an oracle for useful interaction behavior lost from migration docs/implementation.

Already known:

- [x] middle-click current-mode preset cycle/hotswap exists historically and is tracked as H8;
- [x] same-mode cycle wraps;
- [x] Custom snapshot/restore semantics must remain lossless;
- [x] activation is immediate/live;
- [x] persistence is narrow;
- [x] mode-change guard must not be weakened.

Continue the historical scan for:

- [ ] playback-source warm/cold interaction differences;
- [ ] mode-switch freshness semantics;
- [ ] double-click/middle-click/scroll interactions not already in destination docs;
- [ ] preset-specific state reset vs state preservation;
- [ ] pause idle-state behavior for every mode;
- [ ] renderer-visible protected transient/event behavior;
- [ ] settings refresh/reconfigure behavior that changed a live engine without recreation.

Newly found contracts go into durable mode/interaction docs, not only `Current_Plan.md`.

## 18. Focused tests to add with repairs

### Configuration ownership

- [ ] Quick owner canonical Spectrum `bars` -> logical continuous topology.
- [ ] Quick owner canonical Spectrum `segment` -> logical segmented topology.
- [ ] Quick owner applies each Spectrum BeatEngine shaping field to the one existing engine.
- [ ] Quick owner applies Bubble drift/pop/smoothing fields to logical state.
- [ ] Representative presets verify non-default values survive model -> owner -> consumer.

### Spectrum renderer transfer

- [ ] Quick renderer uses the canonical historical `0.55` transfer exactly once for bars.
- [ ] Same for peaks.
- [ ] Logical/snapshot values remain unmodified canonical values.

### Readiness/timing

- [ ] Current source identity becomes ready without spurious extra activation reset.
- [ ] Stale source remains rejected.
- [ ] warm Play resume does not invoke avoidable cold-source admission delay.
- [ ] Play/Pause does not recreate owner/runtime/pacer.

### Sine idle

- [ ] paused authored frames advance animation/phase/shift.
- [ ] changing paused state publishes through bridge.
- [ ] retained Quick renderer receives changing idle uniforms.

### Regression preservation

- [ ] maintained H profile remains GREEN.
- [ ] BTF/visualizer deterministic suites remain GREEN.
- [ ] CUSTOM size/viewport contracts remain unchanged.
- [ ] one BeatEngine/source/logical owner remains.

## 19. Bounded implementation sequence

This is the recommended source-work decomposition once the documentation-only handoff is accepted. `Current_Plan.md` remains the execution-order authority.

### R1 — configuration parity, no diagnostics required

- [ ] repair Spectrum canonical render-mode mapping;
- [ ] repair Bubble three stranded logical settings;
- [ ] add focused configuration tests.

These are source-proven, low-risk, configuration-time repairs.

### R2 — Spectrum engine-shaping parity

- [ ] build/extend narrow controller-owned Spectrum engine-config path;
- [ ] apply existing BeatEngine setters;
- [ ] add in-place reconfigure tests.

### R3 — Spectrum final transfer parity

- [ ] reuse/export canonical `0.55` transfer;
- [ ] apply to Quick bars/peaks exactly once;
- [ ] add renderer tests.

### R4 — re-measure Spectrum

- [ ] inspect live D0-D6 after R1-R3;
- [ ] only pursue further Spectrum math if variation remains wrong.

### R5 — shared reactivity edge instrumentation

- [ ] add bounded `[VIS_REACTIVITY]` identity/readiness telemetry;
- [ ] add T0-T7 Play/Pause edge timestamps;
- [ ] no continuous logging/timers.

### R6 — Bubble/common-source classification

- [ ] run B0-B9 source-to-visible trace;
- [ ] fix the earliest source-proven shared seam if one exists;
- [ ] otherwise continue mode-specific parity.

### R7 — Sine idle + line modes

- [ ] finish paused Sine trace;
- [ ] fix earliest broken transport/presentation seam;
- [ ] complete Oscilloscope/DevCurve final-value comparison.

### R8 — durable closure

- [ ] update this document with exact repaired seams/commits/tests;
- [ ] update operator ledger physical results;
- [ ] update `03_Visualizer.md` only for durable contract changes;
- [ ] keep `Current_Plan.md` compact and sequencing-oriented.

## 20. Performance guardrails for every H5c repair

- [ ] zero new authored clocks/timers;
- [ ] zero duplicate BeatEngines/audio workers;
- [ ] zero second visualizer owner;
- [ ] zero FIFO/catch-up queue replacing latest-state publication;
- [ ] no full settings/preset resolution at 90 Hz;
- [ ] configuration mapping happens on configure/mode/preset/settings edges;
- [ ] diagnostics are edge-triggered/bounded;
- [ ] no render-thread access to SettingsManager or mutable Python widget state;
- [ ] no QML animation used to disguise authored-state failure;
- [ ] no global gain workaround for a mode-specific defect;
- [ ] no reintroduction of old QWidget/GL presentation architecture.

## 21. Ranked evidence matrix

| Rank | Seam | Evidence | Current classification | Next action |
|---|---|---|---|---|
| 1 | Spectrum `spectrum_render_mode` -> topology | exact historical mapping exists; current canonical key is ignored and logical default is segmented | **H proven** | R1 |
| 2 | Spectrum engine shaping config | live BeatEngine setters remain only in old catch-all; Quick technical path omits them | **H proven** | R2 |
| 3 | Spectrum final `0.55` upload transfer | historical renderer scales bars+peaks; Quick uploads raw; current helper still carries `0.55` | **J-shaped / H5b required** | R3 |
| 4 | shared mode `source_ready` gate | can zero reactive state while cadence continues; common to all modes | **H suspect, unproven** | R5/R6 |
| 5 | Bubble drift/pop/smoothing config | current simulation reads fields that Quick logical applier never sets | **H proven** | R1 |
| 6 | Play/Pause edge | direct route exists; historical engine ramp unchanged; physical delay remains | **H suspect, seam unknown** | T0-T7 trace |
| 7 | Sine idle presentation | runtime still advances idle time/shift; physical idle appears absent | **H/J suspect downstream** | Sine transport/render trace |
| 8 | Oscillo/DevCurve final transfer | core logical formulas appear preserved, final equivalence not complete | **open** | comparative audit |

## 22. Exonerated / do-not-start-here list

Unless later evidence specifically reopens them, do **not** begin the next repair by changing:

- [x] global BeatEngine FFT/bar math;
- [x] global audio input gain;
- [x] global sensitivity;
- [x] global noise floor;
- [x] authored cadence target;
- [x] presentation FPS as the explanation for weak music response;
- [x] Bubble physics constants;
- [x] old per-mode `*_growth` controls;
- [x] historical Bubble energy uniforms that were declared/uploaded but unused by its shader;
- [x] the historical 1.5 s BeatEngine cold-start ramp before warm/cold edge classification.

## 23. H5c closure criteria

H5c does not close merely because individual unit tests pass.

- [ ] All source-proven configuration ownership gaps found by the systematic field audit are either repaired or explicitly retired with no live consumer.
- [ ] Spectrum topology follows canonical preset intent.
- [ ] Spectrum BeatEngine shaping follows the selected preset in the one shared engine.
- [ ] Spectrum historical final transfer is restored in Quick without global gain changes.
- [ ] Spectrum is physically reactive and functionally recognizable on real music.
- [ ] Bubble is materially/reactively comparable to the historical implementation under real music, while retaining current correct sizing/CUSTOM behavior.
- [ ] Oscilloscope, Sine and DevCurve react at historical-equivalent magnitude/shape unless an intentional documented improvement exists.
- [ ] Sine retains visible paused idle motion.
- [ ] Play/Pause visible response is classified and any migration-added delay is removed without changing legitimate historical cold-start semantics.
- [ ] stale source frames remain fenced correctly.
- [ ] one owner / one engine / one authored cadence / one retained scene remains true.
- [ ] focused deterministic suites and maintained H profile are GREEN.
- [ ] operator physical gate is recorded in the ledger.

## 24. Immediate next No Quota continuation

After this documentation-only checkpoint, source work should begin with the **already-proven, configuration-time defects** rather than speculative tuning:

1. Spectrum canonical topology mapping;
2. Bubble stranded logical settings;
3. Spectrum narrow BeatEngine shape-config ownership;
4. Spectrum historical `0.55` Quick input transfer;
5. tests for all four;
6. only then re-measure Spectrum and add bounded shared readiness/playback diagnostics for the remaining Bubble/Sine/common symptoms.

This sequencing gets known wrong semantics out of the measurement path before using new traces to diagnose what remains.

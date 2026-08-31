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
- [x] Complete exact historical-vs-current field coverage for every historical mode setting with a live consumer; only retired growth controls, loop-generated line/style fields already owned by the split appliers, three Bubble logical controls, and the Spectrum source-owned block were outside the direct split. Current technical/audio fields were separately compared and retain explicit owners.
- [ ] Complete exact historical-vs-current final renderer-input comparison for Oscilloscope, Sine and DevCurve.
- [ ] Complete Bubble end-to-end magnitude trace under real source state.
- [ ] Complete Sine paused-idle presentation trace.
- [ ] Complete warm/cold Play/Pause edge trace.

### Source-proven defects found

- [x] Spectrum canonical `spectrum_render_mode` no longer reaches the runtime topology boolean.
- [x] Spectrum BeatEngine/source shaping values retained in presets/settings are not applied by the Quick owner path. **This is shared-input relevant:** the unchanged FFT routine uses the configured notch positions when deriving bass/mid/treble source lanes before mode-specific authored state, so omission can alter Bubble/Oscillo/Sine/DevCurve inputs too.
- [x] Spectrum historical final `0.55` bar/peak upload transfer is absent from the Quick renderer.
- [x] Bubble `bubble_group_drift`, `bubble_collision_pop_mode` and `bubble_big_visual_smoothing` were left behind in the old catch-all configuration owner while the Quick logical simulation still consumes them.
- [x] Historical creator translation `spectrum_unique_colors -> spectrum_rainbow_per_bar` was also lost by the Quick ownership split.

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

However, `build_technical_cache()` / `apply_controller_technical_config()` already carries the separate reactivity-critical technical subset correctly:

```text
bar_count
dynamic_floor + manual_floor
adaptive_sensitivity + sensitivity
audio_block_size
dynamic_range_enabled -> canonical 1.18 / 0.85 energy boost
agc_strength
input_gain
kick lane gain
transient gain/clamp/mixes
```

The historical and current technical appliers were compared directly. Their value semantics match, including the deliberately sharp values that curated presets depend on:

- `agc_strength=0.0` remains exactly `0.0`; `bar_computation._apply_adaptive_normalization()` returns immediately below `0.01`, so **zero still means no AGC/raw output** rather than "missing -> default AGC";
- `dynamic_floor=False` remains false and the authored manual floor remains active;
- explicit nonzero `audio_block_size` remains an explicit capture-block request;
- per-mode `bar_count` still reconfigures the one BeatEngine/controller bar domain;
- `dynamic_range_enabled=False` still resolves to the historical `0.85` worker energy multiplier, while true resolves to `1.18`;
- adaptive-sensitivity false, manual sensitivity and input gain preserve their explicit resolved values.

Those controls were **already correct before this H5c repair** and are not duplicated in the new source applier. A focused zero/false parity test was added because these settings change the visualizer dramatically and must not regress silently.

The actual gap is adjacent: the existing technical mapper did **not** carry the Spectrum shaping/mirror/notch/drop controls listed above. Therefore the Quick path could resolve the correct preset/model and correctly apply bar count/floor/AGC/block size while the one shared BeatEngine still retained defaults or stale shaping/notches. That partial success helps explain why the migration looked structurally healthy while live reactivity was wrong.

### 7.3 Classification and shared consequence

This is a source-proven **H configuration-ownership migration defect**.

It is directly relevant to Spectrum's broken reactivity because it changes the intended per-preset engine shaping despite identical upstream algorithms. More importantly, source inspection proves that at least part of this block sits **upstream of every mode**:

```text
fft_to_bars(...)
-> read worker._spectrum_notch_positions
-> choose raw bass/mid/treble split indices
-> compute raw band energy / pre-AGC control lanes / transient bus
-> later produce shaped bars
-> BeatEngine exposes those lanes to Bubble/Oscillo/Sine/DevCurve/Spectrum
```

When `_spectrum_notch_positions` is absent, unchanged `bar_computation.py` falls back to fixed split indices `4` and `10`. Historical full-model application populated the canonical notch family even when the active visualizer mode was **not Spectrum**. With the default mirrored notches `(0.0, 0.30, 0.65, 1.0)`, representative current per-mode bar counts therefore resolve approximately as:

| Active mode | Bars | missing-config fallback | historical/default configured split |
|---|---:|---:|---:|
| Spectrum | 33 | `4 / 10` | `9 / 21` |
| Bubble | 48 | `4 / 10` | `14 / 31` |
| Oscilloscope | 32 | `4 / 10` | `9 / 20` |
| Sine | 40 | `4 / 10` | `12 / 26` |
| DevCurve | 32 | `4 / 10` | `9 / 20` |

This is not a cosmetic Spectrum preset omission: it changes the frequency-bin population used to derive shared source energy. It is therefore a **source-proven common migration deviation capable of affecting every visualizer mode**, and it is now one of the strongest explanations for the cross-mode weak-reactivity report. Physical/source traces are still required to quantify how much of each mode's observed regression it explains after repair.

The rest of the Spectrum shape block (shape nodes, lane strengths, wave amplitude/profile floor) primarily shapes the bar vector itself. Oscillo/Sine and any other consumers of bar-derived `BeatEngine.get_energy_bands()` can therefore also inherit those differences; Bubble's dedicated continuous feed is especially guaranteed to inherit the notch-derived raw-band difference.

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

- [x] one BeatEngine remains in the implemented slice;
- [x] source configuration applies only on existing initial configure / mode-activation configuration edges;
- [x] no per-frame SettingsManager/preset reads were added;
- [x] no legacy widget mirror or compatibility presenter was recreated;
- [x] notch selection follows the resolved mirrored state in the same configuration transaction;
- [ ] prove H8 same-mode preset A -> B hotswap updates the existing engine without recreation once that missing product route is restored.

### 7.5 Implemented 2026-08-31 — source-owner repair

- [x] Added `widgets/spotify_visualizer/source_config_applier.py` as a presentation-neutral, configuration-time-only BeatEngine/source authority.
- [x] The one existing Quick owner routes the canonical resolved settings payload into that applier on initial configure and mode activation.
- [x] The applier uses the existing BeatEngine setters for mirrored mode, shape nodes, active notch family, `SpectrumShapeConfig` and drop speed.
- [x] No timer, cadence, polling loop, duplicate worker, duplicate engine or renderer read was added.
- [x] The source block is intentionally applied even while another visualizer mode is active, matching historical full-model semantics and restoring the shared source-band contract described above.
- [x] Added bounded `[VIS_SOURCE_CONFIG]` diagnostics under the existing visualizer diagnostics flag.
- [x] Added focused test coverage that asserts the source contract reaches the shared engine while Bubble is the active mode.
- [ ] Execute the focused test in the normal PySide6 project environment; the supplied Linux audit container has no PySide6, so only syntax/static validation is available here.
- [ ] Physical trace after repair: quantify raw energy before/after and determine which remaining mode symptoms survive.

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

- [x] Centralized/exposed the existing `0.55` transfer rather than introducing a second magic literal.
- [x] Applied it consistently to Quick live bars and peak bars at the final renderer-input boundary.
- [x] Logical/bridge bar values remain canonical; BeatEngine output is not globally attenuated.
- [x] Added focused source-level coverage proving the historical transfer exactly once, including peak fallback behavior.
- [ ] Physically verify continuous and segmented topology both consume the repaired transfer correctly under live music.

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

- [x] Move these three mappings into `apply_logical_vis_mode_kwargs()` because the authored simulation is their current consumer.
- [x] Keep the current Quick owner architecture; do not call the legacy mixed QWidget applier to obtain these side effects.
- [x] Add a Quick-owner configuration test asserting all three non-default resolved preset values reach logical state.
- [ ] Add a preset-cycle/reconfigure test proving values change in-place without a second runtime when the real H8 hotswap route exists.
- [ ] Re-run Bubble deterministic/BTF tests in the normal PySide6 project environment.
- [x] Do **not** tune sensitivity, energy gain, bubble size or physics to compensate.

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

The exact historical/current comparison now proves one more useful boundary: `consume_engine_bars()` is unchanged and performs the historical **pre-copy** freshness fence before current bars are admitted into display/logical state. For line modes that fence also waits for the current waveform generation. The migration-added frame runtimes then perform a **second identity check** against generation/activation metadata. Under the normal path those identities should converge to the same accepted engine epoch, so the second check is currently classified as *redundant-but-not-proven-wrong*, not as a repair target.

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

- [x] emit when `playing` changes;
- [x] emit when `source_ready`/identity admission materially changes or needs bounded classification;
- [x] carry runtime/engine/source generation+activation identities;
- [x] emit the first accepted current source after Play/activation;
- [x] emit only bounded/rate-limited not-ready status while diagnostics are enabled;
- [x] never log full waveform/bubble arrays every tick;
- [x] never create a timer solely for diagnostics.

Implementation note: the telemetry is attached to the existing authored-state and publication boundaries. With diagnostics disabled it introduces no new scheduler or source work; with diagnostics enabled it records compact values only.

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

There is no deliberate Quick visualizer debounce in that route. The current binding also calls `_sync_quick_visualizer_playback()` immediately after connecting `MediaPresentationModel.stateChanged`, so a newly admitted visualizer does not intentionally wait for a future media signal before seeing the model's current truth. This does **not** exonerate H4: if canonical Media truth itself arrives/reconciles late, T0 will be late and the defect belongs upstream of the visualizer owner.

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

Therefore “idle motion field was simply deleted from Python” is **not** supported. The current Quick renderer also uploads the resolved `animation_time`, `playing`, minimum-resolved speed, travel directions and line shifts to the same canonical Sine shader family. The shader still contains its historical paused `idle_motion_gate`/`idle_phase` branches. Static source comparison therefore pushes the unresolved physical Sine-idle defect farther downstream into live publication/dirty/present behavior or an installed-run state mismatch, rather than justifying a new timer or replacement idle formula.

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
- [x] Canonical mapping restored at the logical owner; stale legacy boolean is fallback-only.
- [x] Focused source test covers canonical `bars` and canonical-over-legacy `segment` behavior; normal PySide execution remains pending.

### H5b-B — engine shaping / reactivity

- [x] Root ownership gap found: preset/model Spectrum shape controls were not routed to BeatEngine in Quick owner path.
- [x] Exact engine-consumed values now route through one narrow configuration-time source applier into the existing BeatEngine.
- [x] Historical full-model behavior is preserved even with Bubble active, because this is shared pre-mode source shaping rather than Spectrum presentation state.
- [ ] Re-measure D0-D6 after configuration parity is restored physically.
- [ ] If output still pins at the upper bound, locate the first remaining saturating transformation rather than changing global gain.

### H5b-C — final presentation transfer

- [x] Historical bar/peak `* 0.55` transfer found missing in Quick.
- [x] Existing canonical transfer now applies exactly once at Quick Spectrum renderer input.
- [x] Focused source test covers live-bar and peak transfer/fallback; normal PySide execution remains pending.

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

- [x] Spectrum — historical live-consumer matrix completed; canonical topology, unique-colors translation, source shaping and final transfer gaps identified and implemented.
- [x] Bubble — historical live-consumer matrix completed; three stranded logical controls identified and implemented.
- [x] Oscilloscope — historical direct + loop-generated fields accounted for in current logical/presentation owners.
- [x] Sine — historical direct + loop-generated fields accounted for in current logical/presentation owners.
- [x] DevCurve — historical direct + generated layer fields accounted for in current logical/presentation owners.
- [x] Shared technical/audio controls — historical technical applier compared against `quick_technical_config.py`; bar count, floor, sensitivity, dynamic range/energy boost, AGC, input gain, audio block size, kick gain, transient pulse/clamp and mode-specific transient mixes retain explicit owners.
- [x] Zero/false semantics specifically audited: `agc_strength=0.0` remains no-AGC, `dynamic_floor=False` remains manual-floor mode, explicit `audio_block_size` and mode bar counts remain exact; focused parity coverage added. These were already correct and are **not** rerouted through the new source applier.
- [x] Presentation-only style controls — current split applier owns the historical renderer fields, including generated per-line/ghost fields.
- [x] Retired growth/card-sizing keys — explicitly remain non-targets; current authored viewport/CUSTOM sizing contract wins.
- [ ] Repeat this matrix only if later source work introduces a new settings field or a physical trace proves a supposedly-owned field is not reaching its consumer.

### 16.3 Guardrail

Never solve this by copying every legacy widget attribute into `VisualizerRuntimeController`. Consumer-driven ownership is the migration destination; missing mappings are fixed narrowly.

### 16.4 Why protected goldens could remain GREEN

The replay/golden boundary is downstream of the source-configuration defect. Historical deterministic replay supplies a `FeatureFrame` containing already-authored energy lanes, `raw_bars` and waveform data, calls `engine.accept_feature_frame(...)`, and then exercises the real `tick_pipeline.on_tick(...)`. Presentation goldens similarly sample already-produced logical/presentation state.

Protected path:

```text
FeatureFrame / raw bars / energy lanes
-> accepted BeatEngine replay state
-> logical mode integration
-> latest-state/presentation sampling
```

Broken production path that the goldens do not construct:

```text
canonical preset/settings
-> Quick owner split
-> BeatEngine/audio-worker source setters
-> live FFT/notch/lane shaping
-> FeatureFrame / bars / energy lanes
```

Thus the goldens can correctly prove that a mode behaves like the historical implementation **given healthy authored input** while production Quick fails to configure the source that creates that input from real music. GREEN was therefore compatible with this migration defect.

Live checklist:

- [x] do not regenerate existing goldens to bless the defect;
- [x] add focused Quick-owner/source reachability coverage;
- [x] add focused bar-count/block-size/floor/AGC zero/false technical coverage;
- [ ] once H8 exists, prove same-mode preset A -> B updates this same existing engine without recreation;
- [ ] only change a downstream golden if a separately justified intentional behavior change truly changes its protected domain.

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

- [x] Quick owner canonical Spectrum `bars` -> logical continuous topology test added.
- [x] Quick owner canonical Spectrum `segment` overrides stale legacy boolean test added.
- [x] Quick owner applies each Spectrum BeatEngine shaping field to the one existing engine test added.
- [x] Source-owned Spectrum settings are applied while Bubble is active test added, preserving historical shared-worker semantics.
- [x] Quick owner applies Bubble drift/pop/smoothing fields to logical state test added.
- [x] Technical-owner zero/false test added for `bar_count=48`, explicit `audio_block_size=128`, `dynamic_floor=False`, manual floor/sensitivity, `dynamic_range_enabled=False`, `agc_strength=0.0` and input gain.
- [x] Direct DSP assertion added for the unchanged AGC implementation: `agc_strength=0.0` returns before envelope mutation/array scaling, proving zero remains the real raw-output/no-AGC contract rather than merely reaching a setter.
- [x] `[VIS_TECH_CONFIG]` emits those resolved values only on existing configuration edges when visualizer diagnostics are enabled.
- [ ] Execute these focused tests in the normal PySide6 project environment.
- [ ] Add a preset A -> B in-place reconfiguration test when the live preset-hotswap H8 route is implemented rather than fabricating a second configuration route now.

### Spectrum renderer transfer

- [x] Quick renderer helper uses the canonical historical `0.55` transfer exactly once for bars.
- [x] Same helper applies it to peaks, with historical missing-peak fallback semantics.
- [x] Logical/snapshot values remain unmodified canonical values; scale is confined to the Quick shader-input seam.
- [ ] Execute focused renderer-transfer test in the normal PySide6 project environment.

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

- [x] repair Spectrum canonical render-mode mapping;
- [x] restore historical `spectrum_unique_colors -> rainbow_per_bar` translation at presentation ownership;
- [x] repair Bubble three stranded logical settings;
- [x] add focused configuration tests.

These are source-proven, low-risk, configuration-time repairs.

### R2 — Spectrum engine-shaping parity

- [x] build narrow controller-owned/configuration-time Spectrum source-config path;
- [x] apply existing BeatEngine setters to the one shared engine;
- [x] prove by focused test that the source block is applied even with another active mode;
- [ ] add live preset A -> B in-place reconfigure coverage with H8's real hotswap route.

### R3 — Spectrum final transfer parity

- [x] reuse/export canonical `0.55` transfer;
- [x] apply to Quick bars/peaks exactly once;
- [x] add focused renderer-transfer test.

### R4 — re-measure Spectrum

- [ ] inspect live D0-D6 after R1-R3;
- [ ] only pursue further Spectrum math if variation remains wrong.

### R5 — shared reactivity edge instrumentation

- [x] add bounded `[VIS_REACTIVITY]` identity/readiness + compact raw/resolved magnitude telemetry at each mode's actual admission boundary;
- [x] add T0-T7 Play/Pause edge markers across Media truth, owner, BeatEngine commit, fresh source/readiness, logical publication, Quick bridge and retained-node consumption;
- [x] no continuous logging/timers, no full arrays, no second cadence; all diagnostics are behind the existing visualizer diagnostic flag and transition/rate limited.
- [ ] Collect one physical warm-resume and one cold-start trace and classify the first late stage.

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
| 1 | Spectrum `spectrum_render_mode` -> topology | exact historical mapping exists; baseline Quick ignored canonical key and defaulted segmented | **H proven; repaired in source** | physical S0-S7 + focused test execution |
| 2 | shared source/engine shaping config | historical full-model apply always populated Spectrum notches/shaping; current omission leaves fixed `4/10` raw split fallback and stale/default shaped bars, affecting source lanes consumed by all modes | **H proven, shared-input capable** | R2 implemented; physical re-measure |
| 3 | Spectrum final `0.55` upload transfer | historical renderer scales bars+peaks; baseline Quick uploaded raw; helper retained the historical constant | **J-shaped / H5b required; repaired in source** | physical S0-S7 + focused test execution |
| 4 | shared mode `source_ready` gate | can zero reactive state while cadence continues; common to all modes; bounded boundary telemetry now implemented | **H suspect, unproven** | collect R5 trace / R6 |
| 5 | Bubble drift/pop/smoothing config | current simulation reads fields that baseline Quick logical applier never set | **H proven; repaired in source** | physical B0-B9 re-measure |
| 6 | Play/Pause edge | direct route exists; historical engine ramp unchanged; T0-T7 diagnostic markers now implemented, physical delay remains unclassified | **H suspect, seam unknown** | collect warm/cold T0-T7 trace |
| 7 | Sine idle presentation | runtime still advances idle time/shift; physical idle appears absent | **H/J suspect downstream** | Sine transport/render trace |
| 8 | Oscillo/DevCurve final transfer | core logical formulas appear preserved, final equivalence not complete | **open** | comparative audit |

## 22. Exonerated / do-not-start-here list

Unless later evidence specifically reopens them, do **not** begin the next repair by changing:

- [x] global BeatEngine FFT/bar math;
- [x] global audio input gain;
- [x] global sensitivity;
- [x] global noise floor;
- [x] the already-correct Quick technical mapping for per-mode bar count, explicit audio block size, dynamic/manual floor, adaptive/manual sensitivity, dynamic-range boost, AGC (including exact `0.0` off) and input gain;
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

The first bounded implementation slice is now complete in source: topology/creator translations, Bubble stranded logical fields, shared BeatEngine/source shaping ownership, the historical Spectrum `0.55` renderer transfer, focused configuration/technical-zero parity tests, and bounded readiness/Play-Pause observability are implemented. The audit also records why replay/presentation goldens could remain GREEN: they protect downstream authored state much better than the live preset -> source-configuration seam that failed.

Immediate continuation after this source handoff:

1. run the new focused test in the normal PySide6 environment and preserve maintained H/BTF gates;
2. physically re-measure all five modes because restoring the historical notch/source block can change shared band-energy semantics, not Spectrum alone;
3. capture one warm Play resume and one cold Play edge with `[VIS_PLAYBACK_EDGE]` T0-T7 + `[VIS_REACTIVITY]`;
4. if `source_ready` is late/false, repair the earliest identity mismatch without weakening stale-frame fencing;
5. if raw/resolved values are healthy, continue downstream renderer parity rather than adding gain;
6. finish Sine paused-idle snapshot/uniform/present trace;
7. only after these source-proven/common seams are re-measured continue mode-specific Bubble B0-B9 or Oscillo/DevCurve renderer comparison.

This sequencing keeps known wrong semantics out of the measurement path and uses one bounded trace plane to decide the next source repair.

## 25. Physical checkpoint R2 — post-shared-source repair findings

Detailed source/repair handoff: `H5c_Implementation_Checkpoint_2026-08-31_R2.md`.

### R9 — Bubble downstream transport

- [x] Physical logs prove strong current source energy reaches Bubble while authored integration remains ~90 Hz / one step per request.
- [x] Stop treating source/FFT/gain/cadence as the leading Bubble suspect.
- [x] Source audit found protected Bubble event edges carrying full geometry and overriding the newer ordinary latest-state frame.
- [x] Keep protected event metadata only; newest `BubbleFrame` owns geometry.
- [ ] Physical B6-B9 re-measure after repair.

### R10 — resume edge

- [x] Correct T3/T4 instrumentation so the 1.5 s periodic sampler cannot fabricate source latency.
- [x] Restore historical `engine.wake()` on False->True before playback commit.
- [x] Cold-only ramp 1.5 s -> 1.0 s; warm keepalive resume remains immediate.
- [ ] Re-measure one long-idle resume with corrected T3-T7.

### R11 — Sine

- [x] Physical idle exists; missing-idle hypothesis closed.
- [x] Apply requested paused-only +20% motion adjustment; no shared gain/timer change.

### R12 — DevCurve

- [x] Historical shader proves saved ghost controls were visually inert.
- [x] Remove Quick-invented delayed ghost curves/fills/outlines and their 4x96-float render uploads.
- [x] Preserve adjustable viewport scaling and real solver semantics.
- [ ] Re-measure outline smoothness and bottom transient visibility.
- [ ] If transient remains weak, classify via `[VIS_DEVCURVE_TRANSIENT]` before changing power/gain.

### R13 — Spectrum pause handoff

- [x] Physical steady idle hump is present and logical floor is correct.
- [x] Add bounded retained-state magnitude samples around Pause.
- [ ] Locate the brief zero before floor; do not raise the steady floor.

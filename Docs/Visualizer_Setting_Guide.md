# Visualizer Setting Guide

Reference guide covering every Beat Visualizer mode (excluding Spectrum/Starfield/Helix) with the exact GUI controls surfaced in settings, what each slider/checkbox/color swatch changes, and any overlap/conflict concerns to watch for when tuning.

---

## Technical Controls (All Modes)

- **Manual Floor Baseline** — shared slider (0.05 – 4.0) that now seeds the dynamic floor accumulator the moment you change it, even when Dynamic Floor remains enabled. Treat it as the guaranteed “silence baseline” for every mode; if visuals look stuck too high, check this slider first before touching stage/core floor biases.
- **Dynamic Floor** — still adapts over time, but every preset reload, mode switch, widget reset, or manual floor edit reseeds the accumulator from the Manual Floor Baseline to prevent stale high floors bleeding across modes.
- **Per-mode persistence** — all Technical controls save under `<mode>_<setting>` keys (no more global `audio_block_size`). Every curated preset was re-audited on 2026‑03‑11 so each non-Custom slot ships the mandatory per-mode set: manual/dynamic floor, adaptive toggle, sensitivity, `<mode>_audio_block_size` (Auto/0 means “use driver buffer”), and dynamic range flag. Whenever you touch a preset JSON/SST, rerun `tools/visualizer_preset_repair.py` to keep that structure intact.

---

## Blob Mode

- **Pulse Intensity** (`blob_pulse`) — *Normal slider*
  - Impact: Multiplies core growth amplitude before stage envelopes; raises overall “throb.”
  - Conflicts: High values can saturate Stage Gain and Reactive Deformation, masking those controls.
- **Reactive Glow + Glow Color** (`blob_reactive_glow`, `blob_glow_color`) — *Normal checkbox + swatch*
  - Impact: Enables audio-driven outer glow with selectable hue.
  - Conflicts: Large glow modifiers in Advanced bucket can clip when pulse intensity is high; values persist even if toggle off.
- **Fill / Edge / Outline Colors** (`blob_color`, `blob_edge_color`, `blob_outline_color`) — *Normal swatches*
  - Impact: Define SDF interior, edge feather, and outline stroke colours.
  - Conflicts: Bright outline plus Ghosting opacity can blow highlights; keep some contrast.
- **Card Width** (`blob_width`) — *Normal slider*
  - Impact: Scales card width relative to layout gutter.
  - Conflicts: Competes with Card Height/Blob Growth for perceived size; large width + high growth may overlap neighbours.
- **Blob Size** (`blob_size`) — *Normal slider*
  - Impact: Sets base SDF radius before stage offsets.
  - Conflicts: Extreme values fight Technical manual floor (preventing shrink) and can reveal quantization.
- **Card Height / Growth** (`blob_growth`) — *Advanced slider*
  - Impact: Multiplies widget height; shares DEFAULT_GROWTH helper.
  - Conflicts: High growth plus wide cards exceed safe zone; adjust Stage Bias to avoid clipping.
- **Glow Intensity / Reactivity / Max Size** (`blob_glow_intensity`, `blob_glow_reactivity`, `blob_glow_max_size`) — *Advanced sliders*
  - Impact: Control glow brightness, responsiveness, and spread radius.
  - Conflicts: Sliders apply even when Reactive Glow disabled; keep values moderate to avoid halo saturation.
- **Ghosting Toggle + Opacity / Decay** (`blob_ghosting_enabled`, `blob_ghost_alpha`, `blob_ghost_decay`) — *Advanced controls*
  - Impact: Shows faded outline of recent peak size; opacity and decay govern persistence.
  - Conflicts: Long stage releases + slow decay smear the halo; bright outlines reduce readability.
- **Stage Bias / Stage Gain / Stage 2 & 3 Release** (`blob_stage_bias`, `blob_stage_gain`, `blob_stage2_release_ms`, `blob_stage3_release_ms`) — *Advanced sliders*
  - Impact: Shape staged growth envelopes: bias preloads, gain scales amplitude, release sliders control linger durations.
  - Conflicts: High manual floor or dynamic floor can pin stages, making gain changes imperceptible.
- **Core Scale / Core Floor Bias** (`blob_core_scale`, `blob_core_floor_bias`) — *Advanced sliders*
  - Impact: Core Scale is uniform multiplier after staging; Core Floor keeps minimum radius.
  - Conflicts: Large floor bias reduces effect of Technical floors; too much scale causes clipping.
- **Reactive Deformation** (`blob_reactive_deformation`) — *Advanced slider*
  - Impact: Multiplies outward energy-driven growth.
  - Conflicts: Stack carefully with Technical Dynamic Range; both amplify spikes and can overdrive geometry.
- **Constant Wobble / Reactive Wobble** (`blob_constant_wobble`, `blob_reactive_wobble`) — *Advanced sliders*
  - Impact: Base wobble during silence vs energy-driven wobble on peaks.
  - Conflicts: High values cause jitter, especially with small audio block sizes.
- **Stretch Tendency / Inner / Outer** (`blob_stretch_tendency`, `blob_stretch_inner`, `blob_stretch_outer`) — *Advanced sliders*
  - Impact: Determine directional juts/dents magnitude and asymmetry.
  - Conflicts: Large outer stretch + high pulse breaks bounds; inner stretch below manual floor appears clipped.
- **Bar Count** (`blob_bar_count`) — *Technical spinner*
  - Impact: FFT bins sampled per frame; higher count = finer detail.
  - Conflicts: High counts distribute energy thinly (muted pulse); low counts exaggerate aliasing in stretch.
- **Block Size, Adaptive Sensitivity, Sensitivity, Dynamic Floor, Manual Floor, Dynamic Range** — *Technical group*
  - Impact: Govern audio pipeline (FFT smoothing, gain, floors, dynamic range boosting).
  - Conflicts: Treat as signal-level controls; overlapping with Advanced floor/bias sliders can double-clamp or double-amplify.

---

**Recommended Blob baselines**

1. *Glow stack*: Keep Reactive Glow enabled but cap Glow Intensity around 45–55 % and Max Size ≈150 % while using a darker Outline color to prevent clipping when Pulse Intensity or Stage Gain are high.
2. *Envelope balance*: Stage Bias ±0.15, Stage Gain ≈120 %, Stage 2 Release ≈1.0 s, Stage 3 Release ≈1.3 s yield lively hits without fighting Technical Manual Floor.
3. *Wobble blend*: Constant Wobble ~35 %, Reactive Wobble ~90 % keeps idle motion subtle yet allows peaks to pop. Increase Constant Wobble only if Audio Block Size is large.
4. *Stretch safety*: Keep Stretch Tendency ≤45 % unless Card Width/Growth stay near defaults; Inner Stretch ≈40 % + Manual Floor around 0.3 preserves dents without clipping.
5. *Sensitivity strategy*: Leave Adaptive Sensitivity ON for most playlists. If you disable it, set Sensitivity ≈1.10× and avoid pushing Stage Gain beyond ~120 % to prevent double amplification.
6. *Pulse Intensity*: Treat 1.0× (100 %) as the default. Staying between 0.85×–1.25× keeps Stage Gain/Reactive Deformation in their useful range; only push higher after dialing Stage Gain down so you don’t double-scale the same amplitude envelope.
7. *Bar layout*: Keep Bar Count between 32–48 for a balanced look. Going past 64 spreads energy too thin (muted pulse) unless Pulse Intensity/Stage Gain drop to compensate; dipping below 24 makes stretch spikes chunky.

---

## Bubble Mode

- **Big Bubble Bass Pulse** (`bubble_big_bass_pulse`) — *Advanced (Audio Reactivity)*
  - Impact: Scales radius/expansion of large bubbles from low-frequency bands.
  - Conflicts: High values plus large Big Bubble Size can exceed card bounds; competes with Technical sensitivity.
- **Small Bubble Freq Pulse** (`bubble_small_freq_pulse`) — *Advanced*
  - Impact: Drives medium/high-frequency expansion on small bubbles.
  - Conflicts: Pairing high pulse with large Small Bubble Size creates noisy background and hides pop flashes.
- **Stream Direction** (`bubble_stream_direction`) — *Advanced combo*
  - Impact: Sets base travel direction (None/Up/Down/Left/Right/Diagonal/Random).
  - Conflicts: Ignored when Swirl Mode enabled; removing direction makes reactivity sliders feel weaker.
- **Stream Constant Speed** (`bubble_stream_constant_speed`) — *Advanced slider*
  - Impact: Baseline stream velocity regardless of audio.
  - Conflicts: Must balance with Speed Cap; zero constant relies solely on reactivity.
- **Stream Speed Cap** (`bubble_stream_speed_cap`) — *Advanced slider*
  - Impact: Upper bound on stream velocity multiplier.
  - Conflicts: Too low mutes Speed Reactivity; too high yields teleport-like motion.
- **Speed Reactivity** (`bubble_stream_reactivity`) — *Advanced slider*
  - Impact: Audio-driven modulation of stream speed.
  - Conflicts: High values with Swirl Mode can cause motion sickness; coordinate with constant speed/cap.
- **Rotation Amount** (`bubble_rotation_amount`) — *Advanced (Drift & Rotation)*
  - Impact: Rotational drift of entire field.
  - Conflicts: High rotation plus Swirl or fast Drift is dizzying and can desync lighting.
- **Drift Amount / Speed / Frequency** (`bubble_drift_amount`, `bubble_drift_speed`, `bubble_drift_frequency`) — *Advanced sliders*
  - Impact: Amount sets offset magnitude, Speed sets oscillation rate, Frequency sets direction change cadence.
  - Conflicts: Require nonzero values to matter; Swirl Mode disables drift; high frequency + low speed looks jittery.
- **Drift Direction** (`bubble_drift_direction`) — *Advanced combo*
  - Impact: Chooses drift axis/pattern (None/Left/Right/Diagonal/Swish variants/Random).
  - Conflicts: Disabled when Swirl Mode on; legacy swirl values migrate here.
- **Swirl Mode Enable / Direction** (`bubble_swirl_enabled`, `bubble_swirl_direction`) — *Advanced controls*
  - Impact: Forces vortex motion clockwise or counter-clockwise.
  - Conflicts: Disables Drift and Stream direction combos; ensure stream speeds are tuned first.
- **Big Bubble Size** (`bubble_big_size_max`) — *Advanced (Lifecycle)*
  - Impact: Baseline radius for big bubbles (±40% variance).
  - Conflicts: High values plus high Surface Reach clip at card edges; interacts with Bass Pulse.
- **Small Bubble Size** (`bubble_small_size_max`) — *Advanced*
  - Impact: Baseline radius for small bubbles (±45%).
  - Conflicts: Large values reduce contrast and increase fill cost.
- **Big / Small Bubble Count** (`bubble_big_count`, `bubble_small_count`) — *Advanced sliders*
  - Impact: Concurrent population counts.
  - Conflicts: Big counts >18 overlap; high small counts plus Tail Opacity create haze.
- **Surface Reach** (`bubble_surface_reach`) — *Advanced slider*
  - Impact: Max card height before bubbles pop.
  - Conflicts: High reach with high speed causes constant top-edge popping; low reach hides pop colour.
- **Card Height** (`bubble_growth`) — *Advanced slider*
  - Impact: Multiplies card height / widget footprint.
  - Conflicts: Tall cards + diagonal drift overlap other widgets; adjust reach accordingly.
- **Tail Length / Tail Opacity** (`bubble_trail_strength`, `bubble_tail_opacity`) — *Advanced (Motion Tails)*
  - Impact: Trail length and max alpha for motion blur.
  - Conflicts: Both required for visible tails; high settings with many bubbles obscure the scene.
- **Specular Direction** (`bubble_specular_direction`) — *Normal combo*
  - Impact: Highlight origin orientation.
  - Conflicts: Should match Gradient Direction; mismatches look detached.
- **Gradient Direction** (`bubble_gradient_direction`) — *Normal combo*
  - Impact: Lighting gradient orientation (incl. Center Out).
  - Conflicts: Must align with motion cues; otherwise shading feels wrong.
- **Outline / Specular / Gradient Light / Gradient Dark / Pop Colour** — *Normal swatches*
  - Impact: Define outline ring, highlight tint, gradient endpoints, and pop flash colour.
  - Conflicts: Need sufficient contrast; bright specular + swirl + rotation can blow highlights, strong pulses can hide pop colour.
- **Bar Count** (`bubble_bar_count`) — *Technical*
  - Impact: FFT bins powering bubble energy.
  - Conflicts: >64 spreads energy thin; <24 synchronizes pulses too much.
- **Audio Block Size** (`<mode>_audio_block_size`) — *Technical combo*
  - Impact: FFT sample window size (Auto/0 defers to the active audio driver). Smaller blocks respond faster but jitter more; larger blocks smooth at the cost of latency.
  - Conflicts: Extremely small blocks plus high reactivity exaggerate jitter; larger blocks typically need higher pulse/sensitivity sliders to stay lively.
  - Notes: Set per preset/mode only. Global `audio_block_size` was removed in Mar 2026 — if you see it in a preset, run the repair tool.
- **Adaptive Sensitivity / Sensitivity** — *Technical checkbox + slider*
  - Impact: Adaptive auto-normalizes gain; manual sensitivity applies when adaptive off.
  - Conflicts: Disabling adaptive requires retuning stream/size sliders to avoid clipping.
- **Dynamic Range Boost** — *Technical checkbox*
  - Impact: Allows spikes to deviate further from floor.
  - Conflicts: High boost with high reactivity causes erratic velocity; disable for calmer motion.
- **Dynamic Noise Floor / Manual Floor** — *Technical checkbox + slider*
  - Impact: Dynamic floor auto-adjusts baseline; manual floor takes over when dynamic disabled.
  - Conflicts: Set manual floor before toggling; high values reduce contrast between big/small bubbles.

**Recommended Bubble baselines**

1. *Pulse split*: Big Bubble Bass Pulse ~55 % and Small Bubble Freq Pulse ~45 % keep contrast between hero bubbles and filler while leaving headroom for Sensitivity boosts.
2. *Stream tuning*: Direction = Up or Diagonal, Constant Speed 45–55 %, Speed Cap ~220 %, Reactivity ~60 % delivers energetic flow without runaway speeds.
3. *Drift vs swirl*: Use drift (Amount 35 %, Speed 45 %, Frequency 40 %) when you want gentle sway. Only enable Swirl Mode for spotlight presets; when enabled, drop stream reactivity under 40 % to prevent corkscrews.
4. *Population mix*: 8–10 big bubbles with size 38–42, 24–28 small bubbles with size 16–18 keeps layering clear. Increase Surface Reach only after verifying card height doesn’t intersect other widgets.
5. *Tail discipline*: Tail Length 40 % with Tail Opacity 25 % adds motion blur without fog. Raise opacity only if bubble counts are modest (<20 small).
6. *Lighting*: Pair Specular Direction “Top Left” with Gradient Direction “Center Out” for dimensional highlights; keep Gradient Light at least 30 % brighter than Gradient Dark so pop colour remains readable.
7. *Technical*: Start with Bar Count 48, Adaptive Sensitivity ON, Manual Floor governed by dynamic floor. If you disable dynamic floor, set Manual Floor ≈0.22 and lower Speed Cap by ~20 % to offset the higher baseline energy.

---

## Spectrum Mode

- **Bar Fill / Border Colours & Opacity** (`bar_fill_color`, `bar_border_color`, `bar_border_opacity`) — *Normal controls*
  - Impact: Define main pillar colour, outline, and outline alpha.
  - Conflicts: High opacity borders plus ghosting can leave bright after-images; lower opacity when ghost trails enabled.
- **Ghosting Enable / Opacity / Decay** (`ghosting_enabled`, `ghost_alpha`, `ghost_decay`) — *Advanced group*
  - Impact: Draws decaying peak bars; opacity sets brightness, decay controls linger length.
  - Conflicts: Slow decay + curved profile amplifies shimmer; combine with Single Piece to avoid floating peaks.
- **Single Piece Mode** (`spectrum_single_piece`) — *Advanced checkbox*
  - Impact: Renders solid pillars (no segments) using the curved shader path.
  - Conflicts: Requires adequate border radius or slanted profile for polish; legacy profile ignores this toggle.
- **Rainbow Per-Bar** (`spectrum_rainbow_per_bar`) — *Advanced checkbox*
  - Impact: Distributes rainbow shader across bars instead of treating the stack as one gradient.
  - Conflicts: Adds GPU cost; with Single Piece OFF the stripes exaggerate segment gaps.
- **Bar Profile** (`spectrum_bar_profile`) — *Advanced combo*
  - Impact: Switch between legacy template and curved dual-peak math.
  - Conflicts: Curved engages additional smoothing; keep Adaptive Sensitivity ON to avoid clipped peaks when switching back.
- **Border Radius** (`spectrum_border_radius`) — *Advanced slider*
  - Impact: Rounds bar tips when using Curved profile (hidden for Legacy).
  - Conflicts: High radius with segment gaps causes visual gaps between segments; pair with Single Piece for best effect.
- **Card Height Growth** (`spectrum_growth`) — *Advanced slider*
  - Impact: Multiplies widget height.
  - Conflicts: Larger cards require higher Manual Floor or Adaptive Sensitivity, otherwise bars look short despite height.
- **Technical controls** (`bar_count`, `<mode>_audio_block_size`, adaptive/sensitivity/floor/dynamic_range)
  - Impact: Govern FFT binning, latency, gain, and floors.
  - Conflicts: Low bar counts (<24) break curved weighting (bass peak shifts); audio block sizes <256 increase jitter unless the new bar gate remains.

**Recommended Spectrum baselines**

1. *Curved kit*: Bar Profile = Curved, Border Radius ~4px, Single Piece ON, Rainbow Per-Bar OFF for a clean wave look.
2. *Ghost tuning*: Enable Ghosting only when bar_border_opacity ≤80 %; set Ghost Alpha 35 %, Decay 55 % for smooth peaks without smearing.
3. *Height vs gain*: At Spectrum Growth >1.3×, raise Adaptive Sensitivity offset by +0.1 (or raise Manual Floor by +0.15) to keep bars from hugging the bottom.
4. *Bar count*: 32–48 bins keep curved weighting intact; going to 64 needs Sensitivity +15 % to compensate for thinner energy per bar.
5. *Latency trade*: Audio Block Size 256 (Auto) balances response and smoothness. Drop to 128 only when you also increase ghost decay (faster fade) to avoid shimmer.
6. *Colour discipline*: Keep Fill alpha ≥85 % if you disable Single Piece; otherwise the gaps show wallpaper bleed and look noisy.

---

## Oscilloscope Mode

- **Glow Enable / Intensity / Colour / Reactive** (`osc_glow_enabled`, `osc_glow_intensity`, `osc_glow_color`, `osc_reactive_glow`) — *Normal controls*
  - Impact: Adds halo around lines; reactive mode ties brightness to bass.
  - Conflicts: Glow widgets remain active when toggle off; zero intensity before disabling to avoid stale values.
- **Ghost Trail & Intensity** (`osc_ghosting_enabled`, `osc_ghost_intensity`) — *Normal*
  - Impact: Leaves faded previous waveform.
  - Conflicts: Ghost trail + multi-line often looks cluttered unless Line Dim is active.
- **Line Amplitude / Smoothing / Speed** (`osc_line_amplitude`, legacy `osc_sensitivity`, `osc_smoothing`, `osc_speed`) — *Normal sliders*
  - Impact: Line Amplitude is the visual gain applied inside the oscilloscope shader (scales waveform height) while Smoothing and Speed retain their previous behaviour.
  - Conflicts: Treat Line Amplitude separately from the Technical Sensitivity slider (global gain). High amplitude with low smoothing still creates jitter, and increasing both the Technical gain and Line Amplitude clips even faster; retune one at a time.
- **Line Dim / Offset Bias / Vertical Shift** (`osc_line_dim`, `osc_line_offset_bias`, `osc_vertical_shift`) — *Advanced controls*
  - Impact: Dim lines 2/3 glow, spread lines vertically, and add per-band offsets.
  - Conflicts: Offset Bias requires multi-line mode; Vertical Shift >120 clips at card edge in short cards.
- **Multi-Line Mode + Line Count** (`osc_multi_line`, `osc_line_count`) — *Advanced*
  - Impact: Enables 2–3 simultaneous waveforms with separate colours/glow.
  - Conflicts: Line count forces card height adjustments; without enough Vertical Shift lines overlap.
- **Line Colours & Glow Colours** (`osc_line*_color`, `osc_line*_glow_color`) — *Advanced swatches*
  - Impact: Per-line palette.
  - Conflicts: Keep glow alpha lower than primary line to avoid washing out line 1.
- **Card Height** (`osc_growth`) — *Advanced slider*
  - Impact: Widget height multiplier.
  - Conflicts: Large growth plus Vertical Shift can overlap other widgets; adjust Layout margins accordingly.
- **Technical controls** (`osc_bar_count` via technical group, block size, adaptive/sensitivity, floors)
  - Impact: Shared audio parameters.
  - Conflicts: Lowering bar count below default reduces multi-line energy separation.

**Recommended Oscilloscope baselines**

1. *Core trio*: Sensitivity 3.2×, Smoothing 65 %, Speed 80 % keeps flow responsive without jitter.
2. *Glow discipline*: Glow ON with Intensity 55 %, Reactive ON; when multi-line enabled enable Line Dim to keep line 1 dominant.
3. *Ghosts vs glow*: If Ghost Trail ON, reduce glow intensity by 10 % to prevent double halos.
4. *Multi-line spacing*: Line Count = 2, Offset Bias 35 %, Vertical Shift 60 for layered look. At 3 lines set Offset Bias ≥55 % and Vertical Shift ≥110.
5. *Technical split*: Leave Adaptive Sensitivity ON; if you disable it and raise the Technical Sensitivity slider, dial Line Amplitude back ~10 % so the two gains don’t double-scale. Manual Floor 1.6 + Dynamic Floor OFF still needs Smoothing around 75 % to avoid chatter.
6. *Card height*: Growth 1.2× for two lines, 1.4× for three. Re-check widget overlap whenever Smoothing <50 % (lines spike higher).

---

## Sine Wave Mode

- **Glow Enable / Intensity / Colour / Reactive** (`sine_glow_enabled`, etc.) — *Normal*
  - Impact: Same as oscilloscope but applied to multiple sine lines.
  - Conflicts: Glow persists even when Multi-Line is off; dial intensity down when Crawl is high to avoid clipping.
- **Line Colour + Travel** (`sine_line_color`, `sine_travel`) — *Normal*
  - Impact: Base hue and scroll direction.
  - Conflicts: Travel speed inherits from Speed slider; high travel plus Crawl >60 % looks blurry.
- **Sensitivity / Speed** (`sine_sensitivity`, `sine_speed`) — *Normal sliders*
  - Impact: Amplitude and animation rate.
  - Conflicts: Sensitivity >1.6× with Card Adaptation >70 % clips at card bounds.
- **Wave Effect / Micro Wobble / Crawl / Width Reaction** — *Normal sliders*
  - Impact: Additional undulation, jagged wobble, gentle dents, and bass-driven line thickening.
  - Conflicts: Micro Wobble + Crawl both distort shape; choose one primary effect.
- **Density / Heartbeat / Displacement** (`sine_density`, `sine_heartbeat`, `sine_displacement`) — *Advanced sliders*
  - Impact: Controls cycles per card, transient swells, and multi-line shove.
  - Conflicts: Density >2.2× with Width Reaction >40 % drops FPS on lower GPUs; Heartbeat relies on bass detection and ignores Sensitivity.
- **Vertical Shift / Line Offset Bias / Card Adaptation** — *Advanced*
  - Impact: Spread lines vertically, set base height usage.
  - Conflicts: Card Adaptation >80 % requires Manual Floor ≥0.4 to avoid clipping.
- **Line Shifts & Multi-Line Controls** (`sine_line*_shift`, `sine_multi_line`, `sine_line_count`, `sine_travel_line*`) — *Advanced*
  - Impact: Phase offsets and per-line travel.
  - Conflicts: Horizontal shifts only visible when multiple lines enabled; keep shifts within ±0.3 cycles to preserve readability.
- **Card Height** (`sine_wave_growth`) — *Advanced*
  - Impact: Widget height multiplier.
  - Conflicts: Growth >1.5× combined with Density <0.8× wastes vertical space.
- **Technical controls** (per-mode audio block size, adaptive, floors, bar count) — as above.
  - Conflicts: Dropping bar count below ~40 collapses the bass/mid split the sine displacement math expects, so multi-line offset bias and displacement all converge; retune line shifts or raise bar count before blaming density settings.

**Recommended Sine Wave baselines**

1. *Layered duet*: Multi-Line ON, Line Count 2, Line 2 Travel = Left, Line 3 disabled; Width Reaction 25 % for subtle swell.
2. *Motion mix*: Speed 0.8×, Crawl 35 %, Micro Wobble 0 % for smooth R&B visuals; swap Crawl for Micro Wobble (45 %) when you want EDM jaggedness.
3. *Density sweet spot*: Density 1.1× with Card Adaptation 55 % keeps lines readable on 16:9 monitors; push to 1.6× only when Card Height ≥1.3×.
4. *Heartbeat gating*: Keep Heartbeat ≤20 % unless Sensitivity <0.9×; high heartbeat on loud mixes causes constant swells.
5. *Technical*: Audio Block Size 256 (Auto) plus Adaptive Sensitivity ON; if you force block=128, increase Smoothing preset (manual floor) by +0.05 to counter jitter.
6. *Colour & glow*: Use complementary colours per line (e.g., white primary, cyan secondary) and keep Glow Intensity ≤60 % to avoid blending lines together.

---


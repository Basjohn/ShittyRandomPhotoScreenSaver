# Visualizer Signal Contract

This is the canonical contract for how Spotify visualizer modes consume:
- continuous energy bands
- transient bus energy
- micro-scheduler events
- smoothing ownership

Use this alongside [Visualizer_Reset_Matrix.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Reset_Matrix.md), [Visualizer_Baseline_Tuning_Matrix.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Baseline_Tuning_Matrix.md), and [Visualizer_Debug.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Debug.md). If temporary validation or investigation is still active, route through [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Current_Plan.md) instead of depending on audit documents here.

## 1. Shared Buses

### 1.1 Continuous Energy

- Source: `beat_engine.get_energy_bands()` in all normal persisted-settings flows.
- Shape: bass / mid / high / overall.
- Job: sustained loudness, lane presence, stable motion support.
- Ownership:
  - engine extracts it
  - mode-local runtime may smooth or remap it before rendering

Runtime note:
- `get_pre_agc_energy_bands()` still exists as a runtime/debug seam, but it is no longer part of the authored visualizer settings schema.

### 1.2 Transient Bus

- Source: `TransientBus` / `TransientEnergyBands`.
- Shape: fast-path bass / mid / high transient channels.
- Job: immediate punch without replacing continuous energy.
- Ownership:
  - bar computation updates the transient bus
  - each mode uses its own mix slider(s) and clamp rules

### 1.3 Micro-Scheduler Events

- Source: event scheduler `peek_latest(...)`.
- Shape: discrete kick / snare classified events with strength and age.
- Job: confirm musical hits and give short lived, mode-local assist.
- Ownership:
  - scheduler detects and debounces
  - modes should treat events as assist signals, not the whole visual language

## 2. Mode Matrix

| Mode | Primary continuous driver | Transient injection | Scheduler role | Consume / Peek | Smoothing ownership |
|------|---------------------------|---------------------|----------------|----------------|---------------------|
| `spectrum` | lane-routed bass/mid/treble across authored profile | `spectrum_lane_transient_mix` feeds kick lane | kick lane confirmation / snap | `peek` | bar computation + mode lane routing |
| `bubble` | sustained mid/high for stream speed, bass for pulse floor | `bubble_transient_mix_bass` / `bubble_transient_mix_vocal` | beat promotions / pulse accents | `consume_once` for promotion-style behavior, otherwise local state | bubble simulation owns motion envelopes |
| `blob` | continuous bass + overall for size/stage, mid/high for wobble | `blob_transient_mix_bass` / `blob_transient_mix_vocal` | kick helps stage/impact, snare helps wobble-side deformation | `peek` | overlay owns Blob-local event envelope, per-band filtering, stage filtering |
| `sine_wave` | smoothed line energy and heartbeat floor | `sine_wave_transient_width_mix` widens/reacts | kick/snare beat assist for width / amplitude / heartbeat | `peek` | overlay + sine renderer state |
| `oscilloscope` | waveform samples plus smoothed band glow support | `oscilloscope_transient_width_mix` boosts width / sensitivity | kick/snare beat assist for width confirmation | `peek` | engine waveform freshness + overlay line envelopes |

## 3. Blob-Specific Contract

Blob is the easiest mode to destabilize because it mixes multiple signals into a single silhouette.

### 3.1 Intended behavior

- Bass + overall:
  - own size, stage progress, and major outward impact
- Mid + high:
  - own wobble and softer shape character
- Transient bus:
  - reinforces the same roles above, but must stay clamped
- Scheduler events:
  - assist existing motion, never create giant calm-passage pulses on their own

### 3.1.1 Runtime mapping quick map

- Core size / body breathing:
  - primarily bass-led, with a small smoothed body-breath floor so the silhouette does not flicker between low phrases
- Stage progression:
  - bass/overall-biased stage-input bands, with modest vocal support available to the upper ladder so strong vocal passages are not ignored
  - kick assists stage/impact when low-end support is real
- Stretch / protrusions:
  - primarily vocal/mid-led with light bass support so it is expressive without going dead on non-bass phrases
- Wobble / vocal-side character:
  - almost entirely vocal/mid-led, with only light high-frequency sparkle on top
  - snare assists wobble-side deformation more than whole-body size
- Glow / intensity feel:
  - bass-led CPU-smoothed energy, not one-frame transient spikes

### 3.2 Current guardrails

- Blob-local scheduler event envelope:
  prevents one-frame event hits from vanishing instantly
- Blob-local `dt` clamp:
  keeps hitches from becoming visual punches
- Blob per-band live filtering:
  smooths bass/mid/high/overall before the live silhouette uses them
- Support-weighted scheduler reinforcement:
  prevents low-support passages from getting the same boost as real loud passages
- Separate Blob stage-input bands:
  stage progression uses a bass/overall-biased input set instead of the more decorative mid/high-boosted silhouette bands
- Upper-stage vocal support:
  stage 2 / 3 are allowed a modest mid contribution; Blob should stay bass-led on whole-body growth, but upper progression must not act like vocals do not exist
- Re-spaced Blob stage ladder:
  stage 1 should answer to ordinary support without saturating immediately, while stage 2/3 must still be reachable on strong real passages
- Faster stage-1-only release:
  keeps Blob size breathing between phrases instead of parking at one silhouette while wobble/stretch twitch on top

### 3.3 Diagnostics

When `SRPSS_VIZ_DIAGNOSTICS=1`, Blob diagnostics log:
- raw frame `dt`
- clamped Blob `blob_dt`
- kick/snare raw vs enveloped strength
- base continuous Blob bands
- transient contribution bands
- `raw_live` Blob bands
- filtered live Blob bands
- smoothed overall energy
- stage raw / filtered / previous values

## 4. Shared-vs-Divergent Lineage

### 4.1 Sine Wave and Oscilloscope must stay shared on

- waveform freshness gating
- waveform-count correctness
- shared line/glow uniform conventions
- base CPU-smoothed glow bands

### 4.2 Sine Wave and Oscilloscope must stay isolated on

- heartbeat behavior
- scheduler assist strength
- width reaction semantics
- density / displacement / travel tuning
- preset defaults and feel tuning

## 5. Retired Authored Keys

These are no longer part of the canonical curated/preset authored shape:
- `energy_boost`
- `use_raw_energy`

Policy:
- curated preset JSON, preset save/export, and preset repair should not emit them
- the shipped curated tree is now audited to stay free of them
- live settings/defaults/model serialization no longer persist them either
- any remaining runtime-only/internal presence is technical debt or a debug seam, not a signal to re-author them into presets again

## 6. Test Links

- `tests/test_transient_per_mode_integration.py`
- `tests/test_spectrum_shaping.py`
- `tests/test_bubble_reactivity.py`
- `tests/test_ghost_isolation.py`
- `tests/test_spotify_visualizer_widget.py`

## 7. Settings / Signal Boundary

- `ui/tabs/media/*_settings_binding.py` modules own Qt load/save translation only. They should not reinterpret DSP or signal semantics.
- `core/settings/visualizer_settings_contract.py` owns shared sparse-mapping/per-mode fallback resolution for settings models only. It should not reinterpret DSP or signal semantics.
- `core/settings/visualizer_preset_indices.py` owns sparse preset-index fallback/lookup only. It should not interpret renderer behavior or curated aesthetic intent.
- `core/settings/visualizer_settings_snapshot.py` owns canonical persisted/SST/preset-payload normalization for `widgets.spotify_visualizer` only. It should not reinterpret DSP or signal semantics.
- `core/settings/bubble_gradient_semantics.py` owns Bubble label migration and canonical brightest-point -> shader mapping only. It is a renderer/settings contract helper, not a signal-behavior layer.
- `core/settings/visualizer_mode_registry.py` and `ui/tabs/media/visualizer_mode_binding.py` own mode identity, preset keys, and per-mode preset/rainbow persistence. They do not own signal behavior.
- `rendering/display_overlays.py` owns the timing constants/policy for the primary-overlay wave and Spotify secondary-wave only. Primary overlays should begin fading as soon as the compositor is ready; the startup delay belongs to the Spotify secondary wave, not to the whole overlay system.
- `rendering/widget_manager.py` owns the live runtime source of truth for startup fade coordination plus Spotify secondary-stage scheduling. It mirrors expected-overlay, started, and `_spotify_secondary_not_before_ts` state onto the parent display for runtime consumers, but the manager/fade-coordinator path is authoritative.
- `rendering/widget_manager.py` owns Spotify secondary-stage registration/wakeup routing only.
- `rendering/widget_setup.py` owns the primary expected-overlay contract. `spotify_visualizer` must stay out of that primary expected set so staged startup remains decoupled from the first compositor wave.
- `rendering/display_image_ops.py` plus `widgets/spotify_bars_gl_overlay.py::prewarm_context()` own visualizer GL overlay prewarm. They should prepare the overlay before reveal, not reinterpret signal semantics.
- `widgets/spotify_visualizer/shaders/__init__.py::preload_fragment_shaders()` is part of that same startup seam. Shader-source loading should happen before visualizer overlay prewarm, not during the first visible reactive seconds.
- `widgets/media/runtime_state.py` plus `widgets/media/display_update.py` own retained media-card lifecycle only. When fresh session data disappears but retained metadata exists, the media card stays visible while emitted media payloads are downgraded to paused/non-reactive state; this seam must not hide the card just because the visualizer should stop reacting.
- `widgets/spotify_visualizer_widget.py` owns visualizer startup staging: seed playback state, self-register into the Spotify secondary stage when the parent exposes that seam, defer hot-start to the secondary stage, defer any pre-stage wake request until that hot-start actually begins, obey the parent display's manager-mirrored Spotify secondary-stage deadline even when anchor/media updates arrive early, prewarm the overlay, and reveal only after the first fresh frame plus the minimum hidden warmup window, with an exact ready-driven follow-up attempt when the warmup deadline arrives and a guarded fallback timer for quiet/paused startup.
- Deferred startup wake is not the same thing as a normal post-pause wake. When staged hot start is already performing the engine reset/start, consuming a deferred startup wake must not immediately re-run the normal `engine.wake()` capture-restart path.
- The visualizer must not re-register itself as a primary overlay-fade participant during startup; doing so breaks the staged-start contract and reintroduces hot work into the first reactive window.
- `widgets/shadow_utils.py::ShadowFadeProfile.start_fade_in()` owns the shared fade-helper visibility contract: a widget must be shown immediately while pinned at `opacity=0.0`, rather than waiting for the first animation tick to make the widget visible.
- Shared startup fade timing should derive from `widgets/shadow_utils.py::ShadowFadeProfile`, with visualizer-specific startup delays layered on top of that source of truth rather than copied as local literals.
- Media-card re-entry after a true hide must also come back through the shared fade helper path. “First track ever” and “metadata returned later” are not allowed to diverge into separate visibility contracts.
- Signal ownership changes belong in runtime layers such as:
  - beat engine / bar computation
  - transient bus / scheduler consumption
  - per-mode renderer and overlay state
- If a visualizer behavior bug can only be “fixed” by changing settings-binding semantics, sanity-check whether the real issue is in runtime signal consumption instead.

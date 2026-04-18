# Spec

Single source of truth for current architecture and key decisions.

Use `Current_Plan.md` for active rollout and validation state, and `Docs/Historical_Bugs.md` for dated regressions, failed approaches, and final fix summaries. `Spec.md` should stay focused on the current contract.

Use `Docs/Visualizer_Change_Checklist.md` whenever a visualizer mode setting is introduced, removed, renamed, split, or materially retuned. That checklist is the stable sweep for UI, bindings, runtime, presets, tools, tests, and docs.

## Goals
- Smooth, flicker-free image transitions on multi-monitor setups.
- Centralized managers for threads, resources, settings, animations.
- Predictable performance with memory-aware caching and prefetching.

## UI Component Specifications
- **Custom Styling (checkboxes/combos/sliders)**: `Docs/Custom_Style_Implementation.md` now captures the full asset pipeline, helper usage, and the March 2026 “parity pass” contract. Consult it for circle indicator geometry, combo shell QSS, shared `_aligned_row` helpers, and the checklist used to keep settings tabs visually aligned. Any new control chrome must be documented there before shipping.
- **Settings Shell Outer Border**: `ui/settings_dialog.py` uses the current paint-based rounded-edge treatment for the settings shell. Acrylic, the custom title bar, and inner styling are part of that contract.
- **Styled ComboBox / Font ComboBox**: All dropdowns in settings tabs must use `ui/widgets/styled_combo_box.py` plus the shared `COMBOBOX_STYLE` appended at the dialog level. Font pickers must instantiate `ui/widgets/styled_font_combo_box.py` so the preview rows stay intact while inheriting the same chrome. `WidgetsTab` and TransitionsTab both import `COMBOBOX_STYLE`, so every dropdown inherits the skin without per-tab QSS; DisplayTab remains the reference for standalone dialogs.
- **Rounded Input Fields**: `SPINBOX_STYLE` in `ui/tabs/shared_styles.py` now defines the shared rounded border/hover/focus state for `QSpinBox`, `QDoubleSpinBox`, and `QLineEdit`. Append that stylesheet alongside `COMBOBOX_STYLE` in any dialog so numeric/text inputs keep parity with the combo box chrome.
- **Slider Style**: `SLIDER_STYLE` in `ui/tabs/shared_styles.py` provides a dark glass indented groove with a pill-shaped notch handle (16×10px, dark gradient, `#444` border). Applied at the tab level so all `NoWheelSlider`/`QSlider` instances inherit it. Includes hover, pressed, and disabled states. Never use inline slider QSS — always inherit from the centralized constant.
- **Section vs Swatch Labels**: `add_section_label()` (34 px) is the default helper for combo/spin/text rows. Color swatch rows **must** use `add_swatch_label()` (28 px, `SWATCH_LABEL_STYLE`) so their shorter labels sit lower and align with `ColorSwatchButton` shadows. Mirror this via local `_swatch_row` helpers instead of duplicating QSS tweaks per tab.
- **CSS Specificity Warning**: Never use `QScrollArea QWidget { background: transparent; }` — specificity 002 overrides type-only selectors (001). Use `QScrollArea > QWidget > QWidget` (direct-child) instead. See `Docs/Custom_Style_Implementation.md` for details and `SCROLL_AREA_STYLE` for the safe pattern.
- **Rollout Tracking**: Track active implementation status and validation in `Current_Plan.md`. Record dated regressions and final fix notes in `Docs/Historical_Bugs.md`.
- **Visualizer buckets (ordering + persistence)**: For Spectrum, Bubble, Blob, Sine Wave, and Oscilloscope, each mode layout presents an **Advanced** collapsible group first, followed immediately by a **Technical** collapsible group. Both buckets are top-level siblings (not nested) and use the shared helper styles (toolbutton + helper label). Expanded/collapsed state persists per mode via `WidgetsTab._visualizer_adv_state` / `_visualizer_tech_state`. **Helix and Starfield are officially deprecated** (kept dev-only for archive/back-compat) and may omit UI buckets entirely.
  - Blob authored cleanup now follows `Docs/Visualizer_Mode_Consolidation_Mental_Model.md`: simplify the main control surface around user outcomes, keep color/glow basics, hide controls that fight the active mode/state, and preserve `Technical` as an expert/runtime layer instead of overflow for authored controls.

**Visualizer subtab + master toggle**: Widgets tab now exposes a dedicated **Visualizers** subtab beside Media. The subtab hosts a master toggle `spotify_visualizer.visualizers_enabled` that gates all Beat Visualizer controls. UX toggle is independent; runtime spawning of the visualizer remains linked to Media enablement/monitor positioning. Persistence: `spotify_visualizer.visualizers_enabled` and `spotify_visualizer.enabled` are saved independently; both must be true (and Media enabled) for runtime activation.

**Per-mode technical schema + presets**:
- Canonical per-mode technical keys live in `SpotifyVisualizerSettings` (`PER_MODE_TECHNICAL_MODES`). All Spectrum/Bubble/Blob/Sine/Osc advanced/technical controls persist per mode via `widgets.spotify_visualizer.<mode>_<key>`. The legacy global `audio_block_size` field has been fully removed; presets/UI/storage must only reference `<mode>_audio_block_size` (0 = Auto) alongside the usual manual/dynamic floor, sensitivity, dynamic range keys.
- Visualizer mode identity is centralized in `core/settings/visualizer_mode_registry.py`. Mode ids, display labels, preset keys, preset-slider ownership, and accepted mode setting prefixes (`sine_`, `sine_wave_`, `osc_`, `oscilloscope_`, etc.) must come from that registry rather than being re-declared in WidgetsTab/preset/runtime code. WidgetsTab mode combo initialization plus per-mode preset/rainbow load/save wiring flow through `ui/tabs/media/visualizer_mode_binding.py`, and missing preset fallback resolves from the preset registry's first non-custom slot for the mode rather than from shipped settings defaults or literal slot constants.
- Shared sparse-mapping/per-mode fallback resolution now lives in `core/settings/visualizer_settings_contract.py`, which is consumed by `SpotifyVisualizerSettings.from_settings()` and `.from_mapping()` so the model no longer duplicates baseline/per-mode technical resolution in two separate loaders.
- Shared preset-index fallback/lookup now lives in `core/settings/visualizer_preset_indices.py`, separating sparse preset resolution from curated preset file loading so models and normalization helpers can use the same contract without import-order coupling.
- Canonical persisted/SST/preset-payload normalization for `widgets.spotify_visualizer` now lives in `core/settings/visualizer_settings_snapshot.py`. Reset/defaults, SST import/export/preview, preset parsing, and WidgetsTab custom preset payload generation should route through that layer instead of open-coding their own sparse-mapping corrections.
- Blob and Bubble continuous-energy sourcing remain part of the shared visualizer signal contract, not mode-local persisted sidecar systems. `widgets/spotify_visualizer/config_applier.py` now routes those two modes onto explicit pre-AGC energy bands because the shared post-AGC/dynamic-floor path can visually flatten them under hot floor pressure. This routing is mode-owned runtime behavior, not a persisted `_use_raw_energy` schema seam; do not revive the retired toggle or invent extra saved settings for it.
- Blob/Bubble signal-contract warning: switching those modes onto pre-AGC bands is only the first half of the fix. If a hotter pre-AGC signal is fed through downstream support, stage, size, or overdrive math that was tuned around colder smoothed/post-AGC pressure, the failure mode simply flips from dead/flat hold states into Bubble ceiling pinning / jerky speed and non-shaped Blob blowout / judder. Treat that as one recurring bug family and solve it at the signal-contract layer, not as isolated symptom tuning.
- Mode-event handoff contract: scheduler onsets become mode-local edge signals exactly once at the handoff boundary. `config_applier.py` must consume Blob event edges when building the live overlay snapshot, and Bubble must consume its snare/vocal scheduler edges inside `BubbleSimulation.tick()` rather than polling them with `peek_latest()`. Re-reading the same scheduled event across multiple frames turns burst/stage authority into a fake sustained signal and recreates the same hot-state regressions under a different name.
- Bubble/Blob regression-fence contract: keep behavior-level coverage for both sides of this bug family. At minimum, Bubble needs a phrase-level overdrive-latch guardrail and Blob needs a hot-seed unwind guardrail, so the suite can fail on the same family the runtime logs exposed instead of only on idealized alternating phrases.
- Bubble collision contract (Apr 2026): Bubble bounce remains simulation-owned (not a GPU uniform concern). Runtime supports class-scoped bounce probability/speed, `same bubbles bounce only`, and collision-pop policies (`off`/`one`/`all`), with pulse-aware collision radii and drift-aware rebound stabilization to prevent interlock/rebounce snap loops.
- Idle visuals with strict worker-off contract (Apr 2026): Bubble, Sine Wave, and Oscilloscope must remain subtly animated while playback is not `playing`, while the capture worker remains off in that state. Paused mode switches must not deadlock on fresh-frame waits, and playback gating must remain provider-neutral across Spotify/MusicBee payloads.
- Visualizer staged-startup state now has an explicit contract in `widgets/spotify_visualizer/startup_contract.py`. `SpotifyVisualizerWidget` keeps the historical underscored fields (`_startup_secondary_stage_pending`, `_startup_reveal_pending`, etc.) only as compatibility properties; the real source of truth is the shared contract object.
- Mode-owned load/save translation should move into dedicated adapters instead of growing `ui/tabs/widgets_tab_media.py`. Concrete cuts now landed in `ui/tabs/media/spectrum_settings_binding.py`, `ui/tabs/media/blob_settings_binding.py`, `ui/tabs/media/bubble_settings_binding.py`, `ui/tabs/media/oscilloscope_settings_binding.py`, and `ui/tabs/media/sine_wave_settings_binding.py`, which move those mode-owned state translations out of the central coordinator.
- Spectrum / Oscilloscope / Sine Wave / Blob / Bubble now share `ui/tabs/media/builder_scaffold.py` for preset slider wiring, advanced-host collapse state, technical-host attachment, standard swatch-row spacing, and common control-binding helpers (`bind_setting_signal`, `bind_color_button`). The helper layer preserves direct signal -> `WidgetsTab._save_settings` connections so sender-aware advanced auto-switch behavior still works, while explicit normal-layout “force Custom” cases can route through `WidgetsTab._force_visualizer_preset_to_custom()`. Architectural boundary decision: stop at this shared scaffold/binding layer for now rather than pushing every mode-specific control into one giant metadata registry; only clearly repeated feature families should be promoted deeper.
- Spectrum shaping is node-driven via `spectrum_shape_nodes` (mirrored + linear layouts). In mirrored mode, UI editing is half-range (center→edge) and renderer output mirrors that profile to the opposite half. The editor now also owns per-lane vertical Energy Arrows: mirrored layouts persist `Mid / Vocal / Low-Mid / Bass` strengths, linear layouts persist `Bass / Low-Mid / Vocal / Hi-Mid / Treble` strengths, and runtime consumes those label-driven lane-strength maps directly so quiet lanes can collapse instead of inheriting one shared spectrum-wide scalar.
- Visualizer mode-isolation contract: dedicated mode-owned renderers and solver/math helpers must not read another mode's authored/runtime settings implicitly. Shared cross-mode behavior is allowed only in explicitly shared seams such as `widgets/spotify_visualizer/config_applier.py`, `widgets/spotify_visualizer_widget.py`, and `widgets/spotify_bars_gl_overlay.py`, and those seams must stay neutral/documented rather than quietly letting one mode own another's controls.
- Shared technical replay contract: if `SpotifyVisualizerWidget` lacks a technical-cache entry for the target mode, it must no-op rather than falling back to some other mode's cached technical state. Missing cache must never silently apply foreign `manual_floor`, sensitivity, block size, AGC, input gain, or transient-mix settings.
- Shared beat-engine rebuild contract: the Spotify visualizer uses one shared beat-engine lifecycle, not a hidden pool keyed by bar count. If bar-count-dependent runtime state needs rebuilding, startup and runtime must go through the same authoritative reconfigure path rather than keeping warmed alternate engines or ad hoc runtime-only mutations.
- Shared GPU-payload contract: `widgets/spotify_visualizer/config_applier.py::build_gpu_push_extra_kwargs(...)` must emit only the active mode's live extras on top of the shared visualizer baseline. Do not piggyback Blob-only kwargs into Sine/Osc/Bubble payloads, or line-mode kwargs into Bubble/Blob payloads, just because `SpotifyBarsGLOverlay.set_state(...)` can technically accept them.
- Blob stretch contract: unshaped Blob stretch is outward-biased by default. Shared widget/overlay/renderer defaults should keep inward stretch at `0.0` and outward stretch at the authored baseline (`0.35`) unless a deliberate future Blob design change says otherwise. Do not reintroduce inward pinch pressure accidentally through fallback defaults.
- Shared overlay-reset contract: `widgets/spotify_bars_gl_overlay.py` may host multiple modes, but mode-owned retained runtime state must reset or stay inert on mode change. In particular, Spectrum bar-peak memory (`_peaks`, `_last_peak_ts`) is Spectrum-owned and must not be mutated by Blob/Sine/Osc/Bubble frames, and line-mode waveform ring/count state must be cleared on mode re-entry so stale line history cannot bleed across mode switches.
- Spectrum render-style authoring is now canonicalized as `spectrum_render_mode` with supported authored UI values `segment` and `bars` (`BAR` is the default and matches the old single-piece behavior). The old `spectrum_single_piece` boolean is a legacy input only and should not be emitted by current UI/save paths.
- Spectrum unique-colour authoring is now canonicalized as `spectrum_unique_colors`; `spectrum_rainbow_per_bar` remains legacy input only for older preset/runtime payloads.
- Mirrored spectrum editor coordinate contract: node domain remains `x=0 center`, `x=1 edge` in both UI and DSP. The mirrored edit pane (left half) therefore renders edge→center left-to-right, while the ghost pane (right half) renders center→edge. This prevents flat-edge edits from being inverted into forced high-edge output.
- Even-bar mirrored sampling contract: mirrored Spectrum interpolation must treat the center as a half-step when `bar_count` is even. Do not mirror around `num_bars // 2` for counts like `34`, or the far edges become asymmetrical (`Ember Choir` exposed this).
- Spectrum rim-glow contract: Spectrum glow is a thin shader-local inward rim tint owned by `spectrum_glow_enabled`, `spectrum_glow_intensity`, and `spectrum_glow_color`. It should bleed only slightly into the bar fill (roughly 1–2 px), remain non-reactive by default, and should not be escalated into an outer halo, bloom, or trail system unless product direction explicitly changes.
- Spectrum notch-drag contract: bottom notch dragging in the shape editor must move only the active notch while still allowing it to cross adjacent labels. Neighbor labels must not be pushed along during drag, and ordering should be normalized after release rather than by collision-clamping the active notch.
- Migration helpers (`core/settings/visualizer_presets.py::_migrate_preset_settings`) convert legacy fields (e.g., `sine_min_height`, `blob_stretch_x_bias`, global `rainbow_enabled`) into the new per-mode schema. Preset ingestion filters keys via `GLOBAL_ALLOWED_KEYS` + mode prefixes.
- Manual floor baseline slider now clamps 0.12 – 1.0 and immediately reseeds the dynamic floor accumulator on every change, even when Dynamic Floor stays enabled. Engine activation, mode switches, widget resets, preset reloads, and SettingsManager migrations all pull the fresh per-mode manual floor before audio ticks resume, eliminating stale high floors bleeding between modes. Canonical defaults live in `core/settings/default_settings.py` via `core/settings/defaults.py`, and the derived snapshot artifacts (`core/settings/defaults_snapshot.py` / `defaults_snapshot.json`) are generated from that same source. All of those paths seed 0.12 so no baseline drifting back to 2.1 can occur.
- **Input gain contract (Mar 2026)**: Every mode now exposes a per-mode `input_gain` slider (5%–200%, default 100%) that scales PCM samples *before* FFT. The setting is wired through all eight layers (settings model/load/save, creator kwargs, widget cache/apply, beat engine/audio worker) and the audio worker clamps + forwards the gain to `bar_computation.compute_bars_from_samples()`, which multiplies the mono signal prior to peak detection/FFT so the effect matches Windows mixer volume changes without muting actual audio. Docs/TestSuite include regression coverage (`tests/test_input_gain.py`).
- **Preset repair schema enforcement (Mar 2026)**: `tools/visualizer_preset_repair.py` promotes legacy global technical keys (manual_floor, sensitivity, `input_gain`, etc.) into mode-specific namespaces before filtering, injects missing per-mode defaults from `core/settings/default_settings.py`, and now exposes `--audit-curated` so duplicate prefixed keys / stale backup blocks / top-level visualizer duplication fail loudly instead of drifting silently. Mandatory visual keys (glow + line colours, bubble gradients, blob glow) cover every mode to prevent curator edits from yielding incomplete payloads. Retired authored keys such as `energy_boost` and `use_raw_energy` are stripped from curated/save/export payloads, and the live visualizer settings schema no longer persists them either. Repair backups belong under `temp/visualizer_preset_backups`, never beside curated source files.
- **Technical-control wording contract (Apr 2026)**: Shared Technical controls own pre-FFT signal shaping (`Use Recommended Sensitivity`, `Sensitivity`, `Dynamic Noise Floor`, `Noise Floor Baseline`, `AGC Strength`, `Input Gain`, `Audio Block Size`, `Output Lift`). Mode-authored controls must not reuse those same words for different seams without clarifying the distinction. In particular, Sine Wave `Line Response` and Oscilloscope `Line Amplitude` are renderer-side post-analysis response controls, not duplicates of Technical sensitivity.
- **AGC guidance contract (Apr 2026)**: `AGC Strength` remains available for all visualizer modes, but the tooltip must explain that it is a shared normalization layer with mode-specific recommendations rather than a mode-authored creative effect. Keep `Input Gain` available as the explicit pre-FFT gain control; do not collapse those two controls together.
- **AGC recommendation marker contract (Apr 2026)**: `AGC Strength` remains a single shared slider. Per-mode guidance should appear as a subtle groove marker rendered by the centralized slider styling layer (`ui/tabs/shared_styles.py`) rather than as a second handle, ghost knob, or mode-local styling hack.
- **Curated preset policy (Apr 2026)**: Curated visualizer preset names, counts, filenames, and artistic content are intentionally fluid. Regression coverage must guard structural invariants instead: valid schema, modern key hygiene, slot uniqueness per mode, deterministic reindex behavior, and source/release tree parity. If curated slots collide, reindex/rename them; do not delete authored presets merely to satisfy tests.
- **Generated shipped preset artifacts (Apr 2026)**: `presets/visualizer_modes/` is the only authored source-of-truth tree. `presets/visualizer_modes_manifest.json` and `release/main_mc.dist/presets/visualizer_modes*` are generated artifacts rebuilt by `core/visualizer_preset_manifest.py`, `tools/regenerate_visualizer_shipped_presets.py`, and the build-runner pre-step. Do not hand-maintain the release preset tree or chase drift there manually.
- **Preset repair contract refresh (Apr 2026)**: `tools/visualizer_preset_repair.py` must derive missing injected preset keys from the canonical mode-normalized defaults contract (`normalize_visualizer_mode_payload(...)`) instead of broad handwritten mandatory-key maps. That keeps repair flexible when the SST/default schema evolves. Curated-source repairs/reindexes must also regenerate the shipped preset artifacts automatically, backups must continue living under `temp/visualizer_preset_backups` rather than beside curated presets, and the repair UI should keep only a small rotating backup set plus a persistent undo ledger instead of spraying unlimited `.bak` files.
- **Preset verification contract (Apr 2026)**: when presets/settings/runtime bridges are touched, the change is not considered safe until all of the following agree:
  - authored source tree: `presets/visualizer_modes`
  - generated shipped tree: `release/main_mc.dist/presets/visualizer_modes*`
  - defaults snapshot artifacts
  - runtime creator/apply bridge (`rendering/spotify_widget_creators.py`, `rendering/widget_manager.py`)
  - any known roaming `%APPDATA%` drift called out in `Current_Plan.md`
  Hard git reverts do not automatically restore generated release artifacts or live roaming settings to the same point as source code.
- **Preset feel policy (Apr 2026)**: rigid synthetic preset-feel baselines are retired for normal visualizer work. Validate authored preset feel with current curated JSON plus real UI/runtime behavior, and keep automated coverage structural unless a future migration explicitly needs a short-lived temporary authored-feel fence again.
- **Audio block size policy refresh**: Technical controls add a 128-sample option alongside Auto/256/512/1024. PyAudioWPatch now respects the preferred block size (tries it first, then 128→256→512→1024 fallbacks) and logs the negotiated block vs preferred, while the sounddevice backend logs its chosen block size as well. This closes the gap where PyAudio ignored user input and makes telemetry actionable for the remaining CPU/latency metrics task.
- **Anti-drift contract (8b)**: `_apply_adaptive_normalization()` uses tiered decay (0.82/0.90/0.94) and a 1.20 ceiling so `_running_peak` cannot stay elevated for more than ~1–2 seconds without sustained peaks supporting it. Dynamic floor EMA (`_raw_bass_avg`) decay alpha is forced ≥3× rise alpha with a hard ceiling of `base_noise_floor × 2.5`. `reset_floor_state()` also resets `_running_peak` to 0.5 on mode switch / preset reload. These prevent the long-term reactivity degradation that previously flattened energy bands across all visualizer modes during sustained loud passages.
- 2026‑03‑12 audit: all curated preset JSONs under `presets/visualizer_modes/` validated to include the required `<mode>_{manual_floor,dynamic_floor,adaptive_sensitivity,sensitivity,audio_block_size,dynamic_range_enabled}` keys plus `mode`, stored **only** inside `snapshot.widgets.spotify_visualizer`. Any future curated edits must be run through `tools/visualizer_preset_repair.py` (or the batch helper) to preserve the lean single-block structure.
- Normal SCR / onefile stable extraction now relies on a shipped manifest in `presets/visualizer_modes_manifest.json`. `core/visualizer_preset_manifest.py` removes stale shipped curated preset files from frozen extraction trees before curated presets load, while preserving obvious user-save paths such as `preset_*_custom.json` and avoiding mutation of repo/script trees.
- Manifest/source-tree contract refinement (Apr 2026): the shipped manifest remains the cleanup contract for frozen extraction trees, but source-tree-aware operations must reconcile it against the actual curated preset tree. Freshly authored shipped presets missing from the manifest should be auto-accepted during replacement/import workflows, and stale manifest-only paths missing from the source tree should be ignored instead of hard-failing those workflows. `Replace Visualizers` must then rewrite the target manifest from that reconciled shipped-tree view so future frozen sync/cleanup does not immediately drift back to stale metadata.
- The Settings About tab now exposes `Replace Visualizers`, which replaces the shipped curated preset tree from packaged assets in frozen SCR/MC builds while remaining a deliberate no-op in script mode so repo trees are never mutated by accident.
- Blob shaper authored energy nodes now support bound directional arrow metadata (`dir_x`, `dir_y`, `dir_len`) so live energy routing can push the authored reaction limit inward or outward at the same node location. The resting-state intent is base-shape at idle with energy driving toward the reaction limit; user-facing visual validation remains tracked in `Current_Plan.md`.
- Blob shaper angular convention (Apr 2026): authoring uses `0.0 = top`, `0.25 = right`, `0.5 = bottom`, `0.75 = left`. Runtime shaper profile sampling and energy routing must use that same convention; if runtime falls back to the shader's natural `0 = right` orientation, shaped blobs render sideways relative to the GUI.
- Blob shaper ring authoring/runtime contract: runtime ring mode is one authored contour plus a derived thickness band, not separately persisted inner/outer contour data. The editor preview now follows that same contract, and duplicate-angle legacy ring nodes collapse toward the outer contour while explicit `1.0 -> 0.0` wrap aliases must remain non-destructive to avoid seam spikes.
- Blob shaper persistence contract (Apr 2026): directional energy-node metadata must survive all non-visual persistence seams that are supposed to be lossless, including `WidgetsTab.build_visualizer_preset_payload()`, curated preset parsing, SST export/import, and main-preset custom-backup save/restore. These tests should stay shape-preserving rather than re-normalizing authored node direction data away.
- Blob shaper resting-shape fidelity (Apr 2026): when the shaper is enabled and drive is effectively at rest, authored contours should own the silhouette. Constant/reactive wobble must drop to zero at paused/idle shaper drive instead of warping the base shape away from the editor preview.
- Blob shaper canvas contract (Apr 2026): runtime energy routing treats reaction-canvas nodes as authoritative because they define how live energy should pull toward or away from the reaction limit. Base-canvas or untagged energy nodes are legacy fallback only, used when no reaction-canvas routing exists in older presets/settings payloads.
- Blob authored-settings consolidation contract (Apr 2026): the separate `Technical` bucket remains first-class, but the authored Blob surface is now intentionally leaner. Canonical authored Blob controls are `blob_pulse`, `blob_pulse_release_ms`, `blob_reactive_deformation`, `blob_constant_wobble`, `blob_reactive_wobble`, `blob_stretch`, glow/color controls, ghost controls, and Blob Shaper fields. Retired authored Blob keys (`blob_pulse_cap`, `blob_stage_gain`, `blob_core_scale`, `blob_core_floor_bias`, `blob_stage_bias`, `blob_stage2_release_ms`, `blob_stage3_release_ms`, `blob_stretch_tendency`, `blob_stretch_inner`, `blob_stretch_outer`) must not persist in live settings or curated/save/export payloads.
- Visualizer runtime-wiring contract (Apr 2026): a control is not considered live unless it survives the full canonical path (`UI/save/load -> normalization -> settings model -> widget creator/runtime apply`). Direct config-apply coverage alone is insufficient; this was the root cause of Blob controls appearing wired in editor-only paths while remaining dead in the real runtime path.
- GL array-uniform contract (Apr 2026): any visualizer shader uniform declared as an array must be queried from OpenGL with the `name[0]` lookup token, not the bare array name. `widgets/spotify_bars_gl_overlay.py` is the canonical live uniform-manifest seam, and new renderer-side array uniforms must be added there as well as to the per-mode renderer manifest or runtime uploads can silently collapse back to default/fallback visuals even while Python-side tests still pass.
- Blob ring render contract (Apr 2026): ring mode may derive its wall from `abs(signed_distance) - thickness`, but outer glow/ghost occupancy must still distinguish the hollow center from the real exterior. The ring hole must remain hollow; do not let glow or ghost branches reuse the filled signed distance in a way that repaints the center.
- Blob shaper release contract (Apr 2026): shaped Blob uses asymmetric contour pursuit. Travel toward new reaction targets can be comparatively quick, but the return toward base must be noticeably slower and smoother than normal Blob so authored directional energy reads as weighted deformation instead of snap-back flicker. This slower release belongs to the shaper solver path only; do not globally soften normal Blob pulse/release behavior.
- Blob shaper live-drive contract (Apr 2026): runtime applies a moderate-energy gain before the shaper deadzone/easing so ordinary musical energy can visibly move authored shapes without reintroducing the old “always parked on reaction” rest behavior. The paused/idle rest deadzone remains authoritative.
- Blob shaper continuity contract (Apr 2026): routed signed shaper energy must stay continuous across neighboring authored ownership regions. Runtime should preserve the dominant local direction without hard winner-take-all sign cuts, and inward/outward target selection must blend smoothly around zero drive instead of branching sharply.
- Blob shaper motion contract (Apr 2026): Idle Motion and Audio Motion remain live with the shaper enabled, but the authored body contour keeps priority. The current preferred implementation is a solved contour path: a tiny low-frequency residual is added to the solved authored contour before SDF evaluation, and the shader renders that single contour for fill/ring/dark band/edge/outline/glow instead of applying detached post-SDF shell offsets. If the solved-profile residual still fails to feel organic enough, the next fallback is a spring-lattice contour solver.
- Blob shaper drive-source contract (Apr 2026): Blob Shaper directional deformation must not be driven from the intentionally calmer whole-body live bands used to keep the blob body from exploding. Runtime now feeds shaper routing from the more expressive stage/support path, via dedicated shaper-drive uniforms, so authored directional reactions can answer real music while body-size motion stays separately tunable.
- Blob shaper routing smoothness contract (Apr 2026): authored energy nodes should deform coherent silhouette regions, not a few harsh sectors. Runtime routing therefore uses broadened/smoothed angular weight fields, shader-side linear sampling for those routing weights, and calmer shaper-active wobble scaling so authored reaction contours read as an organic pull instead of Catmull-induced blocky flicker.
- Blob pulse scalar-body contract (Apr 2026): `widgets.spotify_visualizer.blob_pulse` is the shader-side master for body-size growth. When `blob_pulse = 0`, direct bass lift, bass-squared lift, breath lift, rest contraction, and staged core-growth sizing must all resolve to zero. `blob_pulse_cap` remains a separate live-band/event ceiling and `blob_pulse_release_ms` remains a release-shaping control, but neither should leave whole-body size motion active when `blob_pulse` itself is zero.
- Oscilloscope visual gain is now surfaced as `osc_line_amplitude`. Runtime accepts the legacy `osc_sensitivity` key for backward compatibility, but all new presets/defaults/docs must emit `osc_line_amplitude`, and the GLSL uniform has been renamed to `u_line_amplitude` to match.
- **6-line ceiling contract (Apr 2026)**: Sine Wave and Oscilloscope modes now support up to 6 authored lines (previously 3). All layers (settings model/defaults, UI/binding, runtime bridge, renderer/math, curated presets, repair tool, and tests) have been updated to handle lines 4-6 with full customization parity (color, glow color, travel, shift, ghost enabled). Line count sliders clamp to 6, shaders accept uniforms for lines 4-6, and the repair tool automatically fills in line 4-6 defaults when migrating 3-line presets.
- Repair workflow:
1. `tools/visualizer_preset_repair.py` (GUI or `--repair-all` / `--audit-curated` CLI) loads JSON/SST snapshots, migrates+filters keys, and rewrites a **single** `snapshot.widgets.spotify_visualizer` block (top-level `widgets.spotify_visualizer` + `snapshot.custom_preset_backup` are no longer emitted). Each run writes `.bak*` backups and supports per-session undo in the GUI.
2. The integrated batch path (`Repair All Presets Found` button / CLI flag) walks `presets/visualizer_modes/**` automatically so repo-wide schema changes are one click/command instead of bespoke scripts, while audit mode flags duplicate prefixes and stale payload shapes before shipping.
  3. Repair backfill now enforces mandatory per-mode visual safety keys for oscilloscope/sine-wave glow + primary line colours so repaired presets cannot silently disable glow rendering.
  4. Regression coverage lives in `tests/test_visualizer_settings_plumbing.py::TestVisualizerPresetRepair`, asserting blob stretch bias → inner/outer conversion, sine card adaptation derivation, and that repaired payloads stay lean.

- Oscilloscope/sine swatch persistence contract: loading settings must sync both stored `_osc/_sine_*_color` attributes and corresponding `ColorSwatchButton` widget state; save fallbacks for glow toggles default to enabled when controls are absent to avoid accidental glow disable.
- Oscilloscope/sine glow contract: `*_glow_intensity` is the primary visible glow-strength control, and `*_glow_reactivity` is a separate scalar controlling how strongly glow responds to energy bands when reactive glow is enabled. Legacy `*_glow_size` values are treated as backward-compatible fallback sources for reactivity during load/migration.
- Preset JSON authoring requirements: include either a `snapshot.widgets.spotify_visualizer` block or top-level `widgets.spotify_visualizer`. Minimal `{"settings": {…}}` presets are auto-wrapped by the repair tool before shipping.
- Snapshot override safety contract: generic SST/profile exports must **not** alter curated visualizer preset slots. Runtime only ingests snapshot-style visualizer overrides from `visualizer_mode_overrides/*.json` when payloads explicitly declare `visualizer_preset_override=true`, matching `visualizer_preset_mode`, and integer `preset_index`. Script mode resolves those folders from the repo tree; frozen SCR and MC builds share the ProgramData override tree instead of splitting overrides by install.
- Runtime preset-cycle interaction contract (Mar 2026): in Ctrl/hard-exit interaction mode, clicking **Middle Mouse** over the Spotify visualizer cycles to the next preset for the active mode; clicking **Mouse 4 / XButton1 / BackButton** cycles to the previous preset. Input routing is hit-tested to the visualizer geometry only (`display_input` → `InputHandler.route_widget_click`), then delegated to `SpotifyVisualizerWidget.handle_mouse_button()`, which calls `WidgetManager.cycle_visualizer_preset()` (settings-backed, non-UI) and forces `_reset_visualizer_state(clear_overlay=False, replay_cached=False)` so no stale bars/ghost/sim state survives between preset swaps.
- Runtime preset-cycle persistence contract (Apr 2026): live preset application must happen immediately in memory and on the live widget, but disk persistence may be coalesced briefly after runtime cycling so repeated preset taps do not stall the render thread on synchronous JSON writes. Deferring the save must never change which preset/config is live, and stale deferred saves must no-op if a newer preset cycle superseded them.
- Runtime Custom-slot preservation contract (Apr 2026): runtime cycling must honor the same Custom snapshot/restore rule as the settings UI. Leaving `Custom` snapshots the live mode-owned payload into `visualizer_custom_presets`; returning to `Custom` restores that cached payload instead of reusing the last curated preset payload. The only intentional overwrite path for `Custom` remains the explicit `Move To Custom` workflow.
- WidgetManager refresh + preset cycling now guarantee that `apply_spotify_vis_model_config()` forwards curated `bar_fill_color` / `bar_border_color` (and opacity) back into `SpotifyVisualizerWidget.apply_vis_mode_config()`, so `_cached_vis_kwargs` is updated immediately and rainbow presets never inherit Mono’s black bars (and vice versa).
- **Spectrum floor naming contract**: `spectrum_profile_floor` is a visual shape-floor parameter (profile minimum) and is distinct from technical `manual_floor` (DSP noise-floor baseline). **Curated note**: the Spectrum "Cake" preset is intentionally exempt from global bar-count swaps to preserve its authored look; document any future exceptions in Index + Visualizer_Setting_Guide before touching curated JSON.

## Architecture Overview
- Engine orchestrates sources → queue → display → transitions.
- DisplayWidget is the fullscreen presenter; transitions are created per-settings.
- ThreadManager provides IO and compute pools; all business threading goes through it.
- ResourceManager tracks Qt objects for deterministic cleanup; includes QPixmap/QImage pooling to reduce GC pressure.
- Overlay startup cadence now has an explicit display-side source of truth in `rendering/overlay_startup_policy.py`. `rendering/display_overlays.py` and `rendering/widget_manager.py` must derive primary-wave and Spotify secondary-stage startup delays from that shared policy rather than carrying separate startup-delay constants.
- Shared overlay fade shape still comes from `widgets/shadow_utils.py::ShadowFadeProfile`. Startup timing policy may reference that shared fade duration, but fade shape/easing should stay centralized there so normal widgets and visualizer card fade-in remain coordinated by design.
- Reddit helper lifecycle is explicitly split by ownership context:
  - SCR/secure-desktop contexts queue work only
  - MC builds do not bootstrap the helper at all and keep using direct URL opening
  - user-session runtime bootstrap lives in `core/windows/reddit_helper_runtime.py`
  - session-scoped helper launches now work even against the installed helper binary, using `--owner-pid` + idle-exit plus an explicit shutdown request on graceful app close
  - persistent HKCU-Run helper behavior is reserved for the installed SCR watcher path when runtime explicitly requests persistence
- Media retained-display lifecycle now has a shared runtime seam in `widgets/media/runtime_state.py`. Session loss must be split into retained metadata/artwork, live-session acquisition, playback/reactivity gating, and provider fallback/rebinding rather than collapsed into one “hide the card” branch.
- `widgets/media/display_update.py` is the canonical retained-display policy: if live session data disappears but a retained snapshot exists, the media card stays visible, metadata/artwork stay cached, and downstream consumers receive a paused/non-reactive state instead of a hide signal.
- Media-dependent satellite widgets now share `widgets/media/dependent_visibility.py` for anchor-driven visibility decisions. Volume/mute-style widgets should derive “hide vs fade/show vs defer while anchor is not yet wired” from that helper instead of carrying separate ad hoc anchor-sync logic.
- Media artwork decode/paint must preserve source aspect semantics. `widgets/media_widget.py::_decode_artwork_pixmap()` is the canonical decode seam (reader auto-transform + normalized pixmap DPR), and `widgets/media/artwork_layout.py` owns the artwork-box layout rule so normal square album art stays square while wide Spotify video-frame thumbnails use a square cover crop instead of stretching or letterboxing.
- Runtime provider fallback must stay settings-backed. `rendering/widget_manager.py` owns the shared provider-runtime rebinding path for the media card and dependent widgets, and runtime auto-fallback must persist through that same settings source of truth instead of inventing a parallel runtime-only provider choice.
- SettingsManager provides dot-notation access, persisted to a JSON snapshot under
  `%APPDATA%/SRPSS/settings_v2.json` (or `%APPDATA%/SRPSS_MC/` for MC). Legacy
  QSettings profiles are migrated once at startup and future writes stay in
  the JSON store so backups and profile copies are simple file operations. The
  backing store (`core/settings/json_store.py`) performs atomic load/save with
  metadata (`version`, `profile`, `migrated_from`, timestamps) and treats
  structured roots (`widgets`, `transitions`, `custom_preset_backup`) as nested
  documents while exposing the dotted-key API expected by the rest of the app.
  Refer to `Docs/Historical_Bugs.md` for dated postmortems of fixed regressions (symptoms, failed attempts, final fix, regression coverage) so future work avoids regressing past issues.
  - Case A: Primary covered + hard_exit → Exit immediately
  - Case B: Primary covered + Ctrl held → Exit immediately
  - Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground
- System-agnostic: Uses `QGuiApplication.primaryScreen()` for detection, not screen index assumptions.

## Developer Feature Gate (SRPSS_ENABLE_DEV)

**Purpose**: Hide experimental, broken, or API-dependent features from end users while keeping code intact for future restoration or development.

**Environment Variable**: `SRPSS_ENABLE_DEV`
- **Default**: `false` (features disabled)
- **Enable**: Set to `true` to activate gated features
- **Usage**: `$env:SRPSS_ENABLE_DEV='true'; python main.py`

**Currently Gated Features**:
1. **Imgur Widget** (`widgets/imgur/`)
   - **Reason**: Imgur's modern website is JavaScript-rendered; BeautifulSoup scraping cannot extract proper gallery URLs with title slugs (e.g., `https://imgur.com/gallery/watching-8ayb0WE`). Only ID-only URLs can be extracted (e.g., `https://imgur.com/gallery/8ayb0WE`), which result in 404 errors or incorrect redirects.
   - **Gate Location**: `rendering/widget_manager.py` line ~1783
   - **Future**: May be restored if Imgur reopens their API or if Selenium/Playwright implementation is added for JS rendering.
   - **Alternative**: Consider Unsplash, Pexels, or Flickr as replacement image sources (all have free APIs or scrapable HTML).
2. **Starfield Visualizer** (`widgets/spotify_visualizer/shaders/starfield.frag`)
   - **Reason**: Experimental shader mode, not yet production-ready. Visual quality and performance still being tuned.
   - **Gate Location**: `ui/tabs/widgets_tab_media.py` — visualizer type combo only shows "Starfield" when dev flag is set.
   - **Future**: Ungated once visual quality and performance are validated.

**Implementation Pattern**:
```python
import os
dev_features_enabled = os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'

if dev_features_enabled:
    # Create experimental widget
    widget = ExperimentalWidgetFactory.create(...)
```

**Guidelines for Adding Gated Features**:
- Use `SRPSS_ENABLE_DEV` for features that are broken, experimental, or require external APIs that may be unavailable
- Document the reason for gating in this spec
- Keep code intact rather than removing it (allows future restoration)
- Do NOT expose gated features in settings UI or documentation unless dev mode is enabled
- Test that features are properly hidden when gate is disabled

## Visualizer Mode Dev Gates (-devblob, -devgoo)

**Purpose**: Gate entire visualizer modes behind CLI flags during active development. Unlike `SRPSS_ENABLE_DEV` (env var for broken/API-dependent features), these are lightweight CLI switches for modes under parallel development.

**CLI Flags** (passed alongside other args like `--debug`):
- `-devblob` — Enables Blob visualizer mode (shaped + unshaped)
- `-devgoo` — Enables Goo visualizer mode (reactive liquid, new)
- **Without either flag, neither mode appears in UI, preset swaps, or shader compilation.**

**Usage**: `python main.py --debug -devblob` or `python main.py --debug -devblob -devgoo`

**Implementation**:
- `core/dev_gates.py` — reads flags from `sys.argv`, exposes `is_blob_enabled()`, `is_goo_enabled()`, `force_gate()` for tests
- `core/settings/visualizer_mode_registry.py` — `_GATED_MODES` maps mode_id → gate function; `_active_descriptors()` filters; `is_mode_active()` for runtime checks
- `widgets/spotify_visualizer/shaders/__init__.py` — `_active_shader_files()` skips gated modes' shaders
- `widgets/spotify_bars_gl_overlay.py` — `set_state()` validates mode via `is_mode_active()`, falls back to default
- `main.py` — flags are in the filtered-args set so they don't interfere with screensaver mode parsing

**Key design rules**:
- Settings/model fields always exist in code (no conditional imports) — only UI visibility and runtime mode selection are gated
- `VISUALIZER_MODE_IDS` includes ALL modes (for settings persistence and tooling)
- `iter_visualizer_mode_descriptors()` returns only ACTIVE modes (drives combo, preset sliders, rainbow)
- Tests call `force_gate(blob=True)` / `force_gate(goo=True)` to enable gates without CLI flags

## Deployment
- **SRPSS.scr** / **SRPSS.exe**: Main screensaver build
- **SRPSS_MC.exe**: Manual Controller variant
- **Inno Setup installer**: `scripts/SRPSS_Installer.iss`
- **Build scripts**: PyInstaller and Nuitka options
- **Defender heuristic mitigation**: Windows Defender may flag the SCR as `Trojan:Win32/Wacatac.B!m` without proper PE version metadata. `scripts/build_nuitka.ps1` forwards `APP_VERSION`, `APP_COMPANY`, `APP_DESCRIPTION`, and `APP_NAME` into Nuitka's `--product-version`, `--file-version`, `--company-name`, `--file-description`, and `--product-name` flags. If heuristics flare up, first confirm those fields are emitted before changing binaries. `-KeepExe` / `-SkipScrRename` exist for experiments only.

## Runtime Variants
- Normal screensaver build:
  - Entry: `main.py`, deployed as `SRPSS.scr` / `SRPSS.exe`.
  - Script/debug launches support `--fresh`, which clears the resolved runtime log folder before `setup_logging()` attaches handlers. `worker_*.log` files are intentionally preserved because active worker handles can hang deletion.
  - Uses the `ShittyRandomPhotoScreenSaver/Screensaver` profile name for legacy migration only; the canonical runtime store is `%APPDATA%/SRPSS/settings_v2.json`.
  - Reddit-link opening from secure desktop is queue-based only: Winlogon / SYSTEM runs must persist ProgramData queue entries and exit, without relying on direct browser launch or graceful cleanup callbacks.
  - The Reddit helper watcher is intentionally singleton-scoped per user session. `helpers/reddit_helper_worker.py` acquires a named watcher mutex before watch mode so duplicate launches exit immediately instead of piling up persistent helpers behind stale heartbeat/launch races.
- Manual Controller (MC) build:
  - Entry: `main_mc.py`, deployed as `SRPSS_Media_Center.exe` (Nuitka onedir) or legacy `SRPSS MC.exe` (PyInstaller onefile).
  - Uses the same organization but stores settings in `%APPDATA%/SRPSS_MC/settings_v2.json`, keeping MC configuration isolated from the normal screensaver profile. Detection now includes the renamed executable stems (`srpss_media_center.exe`) so MC settings stay isolated regardless of the build artifact name and JSON directory.
  - At startup, forces `input.hard_exit=True` in the MC profile so mouse movement/clicks do not exit unless the user explicitly relaxes this in MC settings.
  - `SetThreadExecutionState()` call removed to reduce Defender heuristics; MC runs like any other fullscreen app and relies on Windows power management.
  - MC builds keep their fullscreen DisplayWidget windows out of the taskbar/Alt+Tab list by applying `Qt.Tool` (mirroring the historical behaviour) while a guarded toggle (`rendering.display_widget.MC_USE_SPLASH_FLAGS`) allows splash-style flags when we need to experiment. A dedicated regression test (`tests/test_mc_window_flags.py`) pins this behaviour so any deviation (e.g., accidental SplashScreen flip) is caught immediately.
  - MC packaging defaults to a Nuitka onedir bundle so Defender sees a single EXE plus DLL folder; PyInstaller script (`scripts/build_mc.ps1`) remains as fallback. Nuitka bundle is the primary path referenced by `scripts/SRPSS_MediaCenter_Installer.iss`.

## Image Pipeline
1) Queue selects next `ImageMetadata`.
2) Prefetcher decodes next N images to `QImage` on IO threads and stores in `ImageCache`.
3) On image change, engine loads via cache:
   - If cached `QPixmap` exists: use directly.
   - If cached `QImage`: convert to `QPixmap` on UI thread.
   - Else: fall back to direct `QPixmap(path)` load.
4) DisplayWidget processes to screen size (DPR-aware) via `ImageProcessor`.
5) Transition (GL or CPU) presents old→new.
6) After display, schedule next prefetch.

Optional UI warmup: after a prefetch batch, convert the first cached `QImage` to `QPixmap` on the UI thread to reduce later conversion spikes.

Optional compute pre-scale: after prefetch, a compute-pool task may scale the first cached `QImage` to the primary display size and store it under a `"path|scaled:WxH"` cache key. This is a safe, removable optimization to reduce per-frame scaling cost without visual changes.

## RSS Image Source Architecture

The RSS system is split into focused modules under `sources/rss/`:

- **constants.py**: Feed URLs, priorities, rate limits, cache settings (single source of truth).
- **cache.py** (`RSSCache`): Disk cache with ResourceManager integration, startup loading, LRU eviction, image header validation.
- **parser.py** (`RSSParser`): Stateless feed parsing — detects RSS/Atom vs Flickr JSON vs Reddit JSON, extracts image URLs and metadata into `ParsedEntry` objects. No network I/O.
- **downloader.py** (`RSSDownloader`): All network I/O — RSS fetch (feedparser), JSON fetch (requests), image download with atomic write (temp→rename). Domain-based rate limiting, Reddit rate limiter coordination, shutdown-aware with interruptible waits. **As of v2.75, every downloaded asset is probed with `QImageReader` and rejected if either dimension < 1920×1080, preventing low-res Flickr items from ever hitting cache/prefetch.**
- **health.py** (`FeedHealthTracker`): Persistent feed health tracking with exponential backoff, auto-reset after 24h.
- **coordinator.py** (`RSSCoordinator`): State machine (IDLE→LOADING→LOADED→ERROR), dynamic download budget (target 50 total images), orchestrates cache+parser+downloader+health. Provides `load_async()` (ThreadManager IO pool) and `load_sync()` APIs.

**Key design decisions:**
- No `time.sleep()` in coordinator or parser — interruptible waits live only in downloader.
- Dynamic budget: `new_needed = max(0, TARGET_TOTAL_IMAGES - cached_count)`, distributed across feeds with per-feed cap of 3. **If total usable wallpapers after the main loop < `MIN_WALLPAPER_REFRESH_TARGET` (11), the coordinator immediately tops up using trusted high-res feeds (Bing/NASA) with an elevated `FALLBACK_MAX_PER_FEED_DOWNLOAD` budget, guaranteeing a minimum viable pool without issuing extra feed scans.**
- Sequential single-threaded feed processing — no locks needed for rate limiting state.
- `sources/rss_source.py` retained as thin facade re-exporting constants and wrapping `RSSCoordinator` for backward compatibility.

## Caching and Prefetch
- `ImageCache`: LRU with RLock, stores `QImage` or `QPixmap`, memory-bound by `max_memory_mb` and `max_items`.
- `ImagePrefetcher`: uses ThreadManager IO pool to decode file paths into `QImage`, tracks inflight under lock, and populates cache.
- Look-ahead: `ImageQueue.peek_many(n)` used to determine upcoming assets.
- Skip policy: when a transition is active, prefetch defers to avoid thrash; skipped requests are logged for pacing diagnostics.

## Transitions
- GL and CPU variants for Crossfade, Slide, Wipe, Block Puzzle Flip; GL-only variant for Blinds (`GLBlindsTransition`) when hardware acceleration is enabled. Diffuse retains a CPU-based effect (`DiffuseTransition`) as the authoritative fallback, while a compositor-backed GLSL Diffuse shader now exists for the `Rectangle`, `Membrane`, `Lines`, `Diamonds`, and `Amorph` shapes when routed via `GLCompositorDiffuseTransition`.
- Compositor-backed controllers (`GLCompositorCrossfadeTransition`, `GLCompositorSlideTransition`, `GLCompositorWipeTransition`, `GLCompositorBlockFlipTransition`, `GLCompositorBlindsTransition`, `GLCompositorDiffuseTransition`) delegate rendering to a single `GLCompositorWidget` per display instead of per-transition `QOpenGLWidget` overlays.
- Additional **GL-only, compositor-backed transitions** are implemented as first-class types:
  - **3D Block Spins** (`GLCompositorBlockSpinTransition`) – GL-only single-slab 3D spin rendered by the compositor: a single thin depth-tested box mesh fills the viewport and flips from the old image (front face) to the new image (back face) with neutral glass edges and specular highlights. Spin axis is controlled by direction (LEFT/RIGHT spin around the Y axis, UP/DOWN spin around the X axis) via a shared card-flip shader (`u_axisMode`, `u_angle`, `u_specDir`); legacy Block Puzzle grid settings are no longer used.
  - **Ripple (legacy: Rain Drops)** (`GLCompositorRainDropsTransition`) – radial ripple effect rendered entirely in GLSL, with a diffuse-region fallback path. Feb 2026 shader fix: the additive ring highlight multiplies by `(1.0 - newMix)` so once a pixel is fully blended the halo contribution drops to zero, eliminating the late brightness spike that appeared when 2+ ripples overlapped at T=1.0. Diagnostics: enable `SRPSS_VIZ_DIAGNOSTICS` + `[PERF] [GL COMPOSITOR]` to confirm multi-ripple blends now terminate at true destination brightness.
  - **Warp Dissolve** (`WarpState` + `GLCompositorWarpTransition`) – shared vortex-style dissolve where the old and new images participate in a single whirlpool that intensifies mid-transition and then unwhirls back to the final frame.
  - **Claw Marks / Shooting Stars** – a GLSL Shooting Stars variant for Claw Marks was implemented and evaluated and has now been removed from the active transition pool. Its claws shader path is hard-disabled in the compositor so it cannot be used even if compiled; any legacy requests for this effect are mapped to a safe Crossfade-style fallback instead of a dedicated Claw transition.
- DisplayWidget injects the shared ResourceManager into every transition. Legacy GL overlays are created through `overlay_manager.get_or_create_overlay` so lifecycle is centralized, while compositor-backed transitions render exclusively through `GLCompositorWidget`.
- GL overlays remain persistent and pre-warmed via `overlay_manager.prepare_gl_overlay` / `DisplayWidget._prewarm_gl_contexts` to avoid first-use flicker on legacy GL paths; compositor-backed transitions reuse the same per-display compositor widget and never create additional GL surfaces.
- **Transitions tab alignment (Feb 2026)**: every checkbox/slider row now goes through `_aligned_row()` so labels lock to the shared gutter and we never double-add layouts. This refactor cleared the `QLayout::addChildLayout` spam and codifies the shared advanced-bucket alignment guidance for non-visualizer tabs (Diffuse/Particle/Burn/BlockFlip rows now all follow the helper).
- Compositor pre-upload helpers (`GLCompositorWidget._prepare_*_textures`) now include wipe transitions, matching the shader_dispatch contract so `start_wipe` no longer raises `AttributeError` when `_pre_upload_textures()` is invoked.
- DisplayWidget now runs a per-transition warmup pass before the first animation of each GL compositor transition. This pass calls `GLCompositorWidget.warm_transition_resources(...)`, which ensures the GLSL pipeline is initialized, shader programs are compiled via `GLProgramCache`, and both the generic pixmaps **and** transition-specific state/texture preparations (BlockFlip grids, BlockSpin slab textures, Particle buffers, etc.) are uploaded through `GLTextureManager`. Warmed transition types are tracked per DisplayWidget instance so subsequent runs skip the expensive preflight.
- Diffuse shapes: `Rectangle`, `Membrane`, `Lines`, `Diamonds`, `Amorph`. Block size is clamped (min 4px) and shared between CPU and GL paths and enforced by the Transitions tab UI. The CPU fallback always performs a block-based dissolve; non-Rectangle shapes are implemented only in the GLSL compositor path.
- Durations: a global `transitions.duration_ms` provides the baseline duration for all transition types, while `transitions.durations["<Type>"]` (e.g. `"Slide"`, `"Wipe"`, `"Diffuse"`, `"Block Puzzle Flip"`, `"Blinds"`, `"3D Block Spins"`, `"Rain Drops"`, `"Warp Dissolve"`) stores optional per-type overrides. The Transitions tab slider is bound to the active type and persists its value into `durations` while keeping `duration_ms` up to date for legacy consumers. Legacy settings for "Shuffle" are mapped to Crossfade for back-compat.

### Transition implementation matrix (v1.2 status)

The table below lists all transitions. All are GL-only, running on the compositor via GLSL shaders. Software (QPainter-only) transition classes have been removed; QPainter fallback renderers in `gl_transition_renderer.py` provide session-scoped demotion on shader failure.

| Transition         | GLSL shader path            | QPainter fallback | Notes |
|--------------------|-----------------------------|-------------------|-------|
| Crossfade          | fullscreen quad              | Yes               | Port complete; perf tuning tracked via `[PERF] [GL COMPOSITOR] Crossfade` metrics. |
| Slide              | fullscreen quad              | Yes               | Port complete; per-transition perf tuning (dt_max spikes on some sizes) still open. |
| Wipe               | mask shader                  | Yes               | GLSL Wipe path implemented; remaining work is primarily perf/QA and parity checks. |
| Diffuse            | 5 shapes                     | Yes (region)      | GLSL Diffuse with Rectangle/Membrane/Lines/Diamonds/Amorph shapes. |
| Block Puzzle Flip  | blockflip shader             | Yes (region)      | Directional, centre-biased block wave. |
| Blinds             | blinds shader                | Yes (region)      | GL-only compositor path. |
| 3D Block Spins     | card-flip shader             | Yes (crossfade)   | 6 directions (L/R/U/D + diagonal TL-BR/TR-BL via Rodrigues rotation). |
| Ripple             | ripple shader                | Yes (crossfade)   | Configurable ripple count (1-8, default 3); multiple concentric ripples. |
| Warp Dissolve      | vortex shader                | Yes (bands)       | Shader path tuned; further adjustments are perf/visual polish only. |
| Crumble            | voronoi shader               | No                | GL-only Voronoi crack pattern with physics-based piece falling. Configurable piece count (4-64), crack complexity. |
| Particle           | particle shader              | No                | GL-only particle transition: Directional (8 dirs + random), Swirl (3 build orders), Converge. 3D ball shading, trails, texture mapping, wobble. |
| Burn               | burn shader                  | No                | GL-only, 4 directions (L→R, R→L, T→B, B→T). Jaggedness, glow, char width, smoke/ash toggles. Default 8000ms. |
| Shuffle            | Retired                      | Retired           | Legacy Shuffle fully removed; any future Shuffle would be a new GLSL design. |

- Per-transition pool membership:
  - `transitions.pool` is a map of transition type name → bool controlling whether a type participates in engine random rotation and C-key cycling (explicit selection is always allowed regardless of this flag).
- GL-only gating:
  - GL-only types (Blinds, 3D Block Spins, Ripple, Warp Dissolve, Crumble, Particle, Burn) are only instantiated on the compositor/GL paths when `display.hw_accel=True` and the compositor is available.
  - When hardware acceleration is disabled, the Transitions tab disables these types and the engine maps any request for them to a safe CPU fallback (currently Crossfade).
  - All transitions are now GL-only and run on top of the compositor via GLSL shaders. On any shader initialisation or runtime failure, the engine disables shader usage for the remainder of the session and demotes all subsequent requests to QPainter compositor fallback renderers (crossfade-style). Software-only (CPU) transition classes have been removed; the compositor is the sole rendering path. Per-transition "try GLSL and silently fall back" paths are avoided; demotion is explicit and session-scoped.
- Non-repeating random selection:
  - Engine sets `transitions.random_choice` per rotation, filtered through `transitions.pool` and GL-only gating.
  - Slide: cardinal-only directions; stored as `transitions.slide.direction` and last as `transitions.slide.last_direction` (legacy fallback maintained).
  - Wipe: includes diagonals; stored as `transitions.wipe.direction` and last as `transitions.wipe.last_direction` (legacy fallback maintained).
  - UI 'Random direction' respected when `random_always` is false.
  - Manual selection or hotkey cycling must clear `transitions.random_choice` cache immediately so the chosen type instantiates next rotation.
  - Random selection is disabled when `transitions.random_always=False`; engine then respects explicit `transitions.type` from settings/GUI.

## Performance Notes
- All decoding happens off UI thread.
- DPR-aware pre-scaling reduces GL upload pressure.
- Image prefetch + prescale pipeline:
  - `ImagePrefetcher` decodes upcoming images into `QImage` on IO threads and stores them in `ImageCache`.
  - A COMPUTE-pool prescale step uses `ThreadManager.submit_compute_task` to scale the first upcoming image to distinct display sizes and caches them under `"path|scaled:WxH"` keys as `QImage`.
  - When displaying, `ScreensaverEngine._load_image_task` prefers these prescaled entries and promotes them to `QPixmap` on the UI thread, writing the pixmaps back into `ImageCache` so subsequent loads avoid repeated conversions.
- **Display FPS detection & fallback:** Each `GLCompositorWidget` now caches the first successful refresh-rate detection per display and reuses it after settings dialog hops or restarts. When Qt/GPU fails to report a Hz value, the compositor, display setup helpers, `DisplayWidget`, and adaptive timer all fall back to an uncapped 240 Hz target instead of 60 Hz so high-refresh panels never get stuck at 60 fps.
- Image processing pipeline (v1.2 and beyond):  
  - Fully wire prefetch + prescale so large 4K–8K images are decoded on IO threads and pre-scaled for distinct display sizes using COMPUTE threads, caching under "path|scaled:WxH" keys in `ImageCache` while keeping QPixmap creation on the UI thread.  
  - Design an optional further-async `ImageProcessor` path that can move safe crop/composite steps to COMPUTE threads while preserving current quality and semantics.  
    - Operate on `QImage` frames sourced from `ImageCache` (including prescaled `"path|scaled:WxH"` entries) on the COMPUTE pool; avoid `QPixmap` work off the GUI thread.
    - Promote the final cropped/composited `QImage` to `QPixmap` (or GL textures) **once per image per display** on the UI thread only, then reuse that pixmap/texture across transitions.
    - Add tests that compare this async QImage-based crop/composite output against `ImageProcessor.process_image(...)` pixel-for-pixel for representative modes (FILL/FIT/SHRINK) and resolutions (1080p/4K) to lock in visual equivalence.
  - Keep DPR-aware sizing and pixmap seeding in [DisplayWidget](cci:2://file:///f:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_widget.py:100:0-4382:16) so base frames are always ready before transitions start.
-- Profiling keys:
  - `GL_SLIDE_PREPAINT`
  - `GL_WIPE_PREPAINT`
  - `GL_WIPE_REPAINT_FRAME`
  - `[PERF] [GL COMPOSITOR] <Name> metrics` summary lines for **all** compositor-driven transitions (Slide, Wipe, Block Puzzle Flip, Ripple/Raindrops, Warp Dissolve, Block Spins, legacy GLSL Claws when enabled). Each line reports `duration`, `frames`, `avg_fps`, `dt_min`, `dt_max`, and compositor `size` and is emitted once per transition completion by `GLCompositorWidget` when PERF metrics are enabled.
 - Telemetry counters record transition type requested vs. instantiated, cache hits/misses, and transition skips while in progress.
 - Animation timing for **all** transitions (CPU and GL/compositor) is centralised through per-display `AnimationManager` instances driven by a `PreciseTimer`-backed loop; transitions use `[PERF] [ANIM]` metrics (duration, frames, avg_fps, dt_min/max, fps_target) as the canonical timing signal rather than ad-hoc timers.
- Spotify visualizer tick instrumentation logs dt spikes with the currently-running transition name, elapsed time, and idle age, allowing correlation between transition warmup gaps and audio/UI timer starvation. `_reset_visualizer_state()` is now the single reset surface for cold starts, settings applies, and double-click mode switches; it replays the last applied settings model, clears GPU/cache state, and restarts fade detection so all modes start identical to a cold launch. `logs/screensaver_perf.log` remains the canonical perf source; set `SRPSS_PERF_METRICS=1` to enable the aggregated summary emitted on exit.
- Frame timing workload regression tests rely on the `FrameTimingHarness` (see `tests/test_frame_timing_workload.py`). The harness provisions a fresh `GLCompositorWidget` and `AnimationManager`, wraps `compositor.update` to sample dt, temporarily silences noisy GL loggers, and performs deterministic teardown. Because the harness is sensitive to GL state, the entire module is marked `@pytest.mark.frame_timing_isolated` and run via `python pytest.py tests/test_frame_timing_workload.py -vv` after the primary suite so dt_max telemetry stays meaningful without affecting faster CI groups.
 - Background work (IO/COMPUTE) is routed through the central `ThreadManager` pools wherever possible; any remaining direct `QThread`/`QTimer` usages outside `core.threading.manager` are explicitly logged fallbacks (e.g. widget-level weather fetch when ThreadManager is unavailable) rather than parallel primary paths.
 - Console debug output uses a suppressing stream handler that groups consecutive INFO/DEBUG lines from the same logger into `[N Suppressed: CHECK LOG...]` summaries while leaving file logs untouched. The high-visibility `Initializing Screensaver Engine 🚦🚦🚦🚦🚦` banner is exempt from grouping so it always appears once per run, and when multiple `[PERF]` lines with `avg_fps=...` are collapsed, the summary includes the trailing `avg_fps` token to keep grouped telemetry readable in the console.
 - A central PERF switch is configured in `core.logging.logger`: `PERF_METRICS_ENABLED` defaults to false and can be overridden by the `SRPSS_PERF_METRICS` environment variable (`0/false/off/no` vs `1/true/on/yes`). In frozen builds, it is finalised at startup by a small `<exe-stem>.perf.cfg` file written next to the executable by the build scripts (`scripts/build_nuitka*.ps1`). GUI/retail builds typically write `0` to disable PERF metrics, while console/debug builds write `1` to keep full telemetry enabled.
 - Optional CPU profiling for both RUN and CONFIG modes is gated by the `SRPSS_PROFILE_CPU` environment variable. When enabled, `main.py` wraps the selected entrypoint (`run_screensaver` or `run_config`) in a `cProfile.Profile` run and writes `.pstats` snapshots into the active log directory returned by `core.logging.logger.get_log_dir()`, so developers can inspect hotspots and feed them back into the roadmap.
 - When PERF metrics are enabled, `GLCompositorWidget` can optionally draw a small on-screen FPS/debug overlay on top of compositor frames (e.g. Slide/Wipe) to visualise real frame pacing during development. This overlay is disabled implicitly when PERF metrics are turned off so retail builds incur no additional HUD cost.
 - On `initializeGL`, `GLCompositorWidget` logs the OpenGL adapter vendor/renderer/version and disables the shader pipeline for the session when a clearly software GL implementation is detected (for example, GDI Generic, Microsoft Basic Render Driver, llvmpipe). In this case, compositor QPainter-based transitions and CPU fallbacks remain active, but shader-backed paths are not used on that stack.
 - If spikes persist, further expand compute-pool pre-scale-to-screen (including DPR-specific variants) as a future enhancement.

## UI Component References
- **Circle Checkbox**: `ui/components/circle_checkbox.py` provides a custom checkbox widget with a circular appearance, used throughout the settings UI.

## Build & Automation Tools
- `tools/regen_qrc.py`: Single entry point for regenerating `ui/resources/icons_rc.py` from `ui/resources/icons.qrc`. Wraps `pyside6-rcc` with a `python -m PySide6.scripts.rcc` fallback and surfaces a modal "Success!" dialog so UI contributors know resources refreshed before reloading stylesheets.
- `tools/build_nuitka.ps1`: Build script for Nuitka, used to create standalone executables for the screensaver and manual controller.

## Settings
- Timer-only rendering: DisplayWidget initialises `_target_fps = 0` (sentinel); `configure_refresh_rate_sync` detects the panel Hz and writes the resolved value. If the compositor reads 0 it forces late re-detection from the screen object. GL surfaces request `swapInterval=0`. No adaptive ladders, no vsync, no user-facing refresh-sync toggle.
- `display.hw_accel`: bool
- `display.mode`: fill|fit|shrink
- `display.use_lanczos`: bool - Use Lanczos resampling for image scaling (higher quality, slightly more CPU intensive)
- `display.sharpen_downscale`: bool - Apply sharpening when downscaling images
- `input.hard_exit`: bool (when true, mouse movement/clicks do not exit; only ESC/Q and hotkeys remain active). Additionally, while the Ctrl key is held, `DisplayWidget` temporarily suppresses mouse-move and left-click exit even when `input.hard_exit` is false, allowing interaction with widgets without persisting a hard-exit setting change. MC builds default this setting to true at startup in their own QSettings profile, while the normal screensaver build respects the saved value.
- `input.halo_shape`: str - Cursor halo shape: circle, ring, crosshair, diamond, dot, cursor_light (light pointer), cursor_dark (dark pointer). Default is cursor_light.
- `transitions.type`: Crossfade|Slide|Wipe|Diffuse|Block Puzzle Flip|Blinds|"3D Block Spins"|"Ripple"|"Warp Dissolve"|Crumble|Particle|Burn (legacy `Shuffle` values are mapped to `Crossfade` for back-compat and are no longer exposed in the UI)
- `transitions.random_always`: bool
- `transitions.random_choice`: str (current random pick for this rotation; cleared on manual type changes)
- `transitions.slide.direction`, `transitions.slide.last_direction` (legacy flat keys maintained).
- `transitions.wipe.direction`, `transitions.wipe.last_direction` (legacy flat keys maintained).
- `transitions.duration_ms`: int global default transition duration in milliseconds.
- `transitions.durations`: mapping of transition type name → per-type duration in milliseconds (e.g. `{"Crossfade": 1300, "Slide": 2000, "Ripple": 7000, ...}`) used by the Transitions tab and `DisplayWidget` to make durations independent per transition. Legacy settings keys using the label `"Rain Drops"` are migrated to `"Ripple"` at load time.
- `transitions.diffuse.block_size` (int, clamped to a 4–256px range) and `transitions.diffuse.shape` (`Rectangle`|`Membrane`). The same block-size was historically reused by Shuffle to size its GL grid; Shuffle is now retired but the configuration key is kept for back-compat.
- `transitions.burn.direction` (`Left to Right`|`Right to Left`|`Top to Bottom`|`Bottom to Top`|`Random`; **Center Out removed**), `transitions.burn.jaggedness` (float 0–1), `transitions.burn.glow_intensity` (float 0–1), `transitions.burn.char_width` (float 0–1), `transitions.burn.smoke_enabled` (bool), `transitions.burn.smoke_density` (float 0–1), `transitions.burn.ash_enabled` (bool), `transitions.burn.ash_density` (float 0–1).
- `transitions.pool`: mapping of transition type name → bool controlling whether a type participates in engine random rotation and C-key cycling (explicit selection is always allowed regardless of this flag).
- Global/general settings presets (`core/settings/presets.py`, settings-dialog Presets tab) are disabled by default unless `SRPSS_ENABLE_GENERAL_PRESETS=1`. When disabled, effective behavior is Custom-only. This gate is strictly separate from visualizer/media presets.
- `widgets.spotify_visualizer.preset_<mode>`: per-mode visualizer preset index. Script mode loads curated JSON files from the repo `presets/visualizer_modes/<mode>/` tree. Frozen SCR and MC builds both load from the shared ProgramData curated tree so dual-install users are not split across separate preset worlds; packaged/bundled preset trees are replacement/bootstrap sources only. Curated payloads should be maintained with `tools/visualizer_preset_repair.py`, which mirrors runtime migration/filtering, preserves compact `snapshot.widgets.spotify_visualizer` payloads, and now explicitly promotes stale non-mirrored Spectrum `Bass / Low / Mid / Hi-Mid / Treble` families into `Bass / Low-Mid / Vocal / Hi-Mid / Treble` while preserving boundary drift. Filenames such as `preset_1_upstream.json` automatically map to index 0 and render as “Preset 1 (Upstream)” — all friendly names follow the `Preset N (Suffix)` convention so UI labels stay consistent regardless of payload `name`. Snapshot files with full settings dumps **still work**: the loader continues to parse both minimal curated payloads and entire SST exports, filtering them down to mode-specific keys (e.g., `sine_`, `blob_`, etc.) plus a small allowlist of shared visualizer fields so incompatible options are ignored instead of erroring. Custom always occupies the last slot, and the number of presets grows automatically if higher-numbered files exist.
- `widgets.spotify_visualizer.bubble_stream_reactivity`: slider controlling how aggressively the Bubble stream speed follows smoothed mid/high energy. UI/runtime now clamp to **0–200 %** (default 50 %). Values above 101 % enter an “overdrive” band that: (a) requires three consecutive frames over 101 % before engaging, (b) holds the boosted speed for 0.5 s before releasing even if energy dips, and (c) slowly bleeds back toward baseline unless energy stays above 101 %. Diagnostics emit `[SPOTIFY_VIS][BUBBLE][OVERDRIVE] state=enter/hold/release react=%.2f gate=%.2f` when `SRPSS_VIZ_DIAGNOSTICS=1`.
- `widgets.spotify_visualizer.sine_crawl_amount`: normalized (0.0–1.0) Crawl slider for sine mode. Crawl is a vocal-reactive positional drift that adds low-frequency horizontal motion to the fine dents on every sine line. Implementation details:
  - Energy shaping: playback must report `u_playing > 0.2`, then line 1 uses `0.65*mid + 0.35*high`, line 2 mixes toward `0.55*mid + 0.45*high`, and line 3 leans `0.60*high + 0.40*mid`, each raised to `pow(energy, 0.85)` before scaling by the slider.
  - Spatial/temporal profile: combines two sin bands per line (1.1–4.2x `nx`) with slow time bases (±0.35–0.8 * `u_time`) and density-aware spacing so Crawl reads as a deliberate ripple crawl instead of Micro Wobble’s sparkly dents.
  - Multi-line variation: line 2/3 blend the shared crawl foundation (`crawl1`) with phase- and energy-biased drifts so stacked cards do not mirror each other. Lines 4-6 follow similar patterns with progressive phase/energy offsets.
  - Diagnostics: when `SRPSS_VIZ_DIAGNOSTICS` is enabled, `SpotifyVisualizerWidget` emits `[SPOTIFY_VIS][SINE][CRAWL] slider/mid/high/drive/playing` every ~0.75 s so QA can confirm energy gating without recording a capture.
  - Defaults follow `Defaults_Guide.md` (0.25). UI clamps to 0–100 % with tooltips describing the motion; shader uniform `u_crawl_amount` is uploaded by `SpotifyBarsGLOverlay` each frame and covered by `tests/test_visualizer_overlay_kwargs.py`.

-### Visualizer drop-in preset workflow

- Loader: `core/settings/visualizer_presets.py` (modes: `spectrum`, `oscilloscope`, `sine_wave`, `blob`, `helix`, `starfield`, `bubble`). It boots with placeholder Preset 1–3 + Custom, then overlays curated JSON and optional snapshot drop-ins before exposing the final list via `get_presets()`.
- File locations:
  1. **Curated slots** – `presets/visualizer_modes/<mode>/preset_<n>_*.json`. Maintain with `python tools/visualizer_preset_repair.py --repair-all` (or `--audit-curated`) so payloads contain only the filtered `snapshot.widgets.spotify_visualizer` block plus metadata (`application`, `preset_index`, `name`, `description`). The tool mirrors runtime filtering using the same migration/filter helpers.
  2. **Snapshot/drop-in slots** – any SST export dropped in `/presets/*.json`. Loader inspects `snapshot.widgets.spotify_visualizer` (plus `custom_preset_backup`) and filters keys, allowing on-the-fly presets without touching curated files.
- Naming/indexing:
  - Filenames such as `preset_3_glow_burst.json` or explicit `{"preset_index": 2}` map to slot index (0-based). Friendly names auto-render as `Preset N (Suffix)` by extracting the suffix from the filename or payload `name`.
  - Slots auto-expand: if any curated/snapshot payload references Preset 5, `_build_presets_for_mode()` inserts placeholder indices so UI shows Presets 1–5 plus Custom.
  - `Custom` is always appended last, is never displaced, and exposes the Advanced bucket.
- Filtering:
  - Global allowlist (`GLOBAL_ALLOWED_KEYS`): `adaptive_sensitivity`, `audio_block_size`, `bar_border_color`, `bar_border_opacity`, `bar_count`, `bar_fill_color`, `dynamic_floor`, `dynamic_range_enabled`, `ghost_alpha`, `ghost_decay`, `ghosting_enabled`, `manual_floor`, `mode`, `monitor`, `rainbow_enabled`, `rainbow_per_bar`, `rainbow_speed`, `sensitivity`, `software_visualizer_enabled`.
  - Mode prefixes (`MODE_KEY_PREFIXES`): Spectrum `spectrum_`, Oscilloscope `osc_`, Sine `sine_`/`sinewave_`, Blob `blob_`, Helix `helix_`, Starfield `star_`/`nebula_`, Bubble `bubble_` (covers `bubble_gradient_direction` vs `bubble_specular_direction`, etc.). Keys outside these sets are dropped. Tests: `tests/test_visualizer_presets.py::test_all_curated_presets_have_unique_keys_and_filtered_settings` and SST round-trip coverage.
- Loading order:
  - Curated JSON applied first, snapshot overrides layered on top so QA can distribute ad-hoc Preset 8 payloads.
  - `_filter_settings_for_mode()` forcibly sets `mode` so payloads cannot switch visualizer modes.
  - Empty/invalid JSON logs `[VIS_PRESETS]` warnings without interrupting other presets.
- UI/Settings interplay:
  - `widgets.spotify_visualizer.preset_<mode>` stores the active slot index. Values clamp between 0 and `custom_index` so corrupted settings never crash the slider.
- `VisualizerPresetSlider` lists the friendly names, auto-hiding the Advanced container whenever a curated slot is active and surfacing it only for Custom. Track active preset validation and follow-up in `Current_Plan.md`.
- Advanced buckets follow the Always-Apply rule: hidden controls remain in force, and SST exports/imports preserve every key (including split gradient/specular directions) even when the UI is collapsed.
- `timing.interval`: int seconds (default 45). The Display tab now always loads this canonical 45 s value when the key is missing so UI defaults match `SettingsManager`. Regression test `tests/test_display_tab.py::TestDisplayTab::test_display_tab_default_values` guards this.
- `display.same_image_all_monitors`: bool
- Cache:
  - `cache.prefetch_ahead` (default 5)
  - `cache.max_items` (default 24)
  - `cache.max_memory_mb` (default 1024)
  - `cache.max_concurrent` (default 2)
 - Sources:
  - `sources.folders` (list[str]): image folder paths, surfaced in the Sources tab.
  - `sources.rss_feeds` (list[str]): RSS/JSON feed URLs; only feeds explicitly configured here are used by `RSSSource`.
  - `sources.rss_save_to_disk` (bool): when true, new RSS images are mirrored into `sources.rss_save_directory` in addition to the temp cache.
  - `sources.rss_save_directory` (str): absolute path for permanent RSS copies.
  - `sources.rss_rotating_cache_size` (int, default 20): max RSS images to keep between sessions; controls initial load cap.
  - `sources.rss_background_cap` (int, default 35): global cap on queued RSS/JSON images at runtime; enforced on initial load, async load, and background refresh. Increased from 30 to 35 (Feb 2026).
- `sources.spotify_visualizer.spectrum_single_piece`: bool (default **True** as of v2.75) — drives Spectrum “Single Piece Mode”, producing pillar-style bars by default to match the preferred UI look. Existing UI + widget wiring already honours the flag; only the default changed.
  - `sources.rss_refresh_minutes` (int, default 10): background RSS refresh interval in minutes, clamped to at least 1 minute.
  - `sources.rss_stale_minutes` (int, default 30): TTL for RSS images; dynamically adjusted based on transition interval (5-15 min). Stale entries are only removed when a refresh successfully adds replacements.
  - **RSS Rate Limiting** (Feb 2026): `RSSSource` implements domain-based rate limiting (15 requests/minute per domain) to prevent overwhelming any single source. Feed health is persisted to `%TEMP%/srpss_feed_health.json` across restarts, maintaining exponential backoff for failed feeds. Default feeds now include Flickr (7 feeds), Wikimedia (2 feeds), Bing, and NASA. **Reddit feeds removed from defaults** due to cross-process rate limit coordination issues (MC build + screensaver = separate `RedditRateLimiter` instances = unsafe). Users can manually add Reddit feeds; rate limiter remains active for user-added feeds.
 - Widgets:
  - `widgets.clock.*` (Clock 1): monitor ('ALL'|1|2|3), position, font, colour, timezone, background options, analogue-only controls (`show_numerals`, `analog_face_shadow`, and the new `analog_shadow_intense` toggle that doubles drop-shadow opacity/size for dramatic analogue lighting on large displays). **Visual Offset Alignment**: Analogue clocks without backgrounds use `_compute_analog_visual_offset()` to calculate precise offset from widget bounds to visual content (XII numeral or clock face edge), ensuring correct margin alignment with other widgets across all scenarios (with/without background, numerals, timezone).
  - `widgets.clock2.*`, `widgets.clock3.*` (Clock 2/3): same schema as Clock 1 with independent per-monitor/timezone configuration.
  - `widgets.weather.*`: monitor ('ALL'|1|2|3), position, font, colour, margin, optional iconography. **FR-5.2**: Weather widget - temperature, condition, location 
    - Open-Meteo provider integration (no API key required, free tier: 10k calls/day, 5k/hour, 600/min), with back-compat parsing for legacy OpenWeather-style JSON in tests/mocks
    - Background fetching and refresh timers run exclusively through ThreadManager-driven overlay timers (no raw QThread usage); failures fall back to cached data with retry timers also registered via the overlay timer helper.
    - 30-minute refresh interval with early 30-second refresh after startup to ensure fresh data
    - Dual cache: provider cache (`%TEMP%/screensaver_weather_cache.json`) + widget cache (`~/.srpss_last_weather.json`), both with 30-minute TTL
    - Day/night icon variants: auto-selected based on `is_day` field from Open-Meteo API
    - Monochrome icon mode: optional grayscale conversion on icon load (cached, zero paint overhead)
    - Font size hierarchy: location 100% (base), condition 80%, detail/forecast 50% of user setting
    - Detail metrics row: rain chance (from hourly[0]), humidity (from current or hourly[0]), wind speed

- **Atomic JSON snapshot** – The canonical store lives at `%APPDATA%/SRPSS/settings_v2.json` (or `%APPDATA%/SRPSS_MC/settings_v2.json`). `core/settings/json_store.py` maintains a flat in-memory map for all dotted keys, persists `{version, profile, metadata, snapshot}` documents atomically via `*.tmp` swap, and treats `widgets`, `transitions`, and `custom_preset_backup` as structured roots so large maps stay nested on disk.
- **Structured key helpers** – `SettingsManager` exposes transparent dotted access for structured roots. Calls like `get("widgets.clock.enabled")`, `set("transitions.Ripple.enabled", False)`, `contains(...)`, and `get_all_keys()` all operate on the nested JSON without flattening hacks, keeping presets/SST/import/export logic identical to the legacy QSettings APIs.
- **One-shot migration** – On first run without `settings_v2.json`, SettingsManager reads the legacy QSettings profile, normalizes via `_to_plain_value`, populates the JSON store, stamps metadata (`migrated_from`, `legacy_profile`, `migrated_at`), and writes a human-readable backup under `%APPDATA%/SRPSS/backups/qsettings_snapshot_YYYYMMDD_HHMMSS.json`. Subsequent runs skip QSettings entirely; deleting the JSON file forces a re-migration or a defaults reset when no registry data exists.
- **Preset backup parity** – `_save_custom_backup()` now captures nested sections (widgets, transitions, display, accessibility, sources) into a JSON-friendly payload kept under `custom_preset_backup`. `_restore_custom_backup()` replays that snapshot via dotted setters so Custom behaves identically between legacy and JSON stores, and MC adjustments operate directly on the nested `widgets` map.
- **Legacy display toggles ignored** – Import paths (SST, preset application, custom restore) drop `display.refresh_sync`, `display.refresh_adaptive`, `display.render_backend_mode`, and `display.hw_accel` keys so historical bundles cannot resurrect driver-vsync or software-backend toggles. Timer-only rendering remains authoritative regardless of imported payloads.
- **SST compatibility** – `export_to_sst()` mirrors the JSON snapshot (including structured sections) and tags the payload with `settings_version`. `import_from_sst()` and `preview_import_from_sst()` coerce values through `_coerce_import_value`, merge structured sections when requested, and remain tolerant of older `.sst` files by flattening their legacy layout into the new schema before writing. `widgets.spotify_visualizer` is normalized through `core/settings/visualizer_settings_snapshot.py` during export/import/preview so SST paths preserve per-mode rainbow state, canonical preset indices, and mode-owned technical keys.
  - `widgets.reddit.*`: Reddit overlay widget configuration (enabled flag, per-monitor selection via `monitor` ('ALL'|1|2|3), 9 position options (Top/Middle/Bottom × Left/Center/Right), subreddit slug, item limit (4-, 10-, or 20-item layouts for ultra-wide/large displays), font family/size, margin, text colour, optional background frame and border with opacity, background opacity). The widget fetches Reddit's unauthenticated JSON listing endpoints with a fixed candidate pool (up to 25 posts), then sorts all valid entries by `created_utc` so the newest posts appear at the top; each layout simply changes how many rows are rendered from that sorted list. The widget hides itself on fetch/parse failure and only responds to clicks in Ctrl-held / hard-exit interaction modes. Initial visibility is coordinated through the shared overlay fade-in system so Reddit, Weather and Media fade together per display.
  - `widgets.reddit2.*`: Second Reddit widget configuration (enabled flag, per-monitor selection via `monitor`, 9 position options, subreddit slug, item limit). Inherits all styling (font, colors, background, border, opacity) from `widgets.reddit.*` to allow showing two different subreddits simultaneously.
  - `widgets.imgur.*`: Imgur image gallery widget (enabled flag, per-monitor selection via `monitor`, 9 position options, tag selection from presets or custom, grid dimensions via `grid_rows`/`grid_columns` for NxM layout, layout mode (vertical/square/hybrid with dynamic aspect ratio), update interval, header visibility with optional border, image border settings). Uses web scraping with BeautifulSoup since Imgur API is closed to new registrations. Implements LRU disk cache (100MB max) with GIF-to-first-frame conversion, conservative rate limiting (24 req/10min with rolling window tracking), exponential backoff, 429 handling, concurrent downloads (4 at a time via ThreadManager IO pool), circular buffer image rotation (max 100 images), smooth fade transitions (300ms), high-DPI pixmap support, async cache loading to prevent UI blocking, cell pixmap caching to avoid re-scaling, click-to-open-in-browser functionality, and Shiboken validity guards on all UI-thread callbacks from background tasks. Paint-cached grid rendering follows minimal painting policy with widget-level and cell-level caching. Fade coordination via FadeCoordinator for synchronized startup with other widgets.
 - `widgets.shadows.*`: global drop-shadow configuration shared by all overlay widgets (enabled flag, colour, offset, blur radius, text/frame opacity multipliers). Individual widgets perform a two-stage startup animation: first a coordinated card opacity fade-in (driven by the overlay fade synchronizer), then a shadow fade where the drop shadow grows smoothly from transparent to its configured opacity using the same global duration/easing. Shadows are slightly enlarged/softened via a shared blur-radius multiplier so all widgets share a consistent halo.
 - Accessibility:
  - `accessibility.dimming.enabled` (bool, default false): enables compositor-based dimming via `GLCompositorWidget.set_dimming()`, rendered after the base image/transition but before overlay widgets.
  - `accessibility.dimming.opacity` (int, 10-90, default 50): opacity percentage (mapped to 0.0–1.0) for compositor dimming. `widgets/dimming_overlay.py` remains as a legacy/test/fallback widget.
  - `accessibility.pixel_shift.enabled` (bool, default false): enables periodic 1px shifts of all overlay widgets to prevent burn-in on older LCD displays.
  - `accessibility.pixel_shift.rate` (int, 1-5, default 1): number of shifts per minute. Widgets drift up to 4px in any direction then drift back. Shifting is deferred during transitions.
- Settings dialog:
  - Palette: app-owned dark theme without Windows accent bleed.
  - Geometry: 60%-of-screen, clamped geometry for the configuration window.
  - Outer shell: subtle forged rounded-border paint only. This is intentionally conservative and may retain tiny compositor-dependent caveats; do not trade acrylic/title-bar stability for stronger radius styling without fresh research and live runtime checks.

### Settings snapshots (SST) and About-tab import/export

- SettingsManager continues to use QSettings as the canonical runtime store for each profile (normal `Screensaver` build vs `Screensaver_MC` for the Manual Controller); no runtime behaviour is gated directly on external files.
- The About tab exposes "Export Settings…" and "Import Settings…" actions that read/write a JSON-formatted Single Source of Truth (SST) snapshot of the *current* QSettings profile. Screenshots and tests should treat these as human‑edited backups/restores, not as a second live config store.
- SST files contain a top-level object with `settings_version` (int), `application` (str, currently informational) and `snapshot` (mapping). The `snapshot` map mirrors the nested schema above: top-level `widgets` and `transitions` sections plus nested `display`, `timing`, `input`, `sources`, and any future sections represented by dotted keys.
- Import is merge‑by‑default: values from the snapshot overwrite the current profile where they overlap, but keys that do not exist in the snapshot are preserved. A full restore is therefore "Reset To Defaults" followed by "Import Settings…".

## Settings Type Safety
- Type-safe settings dataclass models in `core/settings/models.py` provide IDE autocompletion and runtime validation.
- Enums: `DisplayMode` (fill/fit/shrink), `TransitionType` (all transition types), `WidgetPosition` (9 positions).
- Core models: `DisplaySettings`, `TransitionSettings`, `InputSettings`, `CacheSettings`, `SourceSettings`.
- Widget models: `ShadowSettings`, `ClockWidgetSettings`, `WeatherWidgetSettings`, `MediaWidgetSettings`, `RedditWidgetSettings`.
- Container: `AppSettings` aggregates all settings sections with `from_settings(SettingsManager)` factory method.
- Each model has `to_dict()` for serialization back to flat keys.
- **22 unit tests** in `tests/test_settings_models.py`.

## Intense Shadows
- Optional "Intense Shadows" styling for all overlay widgets with dramatic visual effect.
- Multipliers in `widgets/shadow_utils.py`: blur 2.0x, opacity 1.8x, offset 1.5x.
- `BaseOverlayWidget.set_intense_shadow(bool)` method for all widgets.
- Clock widget has separate `analog_shadow_intense` and `digital_shadow_intense` options.
- Settings: `widgets.clock.digital_shadow_intense`, `widgets.weather.intense_shadow`, `widgets.media.intense_shadow`, `widgets.reddit.intense_shadow`.
- Applied via `WidgetManager` during widget creation.

## Thread Safety & Centralization
- All business logic threading goes via `ThreadManager` where available.
- Overlay widgets and engine-level timers (image rotation + background RSS refresh) must obtain timers via `ThreadManager.schedule_recurring`; the legacy raw `QTimer` fallback has been removed and widgets now log/abort startup when no manager is injected.
- UI updates only on the main thread (`run_on_ui_thread`).
- Simple locks (Lock/RLock) guard mutable state; no raw QThread or `ThreadPoolExecutor` in production code.
- **Shiboken validity guards**: All widget callbacks dispatched from background threads via `run_on_ui_thread()` must check `Shiboken.isValid(self)` before touching Qt objects, preventing crashes when widgets are destroyed during shutdown while deferred callbacks are still queued. All overlay widgets audited and guarded (Feb 2026).
- **Deferred lambda C++ deletion guards**: `QTimer.singleShot` lambdas that capture widget references must guard against the widget being destroyed before the timer fires. Pattern: wrap `widget.objectName()` in `try/except RuntimeError` at the top of the closure and bail out if the C++ object is deleted. Applied in `widget_manager.py` `_register_spotify_secondary_fade` closures (Mar 2026).
- Qt objects registered with `ResourceManager` where appropriate.

## OpenGL Overlay Lifecycle
- Persistent overlays per transition type for legacy GL paths (including Blinds and Diffuse), plus a single per-display `GLCompositorWidget` that renders the base image and compositor-backed transitions (Crossfade, Slide, Wipe, Block Puzzle Flip). Reuse prevents reallocation churn across both overlays and compositor surfaces.
- Warmup path (`DisplayWidget._prewarm_gl_contexts`) initializes core GL surfaces per monitor (per-transition overlays and/or compositor) and records per-stage telemetry.
- Warmup uses a dummy pixmap derived from the currently seeded frame (wallpaper snapshot or last image) so any first GL frames match existing content rather than a solid black buffer.
- Triple-buffer requests may downgrade to double-buffer when driver rejects configuration; log and surface downgrade reason through diagnostics overlay.
- Watchdog timers accompany each GL transition; timeout cancellation required once `transition_finish` fires to avoid thread leaks.
- Overlay Z-order is revalidated after each transition to ensure widgets (clock/weather/multi-clocks) remain visible across monitors.

### Widget Overlay Behaviour (canonical reference)

- Overlay widgets (clock/weather/media/Reddit/Spotify) extend `BaseOverlayWidget` (`widgets/base_overlay_widget.py`) which provides:
  - Common font/color/background/shadow/position management
  - Pixel shift support via `_pixel_shift_offset` and `apply_pixel_shift()`
  - Thread manager integration via `set_thread_manager()`
  - Size calculation helpers for stacking/collision detection
  - Widget-specific position enums (ClockPosition, WeatherPosition, MediaPosition, RedditPosition) support 9 positions: Top Left/Center/Right, Middle Left/Center/Right, Bottom Left/Center/Right
  - Position enums are stored separately from the base class `OverlayPosition` for type safety
  - **Lifecycle State Machine**: `WidgetLifecycleState` enum (CREATED→INITIALIZED→ACTIVE⇄HIDDEN→DESTROYED) with validated transitions via `is_valid_lifecycle_transition()`. Public methods `initialize()`, `activate()`, `deactivate()`, `cleanup()` drive state changes and invoke subclass hooks (`_initialize_impl`, `_activate_impl`, `_deactivate_impl`, `_cleanup_impl`). Thread-safe state access via `_lifecycle_lock`. ResourceManager integration for automatic resource cleanup. All 6 overlay widgets (Clock, Weather, Media, Reddit, SpotifyVisualizer, SpotifyVolume) implement lifecycle hooks while preserving backward-compatible `start()`/`stop()` methods.
- Overlay widgets follow the patterns defined in `Docs/10_WIDGET_GUIDELINES.md` for:
  - Card styling and typography.
  - Coordinated fade/shadow application via `ShadowFadeProfile` and the
    global `widgets.shadows.*` config.
  - Integration with `DisplayWidget._setup_widgets`,
    `DisplayWidget.request_overlay_fade_sync`,
    `DisplayWidget._ensure_overlay_stack`, and
    `transitions.overlay_manager.raise_overlay` so widgets stay above both the
    base image and any GL compositor/legacy overlays for the full duration of
    transitions.
  - Recurring overlay timers (clock/weather/media/Reddit) are created via `widgets.overlay_timers.create_overlay_timer`, which prefers `ThreadManager.schedule_recurring` with ResourceManager tracking and falls back to widget-local `QTimer` instances when no ThreadManager is attached. This keeps timer lifecycle unified with the rest of the engine.

`Docs/10_WIDGET_GUIDELINES.md` is the **canonical source of truth** for overlay
widget behaviour; this Spec only summarises the high-level contract.

### Spotify Visualizer Architecture (Mar 2026 split)

The monolithic `SpotifyVisualizerWidget` and `SpotifyBarsGLOverlay` have been decomposed:

- **Per-mode renderers** (`widgets/spotify_visualizer/renderers/`): 7 modules (spectrum, oscilloscope, sine_wave, blob, helix, starfield, bubble) each export `get_uniform_names()` and `upload_uniforms()`. Dispatched via `upload_mode_uniforms(mode, gl, u, state)` — only the active mode's uniforms are pushed, preventing cross-mode bleed.
- **Tick pipeline** (`widgets/spotify_visualizer/tick_pipeline.py`): Extracted `_on_tick()` (~415 lines) from the widget.
- **Mode transition** (`widgets/spotify_visualizer/mode_transition.py`): Extracted mode cycling, fade, teardown (~300 lines). `reset_visualizer_state()` is the single reset surface for cold starts, settings applies, and double-click switches.
- **Bubble simulation** (`widgets/spotify_visualizer/bubble_simulation.py`): CPU-side particle sim with per-bubble state, trail smear, swirl orbits.#### Responsive Bubble Behaviour (Mar 2026)

- Every detected beat now immediately promotes a handful of the largest unpromoted small bubbles (`promote_timer≈0.9s`, max 20% per beat) so bass runs always thicken the scene.
- Running averages use aggressive attack/decay constants (`dt*3` / `dt*6`) so deltas reset between hits even at 128-sample block sizes.
- Stream speed smoothing doubled on attack (`dt*28`) and decay (`dt*10`), eliminating the 80–120 ms lag previously associated with the COMPUTE dispatch cadence.
- Overdrive logging (`[SPOTIFY_VIS][BUBBLE][OVERDRIVE]`) remains for diagnostics; enabling `SRPSS_VIZ_DIAGNOSTICS=1` shows gate/energy factors when tuning.
- Coverage: `tests/test_bubble_reactivity.py` confirms beat promotion lifetime, decay, and quiet→loud transitions.
- **Result**: `spotify_visualizer_widget.py` 2407→1482 lines. `spotify_bars_gl_overlay.py` 2049→1518 lines.
- **Mode isolation**: `_reset_mode_state()` clears per-mode accumulators on switch. Non-active modes get their blob/osc state zeroed. No data bleeds between modes on double-click transitions. Oscilloscope/Sine mode resumes now require both a fresh engine generation and a fresh waveform generation after reset so Spectrum-state bars cannot reopen Osc on stale line data.

- **Per-mode rainbow resolution**: The authoritative rainbow state is mode-local. UI save/load writes `{mode}_rainbow_enabled` and `{mode}_rainbow_speed`; `SpotifyVisualizerSettings` now resolves rainbow from the active mode's keys with fallback to legacy global keys, and live double-click mode switches resync rainbow from persisted mode+preset config instead of reusing stale cached kwargs from the previous mode.

- **AGC & Energy Source Architecture (Mar 2026)**:
  - **Per-mode AGC controls**: Each visualizer mode now persists `dynamic_floor`, `manual_floor`, `dynamic_range_enabled`, `agc_strength`, `input_gain`, and the transient-mix controls as the living schema. `energy_boost` is derived at runtime from `dynamic_range_enabled`, and `use_raw_energy` is no longer part of persisted settings/defaults/preset authoring.
  - **Energy source selection**: `config_applier.py` and `tick_pipeline.py` can still read `widget._use_raw_energy` as a runtime/debug seam. Normal persisted settings paths keep all modes on `get_energy_bands()` (smoothed post-AGC); pre-AGC is not a first-class authored setting anymore.
  - **Bubble hybrid pulse system**: Post-AGC energy is near-constant (~0.5–0.8), which made the old absolute-threshold pulse system permanently peg `gated_energy=1.0`. Fixed with a **hybrid delta + sustained floor**: (1) delta component = deviation above a slow-tracking running average × sensitivity → sharp transient punch for kicks/snares; (2) sustained component = absolute energy through a perceptual curve with high knee → moderate baseline during loud passages. `max(delta, sustained)` ensures both kick transients AND sustained choruses drive visible pulse without degrading over long songs.
  - **UI contract**: The Technical section is now metadata-driven in `technical_controls.py` via `_BASE_CONTROL_DEFS`, `_BUCKET_DEFS`, and `_control_defs_for_mode()`. Visible AGC UI exposes `AGC Strength` and `Input Gain` per mode; retired compat controls `energy_boost` and `use_raw_energy` are no longer part of the live settings UI/schema.

- **Transient Bus Architecture (Mar 2026)**:
  - **Dual-path design**: `transient_bus.py` produces per-frame `TransientEnergyBands` (bass/mid/high transient + onset detection). Fed post-noise-floor, pre-AGC band energies from `bar_computation.fft_to_bars`.
  - **Event micro-scheduler**: `TransientEventScheduler` lives in `transient_bus.py` as an always-on consumer layer over the onset ring buffer. It exposes `consume_next(event_type, max_age_s)` for consume-once flows and `peek_latest(event_type, max_age_s)` for non-destructive multi-consumer reactions. Per-type debounce defaults are kick 90 ms, snare 120 ms, vocal_swell 200 ms. `beat_engine.get_event_scheduler()` is the canonical access point.
  - **Global transient_clamp**: Applied in `bar_computation.py` immediately after the transient bus update. All three channels (`_transient_bass`, `_transient_mid`, `_transient_high`) are clamped to `worker._transient_clamp` (default 1.5, range 0–3) before any downstream consumer reads them. This is mode-agnostic.
  - **Downstream consumers**: (1) Spectrum kick express lane reads `_transient_bass` for bass-bar boost while the lane-aware routing model preserves per-band collapse; (2) Bubble dispatch in `tick_pipeline.py` mixes `_transient_bass × _transient_pulse_gain` into pulse bass and consumes scheduler kick events for single-fire promotions; (3) Blob peeks scheduler kick/snare events through `build_gpu_push_extra_kwargs()` / `SpotifyBarsGLOverlay.set_state()`, then folds transient + scheduler help into one processed live-band source used by both the live blob uniforms and retained ghost peak memory; (4) Sine/Osc keep using transient energy for continuous width/glow behavior but also peek recent scheduler kick/snare events for beat-confirmed line accents, and Sine heartbeat can fall back to recent scheduler kicks when the frame-local onset flag is already gone.
  - **Thread safety**: Transient bus update runs on the audio worker thread inside `fft_to_bars`. Widget attributes (`_transient_bass` etc.) are written atomically (float assignment). Bubble dispatch reads them on UI thread — single-writer/single-reader, no lock needed.
  - **Per-mode transient mix sliders (§2.3)**: Each mode has a contextual transient mix slider controlling how much transient energy feeds its primary reaction channel. Settings path: `default_settings → models.py (dataclass + from_settings/from_mapping/to_dict + resolvers) → widget cache (_build_technical_cache) → widget attrs (_apply_technical_config_for_mode) → overlay propagation → renderer/tick consumer`. Preset repair via `_MANDATORY_MODE_TRANSIENT_MIX` in `visualizer_preset_repair.py`.
  - **Storage rule (Mar 2026 metadata move)**: Generic Technical controls still store ordinary per-mode keys as `widgets.spotify_visualizer.<mode>_<key>`, but the already mode-named transient mix keys (`spectrum_lane_transient_mix`, `bubble_transient_mix_vocal`, etc.) remain direct keys and must not be re-prefixed into doubled forms like `spectrum_spectrum_lane_transient_mix`.
    - **Spectrum**: `spectrum_lane_transient_mix` (0–1, default 0.65) — scales transient bass contribution to kick express lane boost in `bar_computation.py`.
    - **Bubble**: `bubble_transient_mix_bass` (0–1, default 0.75) + `bubble_transient_mix_vocal` (0–1, default 0.25) — weight transient bass/mid mixing into pulse energy in `tick_pipeline.py`.
    - **Blob**: `blob_transient_mix_bass` (0–1, default 0.5) + `blob_transient_mix_vocal` (0–1, default 0.35) — blend transient bass/mid into raw energy bands in GL overlay's blob smoothing loop.
    - **Sine wave**: `sine_wave_transient_width_mix` (0–1, default 0.4) — now feeds a mode-local Sine beat-assist path in `renderers/sine_wave.py` that boosts width reaction/support cues without acting like a second full heartbeat source. Sine also derives a CPU-side `wave_effect_gate` so authored wave motion fades down in calm passages instead of making low-energy sections look busier than loud ones, and its renderer-local assist outputs use a short attack / slower release smoothing pass so confirmed hits stay readable without snapping back on the next frame.
    - **Oscilloscope**: `oscilloscope_transient_width_mix` (0–1, default 0.35) — modulates `u_sensitivity` uniform by `(1 + smoothed_bass × mix)` in `renderers/oscilloscope.py`.

- **Spectrum floor/drop policy**: Spectrum now prioritizes large, readable dips over constant micro-motion. Dynamic floor tracking is intentionally slower, micro-drops are frozen, large drops release faster, and adaptive normalization now yields more aggressively on real drop events so mirrored bars can collapse visibly without adding jitter.
- **Preset hygiene tool**: `tools/visualizer_preset_repair.py` is the official GUI for pruning curated preset JSON/SST payloads. It uses the same `_migrate_preset_settings()` + `_filter_settings_for_mode()` helpers as runtime, merges in live defaults from `core/settings/default_settings.py`, writes `.bak` backups, and offers per-session undo.

### Spotify Visualizer lifecycle & debugging checklist

Canonical reset/freshness behavior now lives in `Docs/Visualizer_Reset_Matrix.md`, and the consolidated visualizer documentation (architecture, signal contract, baseline tuning, per-mode reference, settings/UI, testing/validation) lives in `Docs/Visualizer_Reference.md`. Use those alongside the current tests and `Current_Plan.md` when rollout validation is still active.

#### Bubble gradient vs specular direction

- **Why**: Bubble presets historically tied the background gradient direction to the specular highlight vector, making it impossible to keep the highlight on one side while shading toward another. March 2026 decouple introduces `bubble_specular_direction` (advanced) and `bubble_gradient_direction` (normal bucket) as distinct settings.
- **Defaults**: `bubble_specular_direction="top_left"`, `bubble_gradient_direction="top"` live in `core/settings/default_settings.py`, mirrored in `SpotifyVisualizerSettings` and snapshot exports.
- **UI**: Bubble builder now shows a Gradient Direction combobox directly under Specular Direction (Settings → Widgets → Spotify Visualizer → Bubble). WidgetsTab load/save hydrates both controls so preset toggles and session restore keep custom vectors.
- **Rendering path**: `SpotifyVisualizerWidget.apply_vis_mode_config()` delegates to `config_applier`, which normalizes both directions and pushes them into `build_gpu_push_extra_kwargs()`. `SpotifyBarsGLOverlay.set_state()` now accepts both `bubble_specular_direction` and `bubble_gradient_direction`, mapping them to the new `u_gradient_dir` uniform in `bubble.frag` so gradient shading and specular offsets are fully independent.
- **Gradient semantics contract (Mar 2026)**: `bubble_gradient_direction` now means **brightest point location**. A shared helper in `core/settings/bubble_gradient_semantics.py` owns legacy-label migration, persisted `bubble_gradient_semantics_version`, and canonical label -> shader vector/mode mapping. `center_out` remains the historical radial behavior and `center_out_reverse` is the inverted radial variant.
- **Defaults / migration guard**: existing `widgets.spotify_visualizer` sections must not receive `bubble_gradient_semantics_version` via default-merging alone. That marker is meaningful migration state, so it should only be written by normalized/save paths after a real payload has been interpreted.
- **Presets / repair**: `tools/visualizer_preset_repair.py` keeps Bubble curated payloads aligned with current defaults/filtering, including `bubble_gradient_direction`, `bubble_gradient_semantics_version`, and `bubble_specular_direction`. Re-run repair/audit after modifying those defaults so commits always include the new key.

When the Spotify Beat Visualizer misbehaves (late wake, jittery startup, flat
bars, or popping), debug in this order:

1. **Primary wave vs staged visualizer startup**:
   - `rendering/widget_setup.py::compute_expected_overlays()` must *not* add
     `spotify_visualizer` to the primary expected-overlay set.
   - The Media card still belongs to the primary coordinated fade.
   - The visualizer must start through the Spotify secondary stage instead of
     the first overlay wave, or cold-start hot work leaks back into the first
     visible reactive window.
   - `rendering/display_overlays.py` must let the primary wave begin fading as
     soon as the compositor is ready. The deliberate startup delay belongs to
     the Spotify secondary wave, not to the primary overlay wave. If widgets
     feel like they are popping in instantly again, inspect those shared timing
     constants first.
2. **Secondary-stage registration path**:
   - `rendering/widget_manager.py` should register/wake Spotify secondary-stage
     participants.
   - `SpotifyVisualizerWidget` may self-register through
     `register_spotify_secondary_fade(...)` when that seam is exposed by the
     parent, so startup does not depend on a single brittle creator path.
3. **Playback/media seed before hot start**:
   - `SpotifyVisualizerWidget` startup owns the authoritative playback seed.
   - It should seed from the anchor Media widget and shared media cache, then
     request `refresh_playback_state()` if no snapshot exists yet.
   - The older create-time bridge in `rendering/spotify_widget_creators.py` is
     opportunistic only and must not be treated as sufficient cold-start truth.
4. **Delayed hot start + reveal gating**:
   - `_arm_staged_startup()` should hide the widget and defer heavy engine/timer
     work until `begin_spotify_secondary_stage()`.
   - `_begin_hot_start()` should start the engine calmly, then keep visible
     reveal pending until the first fresh frame and the minimum hidden warmup
     window have both been satisfied.
   - If the first fresh frame arrives before the minimum hidden warmup window
     expires, startup must schedule an exact ready-driven reveal attempt for
     that deadline instead of idling until the coarse fallback timer.
   - The guarded fallback is only for quiet/paused startup, not the normal
     reveal path for active playback.
   - Deferred startup wake must not immediately re-run the normal
     `engine.wake()` capture-restart path when staged hot start is already
     doing the reset/start work.
5. **Overlay prewarm before reveal**:
   - `rendering/display_image_ops.py::prewarm_spotify_visualizer_overlay()`
     plus `SpotifyBarsGLOverlay.prewarm_context()` should create the GL overlay
     and force context/shader bring-up before the visualizer becomes visible.
   - If shader compilation still lands in the first visible reactive seconds,
     inspect this seam first.
6. **Beat engine / smoothing / reset parity**:
   - `_SpotifyBeatEngine` still owns audio capture and bar generation.
   - `SpotifyVisualizerWidget._on_tick()` still owns smoothing and GPU push.
   - If startup remains worse than settings re-entry or mode-cycle refresh after
     staging/prewarm are correct, compare reset/generation/bar-count readiness
     against the mode-switch path before touching buffer or smoothing policy.
7. **GL overlay wiring and metrics**:
   - `DisplayWidget.push_spotify_visualizer_frame(...)` should only push once
     the widget is visible and the overlay is ready.
   - PERF logs (`[PERF] [SPOTIFY_VIS] Tick/Paint metrics`) and
     `[PERF] [GL COMPOSITOR]` summaries remain the canonical signals for
     confirming that frames are being produced and composited.

#### Blob authored surface (Apr 2026 cleanup)

- Sliders live in **Settings → Spotify Visualizer → Blob**.
- The authored surface now follows a leaner contract with real collapsible buckets rather than heading-only grouping:
  - Top-level bucket order: `Body`, `Appearance`, `Shaper`, `Layout`, `Glow`, `Advanced`, `Technical`
  - `Advanced` currently contains Blob-owned sub-buckets `Motion` and `Ghost`
  - Separate shared `Technical` bucket remains intact for expert/runtime tuning
- Canonical authored Blob controls are now:
  - `Body Response` (`blob_pulse`) as the master whole-body size/pulse gate
  - `Body Release` (`blob_pulse_release_ms`) as the authored release control
  - `Idle Edge Motion` + `Audio Edge Motion`
  - single outward `Stretch` (`blob_stretch`)
  - color / glow / ghost / shaper controls
- Blob mode-ownership contract: non-shaped Blob owns the generic freeform motion/deformation surface (`Shape Reactivity`, `Idle Edge Motion`, `Audio Edge Motion`, `Stretch`). Blob Shaper owns authored contour motion through its own shaper-only controls and must not consume or persist those generic freeform motion knobs as hidden runtime tuning.
- Blob pocket-routing contract: non-shaped Blob now also owns a runtime-only concurrent deformation-pocket layer so fresh rapid hits can claim local reaction pockets without waiting for slower whole-body decay to clear. Blob Shaper must not read, persist, or react to that pocket state.
- Blob Shaper mode hides generic `Stretch` + `Shape Reactivity` because the authored shaper owns silhouette deformation.
- Blob Shaper mode also hides generic `Idle Edge Motion` + `Audio Edge Motion`; shaped contour drift now belongs to `blob_shaper_idle_motion` and `blob_shaper_audio_motion` instead of the unshaped wobble system.
- The authored base contour is now the authoritative rest silhouette. `blob_shaper_base_strength` is no longer allowed to flatten the base contour toward a circle; the UI pins that legacy setting to full strength and no longer presents it as a meaningful authored knob.
- `Reactive Glow = off` hides/disables the dependent authored glow rows (`Glow Color`, `Glow Intensity`, `Glow Reactivity`, `Glow Drive`, `Glow Max Size`) so the UI does not leave dead controls visible.
- Ghost enable remains on the normal aligned-row pattern (`Ghosting:` label + standard circle checkbox); Blob must not use one-off checkbox spacing that breaks the visualizer row contract.
- Retired authored Blob keys such as `blob_pulse_cap`, `blob_stage_gain`, `blob_core_scale`, `blob_core_floor_bias`, `blob_stage_bias`, `blob_stage2_release_ms`, `blob_stage3_release_ms`, `blob_stretch_tendency`, `blob_stretch_inner`, and `blob_stretch_outer` are no longer part of the canonical authored settings surface or curated preset payloads.
- Runtime contract:
  - `blob_pulse` gates both scalar body-pulse radius math and staged body-size growth
  - `blob_stretch` derives the shader's internal outward stretch uniforms (`tendency = outer`, `inner = 0`)
  - Non-shaped Blob runtime also maintains a small fixed set of transient local deformation pockets (`widgets/spotify_visualizer/blob_pockets.py`) that are claimed/reused immediately on current-frame kick/snare/high hits; this layer is runtime-only in the current contract and does not add new persisted authored settings
  - Blob Shaper deformation uses its own routed energy field and should not require separate generic stretch controls to reach the authored reaction silhouette
  - Blob Shaper runtime now treats the authored base profile as the fixed rest contour and uses `blob_shaper_react_strength` only to scale how much of the authored reaction limit is reachable
  - Blob Shaper contour residual motion is shaper-owned: `blob_shaper_idle_motion` + `blob_shaper_audio_motion` control the solved-profile residual life, while unshaped `blob_constant_wobble` + `blob_reactive_wobble` remain exclusive to the freeform Blob path
  - Blob Shaper drive uses a stronger reach curve than the old over-damped blend, but still retains a rest deadzone so idle/noise energy does not smear the silhouette away from the authored base shape
  - Blob Shaper routed-energy contract: per-angle deformation must not average opposing signed contributors back toward zero just because multiple authored nodes overlap locally. Runtime now resolves that field by taking the strongest local signed contributor, which better matches the authored "this node/arrow owns this local reaction" mental model and keeps live music from collapsing back toward the base silhouette during mixed-band passages.
  - Blob Shaper drive bands now prefer stage-driving inputs more aggressively than body-size bands do, so authored reaction travel remains reachable under ordinary music instead of only under extreme hits.
  - Blob Shaper authored-direction contract: arrow direction is interpreted relative to the authored local base->reaction delta, not only absolute inward/outward from center. An inward arrow on an inward-authored dip therefore means "drive toward the inward reaction dip", while the opposite arrow means "drive away from that dip".
  - Blob Shaper affordance contract: the draggable tip must read like an arrow, because drag direction is a live authored input, not a decorative marker
  - Blob Shaper opposite-direction contract: inward-directed live response is not a full mirrored version of an outward-authored reaction delta. Runtime must derive a safe opposite-side target so inward arrows cannot drive the contour through the center and create wedge/collapse artifacts.
  - Blob Shaper profile-sampling contract: authored profile interpolation may be smooth, but it must stay bounded by the local authored neighborhood. Runtime must not let Catmull-Rom overshoot create impossible inward sectors or spike cuts between adjacent authored nodes.
  - Blob Shaper distance/energy contract: larger authored base->reaction gaps must require more sustained local energy to fully reach and hold, while max energy can still reach the authored limit.
  - Blob Shaper contour-solver contract: shaped runtime motion is now solved upstream into one CPU-side contour profile (`u_blob_runtime_profile`) rather than invented after the fact with fragment-space shell offsets. Filled/ring/glow/outline rendering must all derive from that same solved contour so the shell cannot peel away into dark gaps, radial lines, or seam wedges.
  - Blob Shaper motion contract: when playback is active, shaped blobs keep subtle contour-space life through the solved profile itself rather than a detached shell wobble. At idle/paused rest, the authored base shape remains stable.
  - Blob Shaper kick-overshoot contract: strong positive shaper drive may push a little beyond the authored reaction contour, but only slightly and only outward. The reaction shape is a soft maximum for musical feel, not a hard wall.

#### Sine Heartbeat (Reworked Mar 5 2026)

- CPU-side beat detection rewritten: uses spike ratio (`fast_bass / avg_bass`) with a low gate (1.6×), separate trigger/decay logic (no decay on trigger frame), 600ms decay via `_heartbeat_intensity` envelope pushed as `u_heartbeat_intensity`.
- Shader `heartbeat_amp_params()` now yields +120% amplitude boost (up from +55%) with a cap of 0.78 (up from 0.58). Envelope is shaped with cubic ease-out (`pulse * pulse * (3.0 - 2.0 * pulse)`) for organic swell.
- Slider `u_heartbeat` (0–1) controls the effect strength. At 0, heartbeat is fully disabled (multiplier = 1.0, cap = 0.48).

#### Sine Density (Reworked Mar 5 2026)

- `compute_density_cycles()` uses a two-piece linear mapping: slider 0.25–1.0 → 0.65–3.0 cycles (gentle), slider 1.0–3.0 → 3.0–8.5 cycles (steep). This ensures perceptually balanced changes across the full slider range.
- `density_thickness_factor()` tapers line width at high cycle counts (above 4.0 cycles) to prevent lines from blobbing together. Applied as a multiplier to `line_width` in `eval_line()`.

#### Sine Displacement (Reworked Mar 5 2026)

- Replaced chaotic `randomDirection`-based jitter with smooth bass-reactive offset system. Uses a slowly rotating angle (`u_time * 0.17`) to vary offset direction over time.
- `disp_phase_offset` shifts sine wave phase; `disp_y_offset` shifts vertical position. Both scale with `displacement_slider` and `bass_vector`.
- Per-line variation: Line 1 = 1.0× phase / 1.0× Y, Line 2 = 0.85× phase / 1.10× Y, Line 3 = 1.15× phase / 1.25× Y. Lines 4-6 follow similar progressive offset patterns.
- All old displacement variables (`rand_line*`, `phase_jitter*`, `l*_drive`, `y_push*`, `y_scale`, `phase_scale`, `l23_*`) removed.

#### Blob Ghosting (Updated Mar 22 2026)

- Mar 5 root cause/fix still applies: shared ghost settings (`ghosting_enabled`, `ghost_alpha`, `peak_decay_per_sec`) had been assigned AFTER the blob-specific override in `set_state()`, silently overwriting blob values with spectrum defaults. Blob ghost controls remain isolated and live in the Advanced bucket.
- The current ghost path in code is still the retained-peak envelope model, but the important March 22 correction is that the live blob and retained ghost now share the same processed Blob live-band source before the ghost hold/decay step. That processed source includes Blob's transient mix plus scheduler kick/snare help, so the ghost is remembering the actual visible Blob silhouette rather than reconstructing from a weaker side path.
- The two failed March 22 experiments remain retired: delayed-history/state-blend ghost replay and ghost-only peak time/stage snapshotting. Do not revive either branch without a fresh design review.
- A later ghost-only peak snapshot experiment (`u_blob_peak_time` / peak stage override path) was also retired. That branch attempted to preserve ghost-specific phase/stage memory, but the user still saw wrong-shape behavior.
- A delayed-history/state-blend ghost experiment was also attempted during the micro-scheduler rollout, but it caused user-visible mismatch/flicker and has been retired.
- Important: although the code is back on the retained-peak branch, Blob ghosting is still **not** considered visually validated. Treat Blob ghost behavior as an active investigation item, not a settled feature.
- New uniforms: `u_blob_glow_reactivity` (0–2.0, scales energy contribution to glow sigma/strength), `u_blob_glow_max_size` (0.1–3.0, scales glow spread radius). Both surfaced as Advanced sliders in `blob_builder.py`.

#### Bubble Motion Tails (Reworked Mar 5 2026)

- CPU sim constants reworked: `TRAIL_SMEAR_FOLLOW_RATE` 0.65 (was 1.4), `TRAIL_SMEAR_FOLLOW_MAX` 0.18 (was 0.35), `TRAIL_SMEAR_DECAY_PER_SEC` 0.9 (was 1.6), `TRAIL_SMEAR_STRENGTH_FROM_DISTANCE` 35.0 (was 22.0). Result: longer, more visible streaks.
- Shader reworked for teardrop/tadpole shape matching mock (`BubbleMotionTrailMock.png`): cubic taper (`along_t² × (3 - 2×along_t)`), wider at bubble head (1.8× radius), tapering to 8% at tail tip. Organic longitudinal fade with gentle tip fade-in and head fade-out.

## Banding & Pixmap Seeding
- `DisplayWidget.show_on_screen` grabs a per-monitor wallpaper snapshot via `screen.grabWindow(0)` and seeds `current_pixmap`, `_seed_pixmap`, and `previous_pixmap` before GL prewarm runs. This prevents a wallpaper→black flash during startup even while overlays are initializing.
- `DisplayWidget` seeds `current_pixmap` again as soon as a real image loads, before transition warmup, to keep the base widget drawing a valid frame while overlays warm and transitions start.
- `paintEvent` prefers `current_pixmap`, then `_seed_pixmap`, and finally `previous_pixmap` (when no error is set), only falling back to a pure black fill when no pixmap is available. This keeps startup and fallback paths visually continuous.
- After closing the settings dialog, force reseed and unblock updates before transitions resume (multi-monitor specific).

## Diagnostics & Telemetry
- Structured logging captures overlay readiness stages, swap behavior, and watchdog activity.
- High-verbosity debug sessions require log rotation (size/time bound) to avoid disk pressure. A dedicated rotating `screensaver_perf.log` file, configured via a PERF-only logging filter in `core.logging.logger`, mirrors all `[PERF]` lines (including `[PERF] [SPOTIFY_VIS]`, `[PERF] [ANIM]`, and `[PERF] [GL COMPOSITOR]` summaries) so performance telemetry remains easy to inspect across rotated main logs.
 - Telemetry counters record transition type requested vs. instantiated, cache hits/misses, and transition skips while in progress.
 - Animation timing for **all** transitions (CPU and GL/compositor) is centralised through per-display `AnimationManager` instances driven by a `PreciseTimer`-backed loop; transitions use `[PERF] [ANIM]` metrics (duration, frames, avg_fps, dt_min/max, fps_target) as the canonical timing signal rather than ad-hoc timers.
 - Background work (IO/COMPUTE) is routed through the central `ThreadManager` pools wherever possible; any remaining direct `QThread`/`QTimer` usages outside `core.threading.manager` are explicitly logged fallbacks (e.g. widget-level weather fetch when ThreadManager is unavailable) rather than parallel primary paths.
 - Console debug output uses a suppressing stream handler that groups consecutive INFO/DEBUG lines from the same logger into `[N Suppressed: CHECK LOG...]` summaries while leaving file logs untouched. The high-visibility `Initializing Screensaver Engine 🚦🚦🚦🚦🚦` banner is exempt from grouping so it always appears once per run, and when multiple `[PERF]` lines with `avg_fps=...` are collapsed, the summary includes the trailing `avg_fps` token to keep grouped telemetry readable in the console.
 - A central PERF switch is configured in `core.logging.logger`: `PERF_METRICS_ENABLED` defaults to false and can be overridden by the `SRPSS_PERF_METRICS` environment variable (`0/false/off/no` vs `1/true/on/yes`). In frozen builds, it is finalised at startup by a small `<exe-stem>.perf.cfg` file written next to the executable by the build scripts (`scripts/build_nuitka*.ps1`). GUI/retail builds typically write `0` to disable PERF metrics, while console/debug builds write `1` to keep full telemetry enabled.
 - Optional CPU profiling for both RUN and CONFIG modes is gated by the `SRPSS_PROFILE_CPU` environment variable. When enabled, `main.py` wraps the selected entrypoint (`run_screensaver` or `run_config`) in a `cProfile.Profile` run and writes `.pstats` snapshots into the active log directory returned by `core.logging.logger.get_log_dir()`, so developers can inspect hotspots and feed them back into the roadmap.
 - When PERF metrics are enabled, `GLCompositorWidget` can optionally draw a small on-screen FPS/debug overlay on top of compositor frames (e.g. Slide/Wipe) to visualise real frame pacing during development. This overlay is disabled implicitly when PERF metrics are turned off so retail builds incur no additional HUD cost.
 - On `initializeGL`, `GLCompositorWidget` logs the OpenGL adapter vendor/renderer/version and disables the shader pipeline for the session when a clearly software GL implementation is detected (for example, GDI Generic, Microsoft Basic Render Driver, llvmpipe). In this case, compositor QPainter-based transitions and CPU fallbacks remain active, but shader-backed paths are not used on that stack.
 - If spikes persist, further expand compute-pool pre-scale-to-screen (including DPR-specific variants) as a future enhancement.

## Future Enhancements
 - Further expand compute-pool pre-scale-to-screen (per-display DPR) ahead of time for the next image and potentially cache DPR-specific scaled variants when memory allows.
 - Transition sync improvements across displays using lock-free SPSC queues.
 - Additional tuning of the **GL-only, compositor-backed transitions** (Ripple, Warp Dissolve, 3D Block Spins) based on visual QA and user feedback (e.g. strip counts, band amplitudes, droplet density). The legacy Shuffle transition has been fully retired for v1.2; any future Shuffle effect would be a fresh, tile-based GLSL design scheduled post-v1.2 rather than an evolution of the old compositor-based Shuffle.
- Optional Slide edge spark FX (GL/compositor-backed) where slide edges emit short-lived sparks with direction-aware angles and Auto/Blue/Orange colour modes; Auto samples a dominant edge colour and offsets it for visibility. This effect is strictly opt-in and must respect per-display clipping so it never bleeds across monitors.
- Sine Wave `Crawl` redesign: current Crawl remains a distortion-style effect, but the intended long-term design is additive, not deformative. The current backlog direction is to attempt two separate opt-in effects rather than force one replacement path: (1) spiral companion lines twisting around the sine wave and travelling with wave motion, and (2) slinky-style extra crawler lines that move along the sine paths. Both should be vocal-led in speed, use their own intensity controls with `0 = Off`, and must never deform the base sine line. Track the active backlog item in [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Current_Plan.md).

## Spotify Volume Control

The volume slider widget (`widgets/spotify_volume_widget.py`) uses `core/media/spotify_volume.py` which controls the **Windows mixer session level** for Spotify via pycaw/Core Audio (`ISimpleAudioVolume`).

### Current Implementation (Windows Mixer)
- Controls the per-application volume in Windows Volume Mixer
- Works without authentication or Premium subscription
- **Limitation**: Does NOT sync with Spotify's internal volume slider - they are independent controls
- **Limitation**: Spotify audio sessions are only discoverable via Core Audio when actively playing; volume changes while paused will silently fail
- Volume fill colour alpha is user-configurable (default 140/255 ≈ 55%); border alpha is always forced to 255
- Runtime provider rebinding now flows through the same media settings source of truth used by the media card, so `spotify` / `musicbee` auto-fallback can retarget both the GSMTC metadata path and the Core Audio session filter without recreating the widgets.

### Alternative: Spotify Web API
Spotify's Web API provides `PUT /v1/me/player/volume` which controls the **internal Spotify volume** (the slider inside the app):
- **Pros**: Syncs with Spotify's UI, works across devices via Spotify Connect
- **Cons**: Requires OAuth authentication with `user-modify-playback-state` scope, requires Spotify Premium subscription
- **Implementation complexity**: Would need OAuth flow, token refresh, and API calls

### Recommendation
The current Windows mixer approach is simpler and works for all users. Implementing Spotify Web API volume control would require:
1. OAuth 2.0 PKCE flow for desktop apps
2. Secure token storage
3. Token refresh logic
4. Premium-only feature gating
5. Fallback to mixer control for non-Premium users

This is a **low-priority enhancement** that could be added post-v1.2 if users request Spotify-synced volume.

## Clean Exit Architecture

> **Status**: Clean exit implementation complete - no taskkill required

### Shutdown Pipeline

The application guarantees clean exit through a coordinated shutdown sequence:

1. **ScreensaverEngine.stop()** - Orchestrates shutdown
   - Transitions to SHUTTING_DOWN state (signals async tasks to abort)
   - Stops rotation and RSS refresh timers
   - Clears displays via DisplayManager
   - Shuts down ProcessSupervisor workers
   - Shuts down ThreadManager (wait=False for fast exit)

2. **DisplayManager.cleanup()** - Per-display cleanup
   - Calls `shutdown_render_pipeline("cleanup")` for each display
   - Logs display state via `describe_runtime_state()` before cleanup
   - Clears display widgets and deletes later
   - Flushes deferred Reddit URLs

3. **DisplayWidget.shutdown_render_pipeline()** - Render pipeline teardown
   - Stops transitions via TransitionController with reason logging
   - Stops GL compositor render strategy via `stop_rendering()`
   - Logs state via `describe_runtime_state()` for diagnostics

4. **TransitionController.stop_current()** - Transition cancellation
   - Cancels AnimationManager animations
   - Signals compositor to snap to new image
   - Calls transition.stop() and cleanup()
   - Perf-gated instrumentation for shutdown analysis

5. **Adaptive Timer Fast-Path** - Immediate timer halt
   - `exit_immediate` flag in `AdaptiveTimerConfig`
   - Skips thread wait when set (shutdown only)
   - No performance impact during normal operation

### Key Components

- **GLCompositorWidget.stop_rendering()**: Stops frame pacing and render strategy with perf logging
- **AdaptiveRenderStrategyManager.stop()**: Sets exit_immediate=True before timer stop
- **ThreadManager.shutdown()**: Cancels active tasks, shuts down executors with logging
- **ProcessSupervisor.shutdown()**: Graceful worker termination

### Instrumentation

All shutdown paths instrumented with perf-gated logging (`SRPSS_PERF_METRICS=1`):
- `[PERF][ENGINE]` - Display state aggregation pre-shutdown
- `[PERF][DISPLAY_MANAGER]` - Cleanup display state logging
- `[PERF][DISPLAY]` - Render pipeline shutdown with reason
- `[PERF][GL COMPOSITOR]` - Stop rendering with reason and state
- `[PERF][ADAPTIVE_TIMER]` - Timer stop/pause/resume with state
- `[PERF][TRANSITION]` - Transition cancellation with reason and anim info

### State Description Methods

Diagnostic state capture for shutdown debugging:
- `AdaptiveTimerStrategy.describe_state()` - Timer snapshot (task_id, state, events)
- `AdaptiveRenderStrategyManager.describe_state()` - Strategy config and timer state
- `FrameState.describe()` - Frame interpolation state (progress, samples)
- `TransitionController.describe_state()` - Transition status (running, transition name, elapsed)
- `GLCompositorWidget.describe_state()` - GL state (transition, frame_state, render_strategy)
- `DisplayWidget.describe_runtime_state()` - Aggregated display state

---

## v2.0 Architecture Updates

### Fade Coordination Architecture

- **FadeCoordinator** (`rendering/fade_coordinator.py`) provides centralized, lock-free fade synchronization:
  - Atomic state machine (IDLE → READY → STARTED) using simple attribute assignments (GIL-protected)
  - Lock-free SPSCQueue for cross-thread fade requests
  - Participant registration and compositor-ready signaling
  - Automatic batch fade start when all participants registered and compositor ready
  - No raw locks for business logic - uses atomic operations and queue-based threading
- **WidgetManager** delegates all fade coordination to FadeCoordinator:
  - `reset_fade_coordination()` → `FadeCoordinator.reset()`
  - `set_expected_overlays()` / `add_expected_overlay()` → `FadeCoordinator.register_participant()`
  - `request_overlay_fade_sync()` → `FadeCoordinator.request_fade()`
  - `_on_compositor_ready()` → `FadeCoordinator.signal_compositor_ready()`
- Shared fade timing contract:
  - primary overlays must remain on the shared fade helper path and begin fading immediately once the compositor is ready
  - analog Clock is not allowed to bypass startup fade just because it owns its own painter-based shadow look
  - the shared fade helper must show widgets immediately at `opacity=0.0`; it must not wait for the first animation tick to make a widget exist on screen
  - shared startup fade defaults now live in `widgets/shadow_utils.py::ShadowFadeProfile` and should remain the single source of truth for common fade duration/easing
  - normal widget startup callers should use that shared default directly rather than copying local `1500ms`-style literals into wrapper methods
  - Spotify secondary startup delay should stay derived from `ShadowFadeProfile.DURATION_MS`, so visualizer hot-start cannot drift back into the primary wave by accident
  - `WidgetManager` + `FadeCoordinator` are the authoritative runtime startup source of truth; any mirrored display-local `_overlay_fade_*` or `_spotify_secondary_not_before_ts` fields exist only so widgets can read the current manager-owned state
  - the parent display's `_spotify_secondary_not_before_ts` deadline is the manager-mirrored runtime gate for Spotify secondary-stage startup, including anchor/media-driven retries
  - visualizer fade-in should also derive from `ShadowFadeProfile` rather than shipping separate local timing literals in startup or mode-transition paths
  - explicit shorter/longer durations are allowed only when they are intentionally passed as true overrides and actually honored by the shared fade helper
- Reddit helper lifecycle contract:
    - `core/windows/reddit_helper_bridge.py` is queue-only and must remain benign.
    - `core/windows/reddit_helper_runtime.py` owns user-session helper bootstrap/health through a shared heartbeat file plus a durable interactive scheduled task (`SRPSS_RedditHelper`) that acts as the launch authority for real SCR handoff.
    - Winlogon / SYSTEM screensaver runs must not assume they will receive a polite shutdown path; helper reliability has to come from persisted queue state and a separately healthy user-session watcher launched from the real interactive desktop.
    - The screensaver must not wait on the helper for exit. The contract is `queue URL -> normal exit`; the helper independently waits for shell readiness, launches the URL, and self-exits.
    - Secure-desktop/screensaver-origin queue entries should carry a source-aware `not_before_ts` so user-session draining does not race Explorer handoff immediately after Winlogon exit.
    - `helpers/reddit_helper_worker.py` is the only queue drainer and must keep retry/backoff, launch-not-before deferral, legacy `.retry` migration, stale-entry expiry, and owner-idle shutdown under one canonical contract so queue files cannot become invisible forever, transient shell-handoff waits do not consume the failure budget, and preview/script helpers do not linger indefinitely.
    - Windows helper-health probing and stale-process reaping must use Win32 process APIs (`OpenProcess`/`GetExitCodeProcess`) instead of `os.kill(pid, 0)` semantics, which are unreliable in packaged/background Windows contexts.
    - Authority-layer verification is not guesswork anymore: `tools/reddit_helper_task_harness.py` plus `tests/test_reddit_helper_task_harness.py` are the regression fence for installer/runtime task registration, query, run, and cleanup of the reusable scheduled task.
- Legacy SPSCQueue/TripleBuffer fade coordination has been removed in favor of the centralized FadeCoordinator

### Visualizer Startup Prewarm Contract

- `rendering/display_image_ops.py::prewarm_spotify_visualizer_overlay()` owns centralized visualizer prewarm orchestration.
- `widgets/spotify_visualizer/shaders/__init__.py::preload_fragment_shaders()` should prime shader-source cache before visualizer overlay prewarm begins, so shader file IO does not re-enter the first visible reactive window.
- `widgets/spotify_bars_gl_overlay.py::prewarm_context()` should force actual GL realization while hidden rather than relying on a passive hidden `show()/update()` path.
- `rendering/widget_manager.py` should treat visualizer prewarm as retryable until it has succeeded against a real widget instance; early startup ordering must not permanently burn the prewarm attempt.

### Media Key Updates
  - `play_pause()` bypasses diff gating for optimistic state updates
  - Uses `repaint()` (not `update()`) for immediate feedback
  - Performance-guarded: only repaints if `_show_controls` and `isVisible()`
  - Visualizer already updates instantly; now play/pause glyph matches
- **Media control bar visual improvements** (`widgets/media_widget.py`):
  - Shifted up 5px for better positioning within card
  - Outer border increased from 1px to 2px for better visibility
  - 3D lift/depth effect: filled slab 4px right/4px down
  - Slab uses same gradient as control bar but 15% darker
  - Slab outline: white 10% darker than control bar outline
  - Light shadow (alpha 40) behind slab for depth
  - **Slab Effect - Experimental** setting added to toggle the 3D effect

### GL State Management Refactoring
- **GLStateManager** (`rendering/gl_state_manager.py`) provides centralized GL context state management with validated state transitions.
- **ResourceManager GL Hooks** (`core/resources/manager.py`): Added `register_gl_handle()`, `register_gl_vao()`, `register_gl_vbo()`, `register_gl_program()`, `register_gl_texture()` for VRAM leak prevention.
- **TransitionController** (`rendering/transition_controller.py`): Added `snap_to_new` parameter to `stop_current()` for clean transition interruption.
- All GL handles in `spotify_bars_gl_overlay.py`, `geometry_manager.py`, and `texture_manager.py` are now tracked by ResourceManager.

### Settings Validation
- **validate_and_repair()** in SettingsManager auto-fixes corrupted settings values on startup.
- Sensitivity validation: Values below 0.5 are reset to default 1.0 to prevent visualizer regression.

### Test Coverage
- **1279 unit tests** across 30+ test files (62 skipped in headless) covering process isolation, GL state, widgets, MC features, settings, performance tuning, integration, threading policy compliance, and frame timing.
- Key test files: `test_display_integration.py` (57 tests), `test_weather_widget.py` (26 tests), `test_adaptive_timer.py` (27 tests), `test_integration_full_workflow.py` (19 tests), `test_spotify_visualizer_widget.py` (13 tests), `test_gl_texture_streaming.py` (18 tests), `test_policy_compliance.py` (threading/import policy enforcement).

**Version**: 2.0.0-dev

Settings dialog exposes **Use Recommended Sensitivity** (bool) with a manual multiplier slider. Audio worker treats this path as a curated fixed multiplier (0.285 default) rather than auto-learning, so the UI wording must stay explicit about that distinction. Saving/loading paths continue to persist `adaptive_sensitivity` + `sensitivity` in models/settings JSON, and creator/widgets apply the same schema.

Bubble drift directions remain centralized through the settings pipeline (`bubble_drift_direction`) with the widget combo → model → defaults → config applier → simulation chain. Modes now include **Swish (Horizontal/Vertical)** for axis-locked wobble as well as **Swirl (Clockwise/Counter-Clockwise)**, which drive tangential drift around the card centre while keeping per-bubble bias deterministic, in addition to none/left/right/diagonal/random.

Bubble specular direction follows the same pipeline (`bubble_specular_direction`) and now exposes the four cardinal headings (`top`, `bottom`, `left`, `right`) in addition to the diagonal presets. The overlay maps each string to a normalized 2D vector that the shader uses for highlight placement, while `bubble_gradient_direction` independently controls gradient tilt, so presets/SST exports can pick exact lighting angles without custom values.

**Bubble specular coordinate fix (Mar 2026)**: The specular crescent projection vectors in `bubble.frag` must use aspect-corrected, Y-flipped coordinates matching the `spec_center` offset space. Previously, raw `u_specular_dir` was used with inconsistent negation, producing distorted crescents on diagonals. Fixed by building `adj_dir` with the same conventions as the spec_center offset (aspect-corrected X, negated Y), normalizing, and projecting directly without extra negation.

**Default visualizer mode**: Changed to `bubble` for both MC and normal builds (Mar 2026).

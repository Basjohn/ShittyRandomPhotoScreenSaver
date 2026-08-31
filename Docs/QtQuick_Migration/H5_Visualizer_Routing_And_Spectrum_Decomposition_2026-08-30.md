# H5 Technical Decomposition — Visualizer CUSTOM Routing and Spectrum Saturation

Date: 2026-08-30; Spectrum evidence refreshed 2026-08-31  
Starting source: `af8896b52fbee153fe1cd0b627a55455c14625d1`

This decomposition covers two independent functional Visualizer regressions. Keep them separate in implementation and testing.

## Part A — CUSTOM cross-display admission

### Product contract

Outside CUSTOM:

```text
Visualizer effective position/monitor = Media effective position/monitor
```

Inside committed CUSTOM:

```text
Visualizer effective position/monitor = spotify_visualizer's own persisted CUSTOM route
```

CUSTOM may:

- overlap ordinary widgets;
- live on a different selected display from Media;
- transfer between selected displays;
- persist/rebuild on the new display.

There is still exactly one product Visualizer owner.

### Current-source evidence

`rendering/widget_descriptors.py` already implements the route-key split.

`DisplayManager._resolve_visualizer_requested_screen_index()` already calls the effective-monitor authority.

`QuickDisplayUnit.is_visualizer_participant()` only requires a live, non-binding-lost Quick unit. It does not require a Media card on that screen.

`QuickCustomLayoutOwner.save()` specially persists the Visualizer's current display monitor.

Therefore do not add another route system. Find where the existing truth is being lost.

### Diagnostic record

Emit one bounded generation-level record:

```text
runtime_generation
spotify_visualizer.enabled
spotify_visualizer.position
spotify_visualizer.monitor
media.enabled
media.monitor
is_custom
effective_monitor
requested_screen_index
participants=[screen_index, participating, binding_loss]
failover_state=[target, grace_generation, fallback]
chosen_screen
construct_result
reject_reason
```

Do not emit per-frame routing logs.

### Decision tree

1. `is_custom=False` unexpectedly:
   - inspect persisted `position` after CUSTOM Save and hydration;
   - fix persistence/hydration owner.
2. `is_custom=True`, `effective_monitor` equals Media:
   - effective routing regression; fix descriptor caller/data shape.
3. effective monitor correct, requested screen correct, but participant missing:
   - inspect selected display creation/binding loss.
4. participant exists but failover holds/chooses wrong unit:
   - fix failover/reconcile contract.
5. chosen unit correct but `_construct_quick_visualizer_owner_on()` returns false:
   - instrument exact capability/instance/activation rejection.
6. owner exists on screen 2 but no pixels:
   - then inspect retained scene transfer/admission; do not duplicate owner.

### Tests

Supplied semantic pin:

```text
tests/test_visualizer_custom_route_contract.py
```

Add a production admission test after localization:

```text
Media monitor 1
Visualizer position Custom
Visualizer monitor 2
participants 0 + 1 live
=> chosen owner screen_index 1
=> exactly one owner

same but Visualizer non-Custom
=> chosen owner screen_index 0
```

Also preserve missing-monitor 30 s grace/fallback/reclaim behavior.

## Part B — Spectrum saturation + wrong renderer topology

### Updated evidence status — 2026-08-31

The direct line-by-line comparison against the user-supplied known-good `3fe5df687387b6b6a121142372c43a7719442386` tree has converted the previous broad H5b hypotheses into **three independent source-proven migration deviations**.

The historical source is a behavioral oracle only. The accepted retained Quick architecture remains binding.

### B1 — canonical topology mapping was lost (**H proven**)

Historical `rendering/spotify_widget_creators.py::apply_spotify_vis_model_config()` explicitly derived:

```text
spectrum_render_mode == "bars"    -> spectrum_single_piece = True
spectrum_render_mode == "segment" -> spectrum_single_piece = False
```

Current `core/settings/visualizer_presets.py` correctly makes `spectrum_render_mode` canonical and removes the legacy `spectrum_single_piece` key. But current `apply_logical_vis_mode_kwargs()` still consumes only `spectrum_single_piece`; it ignores `spectrum_render_mode`. The logical default is `_spectrum_single_piece = False`.

Therefore a canonical `bars` preset can reach the Quick owner and still render the default segmented topology. This directly explains the dense mini-cell family independently of energy saturation.

Repair checklist:

- [ ] Normalize/consume canonical `spectrum_render_mode` in the current logical configuration seam.
- [ ] Derive the runtime boolean there; keep any legacy boolean fallback narrow and tested.
- [ ] Test `bars` and `segment` through `QuickDisplayVisualizerOwner`, not only the helper.
- [ ] Preserve mode switch/recreation/preset-swap topology.

Do not revive the historical widget creator.

### B2 — Spectrum BeatEngine shaping ownership was lost (**H proven**)

The old/current legacy mixed applier contains live engine configuration for:

```text
spectrum_mirrored
spectrum_shape_nodes
spectrum_notch_positions_mirrored / linear
spectrum_wave_amplitude
spectrum_profile_floor
spectrum_lane_strengths_mirrored / linear
spectrum_drop_speed
```

Those values reach existing `BeatEngine` setters / `SpectrumShapeConfig` in the historical path.

The new Quick owner correctly avoids the broad catch-all applier, but neither `build_technical_cache()` nor `apply_controller_technical_config()` carries this Spectrum shaping family. The shared engine algorithms themselves are unchanged, yet the selected preset can therefore feed **different/default engine shaping**.

Repair checklist:

- [ ] Route the exact engine-consumed Spectrum shape values through a narrow presentation-neutral controller configuration seam.
- [ ] Apply them through the existing one BeatEngine and existing setters.
- [ ] Apply only on configure/mode/preset/settings refresh; never on every authored/render frame.
- [ ] Keep mirrored-state + active-notch selection coherent in one transaction.
- [ ] Test in-place preset A -> B reconfiguration without engine/runtime recreation.

This must be repaired before interpreting remaining all-`1.00` data as a new math problem.

### B3 — historical final `0.55` renderer transfer is absent (**J-shaped numerical parity / required for H5b functional closure**)

Historical `widgets/spotify_visualizer/renderers/spectrum.py` multiplies both bars and peaks by `0.55` immediately before shader upload.

Current `rendering/quick/visualizer/implementations/spectrum.py` uploads raw authored bars/peaks. The same authored value `1.0` therefore reaches the current shader as `1.0` instead of historical `0.55` — approximately 1.82x the historical input.

Current `widgets/spotify_visualizer/spectrum_solid_hysteresis.py` still owns `_SPECTRUM_UPLOAD_SCALE = 0.55`, reinforcing that this transfer remains part of the intended presentation domain.

Repair checklist:

- [ ] Reuse/export one canonical transfer constant/helper; do not duplicate a new magic number.
- [ ] Apply it exactly once to Quick live bars and peaks at renderer input.
- [ ] Keep logical/snapshot bar values canonical and untouched.
- [ ] Test bar + peak transfer and both continuous/segmented topology.

### B4 — re-measure only after B1-B3

After the three known deviations are removed, trace:

```text
S0 selected preset/model
S1 resolved controller/engine config
S2 actual BeatEngine shape/mirror/notch/drop state
S3 current feature/bar state
S4 SpectrumFrameRuntime source-ready + resolved bars/peaks
S5 immutable SpectrumFrame
S6 Quick input after historical transfer
S7 visible shader/topology
```

- [ ] If S3 is still upper-bound degenerate, find the first engine/config transformation producing it.
- [ ] If S3 is healthy and S4/S5 degenerates, fix Spectrum authored runtime semantics.
- [ ] If S5 is healthy and S6/S7 is wrong, keep the repair in Quick presentation.
- [ ] Do **not** change global visualizer gain based on Spectrum.

### H5b acceptance

H5b is GREEN when:

- [ ] canonical `bars` produces the intended continuous-column family;
- [ ] canonical `segment` remains intentionally segmented;
- [ ] selected Spectrum preset shape/mirror/notch/drop values reach the one BeatEngine;
- [ ] historical `0.55` final transfer is present exactly once;
- [ ] live input is materially/non-degenerately reactive after the known parity repairs;
- [ ] topology + shaping survive mode switch, generation recreation and preset change;
- [ ] one retained Spectrum owner/draw path remains;
- [ ] no shared/global gain/cadence/Bubble workaround is introduced.

J Parity+ still owns fine spacing/glow/gradient/outline/elegance after the functional family is correct.

## Part C — Bubble is excluded from **Spectrum tuning**, not from H

Bubble must not be changed as collateral damage while repairing H5b. In particular, Spectrum's broken height/reactivity is not evidence for a shared global gain change.

However, the 2026-08-31 historical/current audit has now found source-proven Bubble configuration ownership omissions and has promoted the Bubble/common reactivity investigation to **H5c**.

Preserve during H5b:

- [x] ~90 Hz authored cadence;
- [x] one logical runtime / one source owner;
- [x] current good partial/CUSTOM resize contract;
- [x] current scale/viewport sizing architecture;
- [ ] no Bubble sensitivity/physics/growth retune.

H5c owns Bubble's stranded logical settings, shared source-readiness classification, Play/Pause visible delay, Sine idle transport and the full all-mode historical parity audit.

Detailed route: `Docs/QtQuick_Migration/H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`.  
Evidence matrix: `Docs/QtQuick_Migration/Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`.

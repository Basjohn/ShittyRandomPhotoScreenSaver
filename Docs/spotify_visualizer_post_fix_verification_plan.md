# Spotify Visualizer Bleed — Post-Fix Verification Plan

Status: the runtime bar/display clearing patch appears to have changed the exact bad checkpoint.

This plan assumes the bar-state reset fix has already been applied.

Goal: prove the issue is actually solved, prevent regression, and avoid another settings/preset detour.

---

## 1. Current evidence

The new log proves a real mode switch happened.

Do not claim the user did not switch modes.

Relevant log sequence:

```text
[SPOTIFY_VIS] Mode cycle requested: DEVCURVE -> SPECTRUM
[SPOTIFY_VIS] Visualization mode changed to SPECTRUM
```

The target Spectrum path then applied config through the normal switch flow:

```text
reason=mode_switch mode=spectrum
reason=mode_fade_out_complete mode=spectrum
reason=mode_prepare_reset mode=spectrum
```

---

## 2. What improved

Before the fix, stale `_display_bars` survived through the target mode reset path.

Old bad shape:

```text
after_full_runtime_prepare_reset mode=spectrum display_max=0.973
after_technical_config_prepare_reset mode=spectrum display_max=0.973
before_first_overlay_push mode=spectrum display_max=0.841
```

After the fix, the reset checkpoints are clean:

```text
after_full_runtime_prepare_reset mode=spectrum display_max=0.000 display_avg=0.000
after_technical_config_prepare_reset mode=spectrum display_max=0.000 display_avg=0.000
```

This means the previously confirmed stale-display-bar reset bug is likely fixed.

---

## 3. Remaining uncertainty

The new log still shows this after the fresh target frame arrives:

```text
before_first_overlay_push mode=spectrum display_max=0.911 display_avg=0.617
after_first_overlay_push mode=spectrum display_max=0.911 display_avg=0.617 overlay_activation=3 overlay_generation=3
```

This may be legitimate if the engine delivered a fresh Spectrum frame for generation/activation 3 before the first overlay push.

But it is only fully proven safe if the non-zero bars are known to come from the target generation/activation, not from a stale compute result.

Current interpretation:

- The old stale bars are no longer surviving through reset.
- The remaining high first-frame bars may be valid target-mode audio.
- Need one more source-tracking pass to prove it.

---

## 4. Do not do these things

Do not:

- edit presets
- rewrite settings
- implement old Option 3
- edit `restore_visualizer_snapshot()`
- chase sine-specific parameters
- re-add `_replay_engine_config(engine)` to the transition reset path
- remove `_apply_full_runtime_config_for_mode()`
- add a new broad config replay layer
- claim the user did not switch modes

---

## 5. Immediate verification tasks

### Task 1: Add bar-state source tracking

Add source generation/activation fields for runtime bar arrays.

Suggested fields on the widget:

```python
self._display_bars_source_generation = -1
self._display_bars_source_activation = -1
self._target_bars_source_generation = -1
self._target_bars_source_activation = -1
self._visual_bars_source_generation = -1
self._visual_bars_source_activation = -1
self._per_bar_energy_source_generation = -1
self._per_bar_energy_source_activation = -1
```

When bar arrays are cleared during reset, set all source fields to `-1`.

When bar arrays are written from an engine frame, set source fields from that frame or from the current engine generation/activation.

Checklist:

- [ ] `_display_bars` source generation is tracked.
- [ ] `_display_bars` source activation is tracked.
- [ ] `_target_bars` source generation is tracked.
- [ ] `_target_bars` source activation is tracked.
- [ ] `_visual_bars` source generation is tracked.
- [ ] `_visual_bars` source activation is tracked.
- [ ] `_per_bar_energy` source generation is tracked.
- [ ] `_per_bar_energy` source activation is tracked.
- [ ] Reset path sets all source fields to `-1`.
- [ ] Engine frame commit path sets source fields to the committed frame generation/activation.

---

### Task 2: Extend `[RENDER_STATE]` logs

Add these fields to every `[RENDER_STATE]` line:

```text
engine_generation
engine_activation
display_source_generation
display_source_activation
target_source_generation
target_source_activation
visual_source_generation
visual_source_activation
energy_source_generation
energy_source_activation
```

Example desired log:

```text
[SPOTIFY_VIS][RENDER_STATE] reason=before_first_overlay_push mode=spectrum display_max=0.911 display_avg=0.617 engine_generation=3 engine_activation=3 display_source_generation=3 display_source_activation=3 target_source_generation=3 target_source_activation=3 visual_source_generation=-1 visual_source_activation=-1 energy_source_generation=3 energy_source_activation=3 overlay_activation=None overlay_generation=None
```

Acceptance:

- [ ] If `display_max > 0` before first overlay push, `display_source_activation` must equal current `engine_activation`.
- [ ] If `display_source_activation` is old, stale compute/frame commit is still happening.
- [ ] If source fields are missing, verification is incomplete.

---

### Task 3: Add stale compute/frame rejection test

Purpose:

Prove an old activation cannot write bars after a mode reset.

Suggested test shape:

```python
def test_stale_activation_frame_cannot_commit_display_bars_after_mode_reset():
    """
    Pseudocode. Adapt to actual tick/engine frame commit API.

    Arrange:
    - Widget starts with activation 2.
    - A fake/stale frame from activation 2 exists.
    - Mode reset advances engine/widget to activation 3.
    - Attempt to commit the stale activation 2 frame.

    Assert:
    - _display_bars remains zero or remains target activation 3 data.
    - _display_bars_source_activation is not 2.
    - _target_bars_source_activation is not 2.
    - _visual_bars_source_activation is not 2.
    - _per_bar_energy_source_activation is not 2.
    """
```

Concrete assertions:

```python
assert widget._display_bars_source_activation != old_activation
assert widget._target_bars_source_activation != old_activation
assert widget._visual_bars_source_activation != old_activation
assert widget._per_bar_energy_source_activation != old_activation
```

Acceptance:

- [ ] Test fails if old activation can write visible bars after reset.
- [ ] Test passes only when stale activation/frame commits are rejected.
- [ ] Test does not need real Spotify.
- [ ] Test does not need OpenGL.
- [ ] Test does not need PyAudio.

---

### Task 4: Keep the existing reset-order tests

Keep or add tests proving the reset path clears arrays before engine reset.

Required tests:

```text
test_on_mode_fade_out_complete_clears_bar_arrays_before_prepare_engine_reset
test_reset_mode_owned_runtime_state_clears_runtime_bar_arrays
test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config
```

Acceptance:

- [ ] `_display_bars` is zero before `prepare_engine_for_mode_reset()`.
- [ ] `_target_bars` is zero before `prepare_engine_for_mode_reset()`.
- [ ] `_visual_bars` is zero before `prepare_engine_for_mode_reset()`.
- [ ] `_per_bar_energy` is zero before `prepare_engine_for_mode_reset()`.
- [ ] `_replay_engine_config(engine)` is not called during mode reset.
- [ ] `_apply_full_runtime_config_for_mode()` is still called.
- [ ] `_apply_technical_config_for_mode()` is still called.

---

## 6. Required runtime validation run

Do two short runs.

### Run A: DevCurve -> Spectrum

Steps:

```text
1. Start runtime in DevCurve.
2. Wait until DevCurve is visibly reactive.
3. Switch DevCurve -> Spectrum.
4. Watch Spectrum for 5-10 seconds.
5. Stop.
```

Expected logs:

```text
Mode cycle requested: DEVCURVE -> SPECTRUM
Visualization mode changed to SPECTRUM
after_full_runtime_prepare_reset mode=spectrum display_max=0.000
after_technical_config_prepare_reset mode=spectrum display_max=0.000
before_first_overlay_push mode=spectrum display_source_activation=<current activation or -1 if display_max=0>
after_first_overlay_push mode=spectrum overlay_activation=<current activation> overlay_generation=<current generation>
```

Pass criteria:

- [ ] Spectrum does not start roof-pinned.
- [ ] Spectrum does not move as one uniform ceiling line.
- [ ] Reset checkpoints are zero.
- [ ] First non-zero display bars are from current activation.
- [ ] Overlay activation/generation match current engine activation/generation.

---

### Run B: Spectrum -> DevCurve

Steps:

```text
1. Start runtime in Spectrum.
2. Wait until Spectrum is visibly reactive.
3. Switch Spectrum -> DevCurve.
4. Watch DevCurve for 5-10 seconds.
5. Stop.
```

Expected logs:

```text
Mode cycle requested: SPECTRUM -> DEVCURVE
Visualization mode changed to DEVCURVE
after_full_runtime_prepare_reset mode=devcurve display_max=0.000
after_technical_config_prepare_reset mode=devcurve display_max=0.000
before_first_overlay_push mode=devcurve display_source_activation=<current activation or -1 if display_max=0>
after_first_overlay_push mode=devcurve overlay_activation=<current activation> overlay_generation=<current generation>
```

Pass criteria:

- [ ] DevCurve does not start dead/barely reactive.
- [ ] Reset checkpoints are zero.
- [ ] First non-zero display bars are from current activation.
- [ ] Overlay activation/generation match current engine activation/generation.

---

## 7. How to interpret results

### Case A: Looks fixed, source activation is current

Conclusion:

The original stale display-bar bleed is fixed.

Next action:

- [ ] Keep tests.
- [ ] Keep source-tracking logs temporarily.
- [ ] Reduce log verbosity later only after several clean runs.

---

### Case B: Looks fixed, but source fields are missing

Conclusion:

Probably fixed, but not fully proven.

Next action:

- [ ] Add source activation/generation fields before closing the issue.

---

### Case C: Still visually broken, source activation is old

Conclusion:

Stale compute/frame commit is still happening after reset.

Next action:

- [ ] Reject old activation frames in the tick/commit path.
- [ ] Add the stale activation test.
- [ ] Do not touch settings/presets.

---

### Case D: Still visually broken, source activation is current

Conclusion:

The old stale-bar bug is fixed, but target-mode normalization may still be too hot/cold immediately after reset.

Next action:

Inspect current-activation runtime values:

```text
dynamic floor applied
manual floor
expansion
AGC current gain
AGC strength
input gain
energy boost
raw bass/mid/high
normalized bass/mid/high
display max/avg
```

Potential next fix would be target-mode ramp/normalization, not settings.

---

## 8. Final done criteria

The issue is only done when all are true:

- [ ] User confirms DevCurve -> Spectrum no longer roof-pins Spectrum.
- [ ] User confirms Spectrum -> DevCurve no longer makes DevCurve barely reactive.
- [ ] Logs prove a real mode switch occurred.
- [ ] Reset checkpoints show zero display/target/visual/energy arrays.
- [ ] First non-zero target-mode bars are from current generation/activation.
- [ ] Overlay generation/activation matches target generation/activation.
- [ ] Automated tests cover reset ordering.
- [ ] Automated tests cover direct runtime array reset.
- [ ] Automated tests cover stale activation rejection or source tracking.
- [ ] No settings rewrite was done.
- [ ] No preset rewrite was done.
- [ ] No `restore_visualizer_snapshot()` rewrite was done.
- [ ] `_apply_full_runtime_config_for_mode()` remains intact.
- [ ] `_replay_engine_config(engine)` is not called during mode reset.

---

## 9. Short instruction for SWE

The user did change modes. The log proves it.

The stale display-bar bug appears partially or fully fixed because reset checkpoints now show zero bars.

Do not pivot back to settings or presets.

Add source generation/activation tracking for bar arrays and prove that the first non-zero bars after reset belong to the current target activation.

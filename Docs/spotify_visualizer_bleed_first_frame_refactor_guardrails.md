# Spotify Visualizer Bleed / First-Frame Regression Guardrails

Purpose: preserve the fix for the historical mode-switch bleed / first-frame contamination bug during future Spotify visualizer refactors.

This document is a regression contract. Any large refactor touching the visualizer transition pipeline, tick pipeline, bar-state storage, overlay push path, or diagnostic logging must preserve these invariants or replace them with an equivalent proven mechanism.

---

## 1. Historical bug summary

The fixed bug was:

```text
DevCurve -> Spectrum:
Spectrum could enter visibly blown out / roof-pinned / nearly uniform.

Spectrum -> DevCurve:
DevCurve could enter barely reactive.
```

The confirmed failure was not primarily presets/settings. It was runtime bar/display state surviving into the target mode transition.

The critical stale state was:

```python
_display_bars
_target_bars
_visual_bars
_per_bar_energy
```

The fix was:

1. Clear mode-owned runtime state during mode switch.
2. Clear bar/display arrays before target engine reset / first target overlay push.
3. Track source generation + activation for bar arrays.
4. Gate bar copying until the target generation/activation handoff is verified.
5. Keep transition diagnostic logs that make this failure visible again if it regresses.

---

## 2. Non-negotiable transition sequencing invariant

The mode transition path must preserve this logical order:

```text
fade-out completes
-> old GL overlay cleared
-> target mode selected
-> target full runtime config applied
-> mode-owned runtime state reset
-> bar/display arrays zeroed
-> prepare/reset engine for target mode
-> wait for fresh target generation/activation frame
-> first target overlay push
-> fade-in completes
```

In current code this is centered around:

```text
widgets/spotify_visualizer/mode_transition.py
```

especially:

```python
on_mode_fade_out_complete()
prepare_engine_for_mode_reset()
reset_mode_owned_runtime_state()
```

---

## 3. Required ordering inside `on_mode_fade_out_complete()`

Do not regress the ordering.

The transition must not allow old bar/display arrays to survive into `prepare_engine_for_mode_reset()`.

Required ordering:

```python
widget._clear_gl_overlay()

# target mode applied
widget.set_visualization_mode(..., reset_runtime=False)

# target visual config applied
_apply_full_runtime_config_for_mode(..., reason="mode_fade_out_complete")

# target transition state set to waiting
_mode_transition_phase = 3
_mode_teardown_state = "waiting_bars"
_mode_teardown_block_until_ready = True

# old runtime visual state cleared
reset_mode_owned_runtime_state(widget, reason="mode_fade_out_complete")

# diagnostic snapshot after reset
_log_active_render_state_snapshot(reason="after_full_runtime_fade_out_complete")

# explicit array clear before engine reset
widget._clear_runtime_bar_state()

# only now reset/prepare engine for target mode
prepare_engine_for_mode_reset(widget)
```

### Guardrail

Do not move:

```python
prepare_engine_for_mode_reset(widget)
```

above:

```python
reset_mode_owned_runtime_state(...)
widget._clear_runtime_bar_state()
```

That reopens the historical bleed path.

---

## 4. Required state reset contract

`reset_mode_owned_runtime_state()` must continue to clear **runtime-only** mode state while leaving authored settings/config intact.

It must clear at least:

```python
_display_bars
_target_bars
_visual_bars
_per_bar_energy
```

It must also reset:

```python
_has_pushed_first_frame = False
_last_gpu_geom = None
_last_gpu_fade_sent = -1.0
```

And all bar source markers:

```python
_display_bars_source_generation = -1
_display_bars_source_activation = -1

_target_bars_source_generation = -1
_target_bars_source_activation = -1

_visual_bars_source_generation = -1
_visual_bars_source_activation = -1

_per_bar_energy_source_generation = -1
_per_bar_energy_source_activation = -1
```

### Guardrail

A refactor may reorganize state storage, but it must preserve the equivalent of:

```text
after runtime reset:
all visible bar arrays are zero
all bar source IDs are invalid / empty
first-frame flag is reset
```

---

## 5. Engine handoff gate must remain

In:

```text
widgets/spotify_visualizer/tick_pipeline.py
```

`consume_engine_bars()` currently refuses to copy engine bars while the target reset generation is unresolved:

```python
if widget._waiting_for_fresh_engine_frame:
    return False, False
```

This is important.

It prevents stale compute output from acquiring visual authority before the new target generation/activation has been verified.

### Guardrail

Do not remove or weaken this gate unless replaced with an equally strict or stronger verified handoff mechanism.

---

## 6. Fresh frame verification must preserve activation correctness

The verified target frame logic must continue checking:

```python
latest_gen >= _pending_engine_generation
```

and also activation identity:

```python
engine_activation_id == _pending_engine_activation_id
```

when a pending activation is expected.

For waveform modes, it must still require fresh waveform generation where applicable.

### Guardrail

A future refactor must not accept "new enough generation" alone if activation can still mismatch.

---

## 7. Source tracking contract

Whenever display bars are written from the engine, current code records:

```python
_display_bars_source_generation
_display_bars_source_activation
```

This must remain or be replaced with equivalent traceability.

Current behaviour:

```python
if any_nonzero:
    widget._display_bars_source_generation = engine_generation
    widget._display_bars_source_activation = engine_activation
```

### Guardrail

If a future refactor changes bar ownership, it must still be possible to answer:

```text
These visible bars came from which engine generation?
These visible bars came from which engine activation?
```

Without that, the bleed bug becomes much harder to prove or disprove.

---

## 8. Required `[RENDER_STATE]` logging contract

The `[SPOTIFY_VIS][RENDER_STATE]` diagnostic line must remain available in diagnostic logging, or be replaced by an equivalent structured state snapshot.

It is not just "nice logging." It was the log that revealed the bug.

### Required state values

Each render-state snapshot must expose at least:

```text
reason
mode
bars
display_max
display_avg
target_max
target_avg
visual_max
visual_avg
energy_max
energy_avg
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
overlay_activation
overlay_generation
```

Mode-specific renderer fields may remain mode-dependent, but the above core fields are mandatory.

---

## 9. Required `[RENDER_STATE]` checkpoint reasons

These checkpoint reasons must remain available, or an equivalent structured checkpoint system must replace them:

```text
after_full_runtime_fade_out_complete
after_full_runtime_prepare_reset
after_technical_config_prepare_reset
before_first_overlay_push
after_first_overlay_push
```

### Why each matters

#### `after_full_runtime_fade_out_complete`

Confirms target mode config has been applied and old runtime state has been reset before engine reset begins.

#### `after_full_runtime_prepare_reset`

Confirms the engine reset path did not reintroduce old visual state before technical config application.

#### `after_technical_config_prepare_reset`

Confirms target technical config application did not repopulate visible bars or reintroduce stale state.

#### `before_first_overlay_push`

Confirms the first visible target push is not using stale or wrong-source bars.

#### `after_first_overlay_push`

Confirms overlay generation/activation matches the target engine handoff.

---

## 10. Required render-state expectations after a mode switch

For every real mode switch, the logs should support this acceptance sequence.

### Reset checkpoints must be clean

At:

```text
after_full_runtime_fade_out_complete
after_full_runtime_prepare_reset
after_technical_config_prepare_reset
```

expected:

```text
display_max=0.000
target_max=0.000
visual_max=0.000
energy_max=0.000
```

and:

```text
display_source_generation=-1
display_source_activation=-1
target_source_generation=-1
target_source_activation=-1
visual_source_generation=-1
visual_source_activation=-1
energy_source_generation=-1
energy_source_activation=-1
```

### First non-zero bars must be target-owned

If:

```text
before_first_overlay_push display_max > 0
```

then:

```text
display_source_generation == engine_generation
display_source_activation == engine_activation
```

The same principle applies to any source-tracked arrays that become non-zero before first push.

### Overlay must match target

At:

```text
after_first_overlay_push
```

expected:

```text
overlay_generation == engine_generation
overlay_activation == engine_activation
```

---

## 11. Required `[MODE_RESET_ASSERT]` logging contract

The technical-config assertion log should remain available:

```text
[SPOTIFY_VIS][MODE_RESET_ASSERT]
```

It must preserve at least:

```text
mode
expected_dynamic
expected_manual
expected_sensitivity
expected_block
expected_input_gain
```

This log does not detect the stale-bar bug by itself, but it prevents future debugging from misclassifying a technical-config regression as a visual-state regression.

---

## 12. Do not reintroduce `_replay_engine_config()` into mode reset

The current mode reset path intentionally does **not** call:

```python
_replay_engine_config(engine)
```

inside:

```python
prepare_engine_for_mode_reset()
```

This was deliberately removed from the transition reset path.

### Guardrail

Do not re-add it there without a specific, reviewed reason and new tests proving no stale replay path exists.

---

## 13. Required tests that must remain passing

Current important file:

```text
tests/test_spotify_visualizer_mode_transition.py
```

These tests are part of the regression fence and should not be deleted, weakened, or replaced with less strict assertions.

### Must retain

```python
test_on_mode_fade_out_complete_clears_bar_arrays_before_prepare_engine_reset
```

Protects ordering: arrays are zero before engine reset.

```python
test_reset_mode_owned_runtime_state_clears_runtime_bar_arrays
```

Protects helper-level reset semantics and source-ID invalidation.

```python
test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config
```

Protects the no-replay reset path.

---

## 14. Existing weak test that should be strengthened when refactoring

Current test:

```python
test_stale_activation_frame_cannot_commit_display_bars_after_mode_reset
```

At present, this mostly verifies that reset clears source fields to `-1`; it does **not fully simulate an actual stale frame attempting to commit after reset**.

During a large refactor, strengthen or replace it with a test that truly proves:

```text
old activation frame arrives late
-> write attempt is rejected
-> visible bar arrays are not updated from stale activation
-> source activation never returns to the old value
```

### Recommended stronger test target

Use or adapt the real commit path in `consume_engine_bars()` or its successor:

```python
def test_old_activation_bars_cannot_become_visible_after_reset():
    # Arrange:
    # - pending target activation = 3
    # - stale engine/result reports activation = 2
    #
    # Act:
    # - tick/consume path executes
    #
    # Assert:
    # - display bars remain zero or unchanged
    # - source activation != 2
    # - no first overlay push is unlocked by stale activation
```

This is the single most valuable test to upgrade during a future architecture refactor.

---

## 15. Refactor review checklist

Before merging any large visualizer refactor, check all boxes.

### Transition ordering

- [ ] `on_mode_fade_out_complete()` clears old runtime state before engine reset.
- [ ] `_clear_runtime_bar_state()` still happens before `prepare_engine_for_mode_reset()`.
- [ ] Target mode is selected before target config application.
- [ ] Fade-in still waits for fresh target handoff or timeout rules as intentionally designed.

### Runtime reset

- [ ] Visible bar arrays are zeroed on mode-owned reset.
- [ ] Source generation/activation fields reset to invalid state.
- [ ] First-frame flags and GPU cache state reset.

### Engine handoff

- [ ] Fresh generation wait still exists.
- [ ] Fresh activation wait still exists.
- [ ] Waveform modes still require fresh waveform data.
- [ ] Bars are not copied while fresh-frame wait is unresolved.

### Logging

- [ ] `[RENDER_STATE]` exists or is replaced with equivalent structured diagnostics.
- [ ] All five checkpoint reasons still exist.
- [ ] `[MODE_RESET_ASSERT]` still exists or equivalent technical assert logging exists.
- [ ] Logs still expose source generation/activation and overlay generation/activation.

### Tests

- [ ] Existing transition regression tests still pass.
- [ ] No test was weakened to fit a refactor.
- [ ] Stale activation rejection test is preserved or strengthened.
- [ ] A real mode-switch manual log run was inspected if transition architecture changed materially.

---

## 16. Manual verification protocol after large refactors

Do two minimal runs.

### Run A

```text
Start in DevCurve
Wait until visibly reactive
Switch DevCurve -> Spectrum
Observe first several seconds
```

### Run B

```text
Start in Spectrum
Wait until visibly reactive
Switch Spectrum -> DevCurve
Observe first several seconds
```

### Required log markers to inspect

```text
Mode cycle requested
Visualization mode changed
[RENDER_STATE] reason=after_full_runtime_fade_out_complete
[RENDER_STATE] reason=after_full_runtime_prepare_reset
[RENDER_STATE] reason=after_technical_config_prepare_reset
Engine delivered fresh frame
[RENDER_STATE] reason=before_first_overlay_push
[RENDER_STATE] reason=after_first_overlay_push
[MODE_RESET_ASSERT]
```

### Required findings

- [ ] Reset checkpoints show zero bar/display/energy state.
- [ ] First non-zero display state belongs to the current engine activation.
- [ ] Overlay activation/generation match current engine activation/generation.
- [ ] No roof-pinned Spectrum after DevCurve.
- [ ] No barely-reactive DevCurve after Spectrum.

---

## 17. What not to conclude from logs

Do not claim the original bleed has returned merely because:

```text
before_first_overlay_push display_max is high
```

That can be valid if:

```text
display_source_activation == engine_activation
```

and the reset checkpoints were clean.

The actual bleed signature is:

```text
non-zero display/target/visual/energy state survives through reset checkpoints
```

or:

```text
first visible target bars belong to an old generation/activation
```

---

## 18. One-line agent guardrail

```text
Do not refactor away the mode-switch reset handoff guarantees: reset checkpoints must remain zero, first visible bars must be target-generation/target-activation owned, and `[RENDER_STATE]` must still prove both facts.
```

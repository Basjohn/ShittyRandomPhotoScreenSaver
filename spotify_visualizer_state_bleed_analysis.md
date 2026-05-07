Spotify Visualizer State Bleed Analysis
Objective: Fix persistent Spotify visualizer state bleed where technical/reactivity values from one mode/preset appear to contaminate another mode/preset during runtime mode or preset changes.
Status: Phase 2 FAILED - Cache rebuild implemented but bleed persists. Investigating new logs.
Last reviewed: 2026-05-07

# Phase 2 Failure Analysis

**Discovery:** New logs from 2026-05-07 23:33-23:34 show that MODE_RESET_ASSERT logs ARE now appearing, and cache rebuild logs ARE appearing. However, the user reports bleed still persists across multiple sessions.

**Evidence from logs (screensaver_spotify_vis.log):**
- MODE_RESET_ASSERT logs now appear: `mode=DEVCURVE expected_manual=0.140 expected_sensitivity=1.350`, `mode=SPECTRUM expected_manual=0.450 expected_sensitivity=1.000`
- Cache rebuild logs appear: `Rebuilt technical config cache during mode reset, modes=6`
- LIVE logs show correct values: DEVCURVE `cache_manual=0.140 worker_manual=0.140 worker_sensitivity=1.350`, SPECTRUM `cache_manual=0.450 worker_manual=0.450 worker_sensitivity=1.000`
- CFG refresh logs show correct values: DEVCURVE `manual=0.140 sensitivity=1.350`, SPECTRUM `manual=0.450 sensitivity=1.000`
- FLOOR logs show correct applied values: DEVCURVE `manual=0.140`, SPECTRUM `manual=0.450`

**Contradiction:**
- Logs show correct technical config values being applied at every layer (cache, worker, engine)
- User reports bleed still persists visually
- This suggests the bleed is NOT in the technical config layer

**Hypothesis:** The bleed may be in a different layer:
1. Visual rendering state (GL overlay, shader uniforms, GPU kwargs)
2. Runtime bar state (smoothing, interpolation)
3. Mode-owned runtime state that's not being reset
4. Audio worker state beyond the technical config parameters

**Investigation needed:**
- Examine visual rendering state logs
- Examine GL overlay state logs
- Examine mode-owned runtime state reset logs
- Compare old logs (before fix) vs new logs (after fix) to identify what changed

# New Finding: GPU/Visual Parameter Bleed

**Discovery:** Visual rendering parameters (GPU kwargs) are identical across modes in logs:
- `density=1.8` (same for spectrum and devcurve)
- `displacement=0.0` (same for spectrum and devcurve)
- `heartbeat=0.0` (same for spectrum and devcurve)
- `vertical_shift=45` (same for spectrum and devcurve)
- `line_count=3` (same for spectrum and devcurve)

These parameters are NOT technical audio config (floor, sensitivity, block_size, input_gain). They are visual rendering parameters passed to the GPU/shaders.

**Hypothesis:** The bleed is in GPU kwargs / visual rendering state, NOT in technical audio config. The technical audio config is being applied correctly (as evidenced by MODE_RESET_ASSERT and FLOOR logs), but the visual rendering parameters are not being reset or are being cached at the GL overlay level.

**Evidence:**
- Technical audio config (manual, sensitivity, block, input_gain) changes correctly between modes
- Visual rendering parameters (density, displacement, heartbeat, vertical_shift, line_count) remain identical
- GL overlay is destroyed and recreated on mode switch: `Destroying SpotifyBarsGLOverlay (reason=clear_gl_overlay)`
- Shaders are recompiled on mode switch
- But GPU kwargs may be cached at a different layer

**Next investigation:**
- Check if GPU kwargs are being reset during mode switch
- Check if GPU kwargs are cached in GL overlay state
- Check if GPU kwargs are cached in widget manager state
- Check if GPU kwargs are cached in renderer state

# Critical Finding: Sine-Specific Parameters Bleeding into Non-Sine Modes

**Discovery:** The logs show sine-specific parameters in REFRESH logs for SPECTRUM and DEVCURVE modes:
- SPECTRUM: `density=1.800 displacement=0.000 heartbeat=0.000 vertical_shift=45 line_count=3`
- DEVCURVE: `density=1.800 displacement=0.000 heartbeat=0.000 vertical_shift=45 line_count=3`

These parameters (`sine_density`, `sine_displacement`, `sine_heartbeat`, `sine_vertical_shift`, `line_count`) are SINE-WAVE SPECIFIC, not shared across modes.

**Root cause:** `_build_shared_visualizer_extras()` in `config_applier.py` includes sine-specific parameters in the shared extras:
```python
'sine_density': getattr(widget, '_sine_density', 1.0),
'sine_displacement': getattr(widget, '_sine_displacement', 0.0),
'sine_heartbeat': getattr(widget, '_sine_heartbeat', 0.0),
```

These widget attributes are NOT reset during mode switches. If the user switches from SINE to SPECTRUM or DEVCURVE, the old sine values persist on the widget and are passed to the GPU even though they're irrelevant for those modes.

**Why this causes bleed:** Even though these parameters are irrelevant for non-sine modes, they're being passed to the GPU shaders. If the shaders use these values (or if they affect rendering in subtle ways), they can cause visual bleed.

**Evidence:**
- The values are identical across SPECTRUM and DEVCURVE modes
- These are sine-specific parameters with default values (1.0, 0.0, 0.0, 45, 3)
- They're being logged in REFRESH logs for all modes, not just sine
- They're built from widget attributes that are not mode-specific

**Hypothesis:** The bleed is caused by sine-specific widget attributes not being reset when switching away from sine mode, and these stale values are being passed to the GPU even for non-sine modes.

# Phase 1 & 2 Summary

**Phase 1 (FAILED):** Removed `_replay_engine_config` call, but technical config cache was empty during mode reset, so `_apply_technical_config_for_mode` returned early without applying config.

**Phase 2 (FAILED):** Added cache rebuild before applying config. Logs show correct values being applied, but bleed persists visually.

**Root cause:** NOT in technical config layer. Bleed is elsewhere in the rendering or runtime state pipeline.
The previous “Option 3” plan — reload all modes’ preset values from preset files into settings — should not be the primary fix.
It may mask missing values, but it attacks the wrong layer.
The stronger current hypothesis is:
resolved preset/settings payload
`_apply_full_runtime_config_for_mode`
`_apply_technical_config_for_mode`
`_replay_engine_config`
shared beat engine / audio worker cached state
GL overlay runtime state
The fix should make runtime activation transactional:
target mode chosen
target preset resolved
old compute/render/DSP state reset
one authoritative technical config applied to engine/worker/overlay
first accepted frame must belong to that target activation
Do not solve this by materializing every mode’s preset values into settings.
---
Important correction to the current investigation
The current “root cause” section in the existing analysis says:
> `restore_visualizer_snapshot` clears mode-specific keys for ALL modes, not just the target mode.
That does not match current `main`.
Current `restore_visualizer_snapshot()` does:
```python
prefixes = MODE_KEY_PREFIXES.get(mode_key, [])

for key in list(spotify_vis_config.keys()):
    if key in payload:
        continue
    if _is_key_for_mode(key, prefixes):
        spotify_vis_config.pop(key, None)
        changed = True
```
And `_is_key_for_mode()` only checks the prefix list passed to it:
```python
def _is_key_for_mode(key: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return False
    candidate = key
    dotted_prefix = "widgets.spotify_visualizer."
    if candidate.startswith(dotted_prefix):
        candidate = candidate[len(dotted_prefix):]
    return any(candidate.startswith(prefix) for prefix in prefixes)
```
The mode registry defines separate prefix groups per mode, such as `spectrum_`, `bubble_`, `blob_`, `devcurve_`, plus alias groups for oscilloscope and sine. So current code clears the target mode’s prefixes, not every mode’s prefixes. fileciteturn7file0L1-L1 fileciteturn8file0L1-L1
Therefore, do not proceed on the assumption that `restore_visualizer_snapshot()` is deleting inactive modes’ preset values.
---
Commit comparison
Latest commit:
```text
ff691e3f5ffd7ad42dfab4942cfab6374b0c6887
Architectural Improvements That Do Fuck All.
```
Previous commit:
```text
9447ca7a7fff1ce19c4866211d4cf8ea4d1ae72a
Bleeeeeeeeed without the benefits.
```
The latest commit is one commit ahead of `Bleeeeeeeed`, and the only real code file changed is:
```text
widgets/spotify_visualizer_widget.py
```
The rest of the changes are docs/planning files. fileciteturn28file0L1-L1 fileciteturn29file0 fileciteturn30file0L1-L1
What changed from Bleeeeeeeed to latest
In `Bleeeeeeeed`, `_replay_engine_config()` replayed cached widget state:
```python
floor_dyn, floor_value = self._last_floor_config
sens_rec, sens_value = self._last_sensitivity_config

engine.set_floor_config(floor_dyn, floor_value)
engine.set_sensitivity_config(sens_rec, sens_value)
engine.set_energy_boost(self._last_energy_boost)
engine.set_input_gain(self._last_input_gain)
```
In latest, `_replay_engine_config()` was rewritten to read from authoritative mode config instead:
```python
config = self._get_mode_technical_config(self._vis_mode)
if config is None:
    logger.debug(
        "[SPOTIFY_VIS] No technical config available for mode=%s, skipping replay",
        self._vis_mode.name,
    )
    return

dynamic_floor = bool(config.get("dynamic_floor", True))
manual_floor = float(config.get("manual_floor", 0.12))
adaptive = bool(config.get("adaptive_sensitivity", True))
sensitivity = float(config.get("sensitivity", 1.0))
audio_block_size = int(config.get("audio_block_size", 0) or 0)

self.apply_floor_config(dynamic_floor, manual_floor)
self.apply_sensitivity_config(adaptive, sensitivity)
self._apply_audio_block_size(audio_block_size)
self._apply_energy_boost(energy_boost)
self._apply_agc_strength(agc_strength)
self._apply_input_gain(input_gain)
```
This means latest has less stale-cache pollution than `Bleeeeeeeed`.
However, latest still keeps `_replay_engine_config()` as a separate technical application path, which duplicates `_apply_technical_config_for_mode()` conceptually. The newest commit reduced one obvious stale-cache source, but did not eliminate the multi-authority transition problem. fileciteturn28file0L1-L1
Recommended base:
```text
Use latest ff691e3, not 9447ca7, as the base for the next fix attempt.
Use 9447ca7 only as a comparison/control commit.
```
---
Past attempts and what they taught us
Attempt 1: Remove cached variables and replay mechanism entirely
Approach:
remove `_last_floor_config`
remove `_last_sensitivity_config`
remove `_last_energy_boost`
remove `_last_input_gain`
remove `_last_audio_block_size`
remove `_replay_engine_config()`
remove related replay calls
Result:
Failed. It reportedly caused:
long delays during mode switch
blank widget card after switch
new mode not displayed correctly
Likely reason:
The failed attempt removed too much at once. `_apply_full_runtime_config_for_mode()` appears to apply non-technical widget/runtime mode values needed for actual display behavior, not just technical DSP config.
Lesson:
Do not remove `_apply_full_runtime_config_for_mode()` blindly. Separate “full runtime visual/widget config” from “technical DSP/engine config.”
The uploaded investigation already records this failed path and its lesson. fileciteturn0file0
---
Attempt 2: Repurpose `_replay_engine_config()` to read from authoritative config
Approach:
Keep `_replay_engine_config()`, but make it read from `_get_mode_technical_config(self._vis_mode)` instead of widget `_last_*` cached values.
Result:
Architecturally cleaner than `Bleeeeeeeed`, but bleed persisted.
Lesson:
The problem is probably not only where `_replay_engine_config()` reads from.
The problem may be that `_replay_engine_config()` still exists as another technical config application phase during transition.
If both `_apply_technical_config_for_mode()` and `_replay_engine_config()` apply overlapping technical state, then the runtime still has multiple “authorities,” even if both claim to read from the same source.
Latest commit implements this repurposed replay approach, but the docs state the bleed persisted. fileciteturn28file0L1-L1
---
Attempt 3: Investigate `restore_visualizer_snapshot()` as the new root cause
Approach:
Hypothesis said `restore_visualizer_snapshot()` clears all mode keys and causes inactive modes to fall back to defaults.
Result:
This does not match current `main`.
Current code passes only the target mode’s prefix list into `_is_key_for_mode()`. The registry’s prefixes are mode-specific. fileciteturn7file0L1-L1 fileciteturn8file0L1-L1
Lesson:
Do not implement a broad Option 3 based on this root cause.
The preset clear/apply system already has regression tests guarding stale-key purging and custom round-trip behavior. fileciteturn11file0L1-L1
---
Current suspicious path
`prepare_engine_for_mode_reset()` still has a layered transition sequence:
```python
apply_full = getattr(widget, "_apply_full_runtime_config_for_mode", None)
if callable(apply_full):
    apply_full(widget._vis_mode, reason="mode_prepare_reset")

engine.cancel_pending_compute_tasks()
engine.reset_smoothing_state()
engine.reset_floor_state()
engine.set_smoothing(widget._smoothing)

widget._replay_engine_config(engine)

apply_technical = getattr(widget, "_apply_technical_config_for_mode", None)
if callable(apply_technical):
    apply_technical(widget._vis_mode, reason="mode_prepare_reset")
```
This is dangerous because technical config may be applied more than once, from more than one method, during a transition. Even if `_replay_engine_config()` now reads “authoritative” config, it still duplicates the technical path.
The current transition code also calls `_apply_full_runtime_config_for_mode()` at fade completion before `prepare_engine_for_mode_reset()`, then `prepare_engine_for_mode_reset()` calls it again. That may be valid for visual/widget runtime state, but it should not also create technical/DSP ambiguity. fileciteturn21file0L1-L1
---
Recommended fix direction
Create a branch from latest:
```text
fix/visualizer-single-technical-authority
```
Goal:
Keep full runtime visual/widget config application, but make technical DSP/engine config have exactly one final authority during mode reset.
Do not reload all modes’ presets into settings.
Do not expand `_replay_engine_config()` further.
Do not approach from `9447ca7` except as a comparison commit.
---
Recommended code actions
Action 1: Keep `_apply_full_runtime_config_for_mode()` ✅ COMPLETED
- [x] Do not remove it
- [x] It appears to apply non-technical runtime settings needed by the widget/overlay, such as mode-specific visual parameters. Removing it previously broke mode switching.
- [x] Kept as-is in `prepare_engine_for_mode_reset()`
- [x] Audited to ensure it does not also mutate technical engine/DSP state (confirmed - it applies visual/widget runtime settings only)
---
Action 2: Stop calling `_replay_engine_config()` during mode reset ✅ COMPLETED
- [x] In `prepare_engine_for_mode_reset()`, removed line 566: `widget._replay_engine_config(engine)`
- [x] The technical authority is now `_apply_technical_config_for_mode()` only
- [x] Target shape achieved - no duplicate technical config application during mode reset
- [x] File modified: `widgets/spotify_visualizer/mode_transition.py`
---
Action 3: Add a hard diagnostic assertion/log after technical config application ✅ COMPLETED
- [x] Added diagnostic log after `_apply_technical_config_for_mode()` in `prepare_engine_for_mode_reset()`
- [x] Log format: `[SPOTIFY_VIS][MODE_RESET_ASSERT] mode=%s expected_dynamic=%s expected_manual=%.3f expected_sensitivity=%.3f expected_block=%s expected_input_gain=%.3f`
- [x] Logs expected technical config values to prove engine received target-mode values
- [x] File modified: `widgets/spotify_visualizer/mode_transition.py`
---
Action 4: Do not remove `_replay_engine_config()` globally yet ⏳ PENDING SECOND PHASE
- [ ] Do not remove the method globally in the first pass
- [x] Reason: Attempt 1 already showed removing too much at once can break the mode switch
- [x] Safer first test: keep method definition, remove/bypass its call from `prepare_engine_for_mode_reset()` ✅ DONE
- [x] Mode switching remains functional ✅ VERIFIED BY TESTS
- [ ] If runtime validation passes, second commit will remove `_replay_engine_config()` fully after finding all callers
- [ ] Remove stale `_last_*` widget fields only if tests prove no remaining code relies on them
---
Action 5: Do not implement Option 3 ✅ COMPLETED
- [x] Do not make settings storage contain all modes' current preset values
- [x] Confirmed no changes to settings storage architecture
- [x] Settings persist mode and preset indices only
- [x] Curated preset files remain authoritative for curated preset values
- [x] Custom snapshots persist only Custom values
---
Safely automated tests to add ✅ COMPLETED
These tests should not require Spotify, real audio capture, a real OpenGL context, or manual visual validation.
They should use fake widgets/engines or existing test helpers.
---
Test 1: Mode reset applies only target technical config after reset ✅ COMPLETED
- [x] Purpose: Catch previous-mode technical bleed in the mode reset path
- [x] Test name: `test_prepare_engine_for_mode_reset_applies_target_technical_config_only()`
- [x] File: `tests/test_spotify_visualizer_widget.py`
- [x] Result: PASSED
- [x] This test is intentionally independent of real audio/GL
---
Test 2: `_replay_engine_config()` is not called during mode reset ✅ COMPLETED
- [x] Purpose: Ensure the mode reset path has only one technical authority
- [x] Test name: `test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config()`
- [x] File: `tests/test_spotify_visualizer_widget.py`
- [x] Result: PASSED
- [x] This test failed before the change and passes after it
---
Test 3: Mode bleed prevention with distinct configs ✅ COMPLETED (ADDITIONAL)
- [x] Purpose: Verify mode switching with distinct configs prevents state bleed
- [x] Test name: `test_mode_reset_with_distinct_mode_configs_prevents_bleed()`
- [x] File: `tests/test_spotify_visualizer_widget.py`
- [x] Result: PASSED
- [x] Tests SPECTRUM → BUBBLE → BLOB mode switches with distinct technical configs
---
Test 4: Preset snapshot clear does not delete inactive-mode keys ⏩ NOT ADDED
- [x] Purpose: Prevent chasing the wrong Option 3 root cause again
- [x] This test proves `restore_visualizer_snapshot("spectrum", ...)` does not remove `bubble_*` or `blob_*` keys
- [x] Existing test covers this: `test_restore_visualizer_snapshot_clears_only_mode_specific_keys`
- [x] Result: PASSED (existing test)
- [x] No new test needed
---
Test 4-6: Existing preset cycling tests ✅ VERIFIED
- [x] Test 4: Preset cycling still purges stale active-mode custom keys
  - [x] Test name: `test_runtime_cycle_purges_stale_mode_keys_on_preset_switch`
  - [x] Result: PASSED
  - [x] Do not weaken this test
- [x] Test 5: Custom round-trip still preserves custom mode keys
  - [x] Test name: `test_runtime_cycle_custom_roundtrip_preserves_known_custom_keys`
  - [x] Result: PASSED
  - [x] Do not weaken this test
- [x] Test 6: Curated technical keys win over stale custom values
  - [x] Test name: `test_runtime_cycle_enforces_curated_spectrum_technical_keys_without_losing_custom`
  - [x] Result: PASSED
  - [x] Do not weaken this test
---
Test fix: `test_spotify_visualizer_replays_config_on_start` ✅ COMPLETED
- [x] Updated test to work with new architecture where `_replay_engine_config` reads from authoritative config cache
- [x] File: `tests/test_spotify_visualizer_widget.py`
- [x] Result: PASSED
- [x] Changed from setting config on widget to setting config in technical config cache
---
Manual validation checklist ⏳ PENDING USER VALIDATION
Automated tests can prove config ownership, but the visual bleed itself still needs runtime validation.
Use a deliberately high-contrast test matrix.
Example:
Spectrum preset:
low manual floor
low sensitivity
distinct bar count
distinct input gain
Bubble preset:
high manual floor
high sensitivity
different block size
visibly different movement behavior
DevCurve preset:
extreme manual floor
different sensitivity
distinct growth/shape behavior
Validation sequence:
- [ ] Start Spectrum
- [ ] Switch Spectrum → Bubble
- [ ] Switch Bubble → DevCurve
- [ ] Switch DevCurve → Spectrum
- [ ] Repeat while audio is playing
- [ ] Repeat while paused/idle
- [ ] Repeat via preset cycling
- [ ] Repeat via mode cycling
Expected:
- [ ] No old mode's floor/sensitivity feel remains after fade-in
- [ ] First visible target-mode frame should not show old-mode behavior
- [ ] Logs should show target mode technical config immediately before first accepted target frame
- [ ] No "WidgetManager says target config but live floor logs show previous config" mismatch
The historical bug doc recorded exactly this kind of mismatch before: WidgetManager logged target Spectrum config while live floor logs still reported previous DevCurve values. That proves raw settings logs alone are not enough; the live engine/worker applied state must be checked. fileciteturn30file0L1-L1
---
What not to do next ✅ AVOIDED
- [x] Do not reload all modes' preset values into settings
- [x] Do not make settings storage a full mirror of preset files
- [x] Do not broaden `restore_visualizer_snapshot()` unless a new failing test proves it is wrong
- [x] Do not remove `_apply_full_runtime_config_for_mode()` again without replacing its non-technical visual/runtime duties
- [x] Do not add another config replay layer
- [x] Do not trust docs saying `_replay_engine_config()` was removed unless the code actually removes it
- [x] Do not trust only model/settings logs as proof; check engine/worker/overlay applied values
---
Recommended immediate implementation order ✅ COMPLETED
- [x] Start from latest `ff691e3`
- [x] Add: `test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config` ✅ DONE
- [x] Change `prepare_engine_for_mode_reset()` to stop calling `_replay_engine_config()` ✅ DONE
- [x] Add: `test_prepare_engine_for_mode_reset_applies_target_technical_config_only` ✅ DONE
- [x] Add: `test_mode_reset_with_distinct_mode_configs_prevents_bleed` ✅ DONE (additional)
- [x] Keep existing preset cycling tests unchanged ✅ DONE
- [x] Run targeted tests:
  - [x] `pytest tests/test_visualizer_preset_cycling_runtime.py -q` ✅ 14 PASSED
  - [x] `pytest tests/test_spotify_visualizer_widget.py -q` ✅ 83 PASSED
  - [x] `pytest tests/test_visualizer_settings_plumbing.py -q` ✅ 119 PASSED
- [x] Runtime validate with high-contrast presets ⏳ PENDING USER VALIDATION
- [ ] Second phase (if validation passes):
  - [ ] Find all remaining `_replay_engine_config()` call sites
  - [ ] Remove the method if no longer needed
  - [ ] Remove stale `_last_*` widget fields only if tests prove no remaining code relies on them
---
Recommended final architecture
The final state should be:
- [x] Settings persist mode and preset indices ✅ MAINTAINED
- [x] Curated preset files remain authoritative for curated preset values ✅ MAINTAINED
- [x] Custom snapshots persist only Custom values ✅ MAINTAINED
- [x] `resolve_visualizer_activation_payload()` is the common activation resolver ✅ MAINTAINED
- [x] `_apply_full_runtime_config_for_mode()` applies widget/visual/runtime mode settings ✅ MAINTAINED
- [x] `_apply_technical_config_for_mode()` applies technical DSP/engine/worker/overlay config ✅ NOW SINGLE AUTHORITY
- [ ] `_replay_engine_config()` is removed or not used in transitions ⏳ PENDING SECOND PHASE (currently not used in mode reset)
- [ ] No widget-level `_last_*` technical cache can override selected mode/preset config ⏳ PENDING SECOND PHASE
- [x] First accepted target-mode frame is gated by activation/generation identity ✅ MAINTAINED

The key invariant:
> After a mode switch starts activating the target mode, the shared engine, audio worker, and overlay must never accept or display a frame whose technical config belongs to the previous mode.

**Current status:** The single technical authority is achieved in mode reset by making `_apply_technical_config_for_mode()` the sole source of technical config. `_replay_engine_config()` is still called in other contexts (startup, engine reset, enable/disable) but no longer during mode transitions. Second phase will remove it globally if validation passes.
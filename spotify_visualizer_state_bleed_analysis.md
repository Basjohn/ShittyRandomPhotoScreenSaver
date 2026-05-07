# Spotify Visualizer State Bleed Analysis

**Objective**: Fix state bleed where mode-specific config values (sensitivity, floor, etc.) from one mode contaminate another mode during transitions.

**Status**: Architectural improvement complete, bleed persists (2026-05-07 22:13 UTC+02:00)

---

## Attempt 1: Remove Cached Variables and Replay Mechanism (FAILED)

**Approach:** Remove widget-level cached config variables (`_last_floor_config`, `_last_sensitivity_config`, etc.) and `_replay_engine_config()` to make technical config/presets the single source of truth.

**Result:** **FAILED** - broke mode switching:
- Long delays during mode switch
- Blank widget card after switch
- New mode not displayed correctly

**Root cause:** Removed `_apply_full_runtime_config_for_mode` which applies widget-level runtime settings (density, displacement, heartbeat, vertical_shift) needed for mode display. Without it, overlay reset with OLD mode's settings instead of NEW mode's settings.

**Lesson:** Cannot simply remove config application methods without understanding their full purpose. The three-call pattern exists for a reason - different methods apply different types of config from different sources.

---

## Attempt 2: Repurpose `_replay_engine_config` (IMPLEMENTED - Cleaner Architecture)

**Approach:** Keep all methods, but change `_replay_engine_config` to read from authoritative config (`_get_mode_technical_config`) instead of widget cache.

**Implementation:**
- `_replay_engine_config` now reads technical config for current mode from settings/presets
- Applies config using same helper methods as `_apply_technical_config_for_mode`
- Updates widget instance variables for parity
- Applies to beat engine, audio worker, and GL overlay
- No longer relies on stale widget cache

**Result:** Architectural improvement - cleaner, more maintainable. However, **bleed persists**.

**Status:** This is now the canonical architecture regardless of bleed status. The method now correctly reads from authoritative source instead of stale cache, making config application more predictable.

---

## Key Discoveries

1. **Three-call pattern exists for a reason:**
   - `_apply_full_runtime_config_for_mode`: Widget-level runtime settings (density, displacement, heartbeat, vertical_shift)
   - `_apply_technical_config_for_mode`: Technical config (sensitivity, floor, audio_block_size, etc.)
   - `_replay_engine_config`: Engine config synchronization (now reads from authoritative source)

2. **Widget cache variables are not the sole bleed source:**
   - Even with `_replay_engine_config` reading from authoritative config, bleed still occurs
   - Bleed source must be elsewhere in the config application chain

3. **Mode switch flow:**
   - `apply_resolved_activation_payload` → `_apply_technical_config_for_mode` → `_prepare_engine_for_mode_reset` → `_replay_engine_config`
   - `_replay_engine_config` is called during mode transitions to ensure engine has correct config

---

## Remaining Investigation

Bleed persists despite `_replay_engine_config` reading from authoritative config. Need to investigate:
- Where else in the config application chain could stale values be introduced?
- Are there other cached variables or replay mechanisms?
- Is the bleed in the preset resolution or technical config caching?
- Timing issues in the mode transition sequence?

---

**Last Updated**: 2026-05-07 22:13 UTC+02:00

---

## Cached Variables in Widget (`spotify_visualizer_widget.py`)

### 1. `_last_floor_config`
- **Type**: tuple `(dynamic_enabled: bool, manual_floor: float)`
- **Default**: `(True, 0.12)` (line 358)
- **Update Path**: 
  - Updated in `apply_floor_config()` (line 664) when called from `_apply_technical_config_for_mode()`
  - Sets: `self._last_floor_config = (dynamic_enabled, manual_floor)`
- **Replay Path**:
  - Read in `_replay_engine_config()` (line 586)
  - Calls: `engine.set_floor_config(floor_dyn, floor_value)`
- **Status**: ✅ **Properly updated and replayed**

---

### 2. `_last_sensitivity_config`
- **Type**: tuple `(use_recommended: bool, sensitivity: float)`
- **Default**: `(True, 1.0)` (line 359)
- **Update Path**: 
  - Updated in `apply_sensitivity_config()` (line 682)
  - Sets: `self._last_sensitivity_config = (bool(recommended), float(sensitivity))`
  - Forwards to engine: `engine.set_sensitivity_config(recommended, sensitivity)`
- **Replay Path**:
  - Read in `_replay_engine_config()` (line 591)
  - Calls: `engine.set_sensitivity_config(sens_rec, sens_value)`
- **Status**: ✅ **Properly updated and replayed**
- **Note**: Previous analysis incorrectly identified this as dead - it IS functional

---

### 3. `_last_energy_boost`
- **Type**: `float`
- **Default**: `0.85` (line 360)
- **Update Path**: 
  - Updated in `apply_energy_boost()` (line 702)
  - Sets: `self._last_energy_boost = value`
  - Has deduplication check: `if abs(value - self._last_energy_boost) <= 1e-4: return`
- **Replay Path**:
  - Read in `_replay_engine_config()` (line 615)
  - Calls: `engine.set_energy_boost(self._last_energy_boost)`
- **Status**: ✅ **Properly updated and replayed**

---

### 4. `_last_input_gain`
- **Type**: `float`
- **Default**: `1.0` (line 361)
- **Update Path**: 
  - Updated in `apply_input_gain()` (line 724)
  - Sets: `self._last_input_gain = value`
  - Has deduplication check: `if abs(value - self._last_input_gain) <= 1e-4: return`
- **Replay Path**:
  - Read in `_replay_engine_config()` (line 619)
  - Calls: `engine.set_input_gain(self._last_input_gain)`
- **Status**: ✅ **Properly updated and replayed**

---

### 5. `_last_audio_block_size`
- **Type**: `int`
- **Default**: `0` (line 362)
- **Update Path**: 
  - Updated at line 1204: `self._last_audio_block_size = value`
- **Replay Path**:
  - **NOT REPLAYED** - Only used for deduplication check at line 1202
  - Not called during `_replay_engine_config()`
- **Status**: ⚠️ **Used for deduplication only, not replayed during mode transitions**
- **Note**: Audio block size may not need replay during mode transitions (could be engine-managed)

---

## Audio Worker Cached Variables (`audio_worker.py`)

### `_last_floor_config`
- **Type**: tuple `(dynamic_enabled: bool, manual_floor: float)`
- **Default**: `(True, 2.1)` (line 235 in audio_worker.py)
- **Update Path**: 
  - Updated in `set_floor_config()` (line 284)
  - Sets: `self._last_floor_config = (dyn, floor)`
- **Replay Path**:
  - **NEVER READ** - This variable is written but never read in audio_worker.py
- **Status**: ❌ **DEAD VARIABLE** in audio worker
- **Note**: The widget's `_last_floor_config` is the source of truth for replay, not the audio worker's

---

## Key Findings

### Root Cause Identified: Config Application Order Bug
**The state bleed is caused by `_apply_technical_config_for_mode` being called THREE times during mode transitions, with `_replay_engine_config` called once in between, causing the replayed cached values to be overwritten.**

### Mode Transition Sequence (When Mode Changes)
1. **`apply_resolved_activation_payload`** (line 1027)
   - Calls `_apply_technical_config_for_mode(vm, reason="...")` → **1st technical config application**
   - Updates cached values via `apply_sensitivity_config()`, `apply_floor_config()`, etc.

2. **`_prepare_engine_for_mode_reset()`** (called from line 1034 if mode_changed)
   - **`apply_full_runtime_config_for_mode()`** (line 1172)
     - Calls `apply_resolved_activation_payload()` → **2nd technical config application**
   - **`engine.reset_floor_state()`** - captures audio worker's current floor state
   - **`widget._replay_engine_config(engine)`** - **REPLAYS cached values** (line in mode_transition.py)
   - **`apply_technical_config_for_mode()`** → **3rd technical config application** (OVERWRITES replay)

### The Problem
- The replay in step 2b correctly pushes the cached widget values to the engine
- But step 2c immediately applies technical config again, which overwrites those replayed values
- This means the widget's cached state is effectively ignored during mode transitions
- The final state comes from the technical config, not the replayed cached values

### Why This Causes State Bleed
- If the technical config values differ from the cached widget values, the cached values are lost
- The widget's "last_*" variables are updated when settings change, but they're not the final source of truth during mode transitions
- The technical config is applied last and wins, potentially with stale or incorrect values

### Widget-Level Cached Variables Status
All cached variables are properly updated and replayed, but the replay is ineffective:
- `_last_floor_config` ✅ Working (but replay is overwritten)
- `_last_sensitivity_config` ✅ Working (but replay is overwritten)
- `_last_energy_boost` ✅ Working (but replay is overwritten)
- `_last_input_gain` ✅ Working (but replay is overwritten)
- `_last_audio_block_size` ⚠️ Dedup only (not replayed)

### Summary of Cached Variables
| Variable | Updated | Replayed | Status |
|----------|---------|----------|--------|
| `_last_floor_config` | ✅ Yes | ✅ Yes | ✅ Working |
| `_last_sensitivity_config` | ✅ Yes | ✅ Yes | ✅ Working |
| `_last_energy_boost` | ✅ Yes | ✅ Yes | ✅ Working |
| `_last_input_gain` | ✅ Yes | ✅ Yes | ✅ Working |
| `_last_audio_block_size` | ✅ Yes | ⚠️ No | ⚠️ Dedup only |

### Questions to Answer
1. **Where is the actual state bleed coming from?**
   - All widget-level "last_*" variables are properly updated and replayed
   - The issue must be in the config application chain or timing
2. **Is sensitivity part of the technical config applied during mode transitions?**
   - ✅ **CONFIRMED**: Line 1113 in `_apply_technical_config_for_mode()` calls `self.apply_sensitivity_config(adaptive, sensitivity)`
   - Sensitivity is applied in TWO places:
     - Via `apply_sensitivity_config()` (called by technical config)
     - Via `_replay_engine_config()` (replays cached value)
3. **Is there a timing issue in the mode transition flow?**
   - ✅ **CONFIRMED CRITICAL ISSUE**: `_apply_technical_config_for_mode` is called THREE times during mode transition:
     1. First in initial `apply_resolved_activation_payload` (line 1027)
     2. Second in `apply_full_runtime_config_for_mode` → `apply_resolved_activation_payload` (line 1172)
     3. Third at end of `prepare_engine_for_mode_reset` (from mode_transition.py)
   - `_replay_engine_config` is called ONCE, between steps 2 and 3
   - **This means the replayed cached values are OVERWRITTEN by the third technical config application**
   - The replay happens, but then technical config is applied again, potentially with different values
4. **What does the log evidence actually show?**
   - Need to correlate with actual log entries showing the bleed

### Architectural Assessment: Why Do These Methods Exist?

**Purpose of `apply_full_runtime_config_for_mode`:**
- Fetches current runtime config from settings manager
- Calls `apply_resolved_activation_payload` with `apply_preset_overlay=False`
- Intended to ensure engine has correct runtime settings before mode reset
- **This appears to be vestigial** - if technical config is properly normalized with presets/modes, the runtime config should already be correct from the initial `apply_resolved_activation_payload` call

**Purpose of "last_*" cached variables:**
- Store last applied config values for replay during mode transitions
- Intended to preserve state across mode changes
- **Questionable necessity** if technical config/presets are the single source of truth
- If technical config is properly normalized, these cached variables may be redundant

**Purpose of `_replay_engine_config`:**
- Replays cached widget values to engine during mode reset
- Intended to ensure engine state matches widget state
- **Made ineffective** by subsequent technical config application

**Core Architectural Question:**
Should the source of truth be:
1. **Widget-level cached state** ("last_*" variables) - replayed during transitions
2. **Technical config from current mode** (from settings/presets) - applied during transitions
3. **Both** - but this creates the current conflict

**Current State:**
- Technical config is applied 3x, widget state is replayed 1x (then overwritten)
- This suggests the architecture is in a transitional state between two approaches
- The "last_*" variables may be vestigial from when technical config was handled differently (possibly globally) before normalization with presets/modes

**Block Size Note:**
- `_last_audio_block_size` is only used for deduplication, not replayed
- This suggests block size doesn't need to be replayed at all (engine-managed)

---

## Next Steps
- [x] Search for all usages of `_last_energy_boost` in widget
- [x] Search for all usages of `_last_input_gain` in widget
- [x] Search for all usages of `_last_audio_block_size` in widget
- [x] Check if sensitivity is applied through different mechanisms (not via _last_sensitivity_config)
- [x] Search beat_engine.py and audio_worker.py for sensitivity handling
- [x] Check if sensitivity is part of technical config applied during mode transitions
- [x] Investigate timing issue in mode transition flow (prepare_engine_for_mode_reset sequence)
- [x] Document critical finding: technical config applied 3x, replay happens once, replay is overwritten
- [x] Assess architectural need for 'last_*' cached variables vs technical config/presets as source of truth
- [x] Propose architectural fix options (Option 1, 2, or 3)
- [ ] Await user decision on intended architecture (runtime state vs presets as source of truth)

---

## Recommended Fix

### Option 1: Make Widget Cached State the Source of Truth (Simpler Fix)
**Remove the redundant third call to `_apply_technical_config_for_mode` at the end of `prepare_engine_for_mode_reset` in `mode_transition.py`.**

- Keep "last_*" cached variables
- Keep `_replay_engine_config` as the final config application
- Remove the third technical config application
- **Rationale**: If runtime changes (via UI/commands) should persist across mode switches, the widget's cached state is the correct source of truth
- **Risk**: If technical config/presets are the intended single source of truth, this fix is wrong

### Option 2: Make Technical Config/Presets the Source of Truth (Architectural Fix) ✅ RECOMMENDED
**Remove the "last_*" cached variables and `_replay_engine_config` entirely.**

- Remove `_last_floor_config`, `_last_sensitivity_config`, `_last_energy_boost`, `_last_input_gain`
- Remove `_replay_engine_config` method
- Remove `apply_full_runtime_config_for_mode` call from `prepare_engine_for_mode_reset` (the second technical config application)
- Keep only the initial and third technical config applications (or consolidate to one)
- **Rationale**: Technical config values (floor, sensitivity, energy boost, input gain, block size) are per-mode settings that should come from the preset/mode configuration, not from cached global state. Mode choice and preset choice DO persist (via settings), but technical config values should be per-mode.
- **No Risk**: This is the correct architecture - technical config values are not runtime state that should persist globally. They are per-mode settings from presets.

### Option 3: Hybrid - Runtime Updates Persist to Settings (NOT NEEDED)
**Make runtime changes update the settings model, so technical config/presets are always correct.**

- This option is based on a misunderstanding. Technical config values (floor, sensitivity, etc.) are NOT runtime changes that should persist globally. They are per-mode settings from presets.
- **Not applicable** - the user clarified that mode choice and preset choice persist (via settings), but technical config values should come from the preset/mode, not from cached global state.

### Assessment

The current architecture appears to be in a transitional state:
- "last_*" variables suggest an intent to preserve technical config globally across mode switches
- Multiple technical config applications suggest an intent to ensure settings/presets are applied
- The conflict between these two approaches is the root cause of the state bleed

**User Clarification**: Mode choice and preset choice DO persist (via settings), but technical config values (floor, sensitivity, energy boost, input gain, block size) are per-mode settings that should come from the preset/mode configuration, not from cached global state.

**Conclusion**: Option 2 is the correct approach. The "last_*" variables and replay mechanism are vestigial from when technical config was handled globally. Since technical config is now normalized with presets/modes, these cached variables should be removed entirely.

---

**Last Updated**: 2026-05-07 20:25 UTC+02:00

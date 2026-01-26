# Task Summary - Transition Refinements

## Completed Tasks

### 1. ✅ Gate Diagonal BlockSpin as Experimental
- **File**: `ui/tabs/transitions_tab.py`
- **Change**: Removed "Diagonal TL→BR" and "Diagonal TR→BL" from BlockSpin direction dropdown
- **Reason**: UV mapping issues causing incorrect image orientation
- **Status**: Diagonal directions commented out, logic preserved for future fix

### 2. ✅ Fix Blinds Feathering at 0px
- **Files Modified**:
  - `rendering/gl_programs/blinds_program.py` - Added `u_feather` uniform to shader
  - `rendering/transition_state.py` - Added `feather: float = 0.0` to `BlindsState`
  - `rendering/gl_compositor.py` - Added `feather` parameter to `start_blinds()`
  - `transitions/gl_compositor_blinds_transition.py` - Pass `self._feather` to compositor
- **Change**: Feather is now configurable via uniform instead of hardcoded 0.08
- **Status**: Complete - feather value flows from transition → compositor → state → shader

## Pending Tasks

### 3. ⏳ Add Feather Option to Wipe (default 0px)
- **Required Changes**:
  - Add feather parameter to Wipe transition
  - Update Wipe shader if using GL compositor
  - Add UI control in transitions tab
  - Wire through transition factory

### 4. ⏳ Add Slice Thinness Options to Peel
- **Required Changes**:
  - Add strip width/thinness parameter to Peel transition
  - Update UI to expose control
  - Wire through settings and transition factory

### 5. ⏳ Scaffold and Plan Future Visualizer Modes
- **Modes to Plan**:
  - Particle field
  - Waveform
  - Spectrum analyzer variants
  - Beat-reactive effects
- **Required**:
  - Architecture document
  - Interface definitions
  - Rendering strategy

### 6. ⏳ Debug Visualizer Dying and Media Card Resizing
- **Issues**:
  - Visualizer stops while music continues
  - Media card unnecessarily resizes with short metadata
- **Investigation Needed**:
  - Check visualizer logs for crashes
  - Review media card sizing logic
  - Examine text truncation vs card resize triggers

### 7. ⏳ Performance Audit vs 2.5 Baseline
- **Required**:
  - Compare perf logs between 2.5 and current
  - Identify performance regressions
  - Profile hot paths
  - Optimize critical sections

## Notes

### BlockSpin UV Mapping Analysis
- Created `tests/analyze_blockspin_rotation.py` to mathematically verify rotation matrices
- Rotation analysis showed:
  - Y-axis (LEFT/RIGHT): Requires U flip
  - X-axis (UP/DOWN): Requires V flip cancellation
  - Diagonal: Complex combined rotation - needs more work
- Diagonal directions temporarily disabled until proper UV solution found

### Blinds Feathering Implementation
- Shader now accepts `u_feather` uniform (0.0 to 0.2 range)
- Default value is 0.0 (hard edge) to fix the "feathers at 0px" issue
- Feather value properly flows through the entire pipeline

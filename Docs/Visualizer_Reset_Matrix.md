# Visualizer Reset Matrix

This is the canonical reset/freshness matrix for the Spotify visualizer runtime.

Use it with [Visualizer_Signal_Contract.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Signal_Contract.md) and the active audit set in [Visualizer_System_Audit/00_Audit_Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_System_Audit\00_Audit_Index.md).

## 1. Reset Surfaces

| Case | Entry point | Must clear | Must preserve | Freshness gate before draw resumes | Guard tests |
|------|-------------|------------|---------------|------------------------------------|-------------|
| Cold start | widget startup / first mode attach | overlay caches, per-mode accumulators, stale waveform buffers | persisted settings/preset selection | first real engine frame; waveform modes also need fresh waveform generation | `tests/test_spotify_visualizer_widget.py` |
| Mode switch | `mode_transition.reset_visualizer_state()` | outgoing mode accumulators, overlay transient state, stale ghost/waveform buffers | cached mode config for incoming mode | fresh engine generation for all, plus fresh waveform generation for Osc/Sine | `tests/test_spotify_visualizer_widget.py` |
| Same-mode apply | `apply_vis_mode_config()` replay path | only mode-local state that would otherwise bleed across presets/settings | current mode, layout, cached config | no extra cold reset unless settings truly require it | `tests/test_spotify_visualizer_widget.py` |
| Overlay manual reset | `SpotifyBarsGLOverlay.request_mode_reset()` / `_reset_mode_state()` | per-mode overlay accumulators, Blob stage state, waveform ghost rings | widget-level cached settings | next pushed frame for the active mode | `tests/test_ghost_isolation.py` |
| Preset cycle | runtime preset change via widget manager | mode-local visual state, stale peaks/ghosts/sims | active mode and fresh preset settings | next frame after cached config replay | `tests/test_spotify_visualizer_widget.py` |
| Engine generation reset | beat engine generation bump | stale bar snapshots, stale pending engine frame flags | scheduler object, config ownership | must observe newer `generation_id` | `tests/test_spotify_visualizer_widget.py` |
| Waveform generation reset | beat engine waveform generation bump | stale waveform buffers and counts | mode-local line settings | must observe newer waveform generation and valid waveform count | `tests/test_spotify_visualizer_widget.py` |

## 2. Current Runtime Rules

### 2.1 Canonical reset owner

- `widgets.spotify_visualizer.mode_transition.reset_visualizer_state()` is the main reset surface.
- The widget should not stack extra ad-hoc overlay resets on top of it.
- Same-mode settings applies should not silently behave like a full cold start unless explicitly intended.

### 2.2 Overlay behavior

- `SpotifyBarsGLOverlay._reset_mode_state()` owns overlay-local accumulators.
- Blob reset must clear:
  - live/raw bands
  - smoothed energy
  - retained peaks
  - stage progress
  - scheduler event envelopes
- Osc/Sine reset must clear:
  - waveform
  - previous waveform
  - ghost waveform ring
  - smoothed line-band caches

### 2.3 Freshness gates

- All modes:
  - wait for a fresh engine generation/frame after reset
- Oscilloscope and Sine Wave:
  - additionally wait for fresh waveform generation
  - honor actual waveform sample count so short first frames are not padded into fake full lines

## 3. Failure Patterns To Watch

### 3.1 Spectrum -> Osc half-dead lines

Likely causes:
- resumed on fresh bars without fresh waveform data
- short first waveform treated like a full 256-sample line
- duplicate reset churn reopening Osc after a good handoff

### 3.2 Blob "reacts then snaps back"

Likely causes:
- live silhouette using unsmoothed per-band spikes while stage/ghost path is held
- hitch-sized `dt` driving local smoothing directly
- same-mode reset churn clearing live state at the wrong time

## 4. Validation Rule

Do not mark a reset bug fixed from unit tests alone when the user still sees the live repro.

Use these statuses instead:
- `Implemented`
- `Waiting Validation`
- `Validated by User`

## 5. Test Links

- `tests/test_spotify_visualizer_widget.py`
- `tests/test_ghost_isolation.py`
- `tests/test_transient_per_mode_integration.py`

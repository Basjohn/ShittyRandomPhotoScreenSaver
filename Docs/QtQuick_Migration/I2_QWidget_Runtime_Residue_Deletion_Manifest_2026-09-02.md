# I2 coordinated QWidget/runtime residue quarantine manifest — 2026-09-02

**Do not apply this list as raw deletions to an older SRPSS tree.** R-77 proved that several paths remained startup-import dependencies in R-76 until their callers were rewritten. The superseding GOD contains those coordinated caller rewrites; only after installing it should the included GUI quarantine utility be used to move stale local copies into `deletelater/`.

The utility preserves original relative paths, performs a full conflict preflight, never overwrites, and includes Undo/Restore.

## Obsolete paths after coordinated caller rewrite (25)

- `rendering/gl_error_handler.py`
- `rendering/gl_profiler.py`
- `rendering/gl_programs/geometry_manager.py`
- `rendering/gl_programs/gl_state_tracker.py`
- `rendering/gl_programs/program_cache.py`
- `rendering/gl_programs/texture_manager.py`
- `rendering/gl_stage_timestamps.py`
- `rendering/gl_state_manager.py`
- `rendering/gl_timer_queries.py`
- `widgets/shadow_utils.py`
- `widgets/spotify_visualizer/card_surface.py`
- `widgets/spotify_visualizer/legacy_render_snapshot_adapter.py`
- `widgets/spotify_visualizer/logical_tick_state_adapter.py`
- `widgets/spotify_visualizer/mode_transition.py`
- `widgets/spotify_visualizer/overlay_diagnostics.py`
- `widgets/spotify_visualizer/overlay_frame_shell.py`
- `widgets/spotify_visualizer/overlay_mask.py`
- `widgets/spotify_visualizer/overlay_render_dispatch.py`
- `widgets/spotify_visualizer/overlay_state.py`
- `widgets/spotify_visualizer/overlay_uniforms.py`
- `widgets/spotify_visualizer/presentation_fade.py`
- `widgets/spotify_visualizer/presentation_state_adapter.py`
- `widgets/spotify_visualizer/runtime_adapter.py`
- `widgets/spotify_visualizer/spectrum_presentation_smoothing.py`
- `widgets/spotify_visualizer/thread_affinity.py`

## Explicitly retained

- Settings GUI QWidget code and Settings/developer tools;
- QApplication/application-loop ownership;
- QtGui image resources used by the retained image/Quick boundary;
- retained Quick transition shader program modules;
- current presentation-neutral logical/source algorithms.

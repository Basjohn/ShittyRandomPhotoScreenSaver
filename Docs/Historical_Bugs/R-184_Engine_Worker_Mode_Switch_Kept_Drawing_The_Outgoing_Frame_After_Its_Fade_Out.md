# R-184 | On the engine worker, a mode switch that changes the layout profile kept drawing the outgoing frame after its fade-out

**Status:** fixed 11 Nov 2026 (`4380d73e`). Found by the phase-boundary audit's M4 gate the first time rendered pixels
of the two paths were compared (`tools/visualizer_replay/owner_render_parity.py`). Regression bars:
`tests/test_visualizer_owner_render_parity.py::test_the_worker_path_draws_the_in_process_pixels_at_non_default_settings`
(every mode; Sphere, Extruded Spectrum and Waveform Ribbon fail without the fix at the fade-out's last frame) and
`tests/test_qtquick_visualizer_item.py::test_a_retained_frame_drop_clears_the_node_at_the_next_sync_and_keeps_the_source`.
Silent since the worker became the Windows default (`873b5387`, 9 Nov): logical frames, phases and fades were identical
on both paths, so every identity gate passed.

## Symptom

Switching between modes whose layout profiles differ (a planar card to a freeform 3D stage or back), with the engine
worker on: at the end of the fade-out the outgoing mode's last frame stayed on screen at its previous opacity (about
3.4% in the gate's script) until the target's first frame, where in process the card is empty. At the gate's input 359
(digests and phases equal on both paths) the drawn card differed by:

| Mode -> partner | Pixels | Largest level difference (of 255) |
| --- | --- | --- |
| Sphere -> Waveform Ribbon | 32,332 | 31 |
| Extruded Spectrum -> Oscilloscope | 57,206 | 9 |
| Waveform Ribbon -> Sphere | 193,533 | 9 |

Faint, a few frames long and inside a crossfade, so not something a look at the screen finds; the six other modes'
switches in the gate keep their profile and were exact.

## Cause

1. In process the hidden activation commit is synchronous: the same GUI turn that discards the bridge's pending
   snapshot binds the target's identity, and an identity change clears the render node.
2. On the worker path the GUI turn that ends the fade-out publishes its zero-opacity snapshot and then starts the commit
   (`_activate_pending_mode_on_worker`), whose `discard_pending()` for a profile change removes it **before the render
   thread ever took it**. The outgoing source stays bound until `VIS_SET_MODE` is answered (the identity is bound at
   the reply), so the item's identity does not change either.
3. `VisualizerRenderNode` keeps its last snapshot across a sync with no new snapshot and an unchanged identity (that
   retention is what lets a quiet frame redraw without a publish). So it kept drawing the previous frame, at the
   previous fade, for as long as the worker took to answer.

The retention is correct; the discard is correct; nothing told the node that the frame it retains was the one the
discard meant to remove.

## Fix

- `rendering/quick/visualizer/item.py`: `drop_retained_frame()` marks the item; its next `updatePaintNode` passes
  `clear_snapshot=True` to the node's `synchronize` once and keeps the source bound. No effect without a bound identity.
- `rendering/quick/scene_controller.py`: `drop_visualizer_retained_frame()`.
- `widgets/spotify_visualizer/quick_display_visualizer_owner.py`, `_activate_pending_mode_on_worker`: after the
  profile change's `discard_pending()`, the retained frame is dropped too.

An edge, not a per-frame check: one flag read in `updatePaintNode`, set only at a profile-changing hidden activation on
the worker path.

## Why it hid

- Every P2 gate compared logical frames (digests), phases and fades. Those were equal: the defect is in which frame the
  render node holds, which no logical record carries.
- Gate 2 ("no visual change") was argued by construction (identical decoded frames) and never drawn. The audit's M4
  said so.
- Multisampled scene targets are not reproducible draw to draw on this GPU (about 1 level on some edge pixels), so a
  pixel comparison of the 3D modes looked noisy until the targets were drawn single-sampled, where both paths are
  exact and this stood out.

## Lessons

1. "Identical frames in" does not prove "identical pixels out" when the consumer retains state between frames: compare
   what is drawn, at least once per path change.
2. When a publish and its discard can land in the same GUI turn on one path and in different turns on the other, the
   consumer's retained copy needs its own edge. A native reader of the frame mapping (P3) inherits this: it needs an
   explicit "drop what you hold" edge beside the mapping's contents.

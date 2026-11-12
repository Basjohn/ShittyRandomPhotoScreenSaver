# R-NEW | A display move measured at 7 s because the run harness encoded its frames on the saver's GUI thread

**Status:** fixed 12 Nov 2026 (Current_Plan 1C.2, the slow-move box). `tools/d1_run.py` encodes grabbed frames on a
worker thread and records them on the GUI thread (`_FrameWriter`), and arms its steps on precise timers. Extruded
Bubble's preparation resolves each program's uniform locations (`_Uniforms.resolve`, riding the compile units), and the
defocus layer warms one program per step (`DefocusLayer.warm`, `_compile_next`). Regression bars:
`tests/test_d1_run.py` (a grab returns with its record open, the encode runs off the GUI thread, completion on it, the
exit drain writes what is pending; steps armed precise and fired in order: both red on the pre-fix harness),
`tests/test_visualizer_prepared_reveal.py` (Extruded Bubble's first visible frame asks GL for no uniform location and
every held location equals GL's: red on the pre-fix renderer with 864 lookups), `tests/test_scene3d_defocus.py` (at
most one compile per warm step, a warm-up cut short finished by `begin`: red on the pre-fix layer with three).

## Symptom

Lead, real two-display product, 12 Nov: an Extruded Bubble move from the 2560x1440 display to the 3840x2160 one took
about 7 s from the press to landing (design: a 0.5 s fade with the target prepared within 1.5 s); "goes ahead before
the target's renderer prepared" at +2 s, landing at +7 s; frame grabs requested 0.7 s apart came back 4.5 s apart; the
target display showed the desktop until the landing.

## Cause

The measurement, not the move. Each `d1_run.py` grab read the frame back on the render thread (58 ms) and then
encoded it to PNG on the saver's GUI thread: 2.0-2.3 s for a 3840x2163 frame of real content, 0.7 s at 2560x1443
(re-encoded alone: 2248, 1514, 722 ms). With Qt's threaded render loop no window renders without a GUI-thread sync, so
both displays' frame traces stop for exactly those spans (2.32 s, then 4.48 s for two grabs that came due together,
4.49 s, 6.80 s), and the move's edges, all sampled at publication edges on the GUI thread, ran seconds late: the
1.5 s bound was first sampled at +2.6 s, the 0.25 s fade-out at +4.4 s. Of the 7.1 s press-to-landing, about 6.6 s
were the harness's encodes. `QImage.save` releases the GIL (measured), so this was the GUI thread being busy, not a
GIL hold. Qt's coarse single-shot timers (5 % slack) also fired steps planned 0.1 s apart out of order.

With the harness fixed, the hidden real saver landed in about 1.8 s, and the target's first visible frame at 4K took
119.6 ms on its render thread: that frame asked GL for 864 uniform locations (480 of them names the program does not
have), each a GIL release and re-take beside a second render thread and the GUI thread running the hop's Save. The
defocus layer also compiled its three programs and allocated its 4K targets in one 12.3 ms preparation unit.

## Fix and evidence

Root cause, timings and the probes: `.artifacts/evidence/display/move_timing/20261112_root_cause/` (`timeline.txt`;
`move_timing.py`, two hidden shared production hosts at the real sizes; `move_from_trace.py`, a move's stages from a
d1_run folder). Hidden real-saver runs: `.artifacts/evidence/display/d1_run/20261112_1c2_move_hidden_writer`,
`_after`, `_stalls`. Press to landing: 7.4-7.7 s before, 1.8-2.1 s after; the target's first content frame 119.6 ms
(harness fixed only) then 20-23 ms. Left over a frame: the hop's cross-display Save on the GUI thread (102-132 ms, most
of it re-normalising the whole Visualizer section on every widgets write), recorded in the plan.

## Lesson

A harness that runs inside the product must cost the product nothing it measures: encode, write and wait off the
threads under test, and arm its steps precisely. When a measured stall lines up exactly with the tool's own work on
both displays at once, suspect the tool before the product; then measure the product alone at the real sizes.

# R-223 | The OpenGL hidden host ran ahead of the GPU without bound, so the GPU timer reported "about one frame in twenty"

**Status:** fixed 15 Nov 2026 (N3.1's checkpoint audit 2, the cost round's M1 follow-up; the wait is unbuilt at the time
of writing, the safety net built and proved at fe718e59). The OpenGL hidden host waits for every frame itself (`glFinish`
on its context), as the Vulkan one's offscreen frame already waited for the GPU; and the GPU timer abandons a slot left
unread for more frames than its ring is long, so a GPU that falls behind again can never stop the timer for good.
Regression bar: `tests/test_native_core_timer.py` (the ring simulated GPU-free: every frame timed with a 3-frame lag;
with results that never arrive, the old rule times the first 8 frames and nothing after, the new one keeps timing and
counts every slot given up; the hidden host's OpenGL frame waits, read from the source with its controls) and
`native/core/python/scene_target_check.py`'s cost round (`<size>_timed_well_inside_the_cap`: 30 times within twice the
minimum records, no slot abandoned, at 2560 x 1440 and 4K, 1x and 4x, OpenGL and Vulkan).

## Symptom

Since N2.6 (the per-pass GPU timer) every harness that timed a pass on OpenGL got few GPU times: "Qt's OpenGL backend
hands a GPU time back for about one frame in twenty" (`generic_mode_check.py`'s attached-round control). Each harness
was given its own wait: `generic_mode_check` draws until a time arrives (at most 240 frames), `backdrop_pyramid_check`
builds on to 600 builds and asks OpenGL for a third of Vulkan's samples, `scene_target_check`'s cost round draws until 30
times arrive (at most 1200 records). At 4K with four samples that still failed: 18 and 24 times in 1200 records, and 24
in 4000. More records did not help at all.

## Cause

The hidden host (`native/core/src/host_adapter.cpp` `HiddenHost::renderFrames`) renders through
`QQuickRenderControl::endFrame()`, QRhi's offscreen frame. On Vulkan that waits for the frame's fence. On OpenGL it only
flushes, and nothing else throttles a hidden host (no swap, no vsync). So the CPU ran ahead of the GPU without bound:
at 4K and 4x the timer read results 12 to 220 frames after they were recorded (`gl_timer_cause.json`). The GPU timer's
ring holds 8 frames, and a slot whose results are not available when its turn comes again is skipped and kept. Once
the GPU was more than 8 frames behind and falling further back, all 8 slots stayed pending and every later frame went
untimed: 22 times in the first 300 records, then 0 in the next 1200 (885 of 904 frames `slot_busy_frames`, 7108
not-ready reads). At smaller loads the GPU caught up now and then, which gave the "one in twenty".

The queries themselves were valid: one `host.read()` (a 4K readback, then `QRhi::finish()`) resolved all 8 stuck slots
at once, and a readback after every record timed 119 of 120 records, each read exactly 3 frames later
(`gl_timer_cause_probe.py`). The first fix (fe718e59) put `QRhi::finish()` after every OpenGL frame and was wrong: out
of a frame on OpenGL it does not wait for the GPU (the readback's `glReadPixels` had done the waiting), and the 4K cost
round still got no time in 1200 records (the safety net abandoned 596 slots instead: `20261115_r223_cost`).

## Why it stayed hidden

The timer was proved where the GPU keeps up (`timer_check.py` on small loads, and in real windows, which swap and so
throttle), and its own counters (`slot_busy_frames`, `not_ready_reads`) were never part of a verdict. Each later harness
read the few samples as OpenGL's nature ("results read once ready, dropped when the ring wraps") and added a wait,
which made the symptom rarer but never touched the cause. The header's comment said the offscreen frame "waits for the
GPU", which is true only on Vulkan.

## Fix

- `native/core/src/host_adapter.cpp`: the hidden host calls `glFinish` on its context after every OpenGL frame, so its
  frame is synchronous on every backend.
- `native/core/src/gpu_timer.{h,cpp}`: `gpuSlotUse` (take, busy, abandon): a slot unread for more frames than the ring
  is long is abandoned, counted in the state's `abandoned_slots`, and reused, so its late result is never read; the
  timer keeps timing every frame it can. `simulateGpuRing` and the module's `gpu_timer_ring_simulation` run the rule
  GPU-free for the tests.
- `native/core/python/scene_target_check.py`: the cost round reports `abandoned_slots` and `slot_busy_frames` beside
  each figure and checks that the times arrive well inside the cap with no slot abandoned.

The waits added to `generic_mode_check.py`, `backdrop_pyramid_check.py` and `scene_target_check.py` stay: with the
cause gone they end after the minimum frames, which is the proof.

Evidence: `.artifacts/evidence/native_core/n3_1/20261115_audit2_fix_probes/` (`gl_timer_results.txt`,
`gl_timer_cause.json` and the two probes), `20261115_audit2_fix_cost/` and `20261115_audit2_fix_cost_opengl/` (before).

## Lesson

A harness host is only a measuring instrument if it paces like the product: a frame loop that nothing throttles lets
the CPU outrun the GPU without bound, and every latched read behind it starves. When a figure is "rare on one backend",
read the service's own counters (busy slots, not-ready reads, latency) before adding a wait; a wait that does not
shorten as the load drops is hiding a cause.

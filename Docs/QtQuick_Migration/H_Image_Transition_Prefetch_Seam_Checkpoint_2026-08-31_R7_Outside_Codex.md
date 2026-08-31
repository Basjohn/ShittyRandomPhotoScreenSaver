# H image/transition/prefetch/surface checkpoint — R7 (outside Codex)

Date: 2026-08-31

This checkpoint follows the R6 native-cursor physical run. It does not reopen the physically accepted R6 Halo performance boundary, the accepted Bubble complete-wake repair, or H9's uniform-resize architecture.

## Evidence that admitted R7

The R6 log run exposed three independent H correctness seams:

1. A timer image-change batch was still active when manual Next was admitted. The newer path cancelled the active Quick transition to its authored destination and immediately replaced it. That cancel-to-destination snap matches the operator's one bare-image flash and also allowed the already-open batch to reuse its prior transition spec.
2. Replacement-runtime prefetch reseeding could log `runtime_ready_reseed` yet never perform useful warmup because deferred ownership was one process-wide boolean. A generation-rejected delayed callback could fail before its body released that latch. While transitions remained pending, the resume callback also rearmed itself periodically instead of waiting for an authoritative completion edge.
3. A one-device-pixel wrong/stale vertical band intermittently remained at the mixed-DPR display seam after some transitions. R-63's all-edge logical overscan was a prime hypothesis because both displays run at DPR 1.5 and the workaround perturbed the shared vertical edge even though only non-exact-cover geometry is required to prevent fullscreen-flip promotion.

## R7 implementation

### Transactional image-change admission

`ScreensaverEngine._try_begin_image_change_work()` now owns the whole admission boundary. Before queue/history/current-image mutation it requires:

- no current load owner;
- no pending/running destination transition work;
- the destination's transition-batch ownership APIs;
- successful opening of exactly one display-manager image batch.

`_show_next_image()` then resolves the batch transition before `image_queue.next()`. The DisplayManager preflights and caches one concrete transition spec for a non-startup batch. If Random/manual transition intent cannot produce an admissible spec, the batch is released and the image request is rejected before queue truth advances.

At the retained presentation edge:

- a running transition is an invariant failure, never a reason to call replacement `cancel_current()`;
- once a source image exists, `spec is None` withholds the destination and fails loudly rather than publishing it directly;
- no-source first-frame publication remains the sole legitimate direct image publication;
- perf tracing distinguishes `base_image_published` from `transition_started`.

A competing timer/manual request may be skipped while busy. Correctness does not require a coalesced replacement intent.

### Generation/token prefetch resume

Deferred prefetch ownership is now a `(runtime_generation, token, reason)` claim rather than `_prefetch_resume_scheduled`.

- a new generation can supersede an old claim even if a stale delayed callback never enters its body;
- transition-pending work leaves one intent waiting and schedules no periodic recheck;
- DisplayManager reconciles whole-batch completion before emitting `transition_completed`, so the final display completion is the authoritative wake event;
- direct first-frame publication closes its batch before `authoritative_first_frames_ready`, so replacement-runtime reseeding sees idle state instead of waiting for a transition event that cannot occur;
- the existing post-transition cooldown remains one legitimate delayed wake. No second prefetch owner/timer/poller was added.

### R-63 seam refinement

R-63 remains binding. Exact-cover top-level windows are still prohibited because PresentMon proved their non-deterministic promotion to `Hardware: Legacy Flip` caused the recurring black/stale frames.

The compatibility geometry now overscans only one virtual-desktop exterior edge. Shared edges remain exactly equal to the `QScreen` geometry. If a display is fully surrounded and has no exterior edge, top-only overscan is the narrow non-exact-cover fallback; exact cover is never returned.

`[QUICK_GEOMETRY]` now records per screen/generation:

- screen logical rect;
- compatibility-window logical rect;
- virtual desktop logical rect;
- DPR;
- projected screen/window device-pixel sizes.

## Deterministic validation

Outside-Codex/source-only gate:

- changed Python files: `py_compile` GREEN;
- `tests/test_runtime_perf_policy_contracts.py` + `tests/test_visualizer_viewport_scaling_contracts.py`: **25/25 GREEN**.

The source contracts specifically prove transition/batch admission precedes queue mutation, replacement cancel-to-destination is absent, no-transition direct publication is absent after a source exists, direct first-frame batch completion precedes authoritative readiness, prefetch has generation/token ownership and no transition-pending rearm loop, and the compatibility window no longer uses all-edge overscan.

## Physical/log gates still required

Do not close these from source tests:

1. Repeatedly press Next during active transitions and allow natural timer overlap. Expected: active transition completes normally; competing request is rejected/skipped; zero bare destination flash/snap and zero transition-spec mismatch.
2. Recreate the runtime through Settings/CUSTOM. Every `runtime_ready_reseed` generation must lead to useful exact-next warmup; no stranded generation and no ~100 ms transition-pending prefetch loop.
3. Exercise repeated mixed transition families on the two-display DPR-1.5 topology. Expected simultaneously: recurring/activation black flash remains zero **and** the intermittent seam pixel remains zero. Inspect `[QUICK_GEOMETRY]` if either fails.
4. Preserve R6 Halo performance and H9 resize behavior while running the above.

GC, residual high-refresh pacer skip/transition render contention, native Halo visual parity, Bubble Ghost/Decay, and the separate event-driven Media migration remain open under `Current_Plan.md`.

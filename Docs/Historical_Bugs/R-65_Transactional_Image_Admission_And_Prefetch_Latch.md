# R-65 — Image Change Admission Could Bare-Snap And Prefetch Could Strand Across Recreation

Date: 2026-09-01
Status: Solved (transaction/prefetch core); R-63 seam remains separate

## Symptom

Two related image/surface integrity failures appeared during the Qt Quick migration:

- a timer/manual overlap could mutate next-image truth and then cancel/replace an already-running transition, exposing the destination without the intended transition;
- after Settings/CUSTOM runtime recreation, exact-next prefetch could remain stranded because a process-wide "resume scheduled" latch belonged to an older generation whose delayed callback was rejected before clearing it.

These were lifecycle/admission defects, not evidence that natural timer transitions needed a separate rendering path.

## Root Cause

Image selection/history mutation happened before the complete replacement transaction had been admitted. Separately, prefetch resume ownership was represented by one process-wide boolean rather than by runtime generation/token identity. A stale generation could therefore hold a claim that the new generation could not supersede.

## Fix

- `_try_begin_image_change_work()` became the transactional gate **before** queue/history mutation. Busy loading/pending/running-transition states reject the request without advancing image truth.
- `_present_quick_image()` no longer cancels an active transition to force replacement. Once a source image exists, failure to resolve a transition spec is loud instead of silently direct-publishing the destination.
- prefetch resume is a `(runtime_generation, token, reason)` claim. New generations supersede stale claims.
- batch completion is reconciled before `transition_completed`, so the final authoritative edge schedules the existing cooldown/resume.
- direct first-frame publication closes its batch before runtime-ready reseeding, so a non-transition first frame cannot wait forever for a completion event that will never occur.

No periodic transition-pending poll loop or second image owner was added.

### 2026-09-14 Quick publication performance refinement

A later performance soak found that the normal async path preserved the transactional ownership above but paid an avoidable
Qt Quick cutover cost: the compute task finished with a processed `QImage`, the GUI thread converted it to `QPixmap`, and the
Quick presenter immediately converted/captured it back into detached image state. At 3840x2160 this cost roughly 28–53 ms on
ordinary image rotations.

The async current/previous-image paths now capture the existing `PresentationImage` value directly from the processed `QImage`
in the compute task and hand that immutable state to DisplayManager. This is a **presentation-boundary optimization only**:
transaction admission, transition source/destination truth, queue/history mutation, generation fencing, image accounting,
scaled-cache ownership, and startup desktop seeding are unchanged.

The immutable presentation state still owns a tightly packed Python RGBA bytes payload. Windows acceptance must therefore prove
that removing the GUI QPixmap bounce did not merely move a material GIL-held image-copy hitch into the compute phase. If such a
residual exists, the next architectural seam is a Qt-native detached buffer/image through texture upload; do not weaken the
transaction contract to chase it.

## Acceptance Evidence

The 2026-09-01 follow-up logs show natural timer and manual Next transition timing in the same broad range, no separate natural-transition performance smell, successful `runtime_ready_reseed` after replacement generations, and no stranded-latch/rearm storm. The operator continued to report **zero returning black flashes**.

The intermittent one-pixel shared-display seam is **not** part of this record. It remains governed by R-63's non-exact-cover anti-fullscreen-flip requirement and must be refined without deleting overscan.

## Binding Lesson

Admission must precede mutation for image-change transactions, and delayed lifecycle claims must carry generation identity. Never recover from a busy transition by advancing queue truth first, canceling the active transition, or reintroducing a process-global prefetch boolean.

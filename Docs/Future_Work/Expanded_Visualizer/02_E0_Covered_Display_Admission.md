# E0: covered-display image admission (design proof for M4, 8 Nov 2026)

Answers plan 01 §E0 before any suppression code. Source traced at main e5960416. Owner: lead. The operator's complaint
this closes: under a fullscreen (Expanded) Visualizer the covered display "still fire[s] complex transitions which
wastes resources".

## What the source does today

One image change is one transaction across every selected display:

1. `ScreensaverEngine._show_next_image(origin)` (timer, manual next/ban, startup, RSS completion, refresh-gate resume)
   claims the image-change owner (`_try_begin_image_change_work` -> `DisplayManager.set_transition_work_pending(True)`,
   which opens the batch with `expected = _selected_destination_screen_indices()`, every display), resolves the batch
   transition, preflights the worker, and only then mutates the queue (`image_queue.next()`).
2. `image_pipeline.load_and_display_image_async` snapshots `snapshot_processing_descriptors()` (every display) and, in
   independent-image mode, takes one more `queue.next()` per further display. Decode/scale run on the worker; the GUI
   callback applies display `i` after `i * TRANSITION_STAGGER_MS`, records per-display history and schedules prefetch.
3. `DisplayManager._present_quick_captured_image` publishes directly only when the display has no source image
   (startup/first frame); otherwise it builds the batch's transition request (later displays' durations extended by
   their stagger index in `sorted(expected)`) and starts it. A display that still owns a running transition is an
   invariant failure, never a cancel.
4. `_on_quick_transition_finalized` commits `current_images[screen]` only after the destination is installed;
   `_finish_quick_transition_batch_if_complete` closes the batch when `expected ⊆ published` and nothing runs, then
   emits `transition_batch_idle` (prefetch resumes on that edge, no polling).

So a display cannot "ignore" `start_transition` or drop its completion: the batch would never close. That is the
§E problem statement, confirmed.

## What a covered display looks like

The expanded card is translucent (`cardBackgroundColor` default `#4c232323`, or a surface material sampling the
wallpaper behind it). The wallpaper under it **is visible**, dimmed or blurred. So the options split as:

| Option | Work on the covered display | Visible result under the card | Batch/history |
| --- | --- | --- | --- |
| A. Keep it in the batch, authored transition (today) | decode + upload + full transition; Glass backdrop refreshes every frame while it runs | changing wallpaper | unchanged |
| B. Keep it in the batch, commit without effect (direct publish) | decode + upload | a hard cut under a translucent card: violates fade-never-vanish | receipts intact |
| C. Keep it in the batch, Crossfade only | decode + upload + one blend; backdrop refresh during the fade | gentle change | intact (the plan's last-resort fallback) |
| **D. Exclude it at admission** | **none**: no queue advance, decode, upload, transition or backdrop refresh | the pre-cover wallpaper, static | expected set and processing targets agree; nothing to receipt |

**Decision: D, exclusion at admission.** It is the strongest safe state (§E0 item 3) and the only one that removes the
transition, the upload and the material refresh together. A static wallpaper under the Visualizer is what a
fullscreen view wants anyway. B is rejected (a visible cut), C is kept only as the documented fallback should D fail
its gate.

## The policy: one admission set at the existing seam

`DisplayManager` owns one per-display admission state, read at the two places that today enumerate every display:

- `normal`: a destination as today.
- `covered_excluded`: the display is under an accepted Expanded Visualizer takeover **and already shows an
  authoritative image** (`screen in current_images`). It is neither expected nor a processing target.

A display with no current image is never excluded: its first image is a direct publish with no transition (startup,
Settings return, monitor wake/replay, cold launch with a persisted expanded intent). Excluding it would leave black
or desktop under a translucent card.

Rules:

1. **Admission-time snapshot.** When `set_transition_work_pending(True)` opens a batch, it freezes the batch's admitted
   set = selected displays minus `covered_excluded`. `snapshot_processing_descriptors()` returns exactly that frozen
   set while the batch is pending. The expected set and the processing targets therefore agree by construction,
   before any queue mutation, and a display is never added to (or removed from) a running batch.
2. **Coverage source.** `covered` comes from the takeover coordinator's committed state (M2/M3: from the accepted
   expand request until the collapse has committed). One owner, read once per batch admission, never per frame.
3. **Zero targets.** If every selected display is excluded, `_show_next_image` returns `False` *before*
   `image_queue.next()` with reason `no_uncovered_destination`, releases the owner it claimed and logs once per run of
   such edges (debug after the first). The rotation timer keeps its cadence; no defer queue, no retry, no catch-up.
4. **Independent images.** Only admitted displays take `queue.next()`, so no image is consumed unseen. The stagger
   index runs over the admitted targets, so the remaining display never waits a stagger behind an invisible one.
5. **Mid-batch coverage change.** A transition already running on a display that becomes covered finishes intact under
   the card (the invariant forbids cancel); the batch closes on its own accounting. The display is excluded from the
   next batch. A display that is uncovered mid-batch was not admitted to it and joins the next one.
6. **Resume (collapse).** The display rejoins at the engine's **next admitted edge**: it is a normal destination whose
   source is its pre-cover image, so it gets the authored transition from that image. No re-seed, no replay, no
   stale-destination publish, no black flash. In same-image mode both displays show different images until that
   edge (at most one interval). This is the documented trade: an immediate catch-up would either advance the
   untouched display early or add a second image path. Recorded as a possible follow-up, not built.
7. **Previous image / manual next / ban.** They use the same admitted set: the previous-image path
   (`load_and_display_image_async_with_metas`) snapshots the same processing targets, so it moves only uncovered
   displays. A ban applies to the image the ban names, as today.
8. **Shared work stays.** Source/prefetch workers are never suspended because one display is covered. Prefetch's
   per-display scaled derivatives for an excluded display are the optional deeper optimisation of E1 step 3, gated
   separately on proof that the work is exclusive to it.

## State diagram

```
                 expand accepted (display has an image)          collapse committed
   NORMAL ─────────────────────────────────────────────▶ COVERED_EXCLUDED ─────────────────────▶ NORMAL
     ▲  │ batch admitted: in expected + targets               │ batch admitted: not in expected/targets   (next edge:
     │  ▼                                                     │ running transition (from before) finishes  authored
   transition runs ─▶ finalized ─▶ current_images[s]          │ intact; pre-cover image stays              transition from
                                                              ▼                                            pre-cover image)
                                                     all displays covered: edge returns False before queue.next()
```

(a) One covered screen of two: the batch is the other screen alone (no stagger), the covered one keeps its image.
(b) All covered: every edge is a no-op before the queue moves.
(c) The last uncovered screen becomes covered mid-batch: its running transition completes, the batch closes, later
edges are no-ops until a collapse commits.

## Built (8 Nov)

- `ExpandedDisplayCoordinator.covered_unit` (M3's cover edges) -> `DisplayManager.covered_image_destination_screens()`
  and `has_admitted_image_destination()`.
- `engine/image_pipeline.py` `_leave_out_covered_destinations`: both image paths (next and previous) drop the covered
  screens through the existing per-screen omission receipt (`set_transition_work_pending(False, screen_index=...)`)
  before any work; `_history_with_covered` keeps one history entry per display, the covered one carrying its last
  meta. Prefetch and monitor replay still see every display.
- `engine/screensaver_engine.py` `image_destination_admitted`: `_show_next_image` and `_on_previous_requested` return
  before the claim, the queue and the history when every display is covered.
- Tests: `tests/test_expanded_visualizer_covered_batch.py` (real batch accounting + real pipeline; disabling the
  exclusion turns 5 of 8 red, the other 3 are the uncovered controls).
- Known limit: a Previous while covered rewinds the covered display's history entry although its image stays (it
  shows the pre-cover image either way, and the next edge after a collapse rewrites it).

## Gate (M4 "Gate 4", restated as tests)

- Pure state tests on `DisplayManager` with fake units: admitted set frozen at open; expected == processing targets;
  zero-target edge leaves queue position and history untouched; mid-batch cover/uncover; never-imaged display admitted
  while covered; stagger index over admitted displays only; the batch closes (`transition_batch_idle`) in every case.
- Engine-level trace (existing `ImageChangePerfTrace` + batch logs): expected / published / covered identities, queue
  and history before and after, active transition count, worker submissions, first-frame identity after collapse, and
  zero pending work after collapse. A test fails when an expected display has no terminal receipt.
- Measurement: GPU time and render-thread CPU on the covered display with and without the policy, through a Visualizer
  session with photo changes on the other display (relative, load recorded; no game60).

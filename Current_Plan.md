# Current Plan (Forward-Looking)

## Media Card & Overlay Reliability — **Status: COMPLETED (Jan 31, 2026)**

- **Why it matters:** MediaWidget, Spotify overlays, and Reddit cards must match the 2.6 experience: coordinated fades, tight control-row layout, responsive media keys, and deterministic polling. Recent regressions blocked live QA because the media glyph never flips on hardware keys and Reddit fades desynchronise across displays.

- **Completed work (Jan 31 04:55):**
  - Lock-free fade coordination implemented using SPSCQueue + TripleBuffer
  - ThreadManager and ResourceManager integration complete for all timers
  - Media key play/pause glyph now flips instantly with `repaint()` (guarded by visibility checks)
  - Reddit widgets fade in coordinated fashion per-display with 500ms secondary timing
  - Documentation updated: `Spec.md`, `Index.md` reflect lock-free fade architecture

- **Exit criteria achieved:**
  - Live build demonstrates instantaneous play/pause glyph flips for media-key input
  - Reddit widgets fade in coordinated fashion per-display
  - Spec/Index reflect the finalized lifecycle + fade orchestration

---

## Next Phase

Pending user direction for next priority tasks.
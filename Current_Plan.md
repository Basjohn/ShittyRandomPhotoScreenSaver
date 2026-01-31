# Current Plan (Forward-Looking)

## Media Card & Overlay Reliability — **Status: In Progress (Active Debugging)**

- **Why it matters:** MediaWidget, Spotify overlays, and Reddit cards must match the 2.6 experience: coordinated fades, tight control-row layout, responsive media keys, and deterministic polling. Recent regressions blocked live QA because the media glyph never flips on hardware keys and Reddit fades desynchronise across displays.

- **Latest progress (Jan 31 04:30):**
  - Lock-free fade coordination implemented using SPSCQueue + TripleBuffer
  - ThreadManager and ResourceManager integration complete for all timers
  - Application launches successfully with new architecture
  - **BUT: Two critical issues remain unresolved:**
    1. Media key play/pause glyph does NOT flip instantly (visualizer does, widget doesn't)
    2. Reddit widgets on different displays still NOT coordinated

- **Root Cause Analysis (In Progress):**
  - **Media glyph issue**: Diff gating in `_update_display()` blocks state-only updates. When `play_pause(execute=False)` creates optimistic state, `_compute_track_identity()` returns same identity (title/artist unchanged), causing early return at line 1043 before updating display.
  - **Reddit coordination**: Each display has independent WidgetManager with separate fade coordination. Reddit widgets on different displays don't share coordination state.

- **Outstanding work (prioritised):**
  1. **Fix media key glyph instant update**
     - [ ] Bypass diff gating for play/pause state changes
     - [ ] Force immediate repaint of controls row on optimistic update
     - [ ] Test with hardware media keys
  2. **Fix Reddit fade coordination**
     - [ ] Implement cross-display fade sync or verify same-display coordination works
     - [ ] Ensure reddit/reddit2 on same display coordinate properly
     - [ ] Capture logs to verify "running immediately" issue resolved
  3. **Documentation + audits**
     - [ ] Update `Spec.md`, `Index.md` with lock-free fade architecture
     - [ ] Document cross-display coordination limitations

- **Exit criteria:**
  - Live build demonstrates instantaneous play/pause glyph flips for media-key input
  - Reddit widgets fade in coordinated fashion (at least per-display)
  - Spec/Index reflect the finalized lifecycle + fade orchestration

---

**Execution Notes:** Both issues stem from architectural assumptions: (1) diff gating is too aggressive for state changes, (2) fade coordination is per-WidgetManager not global. Fixes require targeted bypasses, not rewrites.
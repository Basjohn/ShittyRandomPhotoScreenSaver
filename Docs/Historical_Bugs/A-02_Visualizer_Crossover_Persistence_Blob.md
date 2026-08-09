# A-02 — 2026-02-24 — Spotify Visualizer "Crossover Persistence" (Blob muted after mode switch)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Starting the session in Blob mode behaved normally, but switching into Blob from any other mode (or re-applying Blob via Settings) left radius/glow muted for 5–8 s despite healthy energy readings (`stage_filtered ≈ (1.00,0.03–0.08,0.00)`, radius stuck ~0.27–0.32 while `overall` > 0.6).
- Cold starts (Settings exit) immediately restored reactivity, confirming stale state carried across crossovers rather than shader issues.

**Failed / insufficient attempts**
1. *Overlay-only reset (Jan 2026):* `SpotifyBarsGLOverlay` reset `_blob_stage_progress_*` when `_vis_mode` changed. Helped literal mode flips but not config replays, because the enum often stayed on `blob`.
2. *Widget-only zeroing (Feb 2026 rev 1):* `_reset_visualizer_state()` cleared `_display_bars/_target_bars` and bubble caches but never asked the overlay to reseed, so stale smoothing reappeared on the next GPU push.
3. *Blob smoothing reseed (Feb 2026 rev 2):* Added `_blob_seed_pending` + `_reset_mode_state('blob')` when `_vis_mode` flipped. Still failed whenever settings re-applied Blob without changing the enum.
4. *Overlay reset wiring (Feb 2026 rev 3):* Widget now called `overlay.request_mode_reset()` for `_reset_visualizer_state()` / `_clear_gl_overlay()`. Logs showed `[OVERLAY][RESET]`, yet stage2 remained pinned because the beat engine + widget bars immediately reintroduced stale smoothed data.

**Final fix**
- `_reset_engine_state()` now cancels pending compute tasks, calls `reset_smoothing_state()` / `reset_floor_state()`, replays smoothing config, seeds `_waiting_for_fresh_engine_frame`, and zeros widget bar/energy buffers.
- `_track_engine_generation()` records the post-reset generation so `_on_tick()` blocks GPU pushes (`_waiting_for_fresh_engine_frame`) until `engine.get_latest_generation_with_frame()` reaches the pending generation, guaranteeing Blob never reuses the old smoothing envelope.
- `SpotifyBarsGLOverlay` reseeds `smoothed_energy` on the first non-zero FFT, so stage2 can rise immediately once the engine publishes fresh data.

**Regression coverage & validation**
- Added `tests/test_spotify_visualizer_widget.py::test_blob_crossover_waits_for_fresh_engine_frame`, which stubs the beat engine + overlay bridge, forces a Spectrum→Blob crossover, and asserts GPU pushes remain blocked until the fake engine publishes a new generation with stage2 energy > 0.4.
- Manual log runs (Sine→Blob crossover and Blob cold start, Feb 24) show stage2 surpassing 0.4 within ~1 s after mode switch, with `[SPOTIFY_VIS] Engine delivered fresh frame` immediately clearing the wait gate.

**Takeaways**
- Always reset the shared beat engine, widget bar cache, and overlay state within the same tick when handling cross-mode transitions.
- Gate GPU pushes on fresh FFT generations whenever smoothing state is invalidated.
- Keep regression tests that cover the exact gating contract so future plumbing changes cannot reintroduce stale-state persistence.

## Record Provenance

This standalone file preserves the complete former inline `A-02` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

# U-10 — 2026-06-28 / 2026-06-29 — Oscilloscope Visual Strobe / Waveform-Ghost-Transient Contract Drift (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** Oscilloscope is back to a mode-owned display contract: idle appears without waiting for live playback, pause no longer needs to "break free" into its idle shape, live playback reads as waveform deformation/warp rather than brightness strobe, and line ghosts have an authored `osc_ghost_decay` transport path. Media metadata loss during visualizer preset cycling was a sibling runtime-write bug and is also closed: visualizer preset changes now target `widgets.spotify_visualizer` instead of refreshing the whole media widget state.
- **Evidence to preserve:**
  - `.tmp/perf_collapse_evidence_20260628_164113/screensaver_spotify_vis.log`, around `16:35:07..16:35:13`, shows a clean Oscilloscope first-frame handoff: fresh waveform generation, overlay reset, and matching overlay generation/activation after first push.
  - The same window shows Oscilloscope running with ghosting/reactive glow enabled (`ghost2=True ghost3=True`) while later logs in the window show strong bass/transient evidence, so weak/strobing visuals are unlikely to be explained by "no audio arrived" alone.
  - Curated Oscilloscope presets combine low `osc_speed` (`0.18..0.33`), high line amplitude, ghosting, reactive glow, and transient width mix.
- **Leading hypotheses:**
  1. `widgets/spotify_bars_gl_overlay.py` squares `osc_speed` before waveform interpolation, so common preset speeds become extremely low blend alphas and can make the visible waveform lag the song.
  2. The Oscilloscope ghost ring trails an already-smoothed waveform, compounding lag and possibly weakening ghost clarity.
  3. `widgets/spotify_visualizer/renderers/oscilloscope.py` uses repeated kick/snare event peeks to modulate `u_sensitivity`, which can read as width/brightness strobe rather than coherent waveform motion.
  4. `widgets/spotify_visualizer/shaders/oscilloscope.frag` makes reactive glow alter both sigma and alpha, so glow can visually flash faster than the low-speed waveform changes.
- **Long-term prevention:**
  - keep Oscilloscope fixes mode-owned unless an oracle proves shared waveform extraction is wrong
  - keep the Oscilloscope waveform response, ghost stability, idle/live-boundary, transient-width strobe, and reactive-glow bars green after any visualizer transport change
  - use bounded `--viz` / `--viz-diag` diagnostics for speed alpha, waveform delta, ghost ring depth, transient width mix, sensitivity modulation, and glow drive if the issue reopens
  - do not remove glow, ghosting, multi-line rendering, or current-good mode behavior as a fake fix
- **First implementation pass:**
  - added `widgets.spotify_visualizer.oscilloscope_contract` for mode-owned waveform blend, ghost ring, and transient-width accent contracts
  - replaced `osc_speed ** 2` waveform blending with a perceptual alpha mapping so low authored speeds remain smooth without lagging several beats
  - made ghost ring fill/delay explicit so ghosting does not sample the just-written current frame during initial fill
  - bounded transient width modulation so repeated kick/snare peeks no longer become an oversized second sensitivity authority
  - reduced Oscilloscope shader reactive-glow alpha pumping, keeping reactivity more in glow size/shape than brightness flashing
- **Second implementation correction after runtime regression:**
  - first alpha mapping was too hot at timid speeds and made Preset 2 strobey; the mapping was pulled back while staying above the old `speed ** 2` lag trap
  - Oscilloscope now shares the paused startup idle-reveal contract with Bubble/Sine/DevCurve instead of waiting for live playback
  - live-to-idle entry now clears stale live waveform, ghost ring, and line transient envelopes before accepting the idle seed, preventing the "rapid twitch until it breaks free" shape
  - latest runtime proved idle was closer to the desired look than playback because live playback consumed arbitrary raw PCM phase slices; Oscilloscope now conditions live waveform display input with spatial smoothing, amplitude bounding, and phase/sign alignment before the normal blend
  - repeated paused media snapshots could also restart the 700ms pause-confirmation timer, delaying idle entry well beyond the intended safety window; identical paused/stopped updates now preserve the original pending confirmation
  - latest pause testing exposed a separate shared-idle authority bug: the beat engine generated paused idle waveform/bars but then accepted warm-grace capture PCM as the active waveform while still non-playing. Warm frames are now drained only; they cannot overwrite the idle waveform seed after pause confirmation.
  - live preset cycling could surface partial media snapshots with the same title but blank artist/artwork, erasing visible artist metadata until a play/pause interaction produced a fuller snapshot. Same-track partial snapshots now preserve known visible metadata while keeping incoming playback/control state authoritative.
- **Final validation pass:**
  - runtime testing after the final pass reported the correct contract: idle startup and pause behavior were acceptable, playback reaction was in a good place, line ghost visibility was restored via the new ghost-decay control, and metadata no longer vanished during middle-click preset cycling.
  - focused bars cover the fixed seams in `tests/test_oscilloscope_display_contract.py`, `tests/test_visualizer_preset_cycling_runtime.py`, `tests/test_visualizer_settings_plumbing.py`, `tests/test_spotify_visualizer_widget.py`, and `tests/test_ghost_isolation.py`.
- **2026-07-14 baseline reconciliation:** a stale shared parameterization incorrectly expected paused Oscilloscope to retain `_waiting_for_fresh_engine_frame`, contradicting this entry's accepted idle-reveal contract. The test now keeps that wait only for paused Spectrum; existing four-mode idle-reveal and dedicated Oscilloscope startup bars own Oscilloscope behavior. No runtime or preset code changed, and the focused current-good lock passed all 17 cases.

## Record Provenance

This standalone file preserves the complete former inline `U-10` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.

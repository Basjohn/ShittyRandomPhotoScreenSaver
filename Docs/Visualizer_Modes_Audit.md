# Visualizer Modes Audit — Dual-Path Hybrid Rollout (Mar 2026)

This audit now captures **two things explicitly**:
1. What currently ships in the Spotify visualizer after Approach A.
2. Which refinements remain under consideration (with tense that reflects reality).

## 1. Current Scope & Completed Outcomes
| Goal | Delivered Work |
| --- | --- |
| Restore immediate beat response without reverting to the “Unfuckening Part One” running-peak path | Built a **dual-path pipeline** (transient bus + smoothed/AGC bus) consumed by every renderer. |
| Stop vocals from choking bass recovery | Implemented **dual-stage AGC** with bass/mix envelope split and transient clamp injection. |
| Give Spectrum/Bubble/Blob/Sine/Osc their promised behavior | Wired kick express lane, lane-aware spectrum routing, bubble transient mixer, blob scheduler/transient accents, line-mode scheduler assists, heartbeat gate boost, overlay propagation. |
| Preserve settings/presets across the new controls | Updated defaults, settings dataclass, widget caches, repair tool, and regression tests for `kick_lane_gain`, `transient_pulse_gain`, `transient_clamp`, and the newer Spectrum lane-strength arrow contract. |

## 2. Architecture Snapshot (Actual State)
| Layer | Files | What’s true today |
| --- | --- | --- |
| Capture + FFT | `widgets/spotify_visualizer/audio_worker.py` | Emits transient metrics (`_transient_*`, `_onset_type`), stores per-mode gain/clamp fields, and feeds the dual-stage AGC envelopes. |
| Transient Bus | `widgets/spotify_visualizer/transient_bus.py` | Spectral-flux onset detector + adaptive thresholds + onset ring buffer feeding `TransientEnergyBands`. |
| Dual-Stage AGC & Kick Lane | `widgets/spotify_visualizer/bar_computation.py` | `_apply_adaptive_normalization` maintains bass/mix envelopes; kick express lane boosts the first bass bins whenever transient bass >0.05. Spectrum also now routes bass/mid/treble per bar with soft lane crossfades instead of one shared energy scalar. **Global transient_clamp** applied immediately after transient bus update — caps all three channels (`_transient_bass/mid/high`) before kick lane, bubble dispatch, or AGC reads them. |
| Mode Routing | `widgets/spotify_visualizer_widget.py`, `tick_pipeline.py`, renderers | Spectrum bars now preserve lane-specific energy collapse; Bubble pulses mix transient bass with per-mode gain/clamp and consume scheduler kicks; Blob now computes one processed live-band source (transient + scheduler aware) that feeds both live deformation uniforms and retained ghost memory; Sine/Osc width and heartbeat paths now get scheduler assists in addition to transient energy, and Osc/Sine mode resumes wait for fresh waveform generation after reset. |
| GPU Overlay | `widgets/spotify_bars_gl_overlay.py`, renderers | Overlay `set_state()` stores transient energy and mode-local event envelopes; Blob specifically now resolves processed live bands inside the overlay before handing them to the renderer/ghost path. |

## 3. Solved Issues Matrix
| Original Symptom | Root Cause | Shipped Mitigation | Status |
| --- | --- | --- | --- |
| Spectrum missed kicks / slow bass | Gating + smoothing held lows for 3–4 frames | Kick express lane fed by transient bus | 
| Bubble pulses saturated when AGC off | Pulses referenced smoothed overall energy | Transient pulse mixer + per-mode gain/clamp sliders | 
| Blob deformation ignored beats | Smoothed energy fed stretch + wobble uniformly | Transient uniforms + stage clamps | 
| Sine/Osc heartbeat lagged | EMA-only spike detection | Heartbeat gate now drops when onset bus reports kick | 
| Presets lost new controls | Schema/repair tool lacked keys | Defaults + repair + tests updated | 

## 4. Delivered Feature Timeline
| Phase | Highlights |
| --- | --- |
| **1** | `TransientBus`, beat engine wiring, `_StubEngine` hooks for tests. |
| **2** | Dual-stage AGC split, transient clamp plumbing, regression tests. |
| **3** | Mode integrations (Spectrum/Bubble/Blob/Sine/Osc) + overlay propagation. |
| **4** | UI control refresh, preset schema + repair updates, and eventual retirement of authored `energy_boost` / `use_raw_energy` from live settings/preset flows. |
| **5** | Expanded tests (`test_transient_bus.py`, `test_transient_preset_preservation.py`, `test_transient_per_mode_integration.py`) and doc refresh. |

## 5. Regression Coverage Snapshot (Current)
- `tests/test_transient_bus.py` — onset detection, decay, AGC fields, beat-engine exposure.
- `tests/test_transient_preset_preservation.py` — defaults, model resolvers, repair-tool injection/preservation, mandatory suffix coverage.
- `tests/test_transient_per_mode_integration.py` — kick lane, bubble pulse mixer, blob uniforms, heartbeat trigger gate, GPU kwargs wiring.
- `tests/test_visualizer_overlay_kwargs.py` — overlay still forwards transient kwargs to renderers.

## 6. Mode Status & Pending Decisions
| Mode | Current Behavior | Still To Decide |
| --- | --- | --- |
| **Spectrum** | Kick express lane + lane-aware routing now preserve both authored shape and actual band absence. The shaper now also owns label-driven lane-strength arrows directly, so authored lane power no longer depends on old scalar keys. | Tune lane crossfade width/weighting on real playlists before exposing any new “lane bleed” slider. |
| **Bubble** | Transient pulse gain + clamp restore beat-only pulses; drift stays smoothed. Global clamp now active upstream; Bubble dispatch retains its own downstream clamp as defense-in-depth. Stream-speed reactivity is now vocal-leaning, uses gentler asymmetric smoothing plus a short burst envelope, and its public cap now runs 0–200% end-to-end. | Validate real-playlist feel before adding any new stream-speed slider; prefer preset tuning over more public controls first. |
| **Blob** | Deformation consumes transient uniforms; scheduler kick/snare peeks now reinforce stage/wobble impulses. Global clamp now active upstream. Current code is still on the retained-peak envelope model, but the live blob and ghost now share the same processed live-band source before ghost hold/decay, and `SpotifyBarsGLOverlay.set_state()` now reuses one coherent processed Blob-event snapshot per frame instead of mixing old/new scheduler strengths inside one render tick. Both the delayed-history/state-blend ghost branch and the ghost-only peak snapshot branch remain retired. | Blob ghosting is still not visually validated. If the shared-input retained-peak branch still reads wrong in live use, compare against the last known-good commit before designing any new silhouette-memory path. |
| **Sine/Osc** | Heartbeat gate drops on confirmed kicks, and line width now gets scheduler-assisted beat accents. Sine additionally now receives a sine-only beat assist that boosts uploaded bass/mid/high/overall energy plus amplitude floor from recent kick/snare events, so the waveform reacts more visibly without changing Oscilloscope behavior. Osc mode switches now force a full shared-engine generation reset/wait plus fresh-waveform generation gating before GPU pushes resume, on top of zeroed waveform uploads. | Add noise-gate sliders and clarify AGC defaults; keep live-validating real double-click swaps because the user was still able to repro the half-dead-line issue before the fresh-waveform gate landed. |

### Transient Clamp Adoption Status
- **Implemented (Mar 2026)**: `transient_clamp` is now **global** — applied in `bar_computation.fft_to_bars()` immediately after transient bus update, capping all three channels before any downstream consumer.
- Bubble dispatch retains its own downstream clamp (`min(_t_clamp, _pulse_bass + _t_bass * _t_gain)`) as defense-in-depth.
- The slider is now meaningful for **all modes** and should remain enabled in the Technical UI.

### Slider Enablement Matrix (UI — implemented Mar 2026, refreshed Mar 22 2026)
| Slider | Active Modes | UI State | Label Annotation |
| --- | --- | --- | --- |
| `kick_lane_gain` | Spectrum only | Visible in Spectrum Technical group only | "Kick Lane Gain:" |
| `transient_pulse_gain` | Bubble only | Visible in Bubble Technical group only | "Transient Pulse:" |
| `transient_clamp` | **All modes** (global) | Visible in each mode's Transient bucket | "Transient Clamp:" |
| `spectrum_lane_transient_mix` | Spectrum only | Visible in Spectrum Technical group only | "Kick Lane Mix:" |
| `bubble_transient_mix_bass` | Bubble only | Visible in Bubble Technical group only | "Transient Bass Mix:" |
| `bubble_transient_mix_vocal` | Bubble only | Visible in Bubble Technical group only | "Transient Vocal Mix:" |
| `blob_transient_mix_bass` | Blob only | Visible in Blob Technical group only | "Transient Bass Mix:" |
| `blob_transient_mix_vocal` | Blob only | Visible in Blob Technical group only | "Transient Vocal Mix:" |
| `sine_wave_transient_width_mix` | Sine only | Visible in Sine Technical group only | "Transient Width Mix:" |
| `oscilloscope_transient_width_mix` | Osc only | Visible in Osc Technical group only | "Transient Width Mix:" |

## 7. Control Surface & Future Exposures
- Authored `energy_boost` / `use_raw_energy` have since been retired from the live settings/defaults/preset schema. Treat any mention elsewhere in this audit as historical context, not current guidance.
- **Implemented (§2.3)**: Per-mode transient mix sliders now live in each mode's Technical group. Seven new sliders across five modes, wired end-to-end (model → defaults → UI → widget → overlay → renderer). Preset repair auto-injects via `_MANDATORY_MODE_TRANSIENT_MIX`.
- **Technical declutter refresh**: Mode-only transient controls no longer sit around greyed out in unrelated modes. The UI now uses visibility-only `Show AGC Controls` / `Show Transient Controls` buckets so settings stay compact without changing runtime behavior. Their spacing/chrome is intended to match the standard circle-checkbox rows, but alignment polish is still a live UI follow-up.
- Upcoming exposures: `transient_decay_ms`, event scheduler weighting, noise gate sliders. Bubble stream-speed internals remain intentionally hidden for now; current priority is feel validation, not more user-facing scheduler knobs.

## 8. Active Follow-Up / Optional Backlog
1. **Event micro-scheduler** — Now broadly delivered. `TransientEventScheduler` exists, Bubble consumes kick events once, Blob peeks kick/snare events non-destructively through the GPU push path, and Sine/Osc now use non-destructive peeks for beat-confirmed line accents. Remaining work is tuning, Blob ghost investigation, Osc reset validation, and any future vocal-swell consumers rather than first-pass architecture.
2. **Simulation dt normalization** — Bubble still clamps dt to 0.1 when compute falls behind; move the clamp into `BubbleSimulation` to keep pulses in sync during spikes.
3. Move any one mode only controls into the advanced bucket of that specific mode. Sliders with more than one mode relevance stay in technical.
4. **Configurable FFT front-end / overlap** — Not urgent post-transient bus, but remain ready if <20 ms latency becomes mandatory.
5. **Advanced UI sliders** — Add `transient_decay_ms`, event hold weighting, and any future scheduler-specific shaping only if the current always-on contract proves insufficient.

## 9. Diagnostics & Research References
- Continue using the existing regression suite (Section 5) as the minimum bar.
- If we adopt event scheduling or FFT variants, add dedicated tests capturing latency + missed-beat metrics before shipping.
- Research references (SuperFlux, PLP, windowless DFT, CQT) remain valid but do not require further action unless we pursue optional backlog items.

## 10. Next Actions
1. ~~Decide whether to integrate `transient_clamp` into the AGC pipeline~~ — **Done**. Global clamp is live in `bar_computation.py`; tests expanded in `test_transient_per_mode_integration.py`.
2. ~~Implement per-mode transient mix sliders (§2.3)~~ — **Done**. Seven sliders across five modes, 37 tests passing, all 35 presets repaired.
3. Treat the event micro-scheduler as active architecture, not speculative backlog. Next work is validation/tuning and doc sync, not re-scoping the prototype.

## 11. Mode-Specific Backlog Appendix
### Spectrum (Stable)
- `kick_lane_gain` annotated "(Spectrum only)" and disabled with read-only value outside Spectrum.
- `spectrum_lane_transient_mix` (default 0.65) scales kick lane boost in `bar_computation.py`. Implemented and tested.
- Consider defaulting AGC strength to ~0.25 when this mode is active; no engine work required.

### Bubble (Transient-heavy)
- Optional UI knobs once wiring exists: `transient_decay_ms`, `event_queue_hold_ms`, `pulse_gate_threshold`, `transient_dt_compensation`.
- Merge overlapping sliders (`bubble_stream_speed` vs `bubble_drift_speed`) so only one responds to overall loudness.
- Keep Bubble-specific `transient_clamp` logic even if global clamp ships, since pulses can still overshoot.

### Blob (Stage-driven)
- Need per-stage `bass_transient_mix` / `vocal_transient_mix` sliders plus `stage_decay_speed` to control how quickly deformation relaxes.
- Consider applying the global `transient_clamp` once it lives in AGC so wobble never inherits runaway transient energy.
- Add `event_hold_count` to limit how many transient events can queue before forcing a reset.

### Sine Wave & Oscilloscope (Shared heartbeat pipeline)
- Sine now has a mode-local beat assist in the renderer: scheduler kick/snare peeks lift uploaded band energy and amplitude cues without altering Oscilloscope math.
- Keep observing whether Sine now has enough punch on real music before adding any public slider; current recommendation is still to prefer internal tuning first.
- Add `*_noise_gate_db` sliders to keep transient feed from reacting to hiss in quiet passages.
- Simplify overlapping sliders (`sine_sensitivity` vs `sine_reactivity`, `osc_line_amplitude` vs `osc_sensitivity`) once telemetry confirms the preferred naming.

### Global Controls
- Keep `input_gain` as the only exposed loudness control. Do not reintroduce authored `energy_boost` / `use_raw_energy`; if runtime/debug seams still exist, they are not part of the supported preset/settings contract.
- Once clamp becomes global, allow presets to specify per-mode clamp defaults and surface `transient_bus_mix` / `event_scheduler_weight` sliders in Advanced view.
- Document grey-out behavior directly in the UI so preset authors know which sliders affect which modes today.

## 12. Original Request - Do Not Delete
```
So Visualizer Modes are not ideal right now.

NEW Problems shared across all modes:

- Poor reactivity, missing some beats entirely.
- Slow reactivity even at 128 Audio Block. It's really noticeably late on every single mode.
- Visualizer Modes seem to get often confused between vocals and beats so if they go big on a vocal they cannot shrink in time for a beat. Our modes were supposed to have focuses to prevent this. 
	--Spectrum has defined shape lanes for vocal/bass for example. (Currently Spectrum is the best working mode. It has a delay too but better reaction than the rest)
	--Bubble was supposed to have Bubbles pulsing only to beats like kicks/drums and catching them all while vocals increased or 	decreased drift speed and overall loudness controlled the stream speed. 
	-- Blob was supposed to use its deformation and stretching for kicks/drums/big beats and its wobble for vocals and has its 	staging system for its overall size to grow with overall volume
	-- Sine is weird but fine
	-- Osc is weird but fine
	(Sine and OSC share a lot)
- Is AGC even doing anything? AGC was supposed to give us more reactivity at loud volumes but it seems to just be a normalization pass from my experiments and I've had to turn it down to ~20% on all modes to get even minor reactivity. How is it any better than the running peak we used if it behaves like this?

However we do have advantages now like much more customizability, being able to control input gain and normalization via technical sliders, bubble size clamping and small bubble promotion. Much better shaping controls for spectrum. 

This puts me in a weird position. I don't want to revert to how "Unfuckening Part One" handled audio as it had problems, but it was more reactive.

Can we make an audit of all modes for the problems I mentioned. No code editing yet, actually assessments of why, after this we can compare it to the "Unfuckening Part One" if needed but there might be some obvious tweaking, conflicts or double smoothing/normalization/etc slowing things down. I'll need several approaches whenever it isn't a simple fix.

Make a dedicated Audit Document. Visualizer_Modes_Audit.md in docs. Be as detailed as possible, give multiple suggestions, weigh the benefits, even radical suggestions are welcome. Ideally though all our existing control would work with whatever you suggest (eventually at least). The key points are fast reactions, big reactions (big dips), reactivity in all scenarios and no degredation/bleed over time or swapping. It would be wise to look at the preset settings I have right now (ignore baks) as examples of how I've had to tune the existing architecture in order to get middling results.

Ideally we'd also establish proper tests that show a lack of reactivity, delays or missed beats/reactions.

I'd appreciate it if you did online research after your local findings, from multiple sources and used them to aid your suggestions. Keep this entire Text in the new document word for word in the bottom sectioned off as "Original Request - Do Not Delete"
```

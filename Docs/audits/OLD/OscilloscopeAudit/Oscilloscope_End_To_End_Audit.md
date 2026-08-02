# Oscilloscope End-To-End Audit

Last updated: 2026-06-29

Status: closed to historical reference after runtime acceptance. Reopen only with fresh `--viz` / runtime evidence that Oscilloscope again strobes, loses ghost visibility, poisons idle/live boundaries, or falls out of sync with playback.

This audit covers the Oscilloscope visual failure where the mode looked like brightness flicker/strobe instead of a waveform warping with music, and could feel out of tune with the source. It is now a historical root-cause map and prevention checklist, not active work.

## Current Evidence

- Final runtime state: accepted after the 2026-06-29 pass. Idle starts without waiting for live playback, pause no longer needs to "break free", playback reads as waveform deformation rather than brightness strobe, line ghosts are visible with authored `osc_ghost_decay`, and visualizer preset cycling no longer clears media artist metadata.
- Latest preserved evidence: `.tmp/perf_collapse_evidence_20260628_164113/screensaver_spotify_vis.log`, around `16:35:07..16:35:13`.
- The Oscilloscope handoff itself looked structurally clean in that window:
  - mode switched to `oscilloscope`
  - engine delivered a fresh waveform generation
  - overlay reset happened before first push
  - `after_first_overlay_push` showed overlay generation and activation matching the engine
- The same window still had user-visible weak/strange behavior, with ghosting enabled and hot audio evidence shortly after activation:
  - `[SPOTIFY_VIS][GLOW] mode=oscilloscope ... ghost2=True ghost3=True`
  - `BARS raw_bass=3.529...`
  - transient logs show bass/mid energy while the mode was visible
- This weakens first-frame/activation as the primary suspect for the current visual complaint, while keeping it as a guardrail because visualizer first-frame poisoning has a long history.

## Scope And Guardrails

- Keep this work Oscilloscope-owned unless a stronger bar proves the shared waveform source is wrong.
- Do not touch shared Dynamic Floor, Bubble, Spectrum, Sine, DevCurve, or shared BeatEngine contracts for the first pass.
- Before any shared visualizer seam is touched, run the current-good visualizer lock from `Docs/Harness_Index.md`.
- Do not hide the issue by disabling glow, ghosting, or multi-line fidelity. Those are authored features.
- New logging must route through visualizer diagnostics (`--viz` / `--viz-diag`) and stay bounded.
- Fallbacks or failed renderer paths must remain loud.

## End-To-End Flow

1. Audio samples enter `widgets/spotify_visualizer/beat_engine.py`.
2. BeatEngine extracts the latest 256-sample waveform and tracks `latest_generation_with_waveform`.
3. `widgets/spotify_visualizer/tick_pipeline.py` requires a fresh waveform for `oscilloscope` before reveal.
4. `widgets/spotify_visualizer/config_applier.py` pushes waveform, smoothed energy bands, line settings, ghost settings, and transient event strengths into the GL overlay.
5. `widgets/spotify_bars_gl_overlay.py` stores current/previous waveforms, applies line-speed interpolation, maintains the ghost waveform ring, and smooths line-mode energy bands.
6. `widgets/spotify_visualizer/renderers/oscilloscope.py` uploads the waveform and Oscilloscope uniforms, including transient width/sensitivity modulation.
7. `widgets/spotify_visualizer/shaders/oscilloscope.frag` renders current lines, ghost lines, glow, band-reactive glow sigma/alpha, and final alpha composition.

## Suspected Failure Seams

### 1. Line-speed interpolation is probably too slow at authored preset values

- All curated Oscilloscope presets use low `osc_speed` values: roughly `0.18..0.33`.
- Overlay waveform interpolation squares speed before blending:
  - `alpha = speed * speed`
  - `0.18 -> 0.032`
  - `0.24 -> 0.058`
  - `0.33 -> 0.109`
- This makes low speed dramatically slower than the slider value reads, which can make the waveform feel out of tune or late.
- Because this is stored in the overlay before shader upload, the shader receives an already-lagged waveform.

Likelihood: high.
Risk if fixed poorly: medium. A speed remap can make old presets too twitchy if done without an oracle.
Safe correction shape: mode-owned perceptual speed mapping with a minimum responsive floor, guarded by tests that low-speed presets still move smoothly without lagging multiple beats.

### 2. Ghost trail compounds lag by trailing an already-smoothed waveform

- The ghost ring stores `self._waveform` before applying the next incoming waveform.
- If the current waveform is already low-passed by the squared speed contract, the ghost trail becomes a delayed copy of an already delayed signal.
- Early ring fill can also produce inconsistent ghost depth because the "oldest" index changes while the ring has not reached full delay length.

Likelihood: high for weak/late ghost perception; medium for brightness flicker.
Risk if fixed poorly: medium. Ghosting is authored fidelity and must not be silently removed.
Safe correction shape: add a bar for stable ghost delay and visibility; if current behavior fails, make the ring delay explicit and avoid early-fill current-ish ghosts.

### 3. Transient width mix repeatedly modulates line sensitivity

- `config_applier.py` peeks latest kick/snare events with max ages around `160ms..200ms`.
- `renderers/oscilloscope.py` uses those event envelopes every frame to rewrite `u_sensitivity`:
  - `sensitivity *= 1.0 + beat_drive * transient_width_mix`
- This does not warp the waveform source. It scales/saturates it with `tanh`, which can read as line width/brightness popping rather than coherent audio motion.
- Because the event is peeked over a time window, the same transient can influence many frames and feel visually out of phase.

Likelihood: high for "flickering instead of warping".
Risk if fixed poorly: medium. Transient response is a real authored feature; do not delete it without a replacement contract.
Safe correction shape: keep transient support Oscilloscope-owned, but move it away from repeated raw sensitivity rebasing if the oracle proves strobe. Prefer a bounded accent/warp lane over a second amplitude authority.

### 4. Reactive glow may be acting as a brightness strobe

- `oscilloscope.frag` makes reactive glow change both sigma and alpha from band energy.
- Final composition normalizes RGB by final alpha, so alpha changes can read as brightness/opacity changes rather than shape changes.
- With low waveform speed, glow can react immediately while the waveform lags, which makes the mode appear to flash instead of warp.

Likelihood: medium-high.
Risk if fixed poorly: high. Glow is visible authored fidelity and also shared conceptually with Sine, though shader code is mode-owned.
Safe correction shape: test a visual brightness-stability oracle first; keep glow intensity as master visible-strength control and only retune Oscilloscope shader math if evidence isolates it.

### 5. Raw waveform extraction is less likely but still a shared seam to protect

- BeatEngine currently takes the last 256 samples from a flattened audio array.
- If multichannel data is flattened interleaved, the Oscilloscope line may not represent a single clean channel.
- Sine Wave also relies on waveform source and is currently considered good, so this is not the first seam to edit.

Likelihood: low-to-medium.
Risk if fixed poorly: high. Shared waveform extraction touches Sine and Oscilloscope and can reopen first-frame/source-timing bugs.
Safe correction shape: only inspect after an Oscilloscope oracle proves source mismatch while Sine remains green.

## Required Automation Before Runtime Fixes

- [x] Add an Oscilloscope waveform-response oracle that compares input waveform change timing against displayed/transported waveform change timing for low-speed presets.
- [x] Add a ghost-stability oracle that fails when ghost trails are current-ish during early fill or excessively delayed after steady state.
- [x] Add a transient-width strobe oracle that feeds repeated kick/snare events over a sustained waveform and fails if sensitivity/visible amplitude chatters while the waveform source is stable.
- [x] Add a reactive-glow brightness oracle that proves glow changes do not dominate visible movement when the waveform is supposed to be the primary actor.
- [x] Add a live-to-idle oracle proving Oscilloscope clears stale live waveform/ghost/transient display state before accepting the paused idle waveform.
- [x] Keep existing line-mode plumbing tests green: settings/preset transport, secondary ghost toggles, shader uniform availability.
- [x] Add settings/preset/runtime transport for `osc_ghost_decay`, including creator kwargs and binding coverage.
- [x] Add a narrow media metadata bar proving visualizer preset cycling does not refresh/clear the media widget's artist snapshot.
- [ ] If this issue reopens, run current-good visualizer locks before touching any shared waveform/tick/overlay seam.

## Implementation Order

1. Add bounded Oscilloscope diagnostics under the existing visualizer diagnostics CLI family:
   - `osc_speed`
   - resolved waveform interpolation alpha
   - waveform delta
   - ghost alpha and ring fill depth
   - transient width mix
   - sensitivity before/after transient modulation
   - smoothed band energy/glow drive
2. Add the failing Oscilloscope-specific oracle bars above.
3. Fix the line-speed mapping if the low-speed response bar fails.
4. Fix ghost ring delay/fill behavior if the ghost stability bar fails.
5. Fix transient width authority if the transient strobe bar fails.
6. Only then adjust shader glow composition or presets.

## Implementation Progress

- [x] Added `widgets/spotify_visualizer/oscilloscope_contract.py` for mode-owned display consumption helpers.
- [x] Replaced squared low-speed waveform blend with a perceptual Oscilloscope-owned alpha mapping.
- [x] Made ghost ring fill/delay explicit so the ghost does not sample a just-written/current-ish frame during initial fill.
- [x] Bounded transient width modulation so repeated kick/snare peeks act as display accent rather than a second amplitude authority.
- [x] Added bounded Oscilloscope diagnostics under visualizer diagnostics.
- [x] Added pure contract bars for low-speed response, ghost delay, transient-width boundedness, and mode isolation.
- [x] Reduced Oscilloscope shader reactive-glow alpha pumping so reactivity primarily widens/shapes the glow instead of flashing brightness.
- [x] Restored paused startup idle reveal parity with Bubble/Sine/DevCurve so Oscilloscope can start on its own idle seed.
- [x] Cleared stale live waveform, ghost ring, and line transient envelopes on Oscilloscope live-to-idle entry before accepting the idle waveform.
- [x] Retuned the first alpha mapping downward after runtime showed the initial low-speed response became strobey rather than readable.
- [x] Added display-only live waveform conditioning so raw PCM playback windows become spatially softened, gain-bounded, and phase/sign-aligned before blending.
- [x] Added idle-to-live carrier reset so the coherent idle seed cannot poison the first live playback line.
- [x] Fixed repeated paused media snapshots extending the pause-confirmation debounce; identical paused/stopped updates now keep the original countdown.
- [x] Fixed paused warm-capture waveform poisoning; after non-playing is confirmed, the beat engine may drain warm frames but must not accept them as waveform authority over the idle seed.
- [x] Added authored `osc_ghost_decay` plumbing so Oscilloscope ghost visibility/fade rate is adjustable without changing shared ghost contracts.
- [x] Fixed visualizer preset cycling so it writes only `widgets.spotify_visualizer`, preventing a visualizer-only mode change from refreshing/clearing media metadata.
- [x] Runtime-checked Preset 2 and idle entry against the corrected display contract; no curated Oscilloscope retuning is currently required.

## Closure Notes

- Keep this audit as the first reference if Oscilloscope reopens, especially if the symptom sounds like strobe, ghost invisibility, pause-boundary flash, or out-of-tune waveform movement.
- Do not resurrect the failed shape of solving Oscilloscope through shared audio/floor changes. The successful fixes were mode-owned display consumption, idle/live boundary authority, and scoped visualizer settings writes.
- Keep media metadata preservation as a sibling regression guard: visualizer-only actions should not force broad media widget refreshes.

## Non-Goals

- No Bubble/Spectrum/Sine/DevCurve retuning.
- No shared floor/audio smoothing changes.
- No disabling Oscilloscope ghosting, glow, or multi-line features as a fake fix.
- No UI-thread repaint/update retries.
- No preset rewrite until the runtime contract is proven.

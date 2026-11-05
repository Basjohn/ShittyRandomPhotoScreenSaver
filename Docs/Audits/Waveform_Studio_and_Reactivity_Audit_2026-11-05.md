# Waveform Ribbon: reactivity, visual and Studio audit (5 November 2026)

Audit owner for the 5 November Waveform pass. Live sequencing stays in `Current_Plan.md` §7.1; this document records
the evidence, the decisions taken from it and the execution plan. Design input: the operator's Studio design pack
(`Docs/Audits/SRPSS_Waveform_Studio_Design_Pack_2026-11-03.zip`: UX/architecture brief + concept mock). The pack is the
UX direction, not a renderer specification; the mock is an interaction/styling target, not implementation evidence.

## 1. Evidence method

New tool: `tools/visualizer_replay/waveform_ribbon_motion_audit.py`. It replays recorded PCM through the configured
production worker, transient bus, frame runtime and dynamics projection on deterministic timestamps and measures the
**published body itself** (world units over the scene interval |x| ≤ 18): union vertical envelope, per-ribbon
peak-to-peak, sheet half-width, along-body inflections per unit (lumpiness), centre-line speed/second difference, plus
correlation of envelope against bass and passage with a lag search. The control replays the same clip with the
controller's media state paused, so the mode sees true idle while every other input is identical.

Pitfall found while building it: setting only the replay engine's playback flag leaves the controller "playing"; the
first "idle control" was therefore identical to music. The tool sets `controller.playing`, which the mode reads.

Evidence directory: `.artifacts/evidence/waveform_ribbon/studio_20261105/` (receipts are evidence, not task status).

## 2. Findings: does music reach the deformation consumers?

Preset 3, `ragdoll_quiet_intro_loud_end1`, 5–55 s, curated activation (no overrides):

| Measure | Music | True idle control |
| --- | ---: | ---: |
| Union vertical envelope p50 / p95 (world units) | 4.17 / 5.19 | 0.52 |
| Mean per-ribbon peak-to-peak p50 | 2.85 | 0.44 |
| Envelope, quietest passage quartile p50 | 4.18 | – |
| Envelope, hottest passage quartile p50 | **3.84** | – |
| Correlation envelope ↔ height drive | **−0.05** | – |

**Conclusion 1 — music reaches the body** (≈8× the idle envelope): the live/replay handoff, passage foot and event
admission corrections of 3 November hold in replay. "No change from paused to playing" is not reproduced offline; the
native/live parity question in Current_Plan stays open for a live check, but the body is not dormant.

**Conclusion 2 — the body does not breathe with the music.** Hot passages are *smaller* than quiet ones and the
envelope is uncorrelated with its own height drive. Counterfactual with axial roll disabled (same clip/preset):
envelope ↔ height drive **+0.36**, ↔ passage **+0.37**, hot quartile 4.23 > quiet 3.97. Root cause in
`core/waveform_ribbon_dynamics.py:snapshot`: Height and Bend scale/displace only the pre-rotation **Y** carrier, Depth
only the pre-rotation Z, and the whole body is then rolled about world x. Roll speed itself rises with music, so the
louder the passage, the faster the musical vertical excursion is rotated into depth — invisible from the long-lens
front view. The roll destroys exactly the response the operator asked to double.

**Conclusion 3 — quiet→peak ranges are compressed by the passage domain.** On this clip the published passage spans
p05–p95 = 0.58–0.77 and the Height drive (passage^1.6) 0.42–0.62. Every authored quiet→peak range is therefore used
over roughly a fifth of its width; Preset 3's Height `[0.35, 3.0]` realises ≈1.5–2.0. Increasing gains would only move
the narrow window, not widen it. Body bands (fixed reference) swing far more (bass 0.36–0.83 within the same window),
but reach geometry only through `bass^1.3 × passage` into spring targets on a *standing* spatial sine.

**Conclusion 4 — the bend is a standing wave.** `bend × 1.1 × b × sin(.45x + owner·.7)` is fixed in scene x while the
carrier slides through it, so its contribution reads as a stationary inflating lump field rather than a sweep that
belongs to the travelling cloth — one source of the "lumpy/bumpy" rejection.

Lumpiness today: 0.17 inflections/unit p50 (smooth long sweeps); centre second difference p50 is 36× idle. Motion is
present; its *shape* and *scaling* are wrong.

## 3. Visual audit (native production capture, Preset 3, 20–30 s, 1280×560)

Capture: `studio_20261105/baseline_p3_ragdoll_20s/` (MP4 with original audio, five native frames, receipt).
Against `references/Preset3Goal1.png`, `Preset3ReactivityGoalExample.png`, `Mist Goal.png` and the operator's
3 November material baseline:

- **Ribbons:** colour identity, rims and translucent bodies are close to the baseline the operator liked. Missing:
  the references' fine lattice (cross-hatched filaments), denser white-hot crossings at peaks, larger peak arcs.
- **Floor:** the dominant fidelity gap. A hard luminous horizon line, then blurred reflection blobs over near-black.
  References: continuous textured wet concrete to the bottom edge, long vertical streaked reflections broken by the
  surface, horizon dissolved into mist.
- **Particles:** sparse isolated specks. Reference high-react: dense luminous halo of points around crests and arcs,
  colour-matched to the ribbon that emits them; low-react: a few.
- **Atmosphere:** the background is acceptable dark; the mist goal's gentle ground haze and soft glow around the body
  are mostly absent at this framing.

## 4. Studio architecture audit (design pack §14 questions)

- **Which response model?** Not 14×6. The Studio framework must accept a provider-driven target/source schema; the
  Waveform adapter supplies its current targets. The framework never names ribbons or bands.
- **Truthful preview:** `ui/widgets/waveform_ribbon_preview.py:render_samples` already drives the production
  `WaveformDynamics` + `CompiledWaveformSettings` + `WaveformScene.render` with `physical_view` into an offscreen
  target. A Studio viewport can own a *separate* `WaveformScene` instance and its own deterministic
  `WaveformDynamics` evaluator (same code, same inputs → same output), never the desktop visualizer's GL objects or
  logical history. Recorded clips use the existing `ReplayBeatEngine` + `PcmReanalysis` production analysis; synthetic
  fixtures feed the same `advance()` signature. That is a sandbox *timeline*, not a second model or clock.
- **Rendering in Qt Quick:** first slice renders through the existing `OffscreenRenderTarget` on the Studio window's
  own GL context and presents the frame as a Quick texture; per-mouse-move work is coalesced to one render per Quick
  frame. Readback is acceptable for the first slice only if measured; the next step is presenting the FBO texture
  directly. No sharing of mutable GL owners with the desktop visualizer.
- **Settings lifecycle:** Studio is a top-level `QQuickWindow` (same process). Settings is hidden only after the Studio
  has exposed its first frame; closing restores the *same* dialog, page and scroll and refreshes it from the canonical
  snapshot. Edits go through one typed edit session and the existing Custom/preset save path.
- **Reuse for 3D modes:** shell, viewport host, gesture binding, transport, response curve, gradient strip and
  lifetime timeline are mode-neutral; a mode contributes an adapter (schema, evaluator, fixtures, scene selection).

### Studio viewport decision

Chosen: **(a) a Studio-owned inline `QSGRenderNode`** (`ui/studio/viewport.py`) whose render-thread renderer is
the mode adapter's; for Waveform that renderer wraps the production `QuickWaveformRibbonRenderer` (its own
`WaveformScene`) and is fed a `WaveformRibbonFrame` built exactly as `capture_waveform_ribbon` builds it, from the
Studio's own `WaveformRibbonFrameRuntime`/`WaveformDynamics`. This supersedes the "offscreen target + present as
texture / readback" first slice above.

- **Why not (b) the production `VisualizerRenderItem`:** it is bound to a `VisualizerSnapshotBridge`, runtime
  identities, `ResolvedVisualizerPresentation` card shell/clip SDF and mode registry resolution. A Studio bridge
  would have to forge runtime identities and presentation for a non-runtime surface; the render node, mode
  renderer and `WaveformScene` are the parts that carry visual truth, and (a) reuses exactly those.
- **Why not `QQuickFramebufferObject`:** an extra FBO + texture node and a copy per frame; the production scene
  already renders into its own scene target and composites through the item quad, so it can draw inline.
- **No readback, no rebuild per edit:** pixels go straight to the window framebuffer. The GUI thread evaluates at
  most once per Quick frame (`afterAnimating`), only when an edit, scrub or playback moved; a live drag
  re-publishes the current instant (dt = 0) and the gesture end replays exactly. Renderer resources live across
  edits; GL is released on `sceneGraphInvalidated` / node release with the scene-graph context current.
- **Measured** (`tools/waveform_studio_capture.py`, hidden `QQuickRenderControl`, 1600×900, Preset 3, Peak fixture,
  this workstation, system load not controlled, glFinish per frame, playing): whole Studio frame p50 17.0 ms /
  p90 19.9 ms (QML shell + production scene + one logical step); one logical evaluation step p50 2.9 ms /
  p90 6.5 ms. Relative only: GPU timer queries and a no-scene control are still open. A backward scrub replays from
  the fixture start (≈1.3 ms per logical step; a full 10 s synthetic fixture ≈0.9 s); forward scrubs are
  incremental. The threaded visible window was not measured (no visible windows in probes).
- **Settings concealment:** Settings lives inside `QDialog.exec()` in the runtime; `QDialog.hide()` would end that
  loop and close Settings. The Studio conceals the same window natively (`ShowWindow(SW_HIDE)`) after the Studio's
  first swapped frame and shows it again on every exit path; the Studio window is application-modal so the modal
  Settings loop does not block it.

## 5. Decisions (what is superseded, and why)

Checkpoint before these changes: commit `checkpoint: Waveform pre-Studio baseline` (pushed).

1. **Axial roll stays, but musical vertical response becomes roll-invariant.** Supersedes the 2 November projection
   order (musical deformation applied before the roll). The operator's skewer roll remains a visible rotation of the
   cloth and its helix phase; Height/Bend now act on the world-vertical after the roll, so the louder passage can no
   longer hide its own excursion. Evidence: §2 conclusion 2.
2. **Quiet→peak range position follows a calibrated musical drive, not raw passage alone.** Supersedes "the passage
   alone places every range". A fixed (never learned) mapping widens real music's narrow passage window and blends in
   a medium-time body-energy envelope so phrases and beats move ranges inside a passage. Anchors come from pooled
   recordings, like the existing raw references.
3. **Bend travels with the cloth.** Spatial bend modes are evaluated in cloth (history) coordinates, so a bend is a
   sweep carried by the ribbon rather than a stationary lump field.
4. **Range-slider policy:** the design pack's control policy (§9) supersedes the 1 November "every pair is a range
   slider" rule for the authoring UI. Serialized `[low, high]` data is unchanged.
6. **Opt-in Dynamic Zoom (operator request, 5 Nov)** supersedes "music never changes the lens" for that option
   only: `WaveformDynamics` holds a sustained-level follower (2.5 s up / 4 s down) and a zoom state (1.2 s out /
   7 s in, ±20%), frozen while `view_camera_operated`; `physical_view(zoom=)` scales the lens extents only. Off by
   default in every preset; tests in `tests/test_waveform_dynamic_zoom.py`.
7. **Travelling energy pulse replaces the standing elastic bend (operator, 5 Nov).** The operator judged R1/R2 motion
   "fundamentally wrong": reactions must feel like water waves, gentle but strong, always WITH the waveform's shape.
   Root cause in source: Bend inflated a fixed spatial sine the travelling ribbon slid through. Alternatives weighed
   (research: damped wave-equation height fields; Gaussian wavelet packets carrying `sin(kx-wt)`): both add their own
   crest/trough oscillation on top of the ribbon, i.e. motion against its shape. Chosen: a travelling *envelope*
   that multiplies the waveform's own displacement about its axis (sign never flips), plus width/light/colour.
   Beats inject (typed hits + body-energy rises above 0.08), no steady baseline (it merged swells into a bulge);
   dense rhythms form a moving swell train. Controls: direction, width, speed, colour shift, fade; Bend range =
   Pulse Strength. Evidence: `pulse2_p3_ragdoll_20s/` and `strip_pulse2_t5.png` (125 ms steps).
   Open operator options, not yet built: **Frozen past** (a passing swell leaves the parts it shaped holding their
   colour/size/shape until the next swell arrives) and a **selectable reaction mode** if a second model reaches
   comparable fidelity (Studio + presets). Neither is a reason to keep the rejected standing bend.
5. **The Settings Custom body for Waveform** becomes the sparse Studio launcher (button + camera-save checkbox), per
   the pack. The rejected builder stays reachable only until the Studio covers every field (Advanced coverage gate).

## 6. Execution plan and gates

Ordered; each step has its own evidence. `[ ]` open, `[~]` candidate awaiting evidence/validation.

- [~] **R1 Reactivity correctness:** roll-invariant vertical response, calibrated range drive, travelling bend.
  Gate: motion audit on ≥3 clips — hot-quartile envelope ≥ 1.6× quiet-quartile on the dynamic clip, envelope ↔ drive
  correlation ≥ 0.6, idle unchanged within 10%, inflections/unit not above baseline; native capture with audio.
  **Candidate landed (`core/waveform_ribbon_dynamics.py`), awaiting operator eyes/ears.** Preset 3, four clips,
  `motion_audit_r1a_p3_*.json` vs `motion_audit_baseline_p3_*.json`:

  | Clip | Per-ribbon p-p hot/quiet (before → after) | Hot p-p (before → after) | Envelope ↔ level r |
  | --- | --- | --- | --- |
  | ragdoll_quiet_intro_loud_end1 | 0.84 → 1.55 | 2.39 → 4.76 | 0.00 → 0.88 |
  | human_heavy1 | 1.97 → 1.94 | 2.80 → 3.26 | 0.68 → 0.75 |
  | nightsolong_acousticsoft1 | 1.00 → 1.70 | 2.82 → 5.24 | 0.60 → 0.93 |
  | anything_mixed2 | 1.77 → 1.88 | 3.22 → 5.10 | 0.62 → 0.89 |

  Idle control unchanged (0.52 → 0.51); inflections/unit unchanged or lower (0.15–0.18). Union-envelope hot/quiet on
  ragdoll is 1.51, just under the 1.6 gate: the bundle's own separation sets a floor on the union, while per-ribbon
  shape change passes. Centre speed roughly doubled with amplitude (second difference scales with it); smoothness
  is a native-motion judgement, see `strip_baseline_vs_r1a.png` and `r1a_p3_ragdoll_20s/motion_with_audio.mp4`.
  A hard clamp in the calibrated span pinned a sustained hot bass at exactly 1.0; it now uses the body lanes' soft
  knee (focused test). Operator direction (5 Nov): peaks may rise high; the framing zooms out instead — all three
  presets and the canonical default lens moved from 3° to 5° (integer control), no vertical ceiling.
- [ ] **R2 Punch and grace:** kick impulses visible as a fast vertical lift with a slow graceful settle; no twitch.
  Gate: attack ≤ 120 ms to 70% of peak excursion, settle 0.5–1.2 s, second-difference p95 not worse than baseline ×1.5.
- [ ] **V1 Floor fidelity:** continuous textured wet foreground, long vertical streaked reflections, horizon dissolved.
  Gate: mock | ours sheets at matching framing; reflection OFF still shows material; no hard horizon line.
- [ ] **V2 Particles and lattice:** dense crest-attached halos at peaks, few at quiet; fine lattice texture.
- [ ] **S-A/B Studio shell + truthful preview:** in-process window, Settings hide/restore, live production preview with
  synthetic fixtures and recorded clips, play/scrub, edit session with undo, save through Custom.
- [ ] **S-C Composition + Reactivity workspaces** with target-first tuner, source mix, response curve, measured traces.
- [ ] **S-D Appearance + World workspaces;** **S-E** second-mode adapter proof, teardown, performance.
- [ ] **P Optimization** only after visual/reactive gates, with deterministic packet parity and pixel/temporal parity.

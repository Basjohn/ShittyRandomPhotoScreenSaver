# Future Work

The single router for **deferred** work. `Current_Plan.md` owns active sequencing. Implemented capability belongs in
`Spec.md` / Architecture / Guardrail / Guide / Reference documents; rejected mechanisms belong in Historical Bugs.

Nothing in this file is automatically admitted. The operator or `Current_Plan.md` must promote an item before implementation.

## 1. Admission rules

For any deferred feature that becomes active:

- record the visual/product contract and concrete acceptance gate before coding;
- join existing canonical registries/descriptors/defaults rather than creating a second catalog;
- use the retained Qt Quick presentation authority and existing lifecycle/resource owners;
- preserve lazy resolution, retirement and count-invariant dormancy;
- use deterministic inputs/seeds and bounded state where applicable;
- prove real Quick rendering, lifecycle and measured CPU/GPU/resource cost, not only an offline preview;
- remove rejected experiments cleanly rather than retaining dormant fallback architecture.

Transition and Visualizer membership is deliberately **count-neutral** here. Source registries own the current catalog; future
docs should not encode a cardinality that becomes stale when another effect is registered.

## 2. Graphics API horizon.

Decided 5 Nov 2026: `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`. SMP & Full Display go next; the
eventual Vulkan backend is a native render core on Qt Quick's Vulkan RHI (DLSS/FSR via native handles), started on
measured triggers (never a Python-driven Vulkan port); mixed resolution for soft layers meanwhile (whole-frame
upscalers rejected); port-readiness rules bind new GPU code.

*Superseded in part on 12 Nov 2026 (the document's own addendum and `Native_Core_P3_Decisions.md` D5 to D11):*
the native core is no longer waiting on triggers. It is admitted work, `Current_Plan.md` item 8b, with Vulkan the
default and OpenGL selectable. **Further superseded by the operator on 23 Nov:** SMP no longer immediately follows
NF; it is deferred until **after Melt Pool, Concrete Rain and substantial QoL work**, on renewed operator admission
(§2.5).

## 3. Visual concepts

Accepted transition membership belongs to the canonical registry and `Docs/Reference/Transitions.md`.

The Visualizer programme in `Current_Plan.md` §7 retains Waveform Ribbon's existing work, then after the
native-core flip the **new** modes run **Reactive Liquid / Audio Melt Pool → Concrete Rain**. Usu Moonscape stays
a separately admitted, later long-horizon concept (not a blocker to eventual SMP consideration). The shared
3D primitives are planned in `Current_Plan.md` item 8b (N4/N6). These new modes precede SMP, not the reverse;
Expanded Visualizer is already accepted. The cross-backend port-readiness rules remain binding on legacy
mode ports; N6.7 governs explicitly Vulkan-only new content. Their contracts:
`Docs/Future_Work/Waveform_Ribbon.md`, `Docs/Future_Work/Melt_Pool.md`, `Docs/Future_Work/Concrete_Rain.md`,
`Docs/Future_Work/Usu_Moonscape.md` (with `Usu_Blender_Work.md`). **23 Nov 2026 implementation refinement:**
existing modes retain OpenGL/native-Vulkan port parity; the first two *new* modes after the Vulkan-default flip,
Melt Pool then Concrete Rain, may be Vulkan-only and use the N6.7 mesh-shader route without a forced OpenGL twin.
Optional drifting kelp/leaves in accepted Extruded Bubble is only a conditional N6.7 proof, off by default, never a
flip blocker. Other mode concepts were dropped on 2026-10-25; the
architecture they called for is the shared step in `Current_Plan.md` §6.

### Usu Moonscape: character/world foundations (deferred until §7.4)

Usu walks, runs, Naruto-runs, skids/falls/gets up and lies down across a round moon under a starscape, with orbit
framing and optional fuzz-tip bloom. Its missing foundations, proven one at a time in offscreen harnesses before
combining (no physics engine, no extra animation clock):

- **S19 → S20:** deterministic validated Blender/glTF bake with provenance-stamped packed assets, then shared
  material/instancing static-mesh rendering. Runtime consumes packed data, not Blender authoring graphs.
- **S21 → S22 → S23:** bounded GPU joint palettes/skinning; logical-time clip sampling/crossfades/masks/additive
  layers/root motion/eye tracks; deterministic secondary-motion springs. Usu static silhouette approval remains a
  separate hard gate.
- **S24:** opt-in felt/sheen/bounded fuzz shells and emitted tips; preserve existing shaders and measure tier costs.
- **S25:** the shared shadows of `Current_Plan.md` §6 (S3D-6). **S27 → S26:** prove world-view projection distinct from
  the photo-plane camera, then seeded sphere/crater/stars and logical travel. Bordered consumers use the shared framed
  camera input/persistence; unframed world travel may differ in projection, never duplicate framed-camera authority.

## 4. Deferred maintenance / product work

- Give managed worktrees distinct evidence and scratch junction targets (`tools/artifact_paths.py`).
  Codex worktrees can share the leaf directory name, so the current leaf-based key merges their evidence roots
  and can race first-use junction creation. Preserve existing evidence and update the handover path resolver
  alongside new keys. Until then, use distinct run labels for parallel managed worktrees.

Keep these deferred unless new evidence or an explicit request promotes them:

- ImageWorker lean-spawn entry and residual memory-footprint follow-up;
- `--usage` observer-cost refinement and residual handle-slope attribution;
- remove `SounddeviceBackend`'s unreachable Windows WASAPI selection path after the factory's canonical PyAudioWPatch
  Windows routing; its non-Windows input-device policy also needs an explicit source-selection contract rather than
  silent first-device prioritization;
- Widgets-tab stale position estimates and overfull authored-display planning cost;
- Weather child-edit loading height and low-priority Settings FlowContainer polish;
- surface-preference SSOT cleanup and narrowing broad Qt-test slot-miss suppression;
- Spectrum extreme-viewport smoothness where physical evidence demonstrates a defect;
- installed archive Foundry Windows-diff acceptance;
- wallpaper-feed consolidation only where shared normalization simplifies code without merging cache/scheduling authorities;
- direct live source reconfiguration outside Settings still discards its coordinator without generation retirement
  (`engine_handlers.on_sources_changed`). Audit that separate entry point before admitting external live source edits;
  the Settings resume path already uses the strict runtime/dialog destruction barriers.
- shared HTTP all-phase cancellation: `requests.get` can remain inside status/header parsing while a peer trickles
  bytes, despite per-socket timeouts. Body `read1` cancellation does not solve that phase. Prove it with a bounded local
  server before admitting a transport-level correction; retain strict runtime destruction barriers and refuse source
  cache-writer overlap. Do not add private socket cancellation, weaken retirement or claim a hard deadline from read timeouts;
- Steam asset-cache/catalog reconciliation if missing-image requests recur: the 2026-10-07 loaded RUN received HTTP 404 for
  asset hashes `4b349d51e996` and `3f5b734df3c5`. Resolve the source identities and verify failure backoff before changing asset admission;
- persistent shader/program cache: the GL program binary cache landed 8 Nov (8c4bec4d,
  `rendering/quick/render/gl_program_cache.py`, R-180); only a further measured residual cold-compile hitch after
  gradual warm-up reopens it;
- bindless/sparse texture extension research only for a concrete consumer and without a permanent duplicate renderer path.
- optional long-tail test-oracle cleanup from the completed durability tranche: manually review remaining default-pin,
  source-string and exact-UI-copy advisory candidates only when touched or when they obscure a real contract. Preserve deliberate
  compatibility mappings, goldens, geometry/state oracles, architecture-negative bars and wording contracts; do not turn the
  advisory queues into a standing release blocker or a project-wide rewrite campaign.

### EB composition-lab clean. Clean up scratch and no longer needed files related to labs unless they explicitly help a future visualizer lab implementation.


**Cross-profile Live Settings is already independently admitted in Current Plan 1B.8 as product
QoL, AFTER M4, Theme Studio and Concrete Rain.** Full implementation design:
`Docs/Future_Work/Live_Settings_Transactional_Runtime_2026-11-23.md`.
It establishes the future shared Settings session, live per-owner changes, scoped retire,
optional masking fade, last-resort full teardown and Winlogon-safe admission. It does NOT
advance SMP M0: when separately readmitted, SMP M8 consumes this foundation and still
implements its player-specific audio, queue, library, output-device and SMTC policies.

### 2.5 SMP: deferred long-term work, not an active milestone (operator, 23 Nov 2026)

**Admission order:** finish the native-core parity/flip, Reactive Liquid / Audio Melt Pool, Concrete Rain and a
substantial QoL pass over the current product. SMP is considered **only on renewed operator instruction**, after
reviewing the result of that QoL work. The earlier "SMP foundations first after NF" decision of 12 November is
superseded. Completion of NF, theme unification, N6 primitives or a specific date **does not** automatically
authorise SMP M0. No SMP implementation or proto-service now, including the library, playback engine, SMTC,
`--smp` gating, skin ZIP system or desktop profile.

**Sole complete implementation plan:** `Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`
(§0A phase ladder M0-M10, §13-16A operator targets), with source/PCM contract
`03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`, the complete full-player visual brief
`04_Full_Player_Mock_2026-11-11.md` (all R1-R16, proposals and operator clarifications), and
`05_Theme_Skin_Studio.md`. The original phase **internal order** is preserved when eventually admitted; the
old *entry date/order* is not. References and images in ignored `references/` remain operator-owned, not
reconstructed or deleted. Prior planning ZIPs were superseded by the tracked documents.

**Preserved decisions transferred out of Current Plan item 9 (12-21 Nov):**

- SMP remains a **separate build/profile in the same SRPSS repository**, not a new repository or a runtime
  profile-switching service. Its future library, playlist and playback work begins at M0/M1 in the original
  Dashboard-first sequence, with the two panes as one feature; `--smp` remains an opt-in until accepted Gate M9.
  The exact order of Library/Playlists, playback, Expanded Media, dock/host, live Settings and release is
  already specified in plan 02 and is not reopened by this deferral.
- **Native audio from the first real audio slice** (operator, 16 Nov): M3 is one C++ SMP audio engine,
  FFmpeg native decoding, own PCM/DSP scheduling and event-driven WASAPI shared/exclusive output. No temporary
  Qt Multimedia prototype or later backend rewrite. Share native-core tooling, tracing and ownership
  conventions but **not** the GPU device, render/GUI thread, audio clock, event loop or failure domain;
  Python handles application policy, not sample delivery. Prove decoded PCM versus audible timing;
  keep the existing one-Visualizer-owner, any-host design. See plan 02 §4/§13 and seam 03.
- **Appearance/UX:** M0/M1 consume typed versioned semantic shapes, surfaces, typography and motion tokens,
  full sharp-to-pill/inner-junction geometry and reusable Qt Quick Studio hover/bounce motion with
  reduced-motion policy. M0/M1 later adds safe opt-in target-scoped `.srskin` ZIP support. M2 retains
  SQLite/FTS5, virtualised indexed views and measured 50k/250k-track concurrency, recovery and migration,
  without a custom database core (plan 02 §3.3 / §8.2A). The standalone SMP and Dashboard/library presentation
  share the existing native renderer, not a duplicate.
- **Existing current-product theme/material work stays active, independently of SMP:** `Current_Plan.md`
  1B.8 M3 material border, Context Menu/Now Playing/seeking surfaces and M4 **Unified Appearance Theme**;
  the pre-existing **Theme Studio** still follows the native-core flip and M4. It edits current themes only.
  Future SMP M10 extends that same studio with ZIP skin authoring and Full/Compact previews, without
  a second studio or retroactive theme migration. Nothing in current M4/Theme Studio adds an SMP pane or
  skin loader ahead of SMP admission.
- **Original pre-SMP prerequisites** in plan 02 §0A remain conditional entry requirements, **not**
  newly opened current-plan checklist tasks. The historical checklist records AC-01/02/03, service lifetimes,
  one Media/Visualizer owner and dormancy. Complete the *admitted* shared compositor, material and native
  primitives necessary for the current modes; don't treat speculative future primitives or all deferred
  work (for example Usu) as automatic gates to SMP.
- **Retained full-player mock requirements:** R1-R16 and the 11 Nov clarifications stay in document 04,
  with the two host types, one logical Visualizer owner, reusable Edit controls, custom layouts, skin/playlist
  needs and explicit design freedom. The three outstanding clarifications in its §6
  (`CS`, Lyrics/Artist Collage first milestone, wider dock model) remain deferred until the operator answers;
  no current work waits on them.
- **Retained future import isolation:** `ui/settings_tabs.py` currently imports Settings tab modules at
  import time. Plan 02 §14's SMP-only build import-scan requires moving those imports into appropriate
  builders **when the SMP profile descriptor is implemented**, not in unrelated current-theme work.
- **Retained hot-plug watch:** a future audio-output-device hotplug/reopen case belongs with SMP/Library
  audio endpoint work. Current capture-path testing remains in `Current_Plan.md` 1B.14; revisit the
  playback endpoint only when M3 is admitted.

**Design-not-to-lock-out boundary, binding on today's work but not an SMP implementation task:**
`Docs/Guardrails/Presentation_Change_Preflight.md` keeps Media/Now Playing/seekbar host-independent;
Visualizer retargetable across displays and future hosts at arbitrary aspect; Edit handles/transactions
reusable; and native rendering independent of a wallpaper compositor. No new SMP abstractions,
services, layout registrations, settings tabs or speculative dual-host implementations are required to
honour these invariants. The native core already establishes its future host boundary.

**Other graphics plan:** `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`
records the already accepted fullscreen Visualizer architecture, its 4K budgets and original
backend triggers. It is not a new SMP-phase prerequisite. SMP plan 02 still requires Expanded Media
in Dashboard before the standalone SMP profile once SMP work is explicitly admitted.

### Remaining non-code organization

- The dated-reports review is the plan's item 6 box (one owner).

## 5. Boundary

This is not a changelog or a completed-work register. When a deferred item lands, move its durable contract to the appropriate
current authority and remove it from this file. Retired/rejected work is routed through Historical Bugs and source control, not
kept here as a museum list.

### Shared widget glyph reveal / developer captures: R38 follow-up (not closed)

The physical action-handoff watch item lives in `Current_Plan.md` §5 (R38). The global Edit-only glyph handoff (existing session first, then existing command) remains required across all families; no new edit model or repaint/polling service. Diagnostic `\` capture is source/diagnostic only and requires native evidence of custom GL pixels before treating it as an accepted substitute for Snipping Tool. The UI presentation transition is not acceptance.

### Release catalogue/showcase work — explicit request only

Deferred by the operator on 28 October: animated catalogue reconciliation, visualizer showcases and catalogue
loop/metadata proof (formerly RM1–RM3), plus the Blinds Flat publication endpoint investigation (SC2). Do not maintain or regenerate these automatically after graphics changes.
Reopen only on an explicit request. Guided-setup stills are maintained per `Docs/Reference/Guided_Setup.md` (audited 2026-10-31).

### EB vectorised logical simulation (deferred by the operator, 2026-10-31)

The last measured lever on Extruded Bubble's frame age. Under the calibrated game-like load the logical tick is
~4.2 ms and holds the GIL ~38% of the time, which stalls the render and GUI threads. It is pure-Python per-bubble
motion, collision and wake work, and the bit-identical trims are exhausted
(`Docs/Audits/EB_Performance_Investigation_2026-10-29.md`). A NumPy structure-of-arrays rewrite is estimated at a
~2 ms tick and ~7-10 ms less frame age (22 → about 13-16 ms). It cannot be bit-identical: collisions are chaotic, so
it needs behavioural proof that reactivity, population, fusion and pop rates are unchanged on recorded music, plus
`tools/visualizer_live_check.py --load game60` evidence. The operator chose not to risk it now; reopen only on an
explicit request.

### Orthographic camera projection — removed 5 Nov 2026 (operator), not deferred

The former "optional EB Orthographic appearance parity" entry is withdrawn: Orthographic was removed from the whole
project ("its awful everywhere"). Perspective is the only projection for EB, Waveform and all future 3D modes;
there is nothing to reopen here.

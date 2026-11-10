# SRPSS documentation sweep: current contracts, historical plans, material borders (10 November 2026)

**Scope / authority:** Documentation-only review of the operator's latest complete working-tree archive,
`GODZIP_Studio_Camera_Fullscreen_2026-11-09.zip` (2,531 entries). `Current_Plan.md` remains the only live
ordered-work authority. The underlying source was inspected, not modified. This audit does not claim the
operator's Windows Qt Quick integration tests or native performance tests have run in this environment.

## Method and coverage

- Mechanically enumerated 234 Markdown documents (five root docs and 229 under `Docs/`), extracted 296
  local Markdown link targets and checked each against the supplied tree. Two links point to unavailable files;
  see below. Historical `.artifacts` evidence, shell commands, and code identifiers are not Markdown links.
- Read source ownership at `OverlayCard.qml`, `MaterialSurface.qml`, `surface_material.frag`,
  `rendering/quick/widgets/surface_material.py`, `ui/tabs/widgets_tab_defaults.py`,
  `core/settings/surface_opacity.py`, `core/settings/default_settings.py`, and the latest
  `ui/studio/settings_link.py`, `core/settings/visualizer_presets.py` to establish what is present.
- Cross-checked the current plan against `Docs/Contracts.md`, material architecture,
  Widget Styling guide, Expanded Visualizer and Graphics Backend decision plans, Studio reference and the
  saved Studio/Fullscreen overlay audit. Dated design records and acceptance evidence are not automatically
  wrong just because later phases were implemented.
- This is a targeted semantic review plus broad link scan, **not** a claim that every line of all 234 docs
  has been personally verified against runtime. Changes were restricted to proven conflicts and current
  ownership seams; duplicate context was retained where it serves different audiences.

## Resolved documentation contradictions and stale pointers

| Document | Problem found | Correction |
| --- | --- | --- |
| `Docs/Contracts.md` | Rejected optional materials in Widget Themes, declared framed Visualizer always Normal, and described per-text plates despite one-panel card design | Replaced outdated summary with a short current contract delegating details to material architecture |
| `Docs/Guides/Custom_Style_Implementation.md` | Listed global Surface Material default as Normal, and wrongly called material outside Widget Theme schema | Clarified **Theme** default, optional schema-v3 material, explicit family override |
| `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md` | Said future/not admitted although multiple phases already exist; companion path no longer matched tracked plan | Identified partially implemented phases, remaining evidence and canonical live plan; corrected companion path; retained historical phase gates |
| `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` | Old plan ZIP pointer and "No Vulkan backend now" could be mistaken for current status | Referred to tracked Expanded/SMP plans and added a dated P1/P2/P3 status note, preserving the 5 Nov decision |
| `Current_Plan.md` | H3 Linux worker-default step preceded inherited POSIX accepted-unread lifetime; M4 text understated completed packet-capacity/high-water coverage | Placed POSIX source repair before H3; separated implemented packet tests from pending owner/rendered parity. No Linux runtime pass invented |
| `Current_Plan.md` | P3 rendering scope omitted transition and image/background owners; Vulkan direction read as trigger-only | Described the one C++/QRhi core, gradual port, OpenGL fallback and eventual default Vulkan after raw-GL retirement |
| `Docs/Reference/Visualizer_Studio.md` | No durable contract for fullscreen S → teardown → Settings → Studio, transient camera/FOV, lazy mode-body readiness or QtGui window icon | Added one focused ownership paragraph without restating the full Studio lifecycle |

## Recent work accepted, with distinct field gates retained

The operator reported success for the most recent S-button Studio entry, camera handoff and Save Camera repair,
and for fullscreen Now Playing artwork-axis resizing, positioning-dependent left/right alignment and no
unnecessary re-fade on entering Edit. These are no longer live repair requests. The plan's corresponding
items have been narrowed to the **still-open** independent validation: fresh installed Standard/MC preset
writes and existing-file ACLs; long-text/album/control-layout and multi-size checks. This is an operator
acceptance of the reported functional behavior, **not** a fabricated completion of every mode/DPR test.
`Docs/Reference/Visualizer_Studio.md` and the existing fullscreen implementation/overlay audit retain the
behavior and failure mechanism.

## Material-aware widget borders: admitted to the plan, not implemented

Existing `OverlayCard.qml` has a material-filled card and a separate flat `Rectangle.border`. The shader already
has screen-space backdrop sampling, rounded-box distance and the border-width uniform. A single shader pass can
choose a material-tinted **border ring** in the same material item, with the Rectangle border hidden only when that
ring is actually rendered. No additional capture, blur, per-card framebuffer or per-frame Python path is needed.
This makes the proposal **architecturally viable** at likely modest *incremental* cost, but the exact impact on
shader cost, blending, AA and high-DPR visuals is not measured. Flat/Normal must preserve current pixels.

`Current_Plan.md` §1A (1.7b) now requires: material inheritance by default on material cards; Style Overrides
Border Material = Inherit Surface / Flat / Acrylic / Glass / Frosted / Mica / Smoked; independent Border Opacity
Adjust `-1..+1` with neutral `0`, persisted via the established Style Overrides owner; authored edge colour,
width and corner-radius authority; existing family border opacity unaffected; same shader/backdrop even with
an alternate border recipe; bundled `.qsb` regenerated; focused GPU and DPR testing. This includes the framed
Visualizer card where supported, not every unrelated control outline.

**Related outstanding visual task:** The supplied `surface_material.frag` still sets its legibility panel inset
to `borderWidth + 2.5/3px`, producing an additional inner material strip. The requested material-body-to-border
cleanup is combined with the border-ring shader task; content padding and shadow ownership must not change.
The current code has **not** yet implemented either change.

## Dead links / intentionally unedited history

1. `Docs/Reference/Waveform_Ribbon_Mist_Failure_and_Replacement.md` points to
   `../../.artifacts/evidence/waveform_ribbon/wr_live_game60_p2_profile_v1_20261102/summary.json`.
   The local evidence tree is not in the GODZIP. Retain the evidence locator rather than invent a substitute.
2. `Docs/Reference/Waveform_Ribbon_Visual_Authority_20261103.md` references
   `Images/Waveform_Ribbon_20261103_Operator_Live_Baseline.png`, which is absent from the supplied tree.
   Flag for asset restoration or deliberate pointer correction when the original image is available.

The September material rejection, 5 November backend decision, historical regression cases, code-check
checklists and current acceptance gates are intentionally retained. Their dated rationale differs from today's
implementation; updating their *current-status interpretation* avoids duplicating or erasing the evidence.
There is no evidence to close P2 Linux H3, POSIX lifetime, P3 native renderer, Settings Accent/native corner
clipping, native material-load measurements or the installed ordinary-user ACL gate.

## Hand-off verification

Only full Markdown files are changed; no application code, shaders, authored presets or test fixtures were
modified. Check against the supplied GODZIP for the exact changed-file list and preserved original line-ending
conventions. A source audit is not a substitute for Qt Quick rendered-pixel acceptance after implementing the
material-border feature.

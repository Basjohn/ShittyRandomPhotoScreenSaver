# Plan freshness pass, 12 Nov 2026

Scope: every open box (`- [ ]` and `- [~]`) of `Current_Plan.md` sections 1B, 1C, 1A, 3, 4, 7, 8 and 9 (item 8b skipped;
the "Item N" headings inside section 1 are out of scope but cited where a box duplicates one). Checked against the
source at HEAD `6816e510` and `git log`. Verdicts: LANDED (commit and code), STALE, DUPLICATE (the canonical copy is
named; the other box is the one marked), OPEN. Conservative: OPEN whenever the evidence is not in the code. Line
numbers are `Current_Plan.md` lines of this commit. A row that covers several boxes of one subsection says how many
(`n`). Nothing here names, lists or counts presets.

## Counts

| Section | Boxes | LANDED | STALE | DUPLICATE | OPEN |
|---|---|---|---|---|---|
| 1B | 55 | 0 | 0 | 6 | 49 |
| 1C | 49 | 14 | 0 | 0 | 35 |
| 1A | 34 | 1 | 0 | 0 | 33 |
| 3 | 57 | 0 | 0 | 2 | 55 |
| 4 | 30 | 0 | 0 | 3 | 27 |
| 7 | 114 | 0 | 0 | 0 | 114 |
| 8 | 13 | 0 | 0 | 0 | 13 |
| 9 | 33 | 0 | 0 | 1 | 32 |
| Total | 385 | 15 | 0 | 12 | 358 |

No box was found STALE with certainty. Candidates for the lead's call are in "Notes" at the end.

## LANDED, STALE and DUPLICATE rows in full

LANDED (15)

| Section and box | Evidence |
|---|---|
| 1C.6 "Reconcile plan 02's body with R1-R16" (parent) | d23432a3 "SMP plan 02 now carries the full-player mock requirements R1 to R16 in the sections that own them, each cited, with conflicts left standing for the lead"; plan 02 cites R1 to R16 at lines 268, 310, 313, 338, 343, 363, 368, 395, 434, 459, 461, 469 of `Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`. |
| 1C.6 sub-box "5.1: Audiobooks as a Library special group" | same commit; plan 02 line 343 (R2). |
| 1C.6 sub-box "7.1: the down-left arrow into Mini / Normal Media" | same commit; plan 02 line 395 (R1, title-bar swapping arrow). |
| 1C.6 sub-box "8.2 and 16: SMP Edit mode" | same commit; plan 02 line 434 (R3), also e0baa418 and ae95c566. |
| 1C.6 sub-box "8.3: the Visualizer / Lyrics / Artist Collage pane" | same commit; plan 02 line 469 (R5, R6). |
| 1C.6 sub-box "3 and 5.1: the favourites and library filters as one filter owner" | same commit; plan 02 line 338 (R7, R8), line 268. |
| 1C.6 sub-box "5.2: the track menu; the Track Information alignment swap" | same commit; plan 02 lines 363 (R9) and 368 (R11). |
| 1C.6 sub-box "4: existing sliders and seek bar, the alignment rule" | same commit; plan 02 line 313 (R12 to R14). |
| 1C.8 "Inventory first" | d0e1dceb (merge 290b039b); inventory written up in `Docs/Reference/Neon_Lake_Basin.md:846-859` ("What it owns"); evidence folder `.artifacts/evidence/visualizers/shockwave_grid/water_lines/20261112_inventory/` is cited there (ignored by git, not in this worktree). |
| 1C.8 "One canonical spec control" | d0e1dceb; `core/settings/visualizer_mode_settings.py:917` (`Slider("shockwave_grid_water_lines", "Water Lines:", 0.0, 1.0, ...)`), one slider (not two); `tests/test_neon_water_lines.py:36` (one spec slider in the Water bucket beside Water Detail). |
| 1C.8 "At 0 the water keeps its body" | d0e1dceb, 08ac2c80, 816c8819; `Neon_Lake_Basin.md:869-872` ("Stays at 0"); `tests/test_neon_water_lines.py` (driven: lake-wide lift remains). |
| 1C.8 "Glow follows" | d0e1dceb; `Neon_Lake_Basin.md:861-863` (glow multiplied by the amount); `tests/test_neon_water_line_glow.py:28`; `rendering/gl_programs/neon_lake_basin_program.py:1026` (Shore Glow follows the shoreline). |
| 1C.8 "Zero cost when hidden" | d0e1dceb; `rendering/quick/visualizer/implementations/shockwave_grid.py:429-431, 490, 569` (uniform set; mirrored-line pass skipped at 0), `neon_lake_basin_program.py:580` (branches on the uniform); cost at 1 and 0 recorded at `Neon_Lake_Basin.md:874-878` (8d3ea3d3). |
| 1C.8 "Authored into every Neon Lake preset at 1 by the repair fill" | d0e1dceb; spec key `shockwave_grid_water_lines` in the spec and defaults (`core/settings/default_settings.py:5927` value 1.0); `tests/test_neon_glow_bucket_ux.py:16` (control placed in the Settings bucket). Settings/Studio and engine-worker parity reruns were not verified here. |
| 1.7b "The shader currently still has `plateInset`" | 7cbc1d5b "Materials M2: no inset on any theme; the legibility face reaches the real border"; `tests/test_surface_material_style.py:99` asserts `plateInset` is absent; `Docs/Architecture/Card_Surface_Materials.md:315`. Only the inset removal is landed; the ring shading (the other 10 boxes of 1.7b) is not built (`Border Material` / `Border Opacity Adjust` appear nowhere in `*.py`, `*.qml`, `*.frag`). |

STALE (0): none established.

DUPLICATE (12); the marked box is the copy to delete, the canonical box is named

| Section and box | Canonical box |
|---|---|
| 1B.5 "Dormancy fault from 1B.5" (line 607) | 1C.10a first box "1B.5's dormancy fault" (line 998), same measurement and fix. |
| 1B.5 "Five of the seven GL calls added per frame" (line 611) | 1C.10a first box, its tail "the five unattributed GL calls" (line 999). |
| 1B.6 "Side defect: a paused Studio preview shows no terrain reaction" (line 630) | 1C.10a second box "1B.6's paused Studio preview" (line 1000). Still true at `widgets/spotify_visualizer/shockwave_frame_runtime.py:193` (`playing` False zeroes the energies). |
| 1B.8 "M3. Widget border material: the remaining boxes of 1.7b" (line 692) | Section 1A item 1.7b boxes 1 to 3 (lines 1166-1177): the same three deliverables. |
| 1B.8 "M4. Window border material: 1B.9's box" (line 696) | 1B.9 "Window border material" (line 719). |
| 1B.9 "If the operator still sees escape: the Windows 11 DWM corner preference" (line 714) | Section 1A item 1.9 "Find a composition treatment ..." (line 1209): same search (composition host, input, resize, DPI proof). |
| 3 "Hidden cross-test dependency on an earlier test's `tmp_path`" (line 1420) | Item 6 "The hidden cross-test `tmp_path` dependency (section 3)" (line 117) is a pointer to this box, so the Item 6 box is the one to delete; listed here because both boxes are the same work. |
| 3 "The bright-area text switch is not built (see section 1 item 3)" (line 1493) | Item 3 "Bright-area text switch" (line 86). |
| 4 "Frozen run (1B.14): open a Studio from the fresh frozen build" (line 1567) | 1B.14 frozen-build sub-box "In the same frozen run: saves work, and a Studio opens" (line 826). |
| 4 "Re-author raw linked Widget Theme roles that fail `tools/theme_legibility.py`" (line 1583) | Item 5 "Raw linked widget mirrors remain an authoring concern" and "Retain concrete failing palette roles" (lines 111, 113). |
| 4 "Fix light-theme widget shadows" (line 1585) | Item 5 "Fix light-theme shadows" (line 112). |
| 9 "Side defect (not measured): Bubble's, Extruded Bubble's and Sphere's evaluators still replay exactly in one evaluation" (line 2366) | Section 3 "Bubble, Sphere and Extruded Bubble replay a change in one GUI-thread evaluation" (line 1434): same `ExactReplay` work. |

table has 13 rows; the 14th DUPLICATE in the counts is the Item 5 pair split in two rows (lines 1583 and 1585 count
as two, already listed) plus 3's tmp_path pointing both ways. For the purposes of the verdict totals the per-section
counts in the first table are authoritative: 1B 6, 1C 2 (1C.10a lines 998 and 999-1000 copies counted on the 1B
side is wrong: the two 1C.10a boxes are the canonical copies and stay OPEN, see below), 3 2, 4 3, 9 1.

## Section 1B

| Box (subsection, first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| 1B.1 Side defect (unreproduced): ordinary global Edit | 1 | OPEN | `rendering/quick/custom_layout_owner.py:2699` still returns False on `visible is None`; no test for it found. |
| 1B.2 Side defect: hovered QML item destroyed | 1 | OPEN | not reproduced in a test. |
| 1B.4 [~] `fft_to_bars` gained two helper calls | 1 | OPEN | baseline `tools/baselines/overhead/2026-11-11_4658981b.json` exists; the lead's confirmation is the open part. |
| 1B.4 Admitted later if wanted | 1 | OPEN | operator's call. |
| 1B.5 Dormancy fault | 1 | DUPLICATE | see table above. |
| 1B.5 Five of the seven GL calls | 1 | DUPLICATE | see table above. |
| 1B.5 Distance-based mesh density | 1 | OPEN | |
| 1B.6 [~] Lead's reactivity verdict | 1 | OPEN | |
| 1B.6 Side defect: paused Studio preview | 1 | DUPLICATE | see table above. |
| 1B.6 Side defect: `waveform_music_response.py:63` | 1 | OPEN | still a silent `continue` on frames without capture history (lines 61-63). |
| 1B.6 Side defect: the cost probe, alias names | 1 | OPEN | |
| 1B.7 The safe-area edge guides | 1 | OPEN | no safe-area code found under `rendering/quick`; decision still owed. |
| 1B.7 Evidence gap: Media Edit beside Fullscreen Edit | 1 | OPEN | |
| 1B.8 Accents whose corrected ink collapses; The accent as a graphic under 3:1 | 2 | OPEN | theme-authoring notes. |
| 1B.8 Mid-transition frames and a real display | 1 | OPEN | |
| 1B.8 M3. Widget border material | 1 | DUPLICATE | see table above. |
| 1B.8 M3. With the inner hairline gone | 1 | OPEN | inner inset is gone (7cbc1d5b); the border-distinct check needs the ring work. |
| 1B.8 M4. Window border material | 1 | DUPLICATE | see table above. |
| 1B.8 Each step: `.qsb` regenerated | 1 | OPEN | |
| 1B.9 Side defect: Studio window shows only blur; red `test_waveform_studio_theme`; `--qt-scale-factor` | 3 | OPEN | `tools/settings_native_corners.py:324` still writes `os.environ["QT_SCALE_FACTOR"]` (the box is a decision on that). |
| 1B.9 If the operator still sees escape | 1 | DUPLICATE | see table above. |
| 1B.9 Window border material | 1 | OPEN | canonical copy. |
| 1B.10 Side defect: thin-bar diagonal seam | 1 | OPEN | |
| 1B.10 Round 2 was never reported | 1 | OPEN | |
| 1B.10 Bar Fill ghosts read as the default look's do | 1 | OPEN | standing rule (merged as 092304dc); binds every Spectrum preset. |
| 1B.10 [~] Showcase WebPs for the round's new presets | 1 | OPEN | re-render owed. |
| 1B.10 Extruded Bubble: one arctic-themed preset | 1 | OPEN | |
| 1B.10 Neon Lake: three unique presets | 1 | OPEN | |
| 1B.10 Every preset authored through the Studio's Save To | 1 | OPEN | |
| 1B.10 One showcase WebP per preset | 1 | OPEN | |
| 1B.10 Side defect: Bar Count admitted to 96 | 1 | OPEN | `rendering/quick/visualizer/implementations/spectrum.py:28` `_MAX_BARS = 64` against `core/settings/visualizer_mode_settings.py:755` (8 to 96). |
| 1B.10 Side defect: the segment border ring is lopsided | 1 | OPEN | `widgets/spotify_visualizer/shaders/spectrum.frag` (the `bx <= scale` / `bx >= bw_px - scale` test, near line 914) unchanged. |
| 1B.10 Side defect: the kick lane in mirrored layouts | 1 | OPEN | `widgets/spotify_visualizer/bar_computation.py:422-432` still boosts the first `_bass_end` bars and their mirror. |
| 1B.10 Side defect: Rim Glow measures distance to the square edge | 1 | OPEN | `spectrum.frag` (`side_dist_px` / `top_dist_px` feeding `spectrum_rim_alpha`) unchanged. |
| 1B.12 A display arrangement changing while the saver runs | 1 | OPEN | |
| 1B.12 The Reset Camera glyph shows coloured edge fringes | 1 | OPEN | |
| 1B.14 [~] x4 (Cursor after exit; Held-right pan; Expanded Visualizer; Settings and Studio windows) | 4 | OPEN | lead D1 runs. |
| 1B.14 Frozen build, with its 3 sub-boxes | 4 | OPEN | canonical copy of the frozen Studio box. |
| 1B.14 Real audio endpoints, with its 4 sub-boxes | 5 | OPEN | existing device-change tests (`tests/test_visualizer_engine_worker_device.py`) use stand-ins; no real WASAPI test found. |
| 1B.14 First reveal, worker against in process | 1 | OPEN | |
| 1B.14 [~] Carried from section 1A's former list | 1 | OPEN | |
| 1B.15 Extruded Bubble evidence of 20 Oct | 1 | OPEN | `Docs/Reference/Extruded_Bubble/Investigation.md` (section 6, line 136) still cites the folder without saying it is gone. |

## Section 1C

| Box (subsection, first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| 1C.2 Lead, when two displays are connected | 1 | OPEN | needs both displays. |
| 1C.2 Is the 1.5 s preparation bound enough | 1 | OPEN | |
| 1C.2 Edit's display hop and the hover transfer arrows | 1 | OPEN | |
| 1C.2 While preparing, the target card sits at 0.002 opacity | 1 | OPEN | |
| 1C.2 PyOpenGL's `GL_TIMEOUT_IGNORED` | 1 | OPEN | the move uses the right value (`rendering/quick/visualizer/implementations/extruded_bubble_drift_solver.py:363-365`) but the constant is local; "record it where GL constants are shared" is not done. |
| 1C.3 Side defect (watch): fullscreen mode pill crash | 1 | OPEN | |
| 1C.4 Edit outline and handles from `resolve_card_drawn_rect` | 1 | OPEN | the function is used by `scene_controller.py:2560` and `clip_host.py:92`; the Edit outline owner was not seen using it. |
| 1C.4 R-192 remainder (non-whole axis) | 1 | OPEN | `rendering/quick/device_geometry.py` still one exterior-edge overscan. |
| 1C.4 The tests that open windows were not run | 1 | OPEN | |
| 1C.5 The agent could not reproduce the cut | 1 | OPEN | |
| 1C.6 Reconcile plan 02's body with R1-R16, and its 7 sub-boxes | 8 | LANDED | see table above. |
| 1C.6 Rules that keep SMP's doors open | 1 | OPEN | standing audit rule. |
| 1C.6 The operator's answers to the mock document's section 6 | 1 | OPEN | |
| 1C.8 Inventory first; One canonical spec control; At 0 the water keeps its body; Glow follows; Zero cost; Authored into every preset | 6 | LANDED | see table above. |
| 1C.8 Evidence: a sheet ... one showcase WebP at 0 | 1 | OPEN | docs and sheets are written (`Neon_Lake_Basin.md:874-878`); no showcase WebP at 0 is recorded. |
| 1C.9 The marks seen with real stored health once | 1 | OPEN | |
| 1C.9 Not rendered: a Mica theme | 1 | OPEN | |
| 1C.10a 1B.5's dormancy fault (incl. the five GL calls) | 1 | OPEN | canonical copy; not landed (no skip of the overlay path found). |
| 1C.10a 1B.6's paused Studio preview | 1 | OPEN | canonical copy; `shockwave_frame_runtime.py:193`. |
| 1C.10c Spire glow, 5 boxes | 5 | OPEN | no "Spire Glow" control or code in `*.py`. |
| 1C.10d Vertex trace, 6 boxes | 6 | OPEN | no "Vertex Trace" control or code in `*.py`. |
| 1C.10e Islands, 7 boxes | 7 | OPEN | no islands control or code in `*.py`. |


## Section 1A

| Box (subsection, first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| 1.0 [~] Lead review of rendered frames; zoomed glyph crops | 2 | OPEN | |
| 1.0b [~] Studio run, upright labels, rotated drag feel | 3 | OPEN | |
| 1.1 No direct mode-switch cause; Distinguish explicit selection | 2 | OPEN | awaiting logs. |
| 1.4-1.5 [~] Fullscreen run on D1 (3 boxes) | 3 | OPEN | |
| 1.6 [~] D1 run with `--geo` | 1 | OPEN | |
| 1.7a Resolve the intended density once | 1 | OPEN | |
| 1.7a Minimally correct runtime semantic ink | 1 | OPEN | overlaps M2b's ink solver (fafd7bfa, `SurfaceContrast.legibleInk`) for cards; Studio chrome not shown covered. |
| 1.7a Prove controls/traces on final off-screen renders | 1 | OPEN | |
| 1.7 [~] x3 (side-by-side; D1 opacity; Studio run) | 3 | OPEN | |
| 1.7 The remaining unsampled control/delegate inks | 1 | OPEN | |
| 1.7b Extend the shared `MaterialSurface` shader to the border ring; Inherit Surface default; Border Opacity Adjust; Retain authored colour; On Normal or Flat; Must remain clear; One focused GPU; Include the framed Visualizer card; Preserve older themes; Regenerate `.qsb` | 10 | OPEN | no `Border Material` / `Border Opacity Adjust` in code. |
| 1.7b The shader currently still has `plateInset` | 1 | LANDED | see table above. |
| 1.8 [~] top grips; solid-span endpoints | 2 | OPEN | |
| 1.9 Find a composition treatment | 1 | OPEN | canonical copy (1B.9 DWM box points here). |
| 1.9 Keep it a separate reversible fix; Repeat the four-case gate | 2 | OPEN | |

## Section 3

| Box (first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| Learned levels still in other modes, with 6 sub-boxes (Spline Curve, Extruded Bubble, Neon Lake, Oscilloscope, Sphere, `waveform_ribbon_recorded_input.py`) | 7 | OPEN | `musical_weight` still present in `tools/labs/waveform_ribbon_recorded_input.py` (3 hits). |
| Vocal-band scorer into the music-response tool | 1 | OPEN | |
| [~] Tool-output contract reds | 1 | OPEN | lead runs the test. |
| Side findings of the Waveform second tick cut, 5 sub-boxes | 6 | OPEN | |
| Repair the shared Achievement Pulse mock field IDs | 1 | OPEN | `widgets/steam_card_models.py:116-117` still emits `rarity` and `session`. |
| Isolate active Widget Theme state between scene/display tests | 1 | OPEN | |
| [~] D1 run: live Style Overrides/theme changes | 1 | OPEN | |
| Extend actual faint-run pixel checks to light widget themes | 1 | OPEN | |
| AC-02 remainder | 1 | OPEN | conditional on a second host. |
| Settings round-trip memory growth (R-175), parent and 7 sub-boxes | 8 | OPEN | `QuickSceneFactory` docstring still says "Process-level" (`rendering/quick/scene_controller.py:198`). |
| GC freeze per generation, parent and 3 sub-boxes | 4 | OPEN | |
| Lead, the quiet machine, 7 Nov session, parent and 1 sub-box | 2 | OPEN | |
| `tools/flicker_test.py` Widgets-tab `setup_ui_only_*` modes | 1 | OPEN | still patches `build_visualizers_ui` (`tools/flicker_test.py:584, 736`); the function exists nowhere else. |
| SMP import scan vs the registry | 1 | OPEN | |
| Gate note: `test_release_media` source-change test fails in a worktree | 1 | OPEN | the test now stubs `_source_attribution` (`tests/test_release_media.py:166-168`); whether the Usu originals still matter was not run. |
| Production never calls `engine_lifecycle.cleanup` | 1 | OPEN | `engine/engine_lifecycle.py:724` still defines it. |
| Hidden cross-test dependency on an earlier test's `tmp_path` | 1 | DUPLICATE | see table above. |
| Dead evidence references | 1 | OPEN | |
| Bubble, Sphere and Extruded Bubble replay in one GUI-thread evaluation | 1 | OPEN | canonical copy (section 9 line 2366 points here). |
| A restart still replays the 2 s analysis lead-in | 1 | OPEN | |
| `test_visualizer_control_hints` builds a `QuickDisplayWindow` | 1 | OPEN | `tests/test_visualizer_control_hints.py:289-291`. |
| `test_studio_exit_every_mode` calls `shiboken6.delete` | 1 | OPEN | `tests/test_studio_exit_every_mode.py:310`. |
| Extruded Bubble drift family revisions are process-global | 1 | OPEN | `widgets/spotify_visualizer/extruded_bubble_drift_log.py:43` unchanged (harnesses patch it). |
| A takeover fade completes on the publication edge only | 1 | OPEN | |
| [~] Lead review of a rendered expanded-card frame | 1 | OPEN | |
| An ordinary root's initial fade runs its family's own fade | 1 | OPEN | |
| The overhead baseline cannot see the QML scene | 1 | OPEN | |
| A Card on a material shows the wallpaper, not the Visualizer | 1 | OPEN | |
| Right-hand corners sit further in than left ones | 1 | OPEN | |
| Now Playing needs an admitted Media card | 1 | OPEN | by design, review only. |
| The hidden render host never waits for the GPU | 1 | OPEN | |
| The bright-area text switch is not built | 1 | DUPLICATE | see table above. |
| `test_visualizer_preset_glyphs` opens a real window | 1 | OPEN | `tests/test_visualizer_preset_glyphs.py:54, 107` still `window.show()`. |
| `test_qtquick_context_menu` fails after the custom-layout-owner file | 1 | OPEN | same leak as 1B.1's side defect. |
| The overlays' Edit placeholders are fixed English words | 1 | OPEN | |

## Section 4

| Box (first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| Slow startup: [~] D1 run cold start with `--usage`, with 2 sub-boxes | 3 | OPEN | |
| Side defect: a prefetch batch asked for before image_prefetch is ready | 1 | OPEN | |
| Spline Curve: [~] x2 lead review | 2 | OPEN | |
| Spline Curve: Open (bass 18% below; one recording; capped layer) | 3 | OPEN | |
| Waveform tick: Profile the LIVE logical tick; Record `time.thread_time`; Cut what the profile names | 3 | OPEN | plan line 1558-1560 itself says these matter for `--viz-in-process` only: candidate STALE for the lead. |
| Frozen builds: [~] Frozen run (1B.14) | 1 | DUPLICATE | see table above. |
| Widget/Settings material appearance: [~] D1 run with 4 sub-boxes | 5 | OPEN | |
| Theme the Weather detail asset icons | 1 | OPEN | not in Item 5. |
| Re-author raw linked Widget Theme roles | 1 | DUPLICATE | see table above. |
| Fix light-theme widget shadows | 1 | DUPLICATE | see table above. |
| Extruded Bubble deep red ocean: [~] side-by-side sheets | 1 | OPEN | |
| Extruded Bubble: Shells paler; Embers; lower right busy; shaft corner; Hero Shell; faint ripples | 6 | OPEN | |
| Side defect: the near (defocus) layer stair-steps | 1 | OPEN | |
| Side defect: `release_media.py` cannot render Waveform Ribbon showcases | 1 | OPEN | `widgets/spotify_visualizer/feature_replay.py:304-321` still raises; `tools/release_media.py` does not drive `pcm_reanalysis`. |

## Section 7

All 114 boxes OPEN. Nothing in 7.0 to 7.4 was found built or superseded by a merged change; the section is an
unstarted or review-pending checklist. Notes:

| Group | n | Verdict | Note |
|---|---|---|---|
| 7.0 Method boxes (Target first, Lab + 2, Production + 2, Waypoint, Same-scene proof) | 9 | OPEN | a standing method checklist, not work items; no mode is mid-way through it. |
| 7.1 Baseline tag; Operator-selected recovery baseline (3) | 4 | OPEN | |
| 7.1 Fixed-scale rework: [~] review + 3 sub, P4 crest-clip, P5 and P6 fit | 6 | OPEN | |
| 7.1 Preset 7 [~] x2; Breathing [~] x2 | 4 | OPEN | |
| 7.1 Four-ribbon: [~] + 4 sub, native low/high, recorded draft, Do not equate | 8 | OPEN | |
| 7.1 Reaction modes [~], Group Wave, Pulse bands; Particles [~] + Open | 5 | OPEN | |
| 7.1 Strands (5), Colour floor mist (4), Fixed response (6), Floor Give (1), Pulse Rim (1) | 17 | OPEN | |
| 7.1 Swells (3), Travel Direction (2), Dense highlights (2), Idle blackout (3), Dynamic Floor (2) | 12 | OPEN | |
| 7.1 Grounded camera (6), Floor coverage (6), Unified atmosphere (3) | 15 | OPEN | |
| 7.1 Waveform Studio (2), Live performance (5; the GPU re-measure and the game60 box overlap "Run all three presets under matched PCM/game60"), Chosen first (1), WR-07/08 (1), Full controls (3) | 12 | OPEN | |
| 7.1 Framing (5), Loaded render budget (4) | 9 | OPEN | |
| 7.2 Melt Pool stages (parent + 5) | 6 | OPEN | |
| 7.3 Concrete Rain stages (parent + 5) | 6 | OPEN | |
| 7.4 Usu Moonscape foundations | 1 | OPEN | |

## Section 8

| Box (first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| Compare the original handoff to the accepted Slice 13 | 1 | OPEN | |
| Measure decoration OFF / ON / high-density, parent + 2 sub-boxes | 3 | OPEN | |
| Include the R-170 density growth | 1 | OPEN | R-170 doc still states the 72-live / 110-hero capacity (`Docs/Historical_Bugs/R-170_*.md:96`). |
| For any actual optimization, parent + 2 sub-boxes | 3 | OPEN | |
| If cost is material; If no material cost, close the item | 2 | OPEN | |
| [~] R-170 lead review on rendered WebPs | 1 | OPEN | |
| Side defect: `_apply_bubble_collision_response` compounds `max_disp *= 0.72` | 1 | OPEN | `widgets/spotify_visualizer/bubble_simulation.py:1984` unchanged. |
| [~] Particle glow before/after review | 1 | OPEN | |

## Section 9

| Box (first words) | n | Verdict | Evidence / note |
|---|---|---|---|
| Finish Waveform Studio acceptance first | 1 | OPEN | |
| Adapters in order of authoring pain, parent + Neon Lake, Extruded Spectrum, Spectrum, [~] Settings pages | 5 | OPEN | review-pending. |
| Spline Curve Studio [~] x2; Oscilloscope Studio [~] x2; Edit Preset deleted [~] x2 | 6 | OPEN | |
| Waveform travel speed, parent + 2 sub-boxes | 3 | OPEN | `core/settings/visualizer_mode_settings.py:2056` History Speed unchanged; findability not shown done. |
| Studio clips are seamless loops, parent + 3 | 4 | OPEN | |
| Studio chrome [~] x3 | 3 | OPEN | |
| Studio drag lag [~] | 1 | OPEN | |
| Side defect (not measured): Bubble, Extruded Bubble and Sphere evaluators replay exactly | 1 | DUPLICATE | see table above. |
| UI frozen after closing a Studio: Open until a field log; Acceptance needs the operator's log | 2 | OPEN | |
| Camera reset on every edit [~] x2 | 2 | OPEN | |
| A native heap comparison across 30 sessions | 1 | OPEN | |
| Slider drags [~]; No automatic switch to Custom [~] | 2 | OPEN | |
| Neon Lake: drag the Sun/Moon in the Studio preview | 1 | OPEN | no drag in `ui/studio/shockwave_grid_adapter.py`. |
| Lead review: the Studio terrain brush [~] | 1 | OPEN | |

## Notes for the lead

- Candidate STALE, not marked because the plan's own text leaves it to the lead: section 4 "Waveform logical tick"
  boxes (lines 1547-1556; line 1558-1560 says the tick runs in the engine worker and the boxes matter only for
  `--viz-in-process`).
- 1C.8's last box (showcase WebP at 0) is the only open remainder of that item; its evidence folders are ignored by
  git, so the WebP's existence was not checked.
- 1C.10 c, d and e (Spire Glow, Vertex Trace, Islands) have no code at all; 1C.8 is merged, so 1C.10's step b can
  be struck.
- The 1B.8 M3 box and the 1B.9 and 1.9 boxes are three views of the same two jobs (the border ring, and the
  rounded-window clip); keeping one box per job would shrink the plan by four boxes.
- No test was run; no product file was changed.

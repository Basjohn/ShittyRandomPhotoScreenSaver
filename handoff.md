# Handoff for the interim agent (temporary: 15 Nov to 20 Nov 2026)

Written by the Opus lead on 15 Nov 2026 when the operator wound down for the week. Delete this file when the Opus lead
returns (weekly usage resets Fri 20 Nov, about 21:00 UTC) or when its route is finished, whichever comes first.

**The checkpoint.** Tag `preflip-checkpoint-20261115` is the last known-good point before the flip (Vulkan becoming the
default; the Python OpenGL renderers being deleted in N5.2h). Everything the Python renderers cost was recorded at it:
`Docs/Reference/Benchmarks.md` ("Pre-flip reference", modes and transitions, idle and game60) with baselines in
`tools/baselines/preflip/`. If something goes badly wrong this week, compare against or return to that tag. Never
force-push or rewrite main.

## 16 Nov continuation journal (keep short; Current_Plan.md owns active work)

The operator's current route is P1 spike → N3.1c L3 → N3.2 Audit 4 L6 → N3.4 stream_ring → 1D.13 near-light;
independent agents may overlap. ABI **21** is installed on main from GitHub run `43849213847`, native commit
`2b63f4752`. Section 2 below is the original 15 Nov snapshot, not current ABI or agent status.

- [x] P1 build retirement + fail-closed core harness migration; 219 focused tests, OpenGL/Vulkan checks, High audit.
  Concession: desktop composed alpha, DPI and sleep/wake remain Awaiting Validation; offscreen pixels cannot prove them.
- [x] R-226 caller sweep + post-stage ownership entry; focused regressions and High audit. Scene-target and mesh
  callers are complete with their respective slices.
- [x] N3.1c L3 controls + R-227 partial-resource accounting; two GitHub builds, both-backend negative controls,
  109 merged focused tests and current-module parity/resize/rest/retire PASS. Concession: L2 scissor work and
  timing/other-vendor gates remain separate; this slice proves the named L3 contracts only.
- [x] Audit 4 L6's three executable native/Python oracles; 27 tests, mutation controls and High audit; rechecked in
  the ABI 21 merged gate. Concession: GPU-free matrix/packet tests establish those contracts, not visual/performance acceptance.
- [x] Mesh R-226 caller and stream_ring source contract: exact native record coverage, median admission with
  bracketing-floor sensitivity; 41 focused cases and High audit; merged ABI 21 OpenGL/Vulkan proof PASS.
  Limit: ambient GPU activity (43% before, 28% after) prevents quiet-GPU performance admission; repeat before a
  Waveform consumer (Current_Plan N3.4 / D15). The native pair remains unbuilt; no product per-frame work was added.
- [x] 1D.13 near-light: stale fixture corrected with test-owned visible optics and canonical camera; original alpha0
  reproduced, real stale-composite mutation caught, exact empty/return pixels and resource reuse proved offscreen.
  Concession: product rendering is unchanged; this closes the oracle defect, not a new visual/performance acceptance.
- [x] Reviewed current-ABI stream_ring medians, bracket drift, exact coverage and clean required Vulkan validation;
  22 comparisons per backend within the unchanged 0.05 ms margin. Evidence: `20261116_n34_merged_abi21_median`.
  Existing harness convention: process exit0 means the harness ran; acceptance reads `summary.pass` / printed verdict.

For this session retain every completed plan checkbox, compact inline. Record any incomplete or unsatisfactory
outcome beside its completed item with the reason, so a successor can challenge it; continue work beyond this handoff.
Current continuation (operator, 16 Nov): N3.1c L2 scissor fix and N3.4 defocus diagnosis. Available ambient GPU
activity is explicitly authorised for the diagnosis; section 3's original quiet-GPU stop does not apply to this run.

## 1. Read these first, in this order

1. This file.
2. `Current_Plan.md` sections 0 and 1 ("Now" and "Next, by slot"), then the box you are working on, in full.
3. If you run other agents, `Docs/Guides/Orchestrator_Handbook.md`. If you write code yourself, also
   `Docs/Guardrails/Agent_Worktree_Rules.md` and `Docs/Guardrails.md`.
4. Native core work: `Docs/Guides/Native_Port_Playbook.md` (the port checklist and the standard proof) and the
   primitive's entry in `Docs/Reference/Primitives.md`; the decisions are D1 to D17 in
   `Docs/Future_Work/Native_Core_P3_Decisions.md` (search for `## D<number>`).
5. Before any 3D or transition work: "3D foundation lessons" in `Docs/Reference/Transitions.md`.

## 2. Original state at handoff (15 Nov snapshot; current continuation above)

- Main is green for native work: `pytest tests -k native` gave 861 passed on the merged tree with the ABI 20 module.
- Native ABI is 20 (`native/core/src/abi.h`, `rendering/native/loader.py` `EXPECTED_ABI`). The module the tests load is
  the one the build runner installed into this checkout (`release/native_module`). If tests fail with
  `NativeCoreUnavailable` or an ABI mismatch, the installed module is older than the source: build (section 4), do not
  edit the ABI.
- N3.1 to N3.3 are merged and audited. **N3.4 is merged but NOT audited** (merge 39e661d80): its box in
  `Current_Plan.md` lists the two open steps (the OpenGL defocus cost diagnosis, then the High audit). Nothing may
  consume N3.4 (no Oscilloscope port) until both are done.
- Mode ports: Spectrum and Spline Curve are native. The Bubble port (N5.1) is merged DORMANT (22a99fa45): Bubble is
  not offered on Vulkan until native OpenGL matches Python (rule (a) fails at worst 8 levels on 101 edge pixels; the
  tolerance allows 3). Its box lists the remaining steps, root cause first.
- Transitions: 12 of 28 are native.
- Agent worktrees at handoff: none. Check with `.venv/Scripts/python.exe tools/agent_handover.py`.
- Known stale red: `tests/test_extruded_bubble_empty_near.py` (in the plan's stale-red list); not caused by this week.

## 3. The route for this week, in order

Do these at their asked size. Do not start the heavy ports (N5.4 Waveform, N5.6 Extruded Bubble, N5.5 Neon Lake,
N5.3), N3.6, the flip (NF) or N5.2h (deleting the Python renderers): they need the Opus lead.

1. **N3.4 defocus diagnosis** (its box, "Before N3.4's High audit"). The next action is a measurement, not code:
   the quiet-GPU rerun of `post_stage_check.py --apis opengl --rounds defocus_draws` exactly as the box writes it,
   with the `nvidia-smi` checks before and after. If the GPU is not quiet (the operator gaming, P0, over 15 %), do not
   run it; do something else and try later. Write the figures into the box and D17. Only then, if case (ii) holds,
   the one C++ change the box describes (timestamp marks) and one build.
2. **N3.4 High audit**, only if you are or can dispatch an Opus High audit; otherwise leave it for the lead.
3. **The Bubble port (N5.1)**: follow its box step by step. Every native port obeys the port rule in the playbook:
   (a) OpenGL equals Python under `tools/pixel_tolerance.py`, (b) Vulkan within one level of OpenGL, (c) no Python
   thread state on the render thread, (d) Settings and Studio parity, (e) GPU time and nothing at rest, (f) a Display 1
   rehearsal (lead only: leave it as the last box), (g) no rebuild for Settings or Studio changes.
4. **Small, safe boxes** when 1 to 3 are blocked: the spike retirement box (retarget the N0.6 leftovers to
   `native/core`, then remove the `native_spike` selection; the visible-window part needs the lead, skip it), N3.1c's
   open lows, the `stream_ring` timing-margin side defect (judge relative to the floor measured in the same run), test
   and doc boxes that say they are Sonnet-shaped.
5. **Docs**: whenever a box lands, delete or summarise it in the plan and put the durable contract in its doc.

## 4. How to do the routine things

- **Python**: always `.venv/Scripts/python.exe` from the repo root (or the main checkout's venv from a worktree).
- **Tests**: run the focused files for what you changed (`-q -p no:cacheprovider`, with a timeout). The full chunked
  suite (`tests/run_chunked.py --isolated`) only at milestones. A red in a long full run is often order- or
  load-dependent: rerun it alone before calling it real. Worktrees need `ui/resources/assets.rcc` copied in from the
  main checkout.
- **Builds** (native module): commit, push, then `.venv/Scripts/python.exe tools/build_runner.py --mode github --run
  --select native_module` from the checkout that should receive the module. It builds the pushed HEAD on GitHub and
  installs into that checkout. Local frozen builds are the operator's only. A build is refused if HEAD is not pushed.
- **Commits**: narrow, after each meaningful slice, on main (or the agent's branch), message in plain prose explaining
  what and why, ending with the line `Co-authored by an incoming existential crisis.` (never a Claude co-author). Push
  to origin/main after every commit on main.
- **Retiring a worktree**: only `tools/agent_handover.py --retire <folder-name>` (folder name, not path), after its
  branch is merged. If it refuses because the content reached main another way, `git merge -s ours --no-ff <branch>`
  then retire again. Never `git worktree remove --force` and never copy evidence by hand: the evidence folders are
  junctions and evidence has been lost three times that way.
- **Plan edits**: `Current_Plan.md` is a live checklist of open work. For the 16 Nov session retain and compact completed
  checkboxes inline as the operator requested; otherwise historicalise completed work. Never write "Landed",
  "Fixed", "Rehearsed" paragraphs or evidence lists into it; figures go in commit messages and the focused docs.
- **A fixed long-lived, silent or costly bug** gets its `Docs/Historical_Bugs/R-NNN_*.md` entry and index row in
  `Docs/Historical_Bugs.md` before you report done. Take the next free number from the live index, not this snapshot.

## 5. Mistakes that have cost this project the most (never do these)

- **Display 0 is the operator's primary screen.** Never run anything visible there. Real-display runs are Display 1
  only, through `tools/d1_run.py`, and only by the lead. Probes and tests never create visible windows
  (`QuickDisplayWindow`, `show_on_screen`): use hidden hosts or offscreen rendering. Check that the displays are on
  (`tools/d1_run.py --list-displays`) before any display run; if off, defer, never block.
- **game60 (the load run) needs the operator's explicit yes each time**, at most 10 minutes. Never on your own.
- **Presets are mutable, authored content.** Never name, list, count, pin or test preset names, slots or contents, in
  tests, tools or product code. Never pin default values or UI wording in tests either; derive from the canonical
  source.
- **If the operator edits a preset, default or the installer script, commit and push it at once, silently.**
- **No environment-variable flags or A/B toggles.** No timers or polling (events first). Diagnostic instrumentation
  adds zero work at rest.
- **Fade, never vanish**: anything that appears or disappears fades.
- **Protected performance work**: commits ce07b991, 07486d83 and 985b9d53 (QSG/clip). Never retune production
  rendering to satisfy `clip_smoke` or render-node pixel oracles.
- **The R-63 overscan window is protected** (it hides initialisation flicker). Do not remove it.
- **Settings ownership**: `visualizer_mode_settings.py` and `transition_settings.py` are the single owners. Extend them,
  never bypass them.
- **Product names vs ids**: Neon Lake is `shockwave_grid`, Spline Curve is `devcurve`. Never rename persisted ids;
  search for both names.
- **QML signal connected to a PySide `@Slot(..., result=...)` crashes natively.** QML signal handlers are plain methods.
- **Resolutions are shown in device pixels** (2560 x 1440 at 150 %), as Windows does.
- **No scope padding.** Do exactly the box. Never widen a named action to its siblings. Side defects you find go into
  `Current_Plan.md` as new boxes, never waved off.
- **Never claim "fixed" without reproducing the failure first**, and never claim a visual result without rendering it.
  Visual work is judged on rendered pixels (`tools/release_media.py` showcase WebPs, offscreen renders).
- **Native pixel parity** always uses the shared `tools/pixel_tolerance.py`. Never loosen a tolerance to make a test
  pass; find the difference.
- **Stalls**: a "waiting on background work" agent can be a hung pytest. Run tests in the foreground with a timeout.

## 6. Usage

Check usage often. At 85 % of the 5-hour window, commit everything (WIP commits are fine) and update the box you are
on with exactly where you stopped. At 90 %, start nothing new. Never stop to ask the operator how to pace usage.

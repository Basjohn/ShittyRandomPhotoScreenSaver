# Temporary handoff (27 Nov 2026)

**Whoever reads this, delete this file once you have read it**, and commit the deletion. Everything durable from it is
already in `Current_Plan.md`, in the "Resume here" box and the boxes linked below. This file only says what to do
first and where to send it.

Usage at writing: 5-hour 1 %, weekly 0 % (reset 27 Nov 21:00 UTC). No agent is running.

## State

- **Extruded Bubble (N5.6) is about 40 % ported.** Landed on main:
  - ABI 44: compute storage-buffer limit.
  - ABI 45: mat3 std140 packing and tight OpenGL half-float readback. The readback fix also closed the old
    `fog_steady` garbage texel.
  - Python conversions: packed glass passes, probe backdrop separation, depthless near layer, content-clamped shafts.
  - Drift stream identity and lineage metadata.
  - The D3 geometry reader, proved with the harness writer.
  - The R-251 stream-speed endpoint repair.

  Open, in plan order:
  1. 10 of 18 Python reference runs (the N5.6 "Redraw" sub-boxes).
  2. The native record and route: main-process D3 ownership and seqlock bank reuse, compute stream packing, the
     worker record, and the `native_record_identity` entry with its L proof.
  3. Coverage windows.
  4. P, T and C, then registration.
- **Qt 6.12.1 patch:** half done.
  - The SDK part is staged and verified (`.artifacts/evidence/native_core/n06/20261123_qt_6121_readiness/`).
  - The wheel part has not landed: PyPI still returns 404 for all four 6.12.1 wheels (PySide6, PySide6_Addons,
    PySide6_Essentials, shiboken6), checked 27 Nov. `requirements.txt` stays on 6.12.0.
  - Recheck each session and run the plan's bump box once all four are published.
- **Plan items checked for silent removal** (every unchecked box deleted since 0b273cc3a):
  - Each one was implemented, deliberately moved, or is still present:
    - SMP and its mock-doc questions went to `Future_Work.md` per the operator's 23 Nov sequencing.
    - The display-move placement (1D.6) landed in 47e28de83.
    - The Bubble HUD timing is on the Watchlist.
    - The Studio Stream Speed range slider and the MOTION section are in 1B.10a, after N5.6.
  - Only the "Live agents and where their work is" box was gone. It is restored.
- **Waveform sensitivity (sidequest):** an equivalent exists. It is **Input Gain**, a pre-analysis PCM scale that
  feeds every raw lane Waveform reads. The shared Sensitivity was retired for Waveform on 8 Nov because it never
  reached the frame. Input Gain is already in Settings and in the Studio (Reactivity workspace, Technical group), and
  the presets keep their own values (six at 1.0, one at about 1.08). Recorded under plan section 9. What is left is a
  D1 check of whether it is buried; if it is, move and relabel it in the spec owner and keep the key.
- **Handbook review (the operator's first order for this session):** done as a reading. The findings are boxes
  under "NEXT SESSION STARTS HERE".
  - The cause: the 22 Nov protections lived only in the lead's memory, while the docs agents actually read say the
    opposite.
    - `Agent_Worktree_Rules.md:22` bans load runs and never says that the operator's own load is not one.
    - The proof guide says to rerun any T run above about 40 % CPU.
  - The handbook's Brief and Audit steps lack four rules:
    - quote the operator's defect verbatim;
    - copy out each run's traces;
    - fix the cause wherever it lives;
    - reject "no defect" or "not reproduced" against an operator report.

## Suggested next items and where to send them

Fresh agents only (the operator, 25 Nov: earlier agents carry stale cache and context). Every brief: "read
`Docs/Guardrails/Agent_Worktree_Rules.md`, then `Current_Plan.md` <box>; its proof is <named checklist>, every
bullet", following handbook section 3.

1. **Done 27 Nov:** the handbook findings are applied (`Agent_Worktree_Rules.md`, the proof guide's "Load during
   layer T", handbook section 3 step 2 and section 4). Briefs now inherit them.
2. **Lead, unattended, start at once: the 10 remaining N5.6 Python reference runs.** Use
   `owner_render_parity.py --references-only` into `D:/Temp/Scratch/SRPSS/fast_proof/eb_n56_r251`, with at most
   two processes at a time and the late-window rule. Decide first which 30 s alternates need the whole take, per
   the "Coverage windows" box. These runs need no slot.
3. **High slot, Opus 5.5 High, fresh: the N5.6 "Native record and route" box.** It covers D3 ownership and the
   seqlock, packing the compute streams, the worker record, and the L proof per take and key.
   - Reserve **ABI 46** in the box at dispatch and record the agent id there.
   - Proof: playbook sections 1 and 2 plus the section 3 primitives it uses (D3 arena, compute drift), and the
     proof guide's section 3 "A port" list and section 5 row.
   - It is core concurrency work, so audit it with Opus High at merge.
4. **Medium slot, Opus 5.5 Medium, fresh: the N5.2f warm-up fix and the Volumetric Dissolve retake** (the N5.2f
   hitch box; it gates N5.2h).
   - The brief must say three things:
     - copy each run's trace and session folder out before the next run;
     - the operator's running load is no agent load, so measure under it;
     - fix the cause (the lazy transition-module import and shader-text build) at its owner, wherever it lives,
       as a gradual warm-up per `srpss-warmup-gradual-no-bursts`.
   - It touches no `native/core` files, so it runs beside item 3.
5. **Queue for the High slot after item 3 merges: the Vulkan pipeline cache defect** (N3.6, under "Pipeline cache";
   `qqpc_vulkan` is never written). It is C++ in the pipeline paths, so batch its build with the next C++ merge.
6. **Sonnet Medium, fresh, if a third slot is free: cheap hygiene on the critical path's tooling.**
   - "Guard output lean": hashes per frame, images only for failing frames.
   - The PNG publisher test failure on `bubble_display_wide_response.py`.
   - Both are in plan Item 1.
7. **Lead housekeeping:**
   - Remove the six retained worktrees with `tools/agent_handover.py --retire` after copying their cited evidence.
     All six are clean and merged; `eb-compute-binding-limit` holds the 1.5 MB of N5.6 evidence.
   - The Waveform Studio D1 check (plan section 9).
   - The Qt wheel recheck.

Held until N5.6 lands (as the plan says):
- the Extruded Bubble speed-swing investigation;
- the Studio MOTION section, range slider and particle/microbubble ranges (1B.10a);
- N4.f2;
- N5.5 Neon Lake (its terrain judder root cause comes first).

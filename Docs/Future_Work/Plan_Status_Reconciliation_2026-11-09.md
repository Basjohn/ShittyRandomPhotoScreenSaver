# SRPSS | Canonical plan synchronization register (9 November 2026)

**Why this exists:** agents merged production work without advancing the plan's implementation checkboxes. The plan must distinguish *landed source*, *focused tests*, *formal acceptance evidence* and *operator/native validation* instead of leaving finished programming work labelled as not started. Baseline `main` SHA `9872ca18140c490ed018c42511803005fb3d8ed4`.

## Exact canonical updates required in the next documentation checkpoint

### `Current_Plan.md` §1 / item 8b

- [x] Label P1's native Qt/QRhi four-backend + Nuitka toolchain **proof accepted** (not P3 product release).
- [x] Mark P2b worker capture/DSP/tick, ABI, mailbox, worker default on Windows, H1, H2, M1, M2, L1 and run-bounded recovery **implemented**, with their source checkpoint references from the native closeout plan. Delete no historical evidence.
- [~] Keep formal M4 worker parity/gate 2, first-reveal load comparison and physical audio-device validation **open**; capacity/schema-high-water tests are already implemented and must not be described as missing.
- [ ] Prioritise M5, L2-L5 and inherited POSIX accepted-transfer lifetime ahead of native P3 lifetime commitments. Adjust H3 ordering: Linux source-level default only **after** the inherited POSIX lifetime defect has a bounded design and regression proof, while retaining the explicit operator waiver of physical Linux proof.
- [ ] Add three top-level operator-reported subitems under §1A: **Studio outer-corner parity**, **zero extra card material inset/rim**, and **Visualizer hover Rotate glyph**. Each references its dedicated plan and has separate coded/tested and native/operator acceptance marks. Keep Settings item 1.9 open until native Accent clipping actually passes.
- [ ] Existing Settings theme polarity fix in commit `9872ca181` is **implemented with focused tests**. Do not re-open the material-density retuning, reintroduce the white-to-grey fallback, or claim full physical theme acceptance.
- [ ] Make P3 scope explicit: one native QRhi substrate for Visualizers **and transitions/compositor custom renderers**; Spectrum first, transitions' shared fullscreen pass next; include P3 four decisions and future SMP PCM source/independent-host seam.

### `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md` and `_Engine_Design.md`

- [x] **Retain** the resolution records showing H1/H2/M1/M2/L1 completed, 67 passed L1 combined tests, and frozen/Gate 3/Gate 4 receipts. Do not make already-resolved items new open findings in their old date sections.
- [ ] Append a **9 Nov reconciliation** with the implementation status matrix, a fresh ordered follow-up section (M4, M5/L2-L5/POSIX, H3, P3 decisions), and pointers to `Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md`. An audit's original historical claim remains preserved, but its *current verdict* must refer to the latest resolution.
- [ ] Closeouts need source commit + focused negative controls + what remains untested; do not treat test names as proof they ran today.

### `Linux_Plan.md` Phase 4

- [ ] The Linux worker-default change is **not landed** at the source baseline (`visualizer_engine_worker_platform_default` still returns `IS_WINDOWS`). Keep the checkbox open.
- [ ] Insert accepted-unread POSIX descriptor ownership as a source-level prerequisite, and record that Windows' `DuplicateHandle` path has different ownership and focused passing tests. Preserve operator's 'no Linux machine; assume basic support, no Linux proving prerequisite' decision. If H3 later lands, mark **source landed / native unverified**, not 'Linux tested'.

### `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`

- [x] §7 Nov addendum already commits to **one QRhi native core for custom Visualizers, transitions, image presenter and background nodes** and P3 order substrate → Spectrum → shared fullscreen transition pass → complex Visualizers → rest → backend flip. **Do not replace or narrow this decision.**
- [ ] Append a brief source-status note: P1 spike proven, P2 Windows default landed, native P3 production port not yet landed, four P3 safety decisions still open, with link to the closeout plan. SMP's separate playback source and native host do not require a second render core.

### `Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`

- [x] Mark prerequisite AC-01 Settings tab registry, AC-02 Visualizer host binding, AC-03 process application-service tier **landed**, not their SMP consumer wiring. 
- [ ] At M3, explicitly name the PCM analysis source-selection **transaction** in addition to `AudioAnalysisSource`: source generation, discontinuity, one selected source, capture callback fencing, no decoded+loopback double feed and audible output timestamp calibration. The existing `set_capture_backend_factory` is pre-start-only, not a finished live selector.
- [ ] At M7 and graphical architecture notes, reference general P3 QRhi compositor/Visualizer substrate and native-reader lifetime; no forked SMP renderer or second beat engine. Do not move actual playback implementation earlier than M1/M2 simply because the capture worker is ready.
- [ ] Link `ShittyMusicPlayer/03_PCM_Source_and_Native_Core_Seams_2026-11-09.md` as a focused design source; keep output and exclusive WASAPI playback unimplemented until the M3 native/quality tests prove it.

### `Docs/Architecture/Card_Surface_Materials.md` §3.3 and Studio reference

- [ ] Retire the formerly deliberate **2.5/3 px inner legibility-panel rim** once UI-2 is accepted, and replace its rule with full material face **up to inside the existing border**. Do not edit `OverlayCard.padding`/content geometry, material alpha or shader floors to solve a purely spatial rim. Update shared shader copies and their source-equality tests together.
- [ ] Studio reference should distinguish *shared forged-window edge implemented* from *physically correct native rounded composition unverified*. A visual Studio complaint cannot be closed just by pointing at existing `StudioWindowEdge` code.
- [ ] Visualizer reference/Expanded plan should state hover rotation availability outside Edit, with ordinary and expanded ownership/access limitations and no duplicate action path.

## Discipline for future agents

1. **Before coding**, list the exact canonical plan IDs, current source state and acceptance definition. Reject stale plan assumptions where the code contradicts them.
2. **In the same checkpoint as an accepted slice**, change the actual canonical checkbox/status and `Docs/TestSuite.md` evidence index; update the relevant architecture/guardrail owner only if the contract changed. Do not defer this to a general documentation sweep.
3. Every recorded item has `source implemented?`, `focused regression?`, `physical/operator accepted?` and `remaining follow-up?`. A single `[x]` must never silently mean all four.
4. After changing docs, source-check all paths/test names on current HEAD, run a targeted Markdown/link sanity check, and preserve unrelated sections verbatim. No GitHub Actions, release builds, external installs or performance load without operator authorisation.
5. The three new UI repairs are independent reversible checkpoints. Leave the material surfaces' newly achieved transparency intact; prefer the lowest-overhead ink-only/polarity approach for the Settings contrast regression.

The additional plans in this ZIP are complete standalone source documents, **not destructive replacements for the much larger existing canonical plans**. Merge these verified status updates into their canonical owners on the next local docs synchronization; never overwrite the entire `Current_Plan.md` with a shortened summary.

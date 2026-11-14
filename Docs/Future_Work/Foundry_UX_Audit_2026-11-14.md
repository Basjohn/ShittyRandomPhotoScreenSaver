# Foundry UX Audit (14 Nov 2026)

Scope: the **Build Foundry** (`tools/build_runner.py`, plus `tools/github_remote_build.py` for the GitHub path) and
the **Godzip Foundry** (`tools/godzip_foundry.py`). Audit only: no code was changed, nothing was built, zipped,
dispatched or published. Judged as the operator who runs a GitHub build, a native-module build or a zip many times a day.

**Correction to the brief.** Only the Godzip Foundry is a PySide6 app. The Build Foundry is **Tkinter** (`import tkinter`,
`BuildRunnerApp`; the Godzip FOUNDRIES tab itself labels it "legacy Tkinter"). A Tk window cannot be rendered without
showing it, so the Build Foundry is audited from code alone (no screenshots). The Godzip Foundry was constructed on the
offscreen platform (not shown; no tab action clicked) and every tab grabbed.

Evidence (kept): `.artifacts/evidence/build/foundry_ux/20261114_audit/` (the area `tools` does not exist in
`tools/artifact_paths.py`; `build` is the nearest). Offscreen caveats: no DWM Acrylic, so the translucent body renders as
flat grey (not a product defect); `&` mnemonics draw underlined because Qt shows them without Alt offscreen; the worktree
has no `.venv` or origin branch, which explains the "Repo venv Python is missing" and "PULL inspection failed" lines.

| File | Shows |
|---|---|
| `godzip_00_create_god_zip.png` | Create tab, header chips, tab bar |
| `godzip_01_apply_god_zip.png` | Apply tab empty state |
| `godzip_04_push.png` | Commit / Push |
| `godzip_07_run.png` | Run SRPSS flags and preview |
| `godzip_08_cmd.png` | Cmd tab (section cut at the edge) |
| `godzip_09_foundries.png` | the launcher tab |

---

## Build Foundry

**Summary.** A solid, careful pipeline front end: one window, three modes (Normal, Repo Venv, GitHub Remote), a
pre-flight panel, a checklist of jobs, a progress bar, an Emergency Stop, and a working headless twin
(`--mode github --run`). The common GitHub flow is already cheap: open, leave the preselected rows, press Start (the
mode and auto-close are remembered, `Preferences`, line 645). The weaknesses are feedback during the long wait and a
few risky or opaque moments, not layout.

### High

**B1. Closing the window while a build runs stops it with no confirmation.** `_request_close` (line 2910) calls
`process_owner.shutdown()` immediately, which also cancels the GitHub runs. Alt+F4 is bound (line 2125), and the
operator's window is the taskbar button of a 10-30 minute run. A stray Alt+F4 or close click throws the run away.
*Suggest:* when `self._running`, show "A build is running. Stop it and close?" with Stop And Close / Keep Building;
default is Keep Building. Same dialog for the titlebar close button.

**B2. Concurrent jobs fight over one progress line, and the step text is cut.** The row shows only the first part of
the status (`text.split(" · ")[0]`, line 3425), so every building row just says "Building"; the step (for example the
workflow step name) goes to the single `_progress_detail` label (line 3427), overwritten by whichever of Standard, Media
Center or Linux polled last. With two to four runs in flight you cannot see which is at which step.
*Suggest:* widen the row status to hold "Building · step" (it is already right-aligned; truncate with an ellipsis and a
tooltip), and make `_progress_detail` show a summary ("2 of 4 done · 1 building · 1 queued") instead of a last-event echo.

**B3. No elapsed time, no ETA, no "last build took" anywhere.** `job_running` and `job_status` carry no timestamps. A
GitHub build can sit on "Queued" for minutes; there is no way to tell queued-too-long from normal. *Suggest:* a per-row
elapsed clock (`mm:ss`) started at `job_running`, updated by the existing 100 ms poll (`_poll_events`, no new timer),
and the previous successful duration per job saved in `Preferences` and shown dimmed ("usually 14:20"). This is the
single most valuable addition for the GitHub flow.

### Medium

**M1. A failed job shows only "Failed 1".** `result.detail` (the readable reason, for example "GitHub run failure: url")
is used by the headless printer (line 3602) but never reaches the window: the row gets "Failed {code}" and a Log link
(line 3462). The operator must open a log to learn what the headless mode prints for free. *Suggest:* put `result.detail`
in the row tooltip and in the footer ("Standard + Diagnostic (GitHub): GitHub run failure"), and add the GitHub run link
automatically on failure (it is only attached when `job_link` fired).

**M2. Pre-flight output is truncated to five fragments with no way to see the rest.** `details` keeps one note, two
errors and two warnings joined by "  ·  " (line 3389) in an 8 pt label with `wraplength=740`. A third error is silently
dropped. With the uncommitted-changes and not-pushed warnings (lines 1015-1024) the useful ones compete for two slots.
*Suggest:* list every item, one per line, errors red and warnings amber, in a panel that grows (the body already
scrolls); or at least a "+3 more" link that opens the full text.

**M3. The commit being built is buried.** `GitHub builds <commit>` is a pre-flight note (line 1009) and appears only when
it is the first note. For a GitHub build, the commit, branch and "pushed / not pushed / N uncommitted" state decide
whether the build is the one you meant. *Suggest:* a fixed chip row under the mode buttons, like the Godzip header chips
(branch, short HEAD, CLEAN or DIRTY, "pushed" or "ahead 2"), amber when HEAD is not on origin.

**M4. Start is enabled even when pre-flight has errors.** `preflight` handler enables Start unconditionally (line 3397);
only rows in `unavailable_jobs` are disabled. Defaults-authority or QML-contract errors (lines 1120-1126) therefore
leave Start live and fail later in the worker. *Suggest:* disable Start while `result.errors` is non-empty, with a tooltip
naming the first error; keep Start live for warnings.

**M5. Pre-flight state is invisible while it runs and re-runs on every mode switch.** The label says "Running pre-flight
checks…" and Start is disabled, but `run_preflight` calls three audits plus `gh` calls (lines 1120-1160) in a thread each
switch, taking seconds, with no spinner or elapsed time, and the previous mode's results can flash. *Suggest:* a small
"Checking…" state on the panel (grey, not green: the label is green while checking, line 2517), and cache the result per
mode for about 60 seconds.

**M6. Button and label casing breaks the app's convention.** START SELECTED, EMERGENCY STOP, BUILD ENVIRONMENT, NORMAL,
REPO VENV, GITHUB REMOTE (lines 2475, 2607, 2614) are ALL CAPS. The house rule is Title Case for buttons and ALL CAPS only
for short tags. Mode buttons also use a raw `Radiobutton` with `indicatoron=False`, so the selected mode is a darker
amber with no border, easy to misread at a glance. *Suggest:* Start Selected, Emergency Stop, Normal / Repo Venv / GitHub
Remote; give the active mode a visible amber underline or border.

### Low

**L1.** Emergency Stop is the same size and weight as Start and sits next to All/None (lines 2606-2634). A mis-click
kills a 20-minute build with no confirm. Put it left of the checkbox cluster, danger-coloured, enabled only while running,
and consider a two-step (click arms, second click within 3 s confirms) instead of a dialog.

**L2.** The subtitle (line 2452) is four lines of static text at the top; shorten to one line, rest in a tooltip.

**L3.** Headings use `Jost` (lines 2447, 2730), not a Windows font and not registered in this file; without it the
heading silently falls back. Verify it is bundled.

**L4.** "Output", "Log", "Evidence ZIP" and "GitHub run" links appear in a different order depending on which exist
(lines 3032-3043); fix the order so muscle memory works.

**L5.** No keyboard path: no Enter-to-start, no Ctrl+A for All; the custom checkbuttons take Space (line 1842) but Tab
order across the custom widgets was not verified. Add Ctrl+Enter = Start.

### CLI (`--help`)

Clear but with gaps. `--run` requires `--mode github` (line 3653) and exits 2 otherwise: make it imply the mode.
Job keys are listed only inside the `--select` help string; add `--list-jobs`. `--select` without `--run` is silently
ignored. Headless `[FOUNDRY]` lines carry no time; prefix `HH:MM:SS`, which also makes saved logs readable.

---

## Godzip Foundry

**Summary.** A dense, capable tool with a clear visual language (frameless dark shell, chips, Panels). Ten tabs; the seven
daily ones are the visible tab bar and three (Run, Cmd, Foundries) are corner buttons. Remembered choices are good
(output folder, run flags, entrypoint, theme, commit message, collapsible section state), drag-and-drop of a ZIP or
debris JSON works, destructive steps use confirm dialogs, and the whole thing is guarded so a mutation cannot be
interrupted by close. The gaps are mouse-only operation, no progress or cancel for the long operations, and a
handful of small display faults.

### High

**G1. "&" in button text is eaten as a mnemonic.** `QPushButton("COMMIT & PUSH")` (line 2976) and
`"OPEN CP & DIFF"` (lines 4902, 4678-4707) render as "COMMIT PUSH" / "OPEN CP DIFF" with an underlined D/P (see
`godzip_04_push.png`, `godzip_00_create_god_zip.png`: "COMMIT _PUSH", "OPEN CP _DIFF"). It also creates an accidental
Alt+P / Alt+D shortcut on the most consequential button (commit and push). *Suggest:* `&&` in all three strings (or
drop the ampersand: "Commit And Push"); a repo-wide `grep '"[^"]*& [^"]*"'` check for others.

**G2. Long operations have an indeterminate bar, no elapsed time, no cancel.** `run_task` (line 5135) shows
`busy` (range 0,0, 150 px, line 5015) and a status string; Create (hashing about 2,900 files) or Apply of a large ZIP can run
for minutes and close is fenced until done (lines 4799-4806), so a hung hash or a locked file leaves only "wait". There
is no way to abort and no clue how far along it is. *Suggest:* thread a `progress(done, total)` callback from the core
into the bar (determinate where the count is known), show elapsed seconds beside it, and offer Cancel for the read
phases (hashing, scans) where it is safe; keep mutations fenced but say what they are doing ("Writing 412 / 1,980").

**G3. No keyboard shortcuts anywhere.** No `QShortcut` or `QKeySequence` in the file; tabs, Create, Apply, Commit And
Push and Refresh are mouse-only (only Qt's default Ctrl+Tab and the accidental mnemonics from G1 exist). The frequent
loops (Create, then Apply, then Push) should not need the mouse. *Suggest:* Ctrl+1..7 for the visible tabs, F5 = Refresh
on the current tab, Ctrl+Enter = the tab's primary action (still through its existing confirm), Ctrl+O = browse
GODZIP on Apply, Esc closes the top dialog.

### Medium

**G4. Hidden tabs plus corner buttons look broken in the grabs.** In every screenshot the three hidden tabs (Run, Cmd,
Foundries) leave small ghost rectangles stacked on top of the "CREATE GOD ZIP" label (`godzip_00_create_god_zip.png`
top left), and the RUN / CMD / FOUNDRIES corner buttons are not drawn at the right. Likely an offscreen artifact (the
window was never shown, so the corner widget was never laid out), but this was not confirmed on screen and the
structure (hidden `QTabBar` tabs + a corner widget, lines 4975-5005) is fragile. *Suggest:* check once on the real window; if it reproduces, build the three as a separate right-aligned
button group above the tab body, not as hidden tabs.

**G5. Faint text is hard to read.** The repo path, panel descriptions ("Orange = timestamp-old…", "Deletion intent is
explicit…"), the status bar and the destination line use a faint grey on a mid-grey panel (see all grabs; the status bar
in `godzip_07_run.png`). On a real Acrylic body the contrast differs, but the "hint" tier is below comfortable
contrast on any of them. *Suggest:* raise the hint token by one step and give the status bar normal text colour; keep
faint only for truly decorative text.

**G6. The header carries three large chips of low information.** Branch (very long worktree names get a wide chip),
head, CLEAN or DIRTY each take a 40 px box (`godzip_00_create_god_zip.png`) while the one value that changes behaviour,
dirty, is the smallest. They are not clickable. *Suggest:* shorten branch chips with elision and a tooltip; make the
dirty chip a button that jumps to the Push tab; show ahead/behind (the Pull tab already computes it) as a fourth chip
only when non-zero.

**G7. Case convention.** Tabs and main actions (APPLY GOD ZIP, DIFF, CREATE GOD ZIP, APPLY SELECTED, CREATE LOGZIP, "MOVE
CHECKED TO /DELETEME") are ALL CAPS next to Title Case secondary buttons (Workflow Defaults, Changed Only, Refresh). House
rule is Title Case for buttons. Pick one: Title Case everywhere except short tags like CLEAN, and shorten "MOVE CHECKED
TO /DELETEME" to "Move To /deleteme".

**G8. A new Create zip defaults to the repo's parent folder.** `output_dir` falls back to `repo_root.parent` (line
1049); on a worktree that is `.claude\worktrees`, as shown in `godzip_00_create_god_zip.png`. Reasonable for the main
checkout, wrong for worktrees. *Suggest:* default to the last output folder, else the OS Downloads or Desktop; never a
folder inside `.claude`.

**G9. Error handling is a modal for everything.** `show_error` (line 5130) writes the status line *and* opens a notice
dialog, so a benign "Remote tracking ref does not exist after fetch" on Pull appears twice and the dialog stacks if
two tasks fail in a row. The status text also remains after the cause is fixed (the stale "PULL inspection failed…"
line is visible on five unrelated tabs, `godzip_07_run.png`, `godzip_09_foundries.png`). *Suggest:* status bar
messages that belong to a tab should be cleared on tab change; reserve the dialog for operations that changed or tried
to change files; add a "Copy Details" button on the dialog.

### Low

**L1.** The Apply empty state is a blank table (`godzip_01_apply_god_zip.png`); put "Drop a GODZIP here or choose
one above" in it.
**L2.** Create has no remembered selection (every launch starts from "Workflow Defaults") and "0 changed/new" is small
text.
**L3.** Window minimum 900 x 680 (line 4511), initial 980-1420 by 720-930 (line 4713): fine at 150 % on 2560 x 1440
(about 1700 x 960 logical). The Cmd tab's second section is cut at the body edge at 820 px height
(`godzip_08_cmd.png`); collapse Repo Command Shells by default.
**L4.** The "DPI: per-monitor-v2" label (bottom right) is debug information shown permanently; move it to Settings.

### CLI (`--help`)

`--help` prints only `--repo` and `--open INITIAL_ZIP`, with no help text, and only after the full UI stack imports:
in a fresh worktree it died with "Qt resource pack is missing". *Suggest:* add help strings ("Repository root; default:
the checkout this script lives in", "Open this GODZIP on the Apply tab") and handle `--help` before heavy imports
(`_early_repo_root`, line 31, is the place).

---

## Cross-tool

- **Consistent chrome, divergent toolkits.** The Godzip Foundry is a frameless PySide6 shell with Settings theme
  bridging; the Build Foundry is a hand-drawn Tk shell (custom titlebar, scroll track, checkbutton, drag fallback,
  ~600 lines of window plumbing, lines 1749-2900). Every fix above exists twice. A PySide6 port of the Build Foundry,
  reusing `foundry_chrome.py`, the stylesheet, `FoundryPopupDialog` and the thread bridge, would remove the Tk
  special cases (DPI math, drag fallback, scroll track) and give the Build Foundry the Godzip look and keyboard
  handling. It is a bigger job than any single item here; worth a plan decision, not a quick win.
- **Shared vocabulary.** Same status colours, the same "elapsed" display and the same failure dialog with Copy Details.

## Quick wins (under an hour each)

1. G1: `&&` in three button strings (and the two `setText` copies).
2. B1: confirm before closing a running build.
3. B3: per-row elapsed clock from the existing 100 ms poll.
4. M4: disable Start while pre-flight has errors.
5. M1: show `result.detail` in the footer and row tooltip.
6. Godzip `--help` strings; Build Foundry `--run` implying `--mode github`.
7. Godzip: clear tab-bound status text on tab change (G9).
8. Casing pass on button labels (M6, G7).

## Not verified

The Build Foundry was not rendered (Tk cannot be grabbed hidden); everything about it is from code. The Godzip grabs
are offscreen without the native Acrylic backdrop or a shown window, so exact colours, the tab-bar ghosts (G4) and the
corner buttons need one look on the real window. 150 % scaling was not measured; the conclusions rest on the size
arithmetic in the code. Nothing was timed.

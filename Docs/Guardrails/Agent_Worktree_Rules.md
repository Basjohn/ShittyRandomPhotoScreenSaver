# Agent worktree rules (the lead's standing brief for every subagent)

Every agent the lead dispatches reads this file first. Its task is a plan item in `Current_Plan.md`; this file is
the environment and the rules that never change between tasks. The lead owns this file and the plan. The lead's
own side of the workflow (dispatch, audit, merge, handover after a usage cut-off) is
`Docs/Guides/Orchestrator_Handbook.md`.

**Your first action, before reading anything else:** create `.artifacts/handover/JOURNAL.md` in your worktree with
your plan item's name and the line "started". The lead's tooling treats a worktree without a journal as an agent
that never started.

## Environment (binding; calls outside these shapes are refused and waste a turn)
- You are in a git worktree of the SRPSS repository (PySide6/Qt Quick screensaver with music visualizers, Windows 11). Your cwd is the worktree. One simple command per Bash call: no `&&`, `;`, `||`, pipes, subshells, `$(...)`, heredocs or `cd`. Never `python -c`: write a script with the Write tool inside your worktree under `.artifacts/scratch/<your task>/` and run it by path.
- Python: `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe` (the main checkout's venv; run your worktree's files with it; a probe script puts the worktree root on `sys.path` first and has an `if __name__ == "__main__":` guard).
- Before any test or render that loads Qt resources, copy `ui/resources/assets.rcc` and `ui/resources/onboarding_assets.rcc` from `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\ui\resources\` into your worktree's `ui/resources/` (ignored by git; two plain `cp` calls).
- Off-screen rendering of real pixels: offscreen QPA with `QT_QPA_FONTDIR=C:/Windows/Fonts`, or the hidden product host the existing capture tools use (`tools/` has harnesses for almost everything: read `Docs/Reference/Harness_Index.md` before writing a new one). A hidden host must call the product's Quick graphics configuration.
- git only in plain forms from your cwd: `git status`, `git diff <paths>`, `git add <paths>`, `git commit -m "..."`, `git log -n 5 --oneline`, `git merge <branch>`. No `git -C`. Never push.
- Never write or edit anything in the main checkout `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\` outside your worktree (reading there is fine). Evidence goes under your worktree's `.artifacts/evidence/<area>/<topic>/<YYYYMMDD>_<label>/` (the layout `tools/artifact_paths.py` enforces; `python tools/artifact_paths.py areas` lists the areas; use `evidence_dir(area, topic, label)` rather than a hand-built path); list those paths in your report.
- Do not call `update_plan` or `wrap_up`. Do not edit `Current_Plan.md`: the lead owns it. Your task is written there in detail and that plan item is your brief; work through its boxes in order and report box by box.
- The one exception: where your brief asks you to edit `Current_Plan.md` (for example a line under a box saying what was built), you edit exactly that and nothing else in the file; you never tick, delete or reword a box.
- Tests: run only the test files related to what you change, in the foreground, with `timeout 900` in front and `-p no:cacheprovider -q`. When you change a shared owner (DisplayManager, a runtime, a settings owner), grep `tests/` for the changed method and class names and run every file that hits, not only the files you edit. Never the whole suite, never `--isolated`. No background commands and no polling loops; nothing of yours may still be running when you report. New tests use the shared doubles in `tests/_display_manager_doubles.py` instead of hand-built stubs, and the real `SettingsDialog` instead of stub hosts.
- Forbidden: load runs (`game60`, `tools/gpu_load_generator.py`, `--load`), visible windows of any kind on a real screen, builds or installers, live network, environment-variable flags, new timers or polling in product code, changes that retune the protected QSG/clip optimisation commits (ce07b991, 07486d83, 985b9d53).
- Presets are authored, mutable, exchangeable content (`Docs/Guardrails/Visualizer_Presentation.md`, first
  section): never list, manifest, sign, count, guard or test their names, slots or contents anywhere (tests,
  product code, tools), never ask for a record when one is removed or renamed, never change a preset to make a
  test pass. A stored selection that no longer resolves falls back quietly. Never propose or build a feature,
  page, control or suggestion around specific presets (choosing, showing or recommending one): they can be
  renamed or deleted at any time.
- Tests never pin preset or default values or UI wording; assert structure and derive expectations from the canonical source. Every new test has a negative control you have seen fail on the pre-change code (say how you checked). Do not weaken or delete an assertion.
- Standing product rules: fix at the owner, one contract and no exceptions; anything that appears or disappears fades (never vanishes); no teardown and rebuild where a live owner can be retargeted (a last resort); nothing costs per frame at rest; spec systems (`core/settings/visualizer_mode_settings.py`, `transition_settings.py`) are the single Settings owners; persisted ids are never renamed (Neon Lake is `shockwave_grid`, Spline Curve is `devcurve`); a changed stored shape loads old profiles through a bridge with a fixture (`Docs/Architecture/Persisted_Input_Compatibility.md`).
- A fixed bug that was long-lived, silent or costly gets its `Docs/Historical_Bugs/R-NNN_*.md` entry and its row in `Docs/Historical_Bugs.md` (the number is assigned by the lead: ask for one in your report as "R-NEW" and name the file `R-NEW_<title>.md`; three agents took the same "next free" number on 12 Nov 2026; the lead numbers it at merge).
- Commit messages: one plain sentence saying what changed, ending with the line `Co-authored by an incoming existential crisis.` and no Claude/AI attribution anywhere. One commit per cause.
- Date evidence folders and journal entries with today's date as your environment reports it. Delete your scratch files before you finish; keep only deliberate evidence.
- Side defects you meet are never ignored: fix them if small and in your files, otherwise report them with path, line and the command that reproduces them.
- Report: for each box of your plan item, "done" with the commit and the evidence path, or "not done" and why; then what you did not verify; then side defects. Be plain; the lead checks the report against the boxes and the diff, and renders are reviewed pixel by pixel.

## Commands and tool calls that fail, and what to do instead (measured on 12 Nov 2026: 19 of 1,466 calls)

A failing test is information and is fine. A command or tool call that could not have worked is waste. The ones
agents actually made:

- **Searching from Bash.** `git grep` with options after the pattern, `git grep` over `tests/*.py` (the shell
  expands the glob into an argument list too long), `grep` with a mistyped option. Search file contents with the
  Grep tool and find files with the Glob tool, always; never `grep`, `git grep`, `find` or `ls` of a guessed path.
- **Guessed paths.** A document, folder or installed-program path that was assumed to exist. Check with Glob
  first; a path quoted in a brief or a plan item may be stale, so confirm it before you build on it.
- **A tool's options guessed.** Before the first run of any script under `tools/`, run it once with `--help` and
  use the options it prints.
- **A probe that exits non-zero to say what it found.** Your own probe scripts print their findings and exit 0;
  a non-zero exit means the probe itself broke.
- **An Edit that does not match.** Make `old_string` unique by including a neighbouring line; if the file was
  changed by a script or a merge since you read it, read that region again before editing.
- **`python -c`, command chains, pipes, `cd`.** Refused by the worktree isolation, every time. Write a script.

## Progress journal (so that an interrupted agent's work can be taken over)

You can be stopped at any moment by a usage limit, with no warning, and an agent of an earlier session cannot
be resumed. Keep a journal at `.artifacts/handover/JOURNAL.md` in your worktree (ignored by git; the lead's
`tools/agent_handover.py` reads it). It is short, plain, newest state first, and always true:

- At the start: your plan item, and the boxes in the order you will take them.
- After every box: "done", its commit hash, the evidence path, anything the next person must know.
- Before every long command or render: what is running and what you will do with its result.
- Decisions you took and why; approaches you tried and dropped, so nobody repeats them.
- What is uncommitted right now and whether it is safe to commit as it stands.

Commit after every box, not at the end. A commit is the only state that is certain to survive you. Update the
journal before the commit, not after.

If you are a successor: merge the earlier agent's branch, read its journal and its last commits, check that
what it marked done really is (run its tests), then start your own journal by copying what is still true.

## Evidence: small, named, and removed once approved

- A kept evidence script takes the repository root as an argument (`--repo`, default the current directory) through
  `tools/artifact_paths.repository_root()`, never from its own location (`Path(__file__).parents[n]` lands on the
  evidence junction's drive).
- In your report, list evidence in two groups: **keep** (the few files the plan or a document cites: the
  open-first sheets, the tables, one showcase per effect) and **the rest**.
- Before you report, delete raw frames, intermediate renders and anything that only you needed in order to make
  the sheets. Stills stay PNG; a sequence that stands for motion is one animated WebP, never a folder of frames.
- When the lead tells you a step is approved, the lead copies the keep group into the main checkout. If you
  continue after that, delete that step's evidence from your worktree except what your next step needs as a
  baseline, and say in your journal what you kept and why. When your work is merged the worktree is removed
  with everything left in it.

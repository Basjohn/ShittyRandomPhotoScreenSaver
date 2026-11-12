# Orchestrator handbook (read this first if you are the lead)

How the lead runs agents on this repository without losing their work. The agents' side of the same workflow is
`Docs/Guardrails/Agent_Worktree_Rules.md`; the work itself is `Current_Plan.md`. Written 12 Nov 2026 after a day in
which two usage cut-offs, a session change and duplicated historical-bug numbers cost work and time.

## 1. Roles and roster

- **The lead** orchestrates, audits, reviews and plans. It owns `Current_Plan.md`, this handbook and the agent
  rules, merges every branch, pushes, and is the visual judge (renders it can make itself are never handed to the
  operator). Since 12 Nov 2026 the lead is Opus 5.5 High.
- **Fable 5.2 High** is used rarely, as a one-off audit at a major architectural milestone (for example a native
  core stage closing, a backend switch). The lead asks for it by spawning one agent with `model: "fable"`, a
  read-only brief and a fixed question; nothing else runs on Fable.
- **Agent slots, the cap** (operator, 12 Nov 2026): two Opus 5.5 High (architecture, shaders, visual work), two
  Opus 5.5 Medium (bounded repairs, test work, preset touch-ups at low priority), one Sonnet 5.5 Medium (documents
  and research only; never product code or tests), plus the lead. The cap counts agents running at once; when it
  shrinks, nobody busy is stopped unless their work is safely handed over (journal current, work committed).
- **Closing before opening:** a slot takes no new work while its last report is unreviewed or unmerged. A dispatch
  is one plan item, or one step of a large one, sized to finish and report well inside a usage window.

## 2. Where everything is

| What | Where |
|---|---|
| The work, as live checklists (one box per open step; landed boxes deleted at merge) | `Current_Plan.md` |
| What the agents must do and must never do | `Docs/Guardrails/Agent_Worktree_Rules.md` |
| State of every agent worktree; saving an interrupted agent's work | `tools/agent_handover.py` (section 5) |
| An agent's progress journal | `<worktree>/.artifacts/handover/JOURNAL.md` (ignored by git) |
| Agent worktrees and branches | `.claude/worktrees/agent-<id>/`, branch `worktree-agent-<id>` |
| Every tool and harness | `Docs/Reference/Harness_Index.md` |
| Real-display proof (lead only, Display 1 only) | `tools/d1_run.py` (`--list-displays`, `--help` holds recipes) |
| Evidence layout | `tools/artifact_paths.py`; kept evidence in `.artifacts/evidence/<area>/<YYYYMMDD>_<name>/` |
| Historical bugs | `Docs/Historical_Bugs.md` and `Docs/Historical_Bugs/R-NNN_*.md` |

## 3. The cycle, step by step

1. **Plan first.** The task exists in `Current_Plan.md` as an item with one box per step, starting with a
   root-cause box (the cause proved on the real product path, with a negative control), then the contract, the
   fix at the owner, the guard test, the evidence, the docs. Commit and push the plan before dispatching.
2. **Brief.** Short: "read `Docs/Guardrails/Agent_Worktree_Rules.md`, then `Current_Plan.md` item X; the item is
   your brief", plus only what the item cannot say (the review point where it must stop, files another agent is
   in, anything the operator said that day). Never restate the environment rules.
3. **Dispatch** with `isolation: "worktree"`, the slot's `model` and `effort`. Note the agent id in the plan item.
4. **While it runs:** do not poll. If it seems stuck, `tools/agent_handover.py <worktree>` shows its journal,
   commits and live processes.
5. **Report.** It answers box by box. Check it against the diff, never on trust (section 4).
6. **Merge** (section 6), copy the "keep" evidence into the main checkout, delete the rest with the worktree,
   delete the landed boxes from the plan, write what the audit left open as new boxes, push.

## 4. Audit checklist (every merge)

- Each box claimed done: find it in the diff; run its tests on the merge, not only on the branch.
- A negative control exists for every new test and the agent says how it saw it fail.
- Caller sweep: a changed shared owner (DisplayManager, a runtime, a settings owner, the frame codec) has every
  test file that names it run.
- Pixels: open the "open first" sheets yourself. A new control, row or list is compared side by side, at the same
  scale, with an existing themed sibling: font, weight, size, spacing, colours, states.
- **Presets:** grep the diff for preset names. Anything that lists, records, counts, guards or compares the
  shipped presets is rejected (`Docs/Guardrails/Visualizer_Presentation.md`, first section). Presets are authored,
  mutable and exchangeable; a stored selection that no longer resolves falls back quietly.
- No environment-variable flags, no new timers or polling, nothing per frame at rest, no teardown and rebuild where
  a live owner can be retargeted, the protected clip commits untouched.
- A behaviour the operator accepted earlier is not changed silently: check the plan's "accepted" notes; a change
  goes into section 2 "Changed on ..." once.
- Historical-bug numbers: agents write `R-NEW`; the lead assigns the next free number at merge, one at a time.

## 5. Usage limits, cut-offs and session changes

Agents can stop at any moment, and **an agent of an earlier session cannot be resumed** (SendMessage fails with
"no transcript"). Their branch, their uncommitted files and their journal are what survive.

- **When a usage-limit warning arrives:** stop every running agent (TaskStop), then run
  `tools/agent_handover.py --commit` from the main checkout. It saves each worktree's uncommitted work as one
  "WIP (handover)" commit on that agent's branch and prints each agent's commits, journal and successor brief.
  Write the handover state into the plan (one box per interrupted agent: branch, last commits, what is left).
- **After a cut-off in the same session:** a stopped agent can be resumed with SendMessage; tell it about the
  handover commit.
- **In a new session:** run `tools/agent_handover.py` first. For each interrupted agent dispatch a successor whose
  brief starts with "run `git merge <branch>` first, then read `<worktree>/.artifacts/handover/JOURNAL.md` and the
  branch's last commits; check that what it marked done really is". The tool prints that line.
- The tool also lists agent branches that are not merged into `main` and have no worktree any more, so a branch
  left behind by an automatic worktree clean-up is never forgotten.
- Never delete a worktree or branch before its work is merged or deliberately abandoned (say which in the plan).

## 6. Merging

From the main checkout, on `main`:

    git merge --no-ff worktree-agent-<id> -m "Merge <what landed>" -m "Co-authored by an incoming existential crisis."
    (run the item's tests on the merge)
    git pull --rebase=merges origin main
    git push origin main
    git worktree unlock .claude/worktrees/agent-<id>
    git worktree remove --force .claude/worktrees/agent-<id>
    git branch -D worktree-agent-<id>

Commit messages end with the trailer above and carry no AI attribution. The operator's own edits (presets,
defaults, the installer script) are committed and pushed at once, silently.

## 7. Hard limits the lead keeps

- Display 0 is never taken. Bounded runs on Display 1 are the lead's, through `tools/d1_run.py`; agents never show
  a window on a real screen.
- Load runs (game60) only after the operator's yes, at most 10 minutes, lead only, with nothing else running.
- Builds only through GitHub workflows (`tools/github_remote_build.py`), never on this machine; agents never build.
- Linux is best effort: it passes on code quality and the tests that run on Windows.
- Verification is the lead's job: what can be proved by a harness, a hidden run, a Display 1 run or a frozen build
  is proved, not handed to the operator; what has no simple test goes to the Watchlist and holds nothing open.

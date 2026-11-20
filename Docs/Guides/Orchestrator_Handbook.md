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
  fixed question and a brief that names the few documents it may edit (the decision documents and the plan,
  never product code, tests or builds); nobody else edits the plan while it runs; nothing else runs on Fable.
  Its decisions are written with their reasons where the brief says, and the lead reviews and merges the branch.
- **Agent slots, the cap** (operator, 12 Nov 2026 evening; agents were dying to usage limits before delivering;
  brand-neutral alternatives added 14 Nov). Each slot is a role; the model is whichever provider runs it:

  | Slot | Claude (Agent tool) | Codex (`codex_delegate`) |
  |---|---|---|
  | Complex or architecturally sensitive work | Opus 5.5 High | Sol 6.1 High |
  | General work (bounded repairs, tests, presets) | Opus 5.5 Medium | Sol 6.1 Medium |
  | Audits, including document and plan audits | Opus 5.5 High | Terra 6.1 High (a Codex audit always uses Terra 6.1 High) |
  | Research, documents, and large writing with little deduction (much code, simple logic: mechanical ports, bulk test or doc writing to a decided design) | Sonnet 5.5 Medium | Terra 6.1 Medium |
  | Milestone audit (rare, below) | Fable 5.2 High | none: Opus 5.5 High when Fable is unavailable |

  Plus the lead. The research and writing slot never decides design, never touches architecture-sensitive code,
  and its output is reviewed like any other branch. Codex jobs run only from the repository root (no worktrees),
  never block the lead, and are paused whenever the operator has disabled Codex delegation (out of quota);
  their CLI and setup are in `C:\Users\Basjohn\.local\share\codex-claude-bridge\README.md`.

  Normally one high-end task, one medium task and one audit run at once, unless the operator changes the cap.
  The cap counts agents running at once. When it shrinks, nobody busy is stopped: they finish, or hand over safely
  (journal current, work committed). New work starts only once the plans are in logical order and the open
  worries are solved.
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
| Every tool and harness: path, purpose, flags, who may run it, outputs, retire candidates (kept current: whoever adds, renames or removes a tool edits its row in the same commit) | `Docs/Reference/Tooling.md` |
| Routing of the recurring regression, attribution and acceptance commands | `Docs/Reference/Harness_Index.md` |
| Real-display proof (lead only, Display 1 only) | `tools/d1_run.py` (`--list-displays`, `--help` holds recipes) |
| Evidence layout | `tools/artifact_paths.py`; kept evidence in `.artifacts/evidence/<area>/<topic>/<YYYYMMDD>_<label>/` (enforced; `areas` lists the vocabulary) |
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
6. **Merge** (section 6), retire the worktree with `tools/agent_handover.py --retire` (it copies the evidence first),
   trim the copied evidence to what the report cites,
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

- **Read the plan limits every turn** (`mcp__ccd_session_mgmt__get_usage`: the 5-hour, weekly and Fable windows,
  percent used and reset time; operator, 13 Nov).
  - **At 85 % of the 5-hour or weekly window:**
    - tell every running agent to checkpoint now: a WIP commit of everything on disk, plus a journal entry with
      the exact next step and the numbers measured so far;
    - run `tools/agent_handover.py --commit` from the main checkout. It saves each worktree's uncommitted work
      as one "WIP (handover)" commit on that agent's branch.
  - **At 90 %:** no new dispatch and no new build round.
  - **A usage-limit warning:** the same as 85 %. Write the handover state into the plan: one box per interrupted
    agent, with its branch, last commits and what is left.
- **After a cut-off in the same session:** always resume the same agent with SendMessage, and tell it about any
  handover commit. Never start a fresh agent for the same task: its transcript holds the analysis. On 13 Nov a
  fresh start threw away an Extruded Bubble agent's reading, after its empty worktree had been cleaned up.
- **Every brief requires:**
  - a WIP commit at least every 20–30 minutes of edits, even mid-step;
  - evidence and baselines written to disk the moment they are measured;
  - a "next step" journal line before any long run.
- **In a new session:** run `tools/agent_handover.py` first. For each interrupted agent dispatch a successor whose
  brief starts with "run `git merge <branch>` first, then read `<worktree>/.artifacts/handover/JOURNAL.md` and the
  branch's last commits; check that what it marked done really is". The tool prints that line.
- The tool also lists agent branches that are not merged into `main` and have no worktree any more, so a branch
  left behind by an automatic worktree clean-up is never forgotten.
- Never delete a worktree or branch before its work is merged or deliberately abandoned (say which in the plan).

### 5a. Getting information from agents, live and dead

**A live agent** (started in this session, running or stopped):
- Ask it: `SendMessage` to its id resumes it with its whole transcript (a stopped agent restarts; a running one
  reads the message at its next tool call). Ask specific questions; it answers from what it read and measured.
- Its state without disturbing it: `tools/agent_handover.py <worktree>` (journal, commits, uncommitted files, live
  processes), `git log main..worktree-agent-<id>`, `<worktree>/.artifacts/handover/JOURNAL.md`, its evidence under
  `<worktree>/.artifacts/evidence/`.
- Never read its task output file (the `output_file` the Agent tool returns): it is the full JSONL transcript and
  floods the lead's context. Its final report arrives as the completion notice.
- A Codex job: `wait_for_job` returns its final response; a follow-up is a new `start_job` with `previous_job_id`.

**A dead agent** (an earlier session, or killed): it cannot be resumed (SendMessage fails with "no transcript").
What survives, in order of value:
1. Its branch's commits and its uncommitted files: `tools/agent_handover.py --commit` saves the latter as a
   "WIP (handover)" commit; the tool also lists merged-nowhere branches whose worktree is gone.
2. Its journal (`<worktree>/.artifacts/handover/JOURNAL.md`): the next step and the numbers it measured.
3. Its evidence under `<worktree>/.artifacts/` (scripts, JSON, stills).
4. Its transcript: `~/.claude/projects/<project>/<session-id>/subagents/*.jsonl`. Search it (grep for a file
   name, an error, a figure), never load it whole; `mcp__ccd_session_mgmt__search_session_transcripts` searches
   whole sessions. Use it to recover a finding the journal lacks, not to replay the work.
A successor's brief starts with "run `git merge <branch>` first, then read the journal and the branch's last
commits; check that what it marked done really is" (section 5).

## 6. Merging

From the main checkout, on `main`:

    git merge --no-ff worktree-agent-<id> -m "Merge <what landed>" -m "Co-authored by an incoming existential crisis."
    (run the item's tests on the merge)
    git fetch origin; git log main..origin/main      (empty: just push; otherwise pull, then push)
    git push origin main
    .venv/Scripts/python tools/agent_handover.py --retire agent-<id>

`--retire` copies the worktree's whole evidence tree into the main checkout (never overwriting), refuses an unmerged
branch, uncommitted work or a live process, and only then removes the worktree and the branch. Before recording a branch as merged with `git merge -s ours`, run `git log --oneline main..<branch>`: it must list only
that branch's own commits, whose content is already on main. If it lists another branch's commits (an agent merged a
work-in-progress branch), never use `-s ours`: git would then treat those commits as merged and silently drop them
from the later real merge. Never remove an agent
worktree with a bare `git worktree remove --force`: its evidence is untracked and is deleted for good (the 1C.4
comparison sheets were lost that way on 12 Nov). Trim the copied evidence to what the report cites afterwards.
`git pull --rebase=merges` can fail on a long merge-commit subject ("Filename too long" on `refs/rewritten/...`):
`git rebase --abort`, then fetch and push or merge origin instead.

Commit messages end with the trailer above and carry no AI attribution. The operator's own edits (presets,
defaults, the installer script) are committed and pushed at once, silently.

## 7. Hard limits the lead keeps

- Displays may be unavailable (operator, 12 Nov: "display availability may be on/off later on ... work with what
  you can"):
  - Before a D1 run, check the display exists (`tools/d1_run.py --list-displays`). If it is not there, the run
    stays a pending box and holds nothing.
  - Offscreen work goes on: hidden GL, the harness's hidden hosts, Vulkan offscreen targets, showcase WebPs and
    identity harnesses.
  - Every GPU timing or memory figure records whether the displays were on, and is compared only with figures taken
    in the same state.

- Display 0 (the operator's primary): rare. The lead may use it only for a specific check nothing else can make (operator, 12 Nov: "you can use Display 0 again when you need to", then "The permission is still rare. Do not make display 0 part of automated tests and use it rarely as possible"), through `tools/d1_run.py --allow-primary`, bounded, the reason in the run's label; never in a test, recipe or automated run; agents never take it. Bounded runs on Display 1 are the lead's, through `tools/d1_run.py`; agents never show
  a window on a real screen.
- Load runs (game60) only after the operator's yes, at most 10 minutes, lead only, with nothing else running.
- Builds only through GitHub workflows (`tools/github_remote_build.py`), never on this machine's resources; agents never build. Local frozen builds, local installer compiles (Build Runner's Inno step) and the Reddit Helper's local build stay the operator's own to run.
- Linux is best effort: it passes on code quality and the tests that run on Windows.
- Verification is the lead's job: what can be proved by a harness, a hidden run, a Display 1 run or a frozen build
  is proved, not handed to the operator; what has no simple test goes to the Watchlist and holds nothing open.

## 8. Native core work (C++; `Current_Plan.md` item 8b)

Added 12 Nov 2026 with the native core's direction (`Docs/Future_Work/Native_Core_P3_Decisions.md`, D5 to D11).

- **Compiling the native module goes through GitHub workflows** (operator, 12 Nov 2026: "you are allowed to
  build as long as you use github workflows to do it. This is authoritive."). The audit proposed that agents
  compile the module in their own worktrees with the scripted CMake step; that is *not* in force: no local
  compile exception is added to `Docs/Guardrails/Agent_Worktree_Rules.md` without the operator's explicit yes.
  A C++ slice's module is compiled by a GitHub workflow for a pushed ref (`.github/workflows/native-module.yml`,
  built in N0.9 on 12 Nov; the harness proofs N0.6 and N0.7 ran through it). The artefact is downloaded into the
  worktree (`Docs/Guides/GitHub_Remote_Build.md`, "The native modules"). The lead pushes the agent's branch and
  runs `tools/build_runner.py --mode github --run` from that worktree:
  - `--select native_spike` for a harness slice, landing in `release\native_spike\`;
  - `--select native_module` for the product's native core `native/core`, landing in `release\native_module\`.

  Agents never start a build, remote included. The lead's frozen products and installer payloads go through
  GitHub; the operator may compile locally (including the installer, since no installer is compiled on GitHub).
- **Port briefs cite playbook sections, not restated rules**: `Docs/Guides/Native_Port_Playbook.md` holds the port
  checklist, the standard proof and each primitive's contract, traps and proof; a brief names the sections it uses.
- **A port is audited on both backends.** Beside section 4's checks: the OpenGL parity record against the Python
  renderer, the Vulkan record against the native OpenGL result (hidden host), the thread probe (no call with a
  Python thread state), GPU time per pass, and the Python renderer deleted in the same change (a transition's at
  the background family's switch). A port with one record is not merged as done.
- **Vulkan in a real window is the lead's alone** until the flip: the rehearsal (decision D10) runs through
  `tools/d1_run.py` with the diagnostic backend switch, on Display 1, bounded, once per port. Agents prove Vulkan
  in hidden hosts only.
- **A native route beside QRhi needs its line first.** An agent that wants raw Vulkan or raw OpenGL for a pass
  stops and reports the measurement; the lead admits it as one of D5.3's services (with its twin on the other
  backend) or refuses it. The same holds for anything that would run on Vulkan only.
- **Qt is upgraded only between stages** (decision D11), by the lead, through the scripted step; never inside an
  agent's item.
- **Two ordered tracks, one High slot each,** once the substrate exists (modes; the background family), and a
  primitives track that never holds the flip. A track's next port is dispatched only when its last one is merged.

- Retiring a worktree also deletes its remote branch when the lead pushed it for a GitHub build (`git push origin --delete <branch>`); old branches are archived as `archive/<name>` tags only when they hold unported work (13 Nov: the Linux branch).

### 8a. P1 spike build retirement (16 Nov 2026)

The `native_spike` selection described above is retired. Build the product core only with
`tools/build_runner.py --mode github --run --select native_module`; the workflow accepts `native/core` only.
`native/spike_p1/` remains historical source evidence. Its useful remaining device/translucency proof now belongs to
`native/core/python/host_check.py` and `composite_check.py`; the maintained commands and visible-proof limits are in
`Docs/Reference/Harness_Index.md`. The external validation-layer directory keeps its existing name.

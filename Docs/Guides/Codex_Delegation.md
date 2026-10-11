# Codex delegation

How the Claude Code agent hands work to Codex and audits it (operator direction, 2026-10-11). Claude stays the
integration owner, full reviewer and auditor: nothing Codex produces lands until Claude has read it, checked it against
source, tests or renders, and fixed what falls short. Delegation saves Claude's context and runs in parallel; it is
never blocking. When Codex is out of quota or unavailable, Claude does the work itself.

## The bridge

Claude Code has the user-scoped MCP server `codex_delegate` (setup and troubleshooting:
`C:\Users\Basjohn\.local\share\codex-claude-bridge\README.md`):

- `start_job(prompt, cwd, access="read-only" | "workspace-write", model=None, effort=None, previous_job_id=None)`;
- `wait_for_job(job_id, seconds=30)` until `completed` or `failed`; `list_jobs()`, `cancel_job(job_id)`.

At most two jobs run at once; each is limited to 30 minutes. `model` / `effort` choose the job's Codex model and
reasoning (unset: Codex's configured default, `gpt-6-astra` at xhigh, which spends the most quota).

## Which model

- **`gpt-5.6-luna`, effort `max` or `xhigh`**: precise grunt work. Mechanical edits with objective checks, stale-test
  updates after a deliberate change, renames, lookups, log and test triage, inventories.
- **`gpt-6.1-sol`** (effort `xhigh` for consequential work, `high` otherwise): slower, careful work. Independent audits
  and code review, difficult debugging, bounded implementation with tests.
- Astra (the default) only when an independent flagship view is genuinely worth it.

## Writing a task

Codex starts cold. Every prompt is self-contained:

- what changed and why (the files, the new contract, what is retired);
- exactly which files it may edit, and that everything else is read-only (partition ownership: never two writers on one
  file; say what Claude is editing in parallel);
- the binding rules that apply (the focused guardrail docs by path, "never pin preset or default values", "no
  production edits: report suspected defects with evidence", "do not commit");
- how to verify (the exact commands) and what to report (per file: change and reason; remaining failures with
  evidence; anything regenerated and how).

Default to `read-only`. Use `workspace-write` only for edits inside the operator's authorized scope.

## Auditing the result

Treat every claim as unverified until checked:

1. Read the diff of every file it touched (`git diff -- <files>`), not only its report.
2. Re-run its verification yourself, then the impacted suite (`python tests/run_chunked.py --isolated --changed`).
3. Reject weakened tests: an assertion deleted rather than moved to the new contract, a pinned value, a skip, a widened
   tolerance without a cause.
4. Fix what falls short directly (or follow up with `previous_job_id` when the fix is large and mechanical).
5. Commit only what you have audited; say in the commit what Codex did and what you changed.

## Good parallel work

Stale tests after a reviewed production change; independent read-only audits of a slice before it is committed;
inventories and lookups across the tree; regenerating goldens with the repository's own tools under stated rules.
Not for: product or artistic choices, anything touching the operator's defaults or presets, builds (agents never run
Nuitka, Build Runner or installers), or work whose files Claude is editing at the same time.

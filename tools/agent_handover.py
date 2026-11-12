"""State of every agent worktree, and a clean handover of an interrupted agent's work (lead only).

    .venv/Scripts/python tools/agent_handover.py                 # report every worktree, change nothing
    .venv/Scripts/python tools/agent_handover.py --commit        # also save uncommitted work as a handover commit
    .venv/Scripts/python tools/agent_handover.py --commit agent-a1b2c3   # only the named worktrees
    .venv/Scripts/python tools/agent_handover.py --retire agent-a1b2c3   # after the merge: keep evidence, remove

An agent can stop at any moment (a usage limit, a crash), and an agent of an earlier session cannot be resumed. What
it leaves is its branch, whatever it had not committed, and its progress journal
(``.artifacts/handover/JOURNAL.md`` in its worktree, kept as ``Docs/Guardrails/Agent_Worktree_Rules.md`` requires).
For each worktree under ``.claude/worktrees`` this prints the branch, its commits ahead of ``main``, the uncommitted
files, the journal, and any process still running from the worktree. With ``--commit`` uncommitted work becomes one
"WIP (handover)" commit on the agent's branch, so nothing depends on the worktree surviving. It then prints the lines
a successor's brief needs: the branch to merge first and where the journal and evidence are.

It never pushes, never merges and never stops a process. ``--retire`` is the one way the lead removes a merged
agent's worktree: it refuses a branch that is not merged into ``main`` or a worktree with uncommitted work or a
running process, copies the worktree's whole ``.artifacts/evidence`` and ``.artifacts/webp`` trees into this checkout's (a file that already
exists here is never overwritten; a differing one is reported), and only then removes the worktree and deletes the
branch. A bare ``git worktree remove --force`` deletes untracked evidence for good (12 Nov 2026: the 1C.4 comparison
sheets were lost that way), so the handbook's merge steps use this instead. Trimming kept evidence to what the
report cites is done afterwards in this checkout, where nothing is lost by mistake.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import artifact_paths  # noqa: E402  (the one owner of the artifact layout's names)

WORKTREES = ROOT / ".claude" / "worktrees"
# Each worktree has the same layout as this checkout; only the folder names are taken from the owner.
ARTIFACTS_NAME = artifact_paths.ARTIFACTS_ROOT.name
EVIDENCE_NAME = artifact_paths.EVIDENCE_ROOT.name
# Kept output an agent leaves: evidence (stills, data) and showcase WebPs; both are copied before a worktree goes.
KEPT_NAMES = (EVIDENCE_NAME, artifact_paths.WEBP_ROOT.name)
JOURNAL = Path(ARTIFACTS_NAME) / "handover" / "JOURNAL.md"
TRAILER = "Co-authored by an incoming existential crisis."


def git(worktree: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(worktree), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return (done.stdout or "").strip()


def running_from(worktree: Path) -> list[str]:
    """Processes whose command line names the worktree (Windows; reported, never stopped)."""
    if sys.platform != "win32":
        return []
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('"
              + worktree.name + "') -and $_.Name -ne 'powershell.exe' -and $_.Name -ne 'pwsh.exe' -and -not $_.CommandLine.Contains('agent_handover') } | "
              "ForEach-Object { \"$($_.ProcessId) $($_.Name) $($_.CommandLine.Substring(0, "
              "[Math]::Min(120, $_.CommandLine.Length)))\" }")
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    return [line for line in (done.stdout or "").splitlines() if line.strip()]


def report(worktree: Path, commit: bool) -> None:
    branch = git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
    ahead = git(worktree, "log", "--format=%h %s", "main..HEAD").splitlines()
    dirty = [line for line in git(worktree, "status", "--short").splitlines() if not line.endswith(".rcc")]
    print("=" * 100)
    print(f"{worktree.name}   branch {branch}   {len(ahead)} commit(s) ahead of main   {len(dirty)} uncommitted")
    for line in ahead[:25]:
        print(f"   {line[:150]}")
    if dirty:
        print("   uncommitted:")
        for line in dirty[:40]:
            print(f"     {line}")
        if commit:
            git(worktree, "add", "-A")
            git(worktree, "commit", "-q", "-m",
                "WIP (handover): uncommitted work of an interrupted agent\n\n" + TRAILER)
            print(f"   -> saved as {git(worktree, 'log', '-1', '--format=%h %s')}")
    journal = worktree / JOURNAL
    if journal.is_file():
        print(f"   journal ({journal}):")
        for line in journal.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
            print(f"     | {line}")
    else:
        print("   NO JOURNAL: the agent never started, or broke the first rule of Agent_Worktree_Rules.md")
    evidence = worktree / ARTIFACTS_NAME / EVIDENCE_NAME
    if evidence.is_dir():
        folders = sorted({str(path.parent.relative_to(worktree)) for path in evidence.rglob("*") if path.is_file()})
        print(f"   evidence folders: {', '.join(folders[:8])}{' ...' if len(folders) > 8 else ''}")
    for line in running_from(worktree):
        print(f"   STILL RUNNING: {line}")
    print("   successor's brief:")
    print(f"     run `git merge {branch}` first; the earlier agent's journal is at")
    print(f"     {journal if journal.is_file() else '(none)'} and its evidence under {evidence} (both read only).")


def retire(worktree: Path) -> int:
    """Copy a merged agent's evidence into this checkout, then remove its worktree and branch."""
    if not (worktree / ".git").exists():
        print(f"{worktree.name}: not a worktree")
        return 1
    branch = git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
    # Merged means merged by the lead: the branch tip is a merged-in parent of a merge commit on main. A branch with
    # no commits of its own (an agent that has just started) is an ancestor of main too, and must never be retired.
    tip = git(worktree, "rev-parse", "HEAD")
    merged_in = {parent for line in git(ROOT, "log", "main", "--merges", "-n", "2000", "--format=%P").splitlines()
                 for parent in line.split()[1:]}
    if tip not in merged_in:
        print(f"{worktree.name}: REFUSED, {branch} is not merged into main by a merge commit")
        return 1
    dirty = [line for line in git(worktree, "status", "--short").splitlines() if not line.endswith(".rcc")]
    if dirty:
        print(f"{worktree.name}: REFUSED, {len(dirty)} uncommitted file(s); commit or discard them deliberately first")
        return 1
    if running_from(worktree):
        print(f"{worktree.name}: REFUSED, a process is still running from it")
        return 1
    copied, kept, differing = 0, 0, []
    for name in KEPT_NAMES:
        source = worktree / ARTIFACTS_NAME / name
        target = ROOT / ARTIFACTS_NAME / name
        if not source.is_dir():
            continue
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            destination = target / path.relative_to(source)
            if destination.exists():
                kept += 1
                if not filecmp.cmp(path, destination, shallow=False):
                    differing.append(str(destination.relative_to(ROOT)))
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied += 1
    print(f"{worktree.name}: evidence and WebPs copied {copied} file(s), {kept} already present")
    for name in differing[:20]:
        print(f"   DIFFERS (kept this checkout's): {name}")
    if differing:
        print(f"{worktree.name}: REFUSED to remove, {len(differing)} evidence file(s) differ; resolve them first")
        return 1
    subprocess.run(["git", "-C", str(ROOT), "worktree", "unlock", str(worktree)], capture_output=True)
    done = subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(worktree)],
                          capture_output=True, text=True)
    if done.returncode:
        print(f"{worktree.name}: worktree remove failed: {done.stderr.strip()}")
        return 1
    git(ROOT, "branch", "-D", branch)
    print(f"{worktree.name}: removed; branch {branch} deleted")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("worktrees", nargs="*", help="worktree folder names (default: all)")
    parser.add_argument("--commit", action="store_true", help="save uncommitted work as a WIP (handover) commit")
    parser.add_argument("--retire", action="store_true",
                        help="after the merge: copy the named worktrees' evidence here, then remove them")
    args = parser.parse_args()
    if args.retire:
        if not args.worktrees:
            parser.error("--retire needs the worktree names")
        return max(retire(WORKTREES / name) for name in args.worktrees)
    if not WORKTREES.is_dir():
        print("no agent worktrees")
        return 0
    chosen = [WORKTREES / name for name in args.worktrees] if args.worktrees else sorted(
        path for path in WORKTREES.iterdir() if (path / ".git").exists())
    for worktree in chosen:
        if not (worktree / ".git").exists():
            print(f"{worktree.name}: not a worktree")
            continue
        report(worktree, args.commit)
    if not args.worktrees:
        orphans(chosen)
    return 0


def orphans(worktrees: list[Path]) -> None:
    """Agent branches that are not merged into main and have no worktree any more (an automatic clean-up, a
    removed folder): their work would otherwise be forgotten."""
    with_worktree = {git(path, "rev-parse", "--abbrev-ref", "HEAD") for path in worktrees}
    unmerged = git(ROOT, "branch", "--no-merged", "main", "--format=%(refname:short)").splitlines()
    left = [name for name in unmerged if name.startswith("worktree-agent-") and name not in with_worktree]
    if not left:
        return
    print("=" * 100)
    print("UNMERGED AGENT BRANCHES WITHOUT A WORKTREE (merge or abandon each deliberately; say which in the plan):")
    for name in left:
        print(f"   {name}   {git(ROOT, 'log', '-1', '--format=%h %ad %s', '--date=short', name)[:130]}")


if __name__ == "__main__":
    sys.exit(main())

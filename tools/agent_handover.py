"""State of every agent worktree, and a clean handover of an interrupted agent's work (lead only).

    .venv/Scripts/python tools/agent_handover.py                 # report every worktree, change nothing
    .venv/Scripts/python tools/agent_handover.py --commit        # also save uncommitted work as a handover commit
    .venv/Scripts/python tools/agent_handover.py --commit agent-a1b2c3   # only the named worktrees

An agent can stop at any moment (a usage limit, a crash), and an agent of an earlier session cannot be resumed. What
it leaves is its branch, whatever it had not committed, and its progress journal
(``.artifacts/handover/JOURNAL.md`` in its worktree, kept as ``Docs/Guardrails/Agent_Worktree_Rules.md`` requires).
For each worktree under ``.claude/worktrees`` this prints the branch, its commits ahead of ``main``, the uncommitted
files, the journal, and any process still running from the worktree. With ``--commit`` uncommitted work becomes one
"WIP (handover)" commit on the agent's branch, so nothing depends on the worktree surviving. It then prints the lines
a successor's brief needs: the branch to merge first and where the journal and evidence are.

It never pushes, never merges, never deletes a worktree and never stops a process: those stay the lead's decisions.
"""
from __future__ import annotations

import argparse
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
              + worktree.name + "') -and $_.Name -ne 'powershell.exe' -and $_.Name -ne 'pwsh.exe' } | "
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
        print("   no journal (an agent briefed before the journal rule, or one that had not started)")
    evidence = worktree / ARTIFACTS_NAME / EVIDENCE_NAME
    if evidence.is_dir():
        folders = sorted({str(path.parent.relative_to(worktree)) for path in evidence.rglob("*") if path.is_file()})
        print(f"   evidence folders: {', '.join(folders[:8])}{' ...' if len(folders) > 8 else ''}")
    for line in running_from(worktree):
        print(f"   STILL RUNNING: {line}")
    print("   successor's brief:")
    print(f"     run `git merge {branch}` first; the earlier agent's journal is at")
    print(f"     {journal if journal.is_file() else '(none)'} and its evidence under {evidence} (both read only).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("worktrees", nargs="*", help="worktree folder names (default: all)")
    parser.add_argument("--commit", action="store_true", help="save uncommitted work as a WIP (handover) commit")
    args = parser.parse_args()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

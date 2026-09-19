"""Repo-local, opt-in script-run helpers for GODZIP Foundry's CMD tab.

Pure stdlib: text parsing and archive production are testable without Qt.  The
GUI owns the actual explicit-confirmation and QProcess lifecycle.  Never eval
pasted text in this module and never run it as a side effect of normalization.
"""
from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

_RUN_LIMIT_BYTES = 32 * 1024 * 1024
_ZIP_LIMIT_BYTES = 50 * 1024 * 1024
_MARKDOWN_FENCE = re.compile(r"^\s*```\s*(?:powershell|ps1|pwsh|cmd|bat|batch|text|console)?(?:\s+id=[\w\"-]+)?\s*$", re.I)
_PS_PROMPT = re.compile(r"^\s*PS\s+(?:[A-Za-z]:\\|\\\\|/)[^\r\n>]*>\s?", re.I)
_CMD_PROMPT = re.compile(r"^\s*(?:[A-Za-z]:\\|\\\\)[^\r\n>]*>\s?")
_PS_CONTINUATION = re.compile(r"^\s*>>\s?")


class ScriptRunError(ValueError):
    """Explain why a pasted script or results bundle cannot safely be prepared."""


@dataclass(frozen=True)
class ScriptPreview:
    shell: str
    script: str
    changes: tuple[str, ...]
    warnings: tuple[str, ...]


def normalize_script_paste(raw: str, *, shell: str = "auto") -> ScriptPreview:
    """Remove *only* unambiguous display wrappers; never rewrite shell logic."""
    if shell not in {"auto", "powershell", "cmd"}:
        raise ScriptRunError("Choose PowerShell, CMD or Auto before previewing")
    value = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if len(value) > 200_000:
        raise ScriptRunError("Paste is too large; use a script file instead")
    lines = value.split("\n")
    changes: list[str] = []
    warnings: list[str] = []
    # A pasted fenced block is acceptable only if the closing fence is actually
    # present. Never erase arbitrary backticks or legitimate script lines.
    meaningful = [i for i, line in enumerate(lines) if line.strip()]
    if meaningful and lines[meaningful[0]].lstrip().startswith("```"):
        first, last = meaningful[0], meaningful[-1]
        if last <= first or lines[last].strip() != "```" or not _MARKDOWN_FENCE.fullmatch(lines[first]):
            raise ScriptRunError("Incomplete/unknown Markdown code fence. Remove its wrapper and preview again")
        language = lines[first].strip().split()[0][3:].lower()
        if shell == "auto" and language in {"powershell", "ps1", "pwsh"}:
            shell = "powershell"
        elif shell == "auto" and language in {"cmd", "bat", "batch"}:
            shell = "cmd"
        lines = lines[first + 1:last]
        changes.append("Removed a complete Markdown code fence")
    prompted_ps = any(_PS_PROMPT.match(line) for line in lines)
    prompted_cmd = any(_CMD_PROMPT.match(line) for line in lines)
    if prompted_ps and prompted_cmd:
        raise ScriptRunError("Mixed PowerShell and CMD transcript prompts; choose one command at a time")
    if shell == "auto":
        if prompted_ps or re.search(r"(?m)^\s*\$\w+\s*=|\$LASTEXITCODE|\b(?:Get|Set)-\w+\b|\bif\s*\(\s*\$", "\n".join(lines), re.I):
            shell = "powershell"
        elif prompted_cmd or re.search(r"(?m)^\s*@echo\s+off\b|\b(?:cmd\s+/c|call\s+\S+\.bat)\b", "\n".join(lines), re.I):
            shell = "cmd"
        else:
            # Existing CMD tab's primary terminal is PowerShell; a bare python
            # pytest command works there. Do not infer CMD from a bare 'python'.
            shell = "powershell"
    if prompted_ps and shell != "powershell" or prompted_cmd and shell != "cmd":
        raise ScriptRunError("Selected shell conflicts with the pasted prompt")
    cleaned: list[str] = []
    prompts_removed = False
    for line in lines:
        if prompted_ps:
            match = _PS_PROMPT.match(line)
            if match:
                line = line[match.end():]
                prompts_removed = True
            elif _PS_CONTINUATION.match(line):
                line = _PS_CONTINUATION.sub("", line, count=1)
                prompts_removed = True
        elif prompted_cmd:
            match = _CMD_PROMPT.match(line)
            if match:
                line = line[match.end():]
                prompts_removed = True
        cleaned.append(line)
    if prompts_removed:
        changes.append("Removed terminal prompt/continuation prefixes")
    script = "\n".join(cleaned).strip()
    if not script:
        raise ScriptRunError("There is no command left to run")
    if "```" in script:
        raise ScriptRunError("An embedded or incomplete Markdown fence remains in the script")
    # Transcripts mix commands and printed results. They are not script files.
    # Do not automatically delete output lines because that can erase real code.
    if prompted_ps or prompted_cmd:
        for line in script.splitlines():
            if re.match(r"^\s*(?:\.{12,}\s*\[|=+\s*FAILURES|FAILED\s+tests/|\d+\s+(?:passed|failed)\b)", line, re.I):
                raise ScriptRunError("The paste includes terminal test results. Paste only the command or edit the preview")
    if shell == "powershell" and re.search(r"(?m)^\s*(?:@echo\s+off|set\s+/[ap])\b", script, re.I):
        warnings.append("This looks like CMD syntax, not PowerShell. Review the selected shell")
    if shell == "cmd" and re.search(r"\$LASTEXITCODE|\$\w+\s*=", script):
        warnings.append("This looks like PowerShell syntax, not CMD. Review the selected shell")
    return ScriptPreview(shell, script, tuple(changes), tuple(warnings))


def snapshot_loose_logs(repo_root: Path) -> dict[str, tuple[int, int]]:
    """Metadata-only snapshot. Never recursively scan large evidence archives."""
    logs = Path(repo_root) / "logs"
    if not logs.is_dir():
        return {}
    result = {}
    for item in logs.iterdir():
        if item.is_file() and not item.is_symlink():
            stat = item.stat()
            result[item.name] = (stat.st_size, stat.st_mtime_ns)
    return result


def create_script_results_zip(
    repo_root: Path,
    run_dir: Path,
    *,
    initial_logs: Mapping[str, tuple[int, int]],
    output_dir: Path,
    final_logs: Mapping[str, tuple[int, int]] | None = None,
) -> tuple[Path, tuple[str, ...]]:
    """Bounded ZIP: run transcript and only newly created/changed loose logs.

    No preexisting large ETLs, no recursive traversal, no deletion of sources.
    """
    repo_root, run_dir, output_dir = (Path(p).resolve() for p in (repo_root, run_dir, output_dir))
    state_root = repo_root / ".godzip_foundry" / "runs"
    if not run_dir.is_relative_to(state_root) or not run_dir.is_dir():
        raise ScriptRunError("Results must belong to a repo-local Foundry run directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = []
    for filename in ("command.txt", "output.txt", "result.json"):
        path = run_dir / filename
        if path.is_file() and not path.is_symlink():
            candidates.append((path, f"run/{filename}"))
    logs = repo_root / "logs"
    after = final_logs if final_logs is not None else snapshot_loose_logs(repo_root)
    for name in sorted(after):
        if after[name] == initial_logs.get(name):
            continue
        path = logs / name
        if path.is_file() and not path.is_symlink():
            current = path.stat()
            if (current.st_size, current.st_mtime_ns) == after[name]:
                candidates.append((path, f"logs/{name}"))
    if not candidates:
        raise ScriptRunError("Nothing was captured for this run")
    sizes = [p.stat().st_size for p, _ in candidates]
    if any(size > _RUN_LIMIT_BYTES for size in sizes) or sum(sizes) > _ZIP_LIMIT_BYTES:
        raise ScriptRunError("Run results exceed the 50 MB ZIP safety cap; copy the text output or select smaller logs manually")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = output_dir / f"GODZIP_RUN_RESULTS_{stamp}_{run_dir.name}.zip"
    with tempfile.NamedTemporaryFile(prefix=".godzip_script_",suffix=".tmp",dir=output_dir,delete=False) as tmp:
        staging=Path(tmp.name)
    try:
        with zipfile.ZipFile(staging,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for path, member in candidates:
                archive.write(path,member)
        with zipfile.ZipFile(staging) as archive:
            bad=archive.testzip()
            if bad:
                raise ScriptRunError(f"Run ZIP checksum failed at {bad}")
        os.replace(staging,dest)
    finally:
        staging.unlink(missing_ok=True)
    return dest,tuple(member for _,member in candidates)

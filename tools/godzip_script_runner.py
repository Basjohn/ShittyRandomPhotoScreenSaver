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


# The command editor is the only authority: this helper returns edited text,
# never launches or activates a shell.  Each bare Python command is rewritten
# in place so other commands, branching and failure handling are preserved.
_BARE_PYTHON_COMMAND = re.compile(r"(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?|pytest(?:\.exe)?)\b", re.I)


def add_repo_venv_to_script(raw: str, *, shell: str = "powershell") -> str:
    """Use the repo-local Python for bare Python/pytest shell commands.

    Preserve scripts without Python invocations, already-qualified interpreter
    paths, quoted strings and comments.  PowerShell requires its call operator
    for a relative path; CMD does not.  Repeated use is a no-op.
    """
    if shell not in {"powershell", "cmd"}:
        raise ScriptRunError("Choose PowerShell or CMD before adding the venv")
    venv = r".\.venv\Scripts\python.exe"
    result: list[str] = []
    for line in str(raw).splitlines(keepends=True):
        out: list[str] = []
        i = 0
        quote = ""
        can_start_command = True
        # Shell commands may occur after separators or inside PS if-blocks.
        # Don't alter quoted scripts, arguments, comments or qualified paths.
        while i < len(line):
            ch = line[i]
            if quote:
                out.append(ch)
                if shell == "powershell" and ch == "`" and i + 1 < len(line):
                    i += 1
                    out.append(line[i])
                elif ch == quote:
                    if quote == "'" and shell == "powershell" and i + 1 < len(line) and line[i + 1] == "'":
                        i += 1
                        out.append(line[i])
                    else:
                        quote = ""
                i += 1
                continue
            if ch in ('"', "'"):
                quote = ch
                out.append(ch)
                can_start_command = False
                i += 1
                continue
            if ch == "#" and shell == "powershell" and (i == 0 or line[i - 1].isspace()):
                out.append(line[i:])
                break
            if ch in " \t\r\n":
                out.append(ch)
                i += 1
                continue
            if ch in ";|&{}":
                out.append(ch)
                can_start_command = True
                i += 1
                continue
            if ch == "(" and can_start_command:
                out.append(ch)
                i += 1
                continue
            if can_start_command:
                found = _BARE_PYTHON_COMMAND.match(line, i)
                if found:
                    token = found.group(0)
                    # pip/pytest entry points belong to the venv as well.
                    suffix = " -m pytest" if token.lower().startswith("pytest") else ""
                    prev = "".join(out).rstrip()
                    call = "" if shell == "cmd" or (prev.endswith("&") and not prev.endswith("&&")) else "& "
                    out.append(call + venv + suffix)
                    i = found.end()
                    can_start_command = False
                    continue
            out.append(ch)
            can_start_command = False
            i += 1
        result.append("".join(out))
    return "".join(result)


def _script_log_path(logs: Path, relative_name: str) -> Path | None:
    """Recognize bounded script evidence, never arbitrary paths under /logs.

    The pytest isolated runner writes one file per test in a *single* child
    directory. LOGZIP archives, caches and other recursive trees are excluded.
    Reject foreign/escaped snapshot keys even if supplied by a caller.
    """
    if not relative_name or "\\" in relative_name:
        return None
    parts = relative_name.split("/")
    if len(parts) == 1 and parts[0] not in {"", ".", ".."}:
        return logs / parts[0]
    if (len(parts) == 2 and parts[0] == "pytest_isolated"
            and parts[1] not in {"", ".", ".."}
            and parts[1].lower().endswith((".log", ".dmp"))
            and not (logs / "pytest_isolated").is_symlink()):
        return logs / parts[0] / parts[1]
    return None


def snapshot_loose_logs(repo_root: Path) -> dict[str, tuple[int, int]]:
    """Snapshot run evidence: loose /logs files and per-file isolated pytest logs.

    The public name is retained for compatibility with existing Foundry callers.
    This remains a shallow, metadata-only scan; no large evidence archives or
    arbitrary subdirectories are traversed. Keys are POSIX-relative to /logs.
    """
    logs = Path(repo_root) / "logs"
    if not logs.is_dir() or logs.is_symlink():
        return {}
    result: dict[str, tuple[int, int]] = {}
    for item in logs.iterdir():
        if item.is_file() and not item.is_symlink():
            stat = item.stat()
            result[item.name] = (stat.st_size, stat.st_mtime_ns)
    isolated = logs / "pytest_isolated"
    if isolated.is_dir() and not isolated.is_symlink():
        for item in isolated.iterdir():
            if item.suffix.lower() not in {".log", ".dmp"} or not item.is_file() or item.is_symlink():
                continue
            stat = item.stat()
            result[f"pytest_isolated/{item.name}"] = (stat.st_size, stat.st_mtime_ns)
    return result


def create_script_results_zip(
    repo_root: Path,
    run_dir: Path,
    *,
    initial_logs: Mapping[str, tuple[int, int]],
    output_dir: Path,
    final_logs: Mapping[str, tuple[int, int]] | None = None,
) -> tuple[Path, tuple[str, ...]]:
    """Bounded ZIP: run transcript and newly created/changed run evidence.

    Includes per-test logs and native timeout dumps from /logs/pytest_isolated/,
    not unrelated historical files. No recursive traversal or source deletion.
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
        path = _script_log_path(logs, name)
        if path is None:
            raise ScriptRunError(f"Invalid run-log snapshot path: {name!r}")
        if not path.is_file() or path.is_symlink():
            raise ScriptRunError(f"Run evidence disappeared before ZIP: logs/{name}")
        current = path.stat()
        if (current.st_size, current.st_mtime_ns) != after[name]:
            raise ScriptRunError(
                f"Run evidence changed since completion: logs/{name}. "
                "Preserve the logs before another run replaces them"
            )
        candidates.append((path, f"logs/{name}"))
    if not candidates:
        raise ScriptRunError("Nothing was captured for this run")
    # Protect the text evidence first. Qt minidumps can occasionally exceed
    # the existing 50 MB run-ZIP cap; never let a large dump prevent shipping
    # the actual failure tracebacks. Keep the dump on disk and record its path.
    mandatory = [(path, member) for path, member in candidates if not member.lower().endswith(".dmp")]
    dumps = [(path, member) for path, member in candidates if member.lower().endswith(".dmp")]
    sizes = [path.stat().st_size for path, _ in mandatory]
    if any(size > _RUN_LIMIT_BYTES for size in sizes) or sum(sizes) > _ZIP_LIMIT_BYTES:
        raise ScriptRunError("Run text evidence exceeds the 50 MB ZIP safety cap; preserve smaller logs separately")
    selected = list(mandatory)
    total = sum(sizes)
    omitted = []
    for path, member in dumps:
        size = path.stat().st_size
        if size > _RUN_LIMIT_BYTES or total + size > _ZIP_LIMIT_BYTES - 8192:
            omitted.append((member, size, path))
        else:
            selected.append((path, member))
            total += size
    notice = ("Native diagnostic dumps kept outside this 50 MB run ZIP:\n"
              + "".join(f"{member} ({size} bytes): {path}\n" for member, size, path in omitted)) if omitted else ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = output_dir / f"GODZIP_RUN_RESULTS_{stamp}_{run_dir.name}.zip"
    with tempfile.NamedTemporaryFile(prefix=".godzip_script_",suffix=".tmp",dir=output_dir,delete=False) as tmp:
        staging=Path(tmp.name)
    try:
        with zipfile.ZipFile(staging,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for path, member in selected:
                archive.write(path,member)
            if notice:
                archive.writestr("run/native_dumps_not_bundled.txt", notice)
        with zipfile.ZipFile(staging) as archive:
            bad=archive.testzip()
            if bad:
                raise ScriptRunError(f"Run ZIP checksum failed at {bad}")
        os.replace(staging,dest)
    finally:
        staging.unlink(missing_ok=True)
    return dest,tuple(member for _,member in selected) + (("run/native_dumps_not_bundled.txt",) if notice else ())

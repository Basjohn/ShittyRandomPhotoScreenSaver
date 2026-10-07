"""Run a declarative matrix of bounded SRPSS RUN sessions.

The product owns shutdown through ``--exit-after``. This coordinator launches
only canonical source entrypoints, captures each completed run's canonical
logs before the next run can rotate them, and never terminates a child itself.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
ENTRYPOINTS = {name: ROOT / name for name in ("main_mc.py", "main.py")}
DEFAULT_ENTRYPOINT = "main_mc.py"
SAFE_FLAGS = {
    "--debug", "-d", "--verbose", "-v", "--perf", "--usage",
    "--handle-attribution", "--viz", "--geo", "--life", "--cache",
    "--steam", "--feeds", "--noupdates", "--frame-trace",
    "--gui-stall-stacks", "--fresh", "--set",
}
LOG_NAMES = (
    "screensaver.log",
    "screensaver_verbose.log",
    "screensaver_qml.log",
    "native_faults.log",
    "diagnostic_crash.log",
    "screensaver_perf.log",
    "perf_widgets.log",
    "screensaver_usage.log",
    "screensaver_handles.log",
    "screensaver_spotify_vis.log",
    "screensaver_spotify_vol.log",
    "screensaver_geometry.log",
    "screensaver_settings.log",
    "screensaver_lifecycle.log",
    "screensaver_cache.log",
    "screensaver_steam.log",
    "screensaver_feeds.log",
    "screensaver_frame_trace.bin",
    "gui_stall_stacks.log",
)
FAULT_RE = re.compile(
    r"Windows fatal exception|access violation|BufferError|"
    r"memoryview has 1 exported buffer",
    re.IGNORECASE,
)
MAX_CASES = 100
MAX_EXIT_AFTER_SECONDS = 3600.0
# Maximum retained rotation count from the canonical owners (diagnostic profile
# included). Only these exact names are copied; evidence subdirectories are not.
LOG_ROTATIONS = {name: 5 for name in LOG_NAMES if name.endswith(".log")}
LOG_ROTATIONS.update({"screensaver.log": 11, "screensaver_usage.log": 11,
                      "screensaver_lifecycle.log": 11, "screensaver_verbose.log": 3,
                      "screensaver_qml.log": 3, "screensaver_handles.log": 0,
                      "gui_stall_stacks.log": 0, "screensaver_frame_trace.bin": 3})


class MatrixError(ValueError):
    """Invalid or unsafe run-matrix input."""


@dataclass(frozen=True)
class RunCase:
    name: str
    entrypoint: str
    argv: tuple[str, ...]
    exit_after_seconds: float


def _require_object(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise MatrixError(f"{where} must be an object")
    return value


def load_matrix(path: Path) -> list[RunCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MatrixError(f"cannot read matrix {path}: {exc}") from exc
    matrix = _require_object(payload, "matrix")
    if set(matrix) != {"schema_version", "cases"}:
        raise MatrixError("matrix must contain only schema_version and cases")
    if type(matrix["schema_version"]) is not int or matrix["schema_version"] != 1:
        raise MatrixError("schema_version must be 1")
    raw_cases = matrix["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise MatrixError("cases must be a non-empty list")
    if len(raw_cases) > MAX_CASES:
        raise MatrixError(f"cases may contain at most {MAX_CASES} entries")

    cases: list[RunCase] = []
    for index, raw_case in enumerate(raw_cases):
        where = f"cases[{index}]"
        case = _require_object(raw_case, where)
        if set(case) not in ({"name", "entrypoint", "argv", "exit_after_seconds"},
                             {"name", "argv", "exit_after_seconds"}):
            raise MatrixError(
                f"{where} must contain only name, entrypoint, argv, exit_after_seconds"
            )
        raw_argv = case["argv"]
        if not isinstance(raw_argv, list) or any(not isinstance(arg, str) for arg in raw_argv):
            raise MatrixError(f"{where}.argv must be a list of strings")
        cases.append(RunCase(case["name"], case.get("entrypoint", DEFAULT_ENTRYPOINT),
                             tuple(raw_argv), case["exit_after_seconds"]))
    _validate_cases(cases)
    return cases


def _validate_cases(cases: Sequence[RunCase]) -> None:
    """The public Python seam has the same admission rules as the JSON CLI."""
    if not cases or len(cases) > MAX_CASES:
        raise MatrixError(f"cases must contain 1 to {MAX_CASES} entries")
    names: set[str] = set()
    for case in cases:
        if not isinstance(case, RunCase):
            raise MatrixError("cases must contain RunCase values")
        if not isinstance(case.name, str) or not case.name.strip() or len(case.name) > 80:
            raise MatrixError("case name must be a non-empty string of at most 80 characters")
        if case.name in names:
            raise MatrixError(f"duplicate case name: {case.name}")
        names.add(case.name)
        if not isinstance(case.entrypoint, str) or case.entrypoint not in ENTRYPOINTS:
            raise MatrixError("case entrypoint must be canonical")
        if not isinstance(case.argv, (tuple, list)) or any(not isinstance(a, str) for a in case.argv):
            raise MatrixError("case argv must contain strings")
        if case.argv.count("/s") != 1 or any(a != "/s" and a not in SAFE_FLAGS for a in case.argv):
            raise MatrixError("case argv must contain /s exactly once and only admitted flags")
        if "--gui-stall-stacks" in case.argv and "--frame-trace" not in case.argv:
            raise MatrixError("--gui-stall-stacks requires --frame-trace")
        seconds = case.exit_after_seconds
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds) or not 0 < seconds <= MAX_EXIT_AFTER_SECONDS):
            raise MatrixError("case exit_after_seconds must be finite and between 0 and 3600")


def _artifact_names() -> list[str]:
    return [rotation for name in LOG_NAMES for rotation in
            [name, *(f"{name}.{i}" for i in range(1, LOG_ROTATIONS[name] + 1))]]


def _copy_run_logs(run_dir: Path, log_dir: Path) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    log_dir_resolved = log_dir.resolve()
    for name in _artifact_names():
        source = log_dir_resolved / name
        destination = run_dir / "logs" / name
        present = source.is_file()
        copy_error = None
        if present:
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            except OSError as exc:
                copy_error = str(exc)
                present = False
        artifacts.append({"name": name, "present": present, "path": str(destination.resolve()),
                          "copy_error": copy_error})
    return artifacts


def _capture_log_baselines(log_dir: Path) -> dict[str, bytes | None]:
    baselines: dict[str, bytes | None] = {}
    for name in _artifact_names():
        path = log_dir / name
        try:
            baselines[name] = path.read_bytes() if path.is_file() and ".log" in name else None
        except OSError as exc:
            raise MatrixError(f"cannot read pre-run baseline {path}: {exc}") from exc
    return baselines


def _scan_evidence(
    artifacts: Sequence[dict[str, object]], baselines: dict[str, bytes | None], *, fresh: bool,
    handle_attribution: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Scope scans by byte boundary, including rollover; never rescan old faults.

    A retained baseline tail locates the end of the preceding RUN even when its
    file has moved to .1/.2. If retention or truncation loses that tail, this
    family cannot prove its current-run scope and acceptance is unavailable.
    """
    faults: list[dict[str, object]] = []
    unavailable: list[str] = []
    contents: dict[str, bytes] = {}
    current: dict[str, str] = {}
    for artifact in artifacts:
        if artifact.get("copy_error"):
            unavailable.append(f"cannot snapshot {artifact['name']}: {artifact['copy_error']}")
        if not artifact["present"] or (".log" not in str(artifact["name"])
                                       and artifact["name"] not in {"stdout.bin", "stderr.bin"}):
            continue
        try:
            contents[str(artifact["name"])] = Path(str(artifact["path"])).read_bytes()
        except OSError as exc:
            unavailable.append(f"cannot read {artifact['name']}: {exc}")
    unavailable.extend(f"missing process output: {name}" for name in ("stdout.bin", "stderr.bin")
                       if name not in contents)
    for name in [*(n for n in LOG_NAMES if n.endswith(".log")), "stdout.bin", "stderr.bin"]:
        names = ([f"{name}.{i}" for i in range(LOG_ROTATIONS.get(name, 0), 0, -1)] + [name])
        chunks = [(n, contents[n]) for n in names if n in contents]
        combined = b"".join(content for _, content in chunks)
        offset = 0
        if name.endswith(".log"):
            # Prefer the active baseline. If only rotations existed, the newest
            # retained baseline is still an exact preceding-session boundary.
            baseline = next((baselines[n] for n in reversed(names) if baselines.get(n)), None)
            if baseline is not None:
                position = combined.rfind(baseline)
                handle_reset = False
                if position < 0 and name == "screensaver_handles.log" and handle_attribution:
                    new_sessions = [line for line in combined.splitlines()
                                    if re.search(rb'"event"\s*:\s*"session_start"', line)]
                    handle_reset = bool(new_sessions and new_sessions[0] not in baseline.splitlines())
                if position < 0 and not fresh and not handle_reset:
                    unavailable.append(f"current-run boundary unavailable for {name} (truncated/retention exceeded)")
                    continue
                if fresh and combined == baseline:
                    if FAULT_RE.search(baseline.decode("utf-8", errors="replace")):
                        unavailable.append(f"unchanged fault-bearing fresh log cannot establish current-run scope: {name}")
                        continue
                    # A successful fresh RUN can produce byte-identical main
                    # markers. A new QML session identity below proves restart.
                    offset = 0
                elif position >= 0:
                    offset = position + len(baseline)
                else:
                    # --fresh can fail to delete a stale rotation. Exact old
                    # chunks are not new evidence even under explicit reset.
                    old_chunks = {baselines[n] for n in names if baselines.get(n)}
                    chunks = [(n, content) for n, content in chunks if content not in old_chunks]
                    combined = b"".join(content for _, content in chunks)
        current[name] = combined[offset:].decode("utf-8", errors="replace")
        chunk_start = 0
        for artifact_name, content in chunks:
            skip = max(0, offset - chunk_start)
            chunk_start += len(content)
            if skip >= len(content):
                continue
            line_offset = content[:skip].count(b"\n")
            for line_number, raw_line in enumerate(content[skip:].decode("utf-8", errors="replace").splitlines(), 1):
                if FAULT_RE.search(raw_line):
                    faults.append({
                        "artifact": artifact_name,
                        "line": line_offset + line_number,
                        "text": raw_line.rstrip()[:500],
                    })
    main = current.get("screensaver.log", "")
    qml = current.get("screensaver_qml.log", "")
    starts = re.findall(r"event=session_start\b[^\n]*\bsession=([a-zA-Z0-9]+)", qml)
    ends = re.findall(r"event=session_end\b[^\n]*\bsession=([a-zA-Z0-9]+)", qml)
    old_qml = (baselines.get("screensaver_qml.log") or b"").decode("utf-8", errors="replace")
    old_sessions = re.findall(r"event=session_start\b[^\n]*\bsession=([a-zA-Z0-9]+)", old_qml)
    new_session = len(starts) == 1 and starts[0] not in old_sessions
    markers = {
        "run_started": "Starting screensaver in RUN mode" in main,
        "auto_exit_armed": "[AUTO_EXIT] Armed normal terminal shutdown" in main,
        "auto_exit_reached": "[AUTO_EXIT] Deadline reached" in main,
        "qml_session_started": new_session,
        "qml_session_ended": new_session and ends == starts,
    }
    unavailable.extend(f"missing current-run marker: {name}" for name, present in markers.items() if not present)
    return faults, {"markers": markers, "unavailable": unavailable}


def _source_attribution() -> dict[str, object]:
    """Read-only local provenance; no clean-revision inference from source paths."""
    result: dict[str, object] = {"repository": str(ROOT.resolve()), "captured": "before_launch",
                               "source_hash_extensions": [".py", ".qml", ".glsl", ".frag", ".vert", ".qrc", ".json"],
                               "unavailable": []}
    try:
        def git(*args: str) -> str:
            return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode("utf-8")
        result["revision"] = git("rev-parse", "HEAD").strip()
        result["status_porcelain"] = git("status", "--porcelain=v1", "-z")
        result["dirty"] = bool(result["status_porcelain"])
        paths = sorted(set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")) - {""})
        digest = hashlib.sha256()
        count = 0
        for relative in paths:
            if Path(relative).suffix.lower() not in result["source_hash_extensions"]:
                continue
            source = ROOT / relative
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(source.read_bytes()).digest() if source.is_file() else b"deleted")
            count += 1
        result["source_tree_sha256"] = digest.hexdigest()
        result["source_file_count"] = count
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        result["unavailable"].append(str(exc))
    return result


Runner = Callable[[Sequence[str], Path, Path, Path], int]


def _run_child(command: Sequence[str], cwd: Path, stdout_path: Path, stderr_path: Path) -> int:
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        completed = subprocess.run(
            list(command), cwd=str(cwd), stdout=stdout_file, stderr=stderr_file, check=False
        )
    return int(completed.returncode)


def run_matrix(
    cases: Sequence[RunCase],
    output_dir: Path,
    *,
    runner: Runner = _run_child,
    python_executable: str | None = None,
    log_dir: Path = LOG_DIR,
    matrix_path: Path | None = None,
) -> dict[str, object]:
    _validate_cases(cases)
    output_dir = output_dir.resolve()
    resolved_logs = log_dir.resolve()
    repository = ROOT.resolve()
    if output_dir == repository or output_dir == resolved_logs:
        raise MatrixError("output directory must be a new dedicated evidence directory")
    if output_dir.exists():
        raise MatrixError(f"output directory already exists: {output_dir}")
    safe_names = [_safe_name(case.name) for case in cases]
    if len(set(safe_names)) != len(safe_names):
        raise MatrixError("case names collide after artifact-directory normalization")
    output_dir.mkdir(parents=True, exist_ok=False)
    python = python_executable or sys.executable
    results: list[dict[str, object]] = []
    for index, case in enumerate(cases, 1):
        run_dir = output_dir / f"{index:03d}_{_safe_name(case.name)}"
        if run_dir.exists():
            raise MatrixError(f"run artifact directory already exists: {run_dir}")
        run_dir.mkdir(parents=True)
        source = ENTRYPOINTS[case.entrypoint].resolve()
        command = [python, str(source), *case.argv, "--exit-after", _format_duration(case.exit_after_seconds)]
        stdout_path = run_dir / "stdout.bin"
        stderr_path = run_dir / "stderr.bin"
        log_baselines = _capture_log_baselines(resolved_logs)
        attribution = _source_attribution()
        source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        exit_code = runner(command, ROOT, stdout_path, stderr_path)
        artifacts = _copy_run_logs(run_dir, resolved_logs)
        artifacts.extend([
            {"name": "stdout.bin", "present": stdout_path.is_file(), "path": str(stdout_path.resolve())},
            {"name": "stderr.bin", "present": stderr_path.is_file(), "path": str(stderr_path.resolve())},
        ])
        faults, evidence = _scan_evidence(artifacts, log_baselines, fresh="--fresh" in case.argv,
                                         handle_attribution="--handle-attribution" in case.argv)
        evidence["unavailable"].extend(f"source attribution unavailable: {reason}"
                                      for reason in attribution["unavailable"])
        results.append({
            "name": case.name,
            "source": str(source),
            "source_sha256": source_sha256,
            "source_attribution": attribution,
            "argv": command,
            "exit_code": exit_code,
            "faults": faults,
            "evidence": evidence,
            "artifacts": artifacts,
            "stdout_path": str(stdout_path.resolve()),
            "stderr_path": str(stderr_path.resolve()),
            "status": ("failed" if exit_code != 0 or faults else
                       "unavailable" if evidence["unavailable"] else "passed"),
        })
    report: dict[str, object] = {
        "schema_version": 1,
        "matrix_path": str(matrix_path.resolve()) if matrix_path is not None else None,
        "sequential": True,
        "results": results,
        "status": ("failed" if any(r["status"] == "failed" for r in results) else
                   "unavailable" if any(r["status"] == "unavailable" for r in results) else "passed"),
    }
    report_path = output_dir / "run_matrix.json"
    report["report_path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _format_duration(seconds: float) -> str:
    seconds = float(seconds)
    return str(int(seconds)) if seconds.is_integer() else format(seconds, ".15g")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")[:50]
    return cleaned or "case"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True, help="JSON matrix file")
    parser.add_argument("--output-dir", type=Path, required=True, help="new dedicated evidence directory")
    args = parser.parse_args(argv)
    try:
        cases = load_matrix(args.matrix)
        report = run_matrix(cases, args.output_dir, matrix_path=args.matrix)
    except MatrixError as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

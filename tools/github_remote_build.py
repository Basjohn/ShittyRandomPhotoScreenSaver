"""GitHub Remote builds of the two Windows Nuitka products (Build Runner's GitHub Remote tab).

The Standard (+ Diagnostic) and Media Center builds run on GitHub-hosted Windows runners
(``.github/workflows/windows-build.yml``), each through its canonical worker (``scripts/venv/build_nuitka.ps1``,
``scripts/venv/build_nuitka_mc_onedir.ps1``) with every audit, contract and publication step it runs locally, on
exactly one pushed commit. This module owns the remote contract on both sides:

* on the runner, ``manifest`` records what was built: target, commit, version, run token, and the size and SHA-256
  of every published payload file and of the worker's reports;
* locally, it dispatches the runs through the GitHub CLI (one run per product, so they build in parallel), follows
  them, cancels the real runs on request, downloads each artifact into a staging directory, validates it against the
  manifest, the requested commit and its version, and only then replaces the published release directories. Any
  failure leaves the previous payload exactly where it was.

Nothing here compiles anything locally. Docs/Guides/GitHub_Remote_Build.md is the operator guide.

    python tools/github_remote_build.py run --target standard --target media_center
    python tools/github_remote_build.py manifest ...   (the workflow's own step)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_evidence import RUN_TOKEN, evidence_files, sha256_file, write_build_evidence  # noqa: E402

WORKFLOW_FILE = "windows-build.yml"
WORKFLOW_PATH = Path(".github") / "workflows" / WORKFLOW_FILE
MANIFEST_NAME = "remote_build_manifest.json"
MANIFEST_SCHEMA = 1
POLL_SECONDS = 15.0
RUN_APPEAR_SECONDS = 120.0
FAILED_LOG_LINES = 200
STAGING_DIR = Path("build") / "github_remote"

_SHA = re.compile(r"^[0-9a-f]{40}$")
_APP_VERSION = re.compile(r"""^APP_VERSION\s*(?::\s*str\s*)?=\s*["']([^"']+)["']""", re.MULTILINE)
_ISS_VERSION_LINE = re.compile(r"^(AppVersion|VersionInfoVersion)=.*$", re.MULTILINE)


@dataclass(frozen=True)
class RemoteTarget:
    """One remotely built product: the release directories its worker publishes and the files they must hold."""

    key: str
    payload_dirs: tuple[str, ...]
    primary: str
    companions: tuple[str, ...] = ()

    @property
    def artifact(self) -> str:
        return f"srpss-{self.key}"

    @property
    def artifacts(self) -> tuple[str, ...]:
        return (self.primary, *self.companions)


TARGETS: dict[str, RemoteTarget] = {
    # One compile publishes the screensaver and the same binary as the diagnostic flavour (core/build_profile.py).
    "standard": RemoteTarget(
        "standard", ("screensaver", "diagnostic"), "screensaver/SRPSS.scr", ("diagnostic/SRPSS_Diagnostic.scr",),
    ),
    "media_center": RemoteTarget("media_center", ("media_center",), "media_center/SRPSS_Media_Center.exe"),
}

# Repository inputs an installer reads beside the downloaded payload (scripts/*.iss ``Source:`` lines, the version
# stamp). A local installer is compiled only when these equal the built commit, so a remote payload is never
# packaged with other presets, themes, sounds, helper sources or version.
STANDARD_INSTALLER_INPUTS: tuple[str, ...] = (
    "scripts/SRPSS_Installer.iss", "scripts/reddit_helper_task_template.xml", "SRPSS.ico", "versioning.py",
    "presets/visualizer_modes", "themes", "resources/tutuogg.ogg", "resources/jedimodeyall.mp3",
    "ui/assets/installer",
)
MEDIA_CENTER_INSTALLER_INPUTS: tuple[str, ...] = (
    "scripts/SRPSS_MediaCenter_Installer.iss", "SRPSS.ico", "versioning.py", "ui/assets/installer",
)


class RemoteBuildError(RuntimeError):
    """A remote build, its retrieval or its validation failed; the published payload is untouched."""


class RemoteCancelled(RuntimeError):
    """The operator cancelled while a GitHub CLI call was running."""


def _no_window() -> dict:
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def cli_environment() -> dict[str, str]:
    # Non-interactive CLI use: never wait on a prompt that nobody can answer.
    return {**os.environ, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1", "GIT_TERMINAL_PROMPT": "0"}


# ------------------------------------------------------------------------------------------------- git and versions


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=cli_environment(), **_no_window(),
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        raise RemoteBuildError(f"git {' '.join(args)} failed: {detail[-1] if detail else completed.returncode}")
    return completed.stdout


def parse_app_version(text: str) -> str:
    match = _APP_VERSION.search(text)
    if match is None:
        raise RemoteBuildError("versioning.py names no APP_VERSION")
    return match.group(1)


def version_at_commit(repo_root: Path, sha: str) -> str:
    return parse_app_version(_git(repo_root, "show", f"{sha}:versioning.py"))


@dataclass(frozen=True)
class PushedCommit:
    """The one pushed commit a remote build compiles, fixed at pre-flight and re-checked at start."""

    branch: str
    sha: str
    subject: str
    local_head: str
    uncommitted: tuple[str, ...] = ()

    @property
    def short(self) -> str:
        return self.sha[:8]

    @property
    def matches_local_head(self) -> bool:
        return self.local_head == self.sha

    def describe(self) -> str:
        return f"origin/{self.branch} @ {self.short}: {self.subject}"


def resolve_pushed_commit(repo_root: Path = REPO_ROOT, branch: str | None = None, *, fetch: bool = True) -> PushedCommit:
    """The branch's commit on GitHub (after a fetch), with what differs locally."""

    branch = branch or _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if not branch or branch == "HEAD":
        raise RemoteBuildError("Detached HEAD: check out the branch whose pushed commit GitHub should build")
    if fetch:
        _git(repo_root, "fetch", "--quiet", "origin", branch)
    sha = _git(repo_root, "rev-parse", f"refs/remotes/origin/{branch}").strip()
    if not _SHA.match(sha):
        raise RemoteBuildError(f"origin/{branch} does not resolve to a commit")
    subject = _git(repo_root, "log", "-1", "--format=%s", sha).strip()
    head = _git(repo_root, "rev-parse", "HEAD").strip()
    uncommitted = tuple(line[3:] for line in _git(repo_root, "status", "--porcelain").splitlines() if len(line) > 3)
    return PushedCommit(branch, sha, subject, head, uncommitted)


def _iss_same_but_version(repo_root: Path, sha: str, relative: str) -> bool:
    """Build Runner stamps the installer scripts' version lines from versioning.py; that alone is no mismatch."""

    try:
        committed = _git(repo_root, "show", f"{sha}:{relative}")
        local = (repo_root / relative).read_text(encoding="utf-8")
    except (RemoteBuildError, OSError):
        return False

    def normal(text: str) -> str:
        return _ISS_VERSION_LINE.sub(r"\1=", text.replace("\r\n", "\n"))

    return normal(committed) == normal(local)


def installer_input_mismatches(repo_root: Path, sha: str, paths: Sequence[str]) -> tuple[str, ...]:
    """Repository inputs of an installer that differ in the working tree from the built commit (empty: they match)."""

    changed = [line for line in _git(repo_root, "diff", "--name-only", sha, "--", *paths).splitlines() if line]
    untracked = [
        line for line in _git(repo_root, "ls-files", "--others", "--exclude-standard", "--", *paths).splitlines()
        if line
    ]
    differing = {
        relative for relative in changed
        if not (relative.endswith(".iss") and _iss_same_but_version(repo_root, sha, relative))
    }
    return tuple(sorted(differing | set(untracked)))


# ----------------------------------------------------------------------------------------- manifest (runner side)


def _file_entry(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def build_manifest(
    root: Path, target_key: str, commit: str, token: str, *, run_id: str = "", run_attempt: str = "",
) -> dict[str, Any]:
    """What the runner built: every published payload file and the worker's reports, hashed."""

    target = TARGETS[target_key]
    if not _SHA.match(commit):
        raise RemoteBuildError(f"commit must be a full SHA, got {commit!r}")
    if not RUN_TOKEN.match(token):
        raise RemoteBuildError(f"token must be yyyyMMdd_HHmmss_ffffff, got {token!r}")
    head = _git(root, "rev-parse", "HEAD").strip()
    if head != commit:
        raise RemoteBuildError(f"built {head}, but {commit} was requested")
    files: dict[str, dict[str, Any]] = {}
    for directory in target.payload_dirs:
        base = root / "release" / directory
        if not base.is_dir():
            raise RemoteBuildError(f"the worker published no release/{directory}")
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = _file_entry(path)
    for relative in target.artifacts:
        if f"release/{relative}" not in files:
            raise RemoteBuildError(f"the worker published no release/{relative}")
    for name in evidence_files(target.key, token):
        report = root / "logs" / name
        if report.is_file():
            files[f"logs/{name}"] = _file_entry(report)
    return {
        "schema": MANIFEST_SCHEMA,
        "target": target.key,
        "commit": commit,
        "version": parse_app_version((root / "versioning.py").read_text(encoding="utf-8")),
        "token": token,
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "files": files,
    }


# ------------------------------------------------------------------------------------------- validation (local)


def pe_product_version(path: Path) -> str | None:
    """The fixed product version of a Windows executable ("a.b.c.d"), or None where it cannot be read."""

    if os.name != "nt":
        return None
    try:
        version = ctypes.WinDLL("version")
        size = version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return None
        pointer = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or not length.value:
            return None
        fixed = (ctypes.c_uint32 * 13).from_address(pointer.value)   # VS_FIXEDFILEINFO
        if fixed[0] != 0xFEEF04BD:
            return None
        product_ms, product_ls = fixed[4], fixed[5]
        return f"{product_ms >> 16}.{product_ms & 0xFFFF}.{product_ls >> 16}.{product_ls & 0xFFFF}"
    except (OSError, AttributeError, ValueError):
        return None


def _same_version(pe_version: str, app_version: str) -> bool:
    numbers = [int(part) for part in re.findall(r"\d+", app_version)][:4]
    return [int(part) for part in pe_version.split(".")] == numbers + [0] * (4 - len(numbers))


def _safe_relative(relative: str, target: RemoteTarget) -> None:
    parts = Path(relative).parts
    allowed = relative.startswith("logs/") or any(
        relative.startswith(f"release/{directory}/") for directory in target.payload_dirs
    )
    if not allowed or ".." in parts or Path(relative).is_absolute():
        raise RemoteBuildError(f"the manifest names a file outside the product: {relative}")


def validate_staging(staging: Path, target_key: str, *, commit: str, version: str, token: str) -> dict[str, Any]:
    """Refuse a downloaded artifact unless it is exactly the requested commit's build, whole and unaltered."""

    target = TARGETS[target_key]
    manifest_path = staging / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RemoteBuildError(f"the artifact has no readable {MANIFEST_NAME}: {exc}") from exc
    expected = {"schema": MANIFEST_SCHEMA, "target": target.key, "commit": commit, "version": version, "token": token}
    for name, value in expected.items():
        if manifest.get(name) != value:
            raise RemoteBuildError(f"manifest {name} is {manifest.get(name)!r}, expected {value!r}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise RemoteBuildError("the manifest lists no files")
    for relative, entry in files.items():
        _safe_relative(relative, target)
        path = staging / relative
        if not path.is_file():
            raise RemoteBuildError(f"missing from the download: {relative}")
        if path.stat().st_size != entry.get("bytes") or sha256_file(path) != entry.get("sha256"):
            raise RemoteBuildError(f"integrity check failed: {relative}")
    present = {
        path.relative_to(staging).as_posix()
        for directory in target.payload_dirs
        for path in (staging / "release" / directory).rglob("*") if path.is_file()
    }
    unlisted = sorted(present - set(files))
    if unlisted:
        raise RemoteBuildError(f"the download holds files the manifest does not list: {', '.join(unlisted[:5])}")
    for relative in target.artifacts:
        if f"release/{relative}" not in files:
            raise RemoteBuildError(f"the build did not publish release/{relative}")
    if target.companions:
        primary_hash = files[f"release/{target.primary}"]["sha256"]
        for companion in target.companions:
            if files[f"release/{companion}"]["sha256"] != primary_hash:
                raise RemoteBuildError(f"release/{companion} is not the same binary as release/{target.primary}")
    pe_version = pe_product_version(staging / "release" / target.primary)
    if pe_version is not None and not _same_version(pe_version, version):
        raise RemoteBuildError(f"{target.primary} carries product version {pe_version}, expected {version}")
    return manifest


# --------------------------------------------------------------------------------------------- publish (local)


def publish_payload(staging: Path, release_dir: Path, target_key: str) -> tuple[Path, ...]:
    """Swap the validated payload directories into ``release_dir``; on any failure restore the previous ones."""

    target = TARGETS[target_key]
    release_dir.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:8]
    steps: list[list[Any]] = []          # [final, staged, backup or None, placed]
    try:
        for directory in target.payload_dirs:
            final, staged = release_dir / directory, staging / "release" / directory
            backup = None
            if final.exists():
                backup = release_dir / f".remote_previous_{directory}_{tag}"
                final.rename(backup)
            step = [final, staged, backup, False]
            steps.append(step)
            shutil.move(str(staged), str(final))
            step[3] = True
    except OSError as exc:
        restore_errors = []
        for final, staged, backup, placed in reversed(steps):
            try:
                if placed:
                    shutil.move(str(final), str(staged))
                if backup is not None:
                    backup.rename(final)
            except OSError as restore_exc:
                restore_errors.append(f"{final}: {restore_exc}")
        note = f"; restoring failed for {', '.join(restore_errors)}" if restore_errors else "; the previous payload was kept"
        raise RemoteBuildError(f"could not replace the published payload ({exc}){note}") from exc
    for _final, _staged, backup, _placed in steps:
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    return tuple(release_dir / directory for directory in target.payload_dirs)


# ------------------------------------------------------------------------------------------------- GitHub CLI

Runner = Callable[[Sequence[str], "float | None"], subprocess.CompletedProcess]


def plain_runner(args: Sequence[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args), cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=cli_environment(), **_no_window(),
    )


@dataclass(frozen=True)
class RunState:
    status: str
    conclusion: str
    url: str
    step: str = ""

    @property
    def completed(self) -> bool:
        return self.status == "completed"


class GitHubCli:
    """The few ``gh`` calls a remote build needs. ``run`` executes them (Build Runner routes it through its
    cancellable process owner); ``cancel_runner`` stays usable after the operator's stop, to cancel the real runs."""

    def __init__(self, run: Runner = plain_runner, cancel_runner: Runner = plain_runner) -> None:
        self._run = run
        self._cancel_runner = cancel_runner

    def _call(self, *args: str, timeout: float | None = 120.0) -> str:
        completed = self._run(["gh", *args], timeout)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise RemoteBuildError(f"gh {' '.join(args[:2])} failed: {detail[-1] if detail else completed.returncode}")
        return completed.stdout or ""

    def signed_in(self) -> bool:
        return self._run(["gh", "auth", "status"], 30.0).returncode == 0

    def workflow_registered(self) -> bool:
        """GitHub dispatches a workflow only once its file is on the default branch."""
        return self._run(["gh", "workflow", "view", WORKFLOW_FILE], 60.0).returncode == 0

    def actions_policy_problem(self) -> str | None:
        """Why the repository's Actions policy would refuse to start the workflow (None: it can start).

        The workflow uses GitHub's own actions (checkout, setup-python, cache, upload-artifact); a policy of local
        actions only makes every run end at once in ``startup_failure`` (seen 8 Nov 2026)."""
        try:
            policy = json.loads(self._call("api", "repos/{owner}/{repo}/actions/permissions", timeout=60.0) or "{}")
        except (RemoteBuildError, ValueError):
            return None                     # unreadable: let the run itself report what GitHub says
        if not policy.get("enabled", True):
            return "GitHub Actions is disabled for this repository"
        allowed = policy.get("allowed_actions")
        if allowed == "selected":
            try:
                selected = json.loads(self._call(
                    "api", "repos/{owner}/{repo}/actions/permissions/selected-actions", timeout=60.0) or "{}")
            except (RemoteBuildError, ValueError):
                return None
            if selected.get("github_owned_allowed"):
                return None
        elif allowed != "local_only":
            return None
        return ("the repository allows only its own actions; enable 'Allow actions created by GitHub' "
                "(Settings > Actions > General)")

    def startup_failure(self, since: datetime, sha: str) -> str | None:
        """The URL of a run of this workflow that GitHub refused to start after ``since`` (its custom name is never
        applied, so the request id cannot find it)."""
        listed = json.loads(self._call(
            "run", "list", "--workflow", WORKFLOW_FILE, "--event", "workflow_dispatch", "--limit", "30",
            "--json", "conclusion,createdAt,headSha,url",
        ) or "[]")
        for run in listed:
            created = str(run.get("createdAt", "")).replace("Z", "+00:00")
            try:
                when = datetime.fromisoformat(created)
            except ValueError:
                continue
            if run.get("conclusion") == "startup_failure" and run.get("headSha") == sha and when >= since:
                return str(run.get("url", ""))
        return None

    def dispatch(self, target_key: str, branch: str, sha: str, token: str) -> None:
        self._call("workflow", "run", WORKFLOW_FILE, "--ref", branch,
                   "-f", f"target={target_key}", "-f", f"commit={sha}", "-f", f"token={token}")

    def find_run(self, request_id: str, *, after_stop: bool = False) -> tuple[int, str] | None:
        args = ["gh", "run", "list", "--workflow", WORKFLOW_FILE, "--event", "workflow_dispatch", "--limit", "30",
                "--json", "databaseId,displayTitle,url"]
        if after_stop:      # the operator stopped: look it up anyway, so the run can be cancelled on GitHub
            try:
                completed = self._cancel_runner(args, 60.0)
            except (OSError, subprocess.SubprocessError):
                return None
            if completed.returncode:
                return None
            output = completed.stdout
        else:
            output = self._call(*args[1:])
        listed = json.loads(output or "[]")
        for run in listed:
            if request_id in str(run.get("displayTitle", "")):
                return int(run["databaseId"]), str(run.get("url", ""))
        return None

    def run_state(self, run_id: int) -> RunState:
        data = json.loads(self._call("run", "view", str(run_id), "--json", "status,conclusion,url,jobs") or "{}")
        step = ""
        for job in data.get("jobs") or ():
            for candidate in job.get("steps") or ():
                if candidate.get("status") == "in_progress":
                    step = str(candidate.get("name", ""))
        return RunState(str(data.get("status", "")), str(data.get("conclusion") or ""), str(data.get("url", "")), step)

    def cancel(self, run_id: int) -> bool:
        try:
            return self._cancel_runner(["gh", "run", "cancel", str(run_id)], 60.0).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def download(self, run_id: int, artifact: str, destination: Path) -> None:
        self._call("run", "download", str(run_id), "--name", artifact, "--dir", str(destination), timeout=None)

    def failed_log(self, run_id: int) -> str:
        completed = self._run(["gh", "run", "view", str(run_id), "--log-failed"], 120.0)
        lines = (completed.stdout or completed.stderr or "").splitlines()
        return "\n".join(lines[-FAILED_LOG_LINES:])


# ------------------------------------------------------------------------------------------------ orchestration


@dataclass(frozen=True)
class RemoteResult:
    """One remote product's outcome, shaped like Build Runner's JobResult."""

    key: str
    returncode: int
    detail: str
    log_path: Path
    output_path: Path
    aborted: bool = False
    evidence_path: Path | None = None
    run_url: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class _RunLog:
    def __init__(self, path: Path, header: str) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header, encoding="utf-8")

    def write(self, line: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {line}\n")


Emit = Callable[[str, str, object], None]      # (kind, product key, payload): "status" text, "link" url, "done"


def run_remote_builds(
    repo_root: Path,
    cli: GitHubCli,
    keys: Sequence[str],
    commit: PushedCommit,
    token: str,
    *,
    log_dir: Path,
    release_dir: Path,
    cancelled: Callable[[], bool],
    emit: Emit,
    between: Callable[[], None] | None = None,
    poll_seconds: float = POLL_SECONDS,
    appear_seconds: float = RUN_APPEAR_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, RemoteResult]:
    """Dispatch every selected product at once, follow the runs, then retrieve, validate and publish each success.

    ``between`` runs local work (the Reddit Helper) while GitHub builds. ``cancelled`` is polled throughout; once it
    is set, every run still active on GitHub is cancelled there, not merely abandoned.
    """

    if not RUN_TOKEN.match(token):
        raise RemoteBuildError(f"token must be yyyyMMdd_HHmmss_ffffff, got {token!r}")
    results: dict[str, RemoteResult] = {}
    logs: dict[str, _RunLog] = {}
    for key in keys:
        target = TARGETS[key]
        logs[key] = _RunLog(
            log_dir / f"build_runner_{key}_{token}.log",
            f"SRPSS Build Runner · GitHub Remote\nProduct: {key}\nCommit: {commit.describe()}\nRun token: {token}\n"
            f"Workflow: {WORKFLOW_PATH.as_posix()} (artifact {target.artifact})\n{'=' * 72}\n",
        )

    def finish(key: str, returncode: int, detail: str, *, aborted: bool = False, url: str | None = None) -> None:
        target = TARGETS[key]
        logs[key].write(f"Result: {detail} (exit {returncode})")
        evidence = None
        if returncode == 0:
            # Only a published build has an evidence bundle: after a failure the release tree still holds the
            # previous payload, whose identity must not be filed under this run (its log has the failure).
            try:
                evidence = write_build_evidence(
                    log_dir, key, token, logs[key].path, release_dir / target.primary, returncode,
                    companions=tuple(release_dir / companion for companion in target.companions),
                )
            except (OSError, ValueError) as exc:
                detail += f"; evidence ZIP failed: {exc}"
        results[key] = RemoteResult(key, returncode, detail, logs[key].path, release_dir / target.payload_dirs[0],
                                    aborted=aborted, evidence_path=evidence, run_url=url)
        emit("done", key, results[key])

    try:
        current = resolve_pushed_commit(repo_root, commit.branch)
    except RemoteBuildError as exc:
        for key in keys:
            finish(key, 1, f"Could not re-check origin/{commit.branch}: {exc}")
        return results
    if current.sha != commit.sha:
        for key in keys:
            finish(key, 1, f"origin/{commit.branch} moved since pre-flight ({commit.short} -> {current.short}); "
                           "re-run pre-flight to build the new commit")
        return results
    try:
        version = version_at_commit(repo_root, commit.sha)
    except RemoteBuildError as exc:
        for key in keys:
            finish(key, 1, f"Could not read the built commit's version: {exc}")
        return results

    runs: dict[str, tuple[int, str]] = {}
    pending: list[str] = []
    dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    for key in keys:
        if cancelled():
            finish(key, 130, "Aborted by operator before dispatch", aborted=True)
            continue
        emit("status", key, "Dispatching")
        try:
            cli.dispatch(key, commit.branch, commit.sha, token)
            logs[key].write(f"Dispatched {WORKFLOW_FILE} on {commit.branch} for {commit.sha} ({version})")
            pending.append(key)
        except (RemoteBuildError, RemoteCancelled) as exc:
            finish(key, 1, f"Dispatch failed: {exc}", aborted=isinstance(exc, RemoteCancelled))

    deadline = clock() + appear_seconds
    while pending and len(runs) < len(pending) and not cancelled() and clock() < deadline:
        for key in pending:
            if key in runs:
                continue
            try:
                found = cli.find_run(f"{key}-{token}")
            except (RemoteBuildError, RemoteCancelled) as exc:
                logs[key].write(f"Run lookup failed: {exc}")
                found = None
            if found is not None:
                runs[key] = found
                logs[key].write(f"GitHub run {found[0]}: {found[1]}")
                emit("link", key, found[1])
                emit("status", key, "Queued")
        if len(runs) < len(pending):
            try:
                refused = cli.startup_failure(dispatched_at, commit.sha)
            except (RemoteBuildError, RemoteCancelled, ValueError):
                refused = None
            if refused:
                for key in [key for key in pending if key not in runs]:
                    pending.remove(key)
                    finish(key, 1, f"GitHub could not start the workflow (startup failure: repository Actions "
                                   f"policy or workflow file): {refused}", url=refused)
                continue
            _wait(4.0, cancelled, sleep)
    for key in [key for key in pending if key not in runs]:
        if cancelled():
            found = cli.find_run(f"{key}-{token}", after_stop=True)
            if found is not None:
                runs[key] = found          # cancelled on GitHub below, with the runs already being followed
                continue
            pending.remove(key)
            finish(key, 130, "Aborted by operator; its run was not found to cancel (check the Actions tab)",
                   aborted=True)
        else:
            pending.remove(key)
            finish(key, 1, "The dispatched run did not appear on GitHub; check the Actions tab")

    if between is not None and pending and not cancelled():
        between()

    while pending and not cancelled():
        for key in list(pending):
            run_id, url = runs[key]
            try:
                state = cli.run_state(run_id)
            except RemoteCancelled:
                break
            except RemoteBuildError as exc:
                logs[key].write(f"Status check failed (will retry): {exc}")
                continue
            if not state.completed:
                emit("status", key, _status_text(state))
                continue
            pending.remove(key)
            logs[key].write(f"Run {run_id} completed: {state.conclusion}")
            if state.conclusion != "success":
                failure = cli.failed_log(run_id)
                if failure:
                    logs[key].write("Failed steps (tail):\n" + failure)
                finish(key, 1, f"GitHub run {state.conclusion or 'failed'}: {url}", url=url)
                continue
            _retrieve(repo_root, cli, key, run_id, url, commit, version, token, log_dir, release_dir,
                      logs[key], emit, finish)
        if pending and not cancelled():
            _wait(poll_seconds, cancelled, sleep)

    for key in list(pending):
        run_id, url = runs[key]
        cancelled_there = cli.cancel(run_id)
        logs[key].write(f"Operator stop: GitHub run {run_id} {'cancelled' if cancelled_there else 'cancel FAILED'}")
        finish(key, 130, "Aborted by operator; GitHub run cancelled" if cancelled_there
               else f"Aborted locally, but cancelling the GitHub run failed: {url}", aborted=True, url=url)
    return results


def _status_text(state: RunState) -> str:
    if state.status in ("queued", "waiting", "requested", "pending"):
        return "Queued"
    return "Building" if not state.step else f"Building · {state.step}"[:40]


def _wait(seconds: float, cancelled: Callable[[], bool], sleep: Callable[[float], None]) -> None:
    remaining = seconds
    while remaining > 0 and not cancelled():
        step = min(0.5, remaining)
        sleep(step)
        remaining -= step


def _retrieve(repo_root, cli, key, run_id, url, commit, version, token, log_dir, release_dir, log, emit, finish) -> None:
    target = TARGETS[key]
    staging = repo_root / STAGING_DIR / token / key
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        emit("status", key, "Downloading")
        cli.download(run_id, target.artifact, staging)
        log.write(f"Downloaded {target.artifact} to staging {staging}")
        emit("status", key, "Validating")
        manifest = validate_staging(staging, key, commit=commit.sha, version=version, token=token)
        log.write(f"Validated {len(manifest['files'])} files against the manifest (commit {commit.sha}, {version})")
        emit("status", key, "Publishing")
        published = publish_payload(staging, release_dir, key)
        for relative in manifest["files"]:
            if relative.startswith("logs/"):
                shutil.copy2(staging / relative, log_dir / Path(relative).name)
        log.write("Published " + ", ".join(str(path) for path in published))
    except RemoteCancelled:
        finish(key, 130, "Aborted by operator during retrieval; the previous payload was kept", aborted=True, url=url)
        return
    except (RemoteBuildError, OSError) as exc:
        finish(key, 1, f"Retrieval failed, previous payload kept: {exc}", url=url)
        return
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            staging.parent.rmdir()
        except OSError:
            pass
    finish(key, 0, f"Completed on GitHub · {commit.short} · {version}", url=url)


# ------------------------------------------------------------------------------------------------------- CLI


def _manifest_command(args: argparse.Namespace) -> int:
    manifest = build_manifest(
        REPO_ROOT, args.target, args.commit, args.token, run_id=args.run_id, run_attempt=args.run_attempt,
    )
    Path(args.out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[REMOTE-BUILD] Manifest: {len(manifest['files'])} files, {manifest['target']} {manifest['version']} "
          f"@ {manifest['commit']}")
    return 0


def _run_command(args: argparse.Namespace) -> int:
    cli = GitHubCli()
    if not cli.signed_in():
        print("[REMOTE-BUILD] GitHub CLI is not signed in: run `gh auth login`", file=sys.stderr)
        return 2
    problem = cli.actions_policy_problem()
    if problem:
        print(f"[REMOTE-BUILD] GitHub would refuse to start the workflow: {problem}", file=sys.stderr)
        return 2
    commit = resolve_pushed_commit(REPO_ROOT, args.branch)
    if not commit.matches_local_head:
        print(f"[REMOTE-BUILD] Note: local HEAD {commit.local_head[:8]} is not what GitHub builds.")
    print(f"[REMOTE-BUILD] Building {commit.describe()}")
    token = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    last: dict[str, str] = {}

    def emit(kind: str, key: str, payload: object) -> None:
        if kind == "done":
            print(f"[REMOTE-BUILD] {key}: {payload.detail}  (log {payload.log_path})", flush=True)
        elif last.get(key) != str(payload):
            last[key] = str(payload)
            print(f"[REMOTE-BUILD] {key}: {payload}", flush=True)

    stop = {"requested": False}

    def interrupted(*_args: object) -> None:
        # Ctrl+C stops following and cancels the runs on GitHub (the loop sees it within half a second).
        stop["requested"] = True
        print("[REMOTE-BUILD] Stop requested: cancelling the GitHub runs...", file=sys.stderr)

    signal.signal(signal.SIGINT, interrupted)
    results = run_remote_builds(
        REPO_ROOT, cli, tuple(dict.fromkeys(args.target)), commit, token,
        log_dir=REPO_ROOT / "logs", release_dir=REPO_ROOT / "release",
        cancelled=lambda: stop["requested"], emit=emit,
    )
    return 0 if results and all(result.ok for result in results.values()) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="(workflow step) record what the runner built")
    manifest.add_argument("--target", choices=sorted(TARGETS), required=True)
    manifest.add_argument("--commit", required=True)
    manifest.add_argument("--token", required=True)
    manifest.add_argument("--run-id", default="")
    manifest.add_argument("--run-attempt", default="")
    manifest.add_argument("--out", required=True)
    run = sub.add_parser("run", help="build products on GitHub and publish them into release/")
    run.add_argument("--target", choices=sorted(TARGETS), action="append", required=True)
    run.add_argument("--branch", default=None)
    args = parser.parse_args(argv)
    try:
        return _manifest_command(args) if args.command == "manifest" else _run_command(args)
    except RemoteBuildError as exc:
        print(f"[REMOTE-BUILD] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

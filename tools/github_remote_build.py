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

The native modules are targets of the same contract, both compiled by one workflow
(``.github/workflows/native-module.yml``, whose ``source`` input names the folder): ``native_module`` is the product's
native core (``native/core``, ``_srpss_native_core``; Current_Plan.md item 8b, N2.1) and ``native_spike`` the P1 harness
(``native/spike_p1``, ``_srpss_native_spike``). ``stage-native`` places a module and one baked shader per shader
source under ``release/<target>`` on the runner, its manifest also records the source, Qt, PySide6 and MSVC it was
built with, and locally it is validated against the built commit's pinned Qt (``tools/native_sdk_fetch.py``) and
shader sources and published into ``release/<target>`` with that manifest beside it. A module is built only when the
local HEAD is the pushed commit.

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
from tools.native_sdk_fetch import SdkFetchError, pinned_qt_version, qt_version_from_requirements  # noqa: E402

WORKFLOW_FILE = "windows-build.yml"
WORKFLOW_PATH = Path(".github") / "workflows" / WORKFLOW_FILE
# The native modules (Current_Plan.md item 8b, N0.9 and N2.1): compiled by one reusable workflow, published like a
# product. The workflow's ``source`` input names the folder; its default is the product's native core.
NATIVE_WORKFLOW_FILE = "native-module.yml"
NATIVE_WORKFLOW_PATH = Path(".github") / "workflows" / NATIVE_WORKFLOW_FILE
# The runner's reports per module target (``{key}`` the target, ``{token}`` the run token).
NATIVE_BUILD_LOG = "{key}_build_{{token}}.log"
NATIVE_IMPORT_REPORT = "{key}_import_{{token}}.json"
# A native source's shaders: every file of these kinds in ``<source>/shaders/`` is baked to ``<file>.qsb``.
SHADER_SUFFIXES = (".vert", ".frag", ".comp")
MANIFEST_NAME = "remote_build_manifest.json"
MANIFEST_SCHEMA = 1
POLL_SECONDS = 15.0
RUN_APPEAR_SECONDS = 120.0
FAILED_LOG_LINES = 200
STAGING_DIR = Path("build") / "github_remote"
# The worker's reports in the manifest and the artifact: checkout-relative ``logs/<report>`` keys (the workflow
# uploads ``logs/``). Locally they are copied into the application's log folder (``log_dir``).
REPORTS_DIR = "logs"
REPORTS_PREFIX = f"{REPORTS_DIR}/"

_SHA = re.compile(r"^[0-9a-f]{40}$")
_APP_VERSION = re.compile(r"""^APP_VERSION\s*(?::\s*str\s*)?=\s*["']([^"']+)["']""", re.MULTILINE)


@dataclass(frozen=True)
class RemoteTarget:
    """One remotely built product: the release directories its worker publishes and the files they must hold."""

    key: str
    payload_dirs: tuple[str, ...]
    primary: str
    companions: tuple[str, ...] = ()
    workflow: str = WORKFLOW_FILE
    # A native module: compiled against PySide6's exact Qt (requirements.txt's pin at the built commit), which its
    # manifest records with the PySide6 and MSVC versions.
    module: bool = False
    # Report names (``{token}`` filled in) the runner must upload beside the payload, beyond build_evidence's.
    reports: tuple[str, ...] = ()
    # A native module's source folder in the repository (the native workflow's ``source`` input).
    source: str = ""

    @property
    def artifact(self) -> str:
        return f"srpss-{self.key}"

    @property
    def artifacts(self) -> tuple[str, ...]:
        return (self.primary, *self.companions)

    @property
    def module_name(self) -> str:
        """A native module's import name (the ``.pyd``'s stem)."""
        return Path(self.primary).stem

    @property
    def import_report(self) -> str:
        return NATIVE_IMPORT_REPORT.format(key=self.key)

    @property
    def build_log(self) -> str:
        return NATIVE_BUILD_LOG.format(key=self.key)

    def report_names(self, token: str) -> tuple[str, ...]:
        return (*evidence_files(self.key, token), *(name.format(token=token) for name in self.reports))

    def dispatch_inputs(self, sha: str, token: str) -> tuple[str, ...]:
        """The workflow inputs: the product workflow also takes the product (one workflow, two targets), the native
        workflow the source folder (one workflow, every native module)."""
        inputs = (f"commit={sha}", f"token={token}")
        if self.workflow == WORKFLOW_FILE:
            return (f"target={self.key}", *inputs)
        return (*inputs, f"source={self.source}") if self.module else inputs


def _module_target(key: str, payload: str, module: str, source: str) -> RemoteTarget:
    return RemoteTarget(
        key, (payload,), f"{payload}/{module}.pyd", workflow=NATIVE_WORKFLOW_FILE, module=True, source=source,
        reports=(NATIVE_BUILD_LOG.format(key=key), NATIVE_IMPORT_REPORT.format(key=key)),
    )


TARGETS: dict[str, RemoteTarget] = {
    # One compile publishes the screensaver and the same binary as the diagnostic flavour (core/build_profile.py).
    "standard": RemoteTarget(
        "standard", ("screensaver", "diagnostic"), "screensaver/SRPSS.scr", ("diagnostic/SRPSS_Diagnostic.scr",),
    ),
    "media_center": RemoteTarget("media_center", ("media_center",), "media_center/SRPSS_Media_Center.exe"),
}
# Native modules, both built by the one native workflow and published into ``release/<payload dir>`` like a product,
# never selected by default. ``native_module`` is the product's native core (D5.7; the workflow's default source);
# ``native_spike`` the P1 harness, which never ships.
MODULE_TARGETS: dict[str, RemoteTarget] = {
    "native_module": _module_target("native_module", "native_module", "_srpss_native_core", "native/core"),
    "native_spike": _module_target("native_spike", "native_spike", "_srpss_native_spike", "native/spike_p1"),
}
DEFAULT_NATIVE_TARGET = "native_module"
ALL_TARGETS: dict[str, RemoteTarget] = {**TARGETS, **MODULE_TARGETS}
SHADERS_DIR = "shaders"

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


def qt_version_at_commit(repo_root: Path, sha: str) -> str:
    """The Qt a commit's native module must be built against: its requirements.txt's PySide6 pin."""
    try:
        return qt_version_from_requirements(_git(repo_root, "show", f"{sha}:requirements.txt"))
    except SdkFetchError as exc:
        raise RemoteBuildError(str(exc)) from exc


def module_target_for_source(source: str) -> RemoteTarget:
    """The module target the native workflow builds from ``source`` (refused when no target has that folder)."""
    normalized = source.replace("\\", "/").strip("/")
    for target in MODULE_TARGETS.values():
        if target.source == normalized:
            return target
    known = ", ".join(target.source for target in MODULE_TARGETS.values())
    raise RemoteBuildError(f"no native module is built from {source!r} (the sources are {known})")


def expected_shaders(names: Sequence[str]) -> tuple[str, ...]:
    """The baked shaders a native source must produce: ``<file>.qsb`` for every shader source file in its
    ``shaders/`` folder (``.vert``, ``.frag``, ``.comp``)."""
    return tuple(sorted(f"{name}.qsb" for name in (Path(item).name for item in names)
                        if Path(name).suffix in SHADER_SUFFIXES and not name.startswith(".")))


def shaders_at_commit(repo_root: Path, sha: str, source: str) -> tuple[str, ...]:
    """``expected_shaders`` of ``source`` as the commit ``sha`` has it (not the working tree)."""
    listed = _git(repo_root, "ls-tree", "--name-only", sha, f"{source}/shaders/").splitlines()
    return expected_shaders(listed)


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


# ----------------------------------------------------------------------------------------- manifest (runner side)


def _file_entry(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def msvc_version(msc_full_ver: object) -> str:
    """``_MSC_FULL_VER`` (194435227) as cl prints it (19.44.35227)."""
    value = int(msc_full_ver)          # type: ignore[call-overload]
    if value < 10_000_000:
        raise RemoteBuildError(f"not an _MSC_FULL_VER: {msc_full_ver!r}")
    return f"{value // 10_000_000}.{value // 100_000 % 100}.{value % 100_000}"


def stage_native_module(root: Path, build_dir: Path, target_key: str = DEFAULT_NATIVE_TARGET) -> tuple[Path, ...]:
    """(Runner) Place the compiled module and its baked shaders where the target publishes them:
    ``release/<payload dir>/<module>.pyd`` and ``release/<payload dir>/shaders/<file>.qsb``, one per shader source
    in ``<source>/shaders/``. A build without its module, or without a shader its source has, stages nothing."""

    target = MODULE_TARGETS[target_key]
    module = build_dir / Path(target.primary).name
    if not module.is_file():
        raise RemoteBuildError(f"the build produced no {module.name} in {build_dir}")
    sources = root / target.source / "shaders"
    expected = expected_shaders([path.name for path in sources.iterdir()] if sources.is_dir() else [])
    shaders = [build_dir / "generated" / name for name in expected]
    missing = [path.name for path in shaders if not path.is_file()]
    if missing:
        raise RemoteBuildError(f"the build baked no {', '.join(missing)} in {build_dir / 'generated'}")
    payload = root / "release" / target.payload_dirs[0]
    shutil.rmtree(payload, ignore_errors=True)
    (payload / SHADERS_DIR).mkdir(parents=True)
    placed = [Path(shutil.copy2(module, payload / module.name))]
    placed += [Path(shutil.copy2(shader, payload / SHADERS_DIR / shader.name)) for shader in shaders]
    return tuple(placed)


def _module_fields(root: Path, target: RemoteTarget, token: str, pyside6_version: str | None) -> dict[str, Any]:
    """(Runner) What a module was built against, from the import check the runner ran on it."""

    report_path = root / REPORTS_DIR / target.import_report.format(token=token)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RemoteBuildError(f"no readable import check {report_path.name}: {exc}") from exc
    if not report.get("ok"):
        raise RemoteBuildError(f"the module failed its import check: {report.get('checks')}")
    try:
        pinned = pinned_qt_version(root / "requirements.txt")        # the checkout is the built commit
    except SdkFetchError as exc:
        raise RemoteBuildError(str(exc)) from exc
    runtime = report.get("runtime_info") or {}
    compiled, running = runtime.get("qt_compiled"), runtime.get("qt_runtime")
    if compiled != pinned or running != pinned:
        raise RemoteBuildError(f"the module was built for Qt {compiled} and runs on {running}; "
                               f"requirements.txt pins Qt {pinned}")
    if pyside6_version is None:
        from importlib.metadata import version as distribution_version

        pyside6_version = distribution_version("PySide6")
    return {
        "native_source": target.source,
        "qt_version": compiled,
        "pyside6_version": pyside6_version,
        "msvc_version": msvc_version(runtime.get("msc_full_ver")),
        "with_quick": bool(runtime.get("with_quick")),
    }


def build_manifest(
    root: Path, target_key: str, commit: str, token: str, *, run_id: str = "", run_attempt: str = "",
    pyside6_version: str | None = None,
) -> dict[str, Any]:
    """What the runner built: every published payload file and the worker's reports, hashed (a module's manifest
    also records the Qt, PySide6 and MSVC it was built with)."""

    target = ALL_TARGETS[target_key]
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
    for name in target.report_names(token):
        report = root / REPORTS_DIR / name
        if report.is_file():
            files[REPORTS_PREFIX + name] = _file_entry(report)
        elif target.module:
            raise RemoteBuildError(f"the runner wrote no {REPORTS_PREFIX}{name}")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "target": target.key,
        "commit": commit,
        "version": parse_app_version((root / "versioning.py").read_text(encoding="utf-8")),
        "token": token,
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "files": files,
    }
    if target.module:
        manifest.update(_module_fields(root, target, token, pyside6_version))
    return manifest


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
    allowed = relative.startswith(REPORTS_PREFIX) or any(
        relative.startswith(f"release/{directory}/") for directory in target.payload_dirs
    )
    if not allowed or ".." in parts or Path(relative).is_absolute():
        raise RemoteBuildError(f"the manifest names a file outside the product: {relative}")


def validate_staging(
    staging: Path, target_key: str, *, commit: str, version: str, token: str, qt_version: str | None = None,
    shaders: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Refuse a downloaded artifact unless it is exactly the requested commit's build, whole and unaltered (and, for
    a native module, built from its source against ``qt_version``, the commit's pinned Qt, and the PySide6 that ships
    it, with exactly ``shaders``, the baked shaders the commit's shader sources make)."""

    target = ALL_TARGETS[target_key]
    if target.module and not qt_version:
        raise RemoteBuildError(f"{target.key} is validated against the built commit's pinned Qt; none was given")
    if target.module and shaders is None:
        raise RemoteBuildError(f"{target.key} is validated against the built commit's shader sources; none were given")
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
    if target.module:
        _validate_module(manifest, target, str(qt_version), tuple(shaders or ()))
    pe_version = pe_product_version(staging / "release" / target.primary)
    if pe_version is not None and not _same_version(pe_version, version):
        raise RemoteBuildError(f"{target.primary} carries product version {pe_version}, expected {version}")
    return manifest


def _validate_module(manifest: dict[str, Any], target: RemoteTarget, qt_version: str, shaders: tuple[str, ...]) -> None:
    """A module binds to PySide6's own Qt DLLs and refuses any other Qt: built against anything but the pinned Qt
    (and the PySide6 release that ships it) it would never load. It carries one baked shader per shader source."""

    if manifest.get("native_source") != target.source:
        raise RemoteBuildError(f"manifest native_source is {manifest.get('native_source')!r}, expected "
                               f"{target.source!r}")
    if manifest.get("qt_version") != qt_version:
        raise RemoteBuildError(f"manifest qt_version is {manifest.get('qt_version')!r}, expected {qt_version!r}")
    pyside6 = str(manifest.get("pyside6_version") or "")
    if pyside6.split(".")[:3] != qt_version.split("."):
        raise RemoteBuildError(f"manifest pyside6_version is {pyside6!r}, expected PySide6 {qt_version}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("msvc_version") or "")):
        raise RemoteBuildError(f"manifest msvc_version is {manifest.get('msvc_version')!r}")
    folder = f"release/{target.payload_dirs[0]}/{SHADERS_DIR}/"
    published = tuple(sorted(name[len(folder):] for name in manifest["files"] if name.startswith(folder)))
    if published != tuple(sorted(shaders)):
        raise RemoteBuildError(f"the build published the shaders {list(published)} under {folder}; its shader "
                               f"sources make {sorted(shaders)}")


# --------------------------------------------------------------------------------------------- publish (local)


def publish_payload(staging: Path, release_dir: Path, target_key: str) -> tuple[Path, ...]:
    """Swap the validated payload directories into ``release_dir``; on any failure restore the previous ones."""

    target = ALL_TARGETS[target_key]
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

    def workflow_registered(self, workflow: str = WORKFLOW_FILE) -> bool:
        """GitHub dispatches a workflow only once its file is on the default branch."""
        return self._run(["gh", "workflow", "view", workflow], 60.0).returncode == 0

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

    def startup_failure(self, since: datetime, sha: str, workflow: str = WORKFLOW_FILE) -> str | None:
        """The URL of a run of ``workflow`` that GitHub refused to start after ``since`` (its custom name is never
        applied, so the request id cannot find it)."""
        listed = json.loads(self._call(
            "run", "list", "--workflow", workflow, "--event", "workflow_dispatch", "--limit", "30",
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
        target = ALL_TARGETS[target_key]
        fields = [argument for value in target.dispatch_inputs(sha, token) for argument in ("-f", value)]
        self._call("workflow", "run", target.workflow, "--ref", branch, *fields)

    def find_run(self, request_id: str, *, after_stop: bool = False,
                 workflow: str = WORKFLOW_FILE) -> tuple[int, str] | None:
        args = ["gh", "run", "list", "--workflow", workflow, "--event", "workflow_dispatch", "--limit", "30",
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
        target = ALL_TARGETS[key]
        logs[key] = _RunLog(
            log_dir / f"build_runner_{key}_{token}.log",
            f"SRPSS Build Runner · GitHub Remote\nProduct: {key}\nCommit: {commit.describe()}\nRun token: {token}\n"
            f"Workflow: .github/workflows/{target.workflow} (artifact {target.artifact})\n{'=' * 72}\n",
        )

    def workflow(key: str) -> str:
        return ALL_TARGETS[key].workflow

    def finish(key: str, returncode: int, detail: str, *, aborted: bool = False, url: str | None = None) -> None:
        target = ALL_TARGETS[key]
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
        if ALL_TARGETS[key].module and not current.matches_local_head:
            # A module is built for the work it is tested with: never the pushed tip in place of a local commit.
            finish(key, 1, f"Local HEAD {current.local_head[:8]} is not origin/{current.branch} ({current.short}): "
                           "push it first; GitHub builds only pushed commits")
            continue
        emit("status", key, "Dispatching")
        try:
            cli.dispatch(key, commit.branch, commit.sha, token)
            logs[key].write(f"Dispatched {workflow(key)} on {commit.branch} for {commit.sha} ({version})")
            pending.append(key)
        except (RemoteBuildError, RemoteCancelled) as exc:
            finish(key, 1, f"Dispatch failed: {exc}", aborted=isinstance(exc, RemoteCancelled))

    deadline = clock() + appear_seconds
    while pending and len(runs) < len(pending) and not cancelled() and clock() < deadline:
        for key in pending:
            if key in runs:
                continue
            try:
                found = cli.find_run(f"{key}-{token}", workflow=workflow(key))
            except (RemoteBuildError, RemoteCancelled) as exc:
                logs[key].write(f"Run lookup failed: {exc}")
                found = None
            if found is not None:
                runs[key] = found
                logs[key].write(f"GitHub run {found[0]}: {found[1]}")
                emit("link", key, found[1])
                emit("status", key, "Queued")
        if len(runs) < len(pending):
            any_refused = False
            for name in dict.fromkeys(workflow(key) for key in pending if key not in runs):
                try:
                    refused = cli.startup_failure(dispatched_at, commit.sha, workflow=name)
                except (RemoteBuildError, RemoteCancelled, ValueError):
                    refused = None
                if refused:
                    any_refused = True
                    for key in [key for key in pending if key not in runs and workflow(key) == name]:
                        pending.remove(key)
                        finish(key, 1, f"GitHub could not start the workflow (startup failure: repository Actions "
                                       f"policy or workflow file): {refused}", url=refused)
            if any_refused:
                continue
            _wait(4.0, cancelled, sleep)
    for key in [key for key in pending if key not in runs]:
        if cancelled():
            found = cli.find_run(f"{key}-{token}", after_stop=True, workflow=workflow(key))
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
    target = ALL_TARGETS[key]
    staging = repo_root / STAGING_DIR / token / key
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        emit("status", key, "Downloading")
        cli.download(run_id, target.artifact, staging)
        log.write(f"Downloaded {target.artifact} to staging {staging}")
        emit("status", key, "Validating")
        qt_version = qt_version_at_commit(repo_root, commit.sha) if target.module else None
        shaders = shaders_at_commit(repo_root, commit.sha, target.source) if target.module else None
        manifest = validate_staging(staging, key, commit=commit.sha, version=version, token=token,
                                    qt_version=qt_version, shaders=shaders)
        log.write(f"Validated {len(manifest['files'])} files against the manifest (commit {commit.sha}, {version})")
        if target.module:
            # A module keeps its validated manifest beside it: what it was built from and against (Qt, MSVC).
            shutil.copy2(staging / MANIFEST_NAME, staging / "release" / target.payload_dirs[0] / MANIFEST_NAME)
            log.write(f"Built from {manifest['native_source']} against Qt {manifest['qt_version']}, PySide6 "
                      f"{manifest['pyside6_version']}, MSVC {manifest['msvc_version']}")
        emit("status", key, "Publishing")
        published = publish_payload(staging, release_dir, key)
        for relative in manifest["files"]:
            if relative.startswith(REPORTS_PREFIX):
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


def _stage_native_command(args: argparse.Namespace) -> int:
    placed = stage_native_module(REPO_ROOT, Path(args.build_dir).resolve(), args.target)
    print(f"[REMOTE-BUILD] Staged {len(placed)} files into release/{MODULE_TARGETS[args.target].payload_dirs[0]}")
    return 0


def _native_target_command(args: argparse.Namespace) -> int:
    print(module_target_for_source(args.source).key)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    manifest = sub.add_parser("manifest", help="(workflow step) record what the runner built")
    manifest.add_argument("--target", choices=sorted(ALL_TARGETS), required=True)
    manifest.add_argument("--commit", required=True)
    manifest.add_argument("--token", required=True)
    manifest.add_argument("--run-id", default="")
    manifest.add_argument("--run-attempt", default="")
    manifest.add_argument("--out", required=True)
    stage = sub.add_parser("stage-native", help="(workflow step) place a compiled module under release/")
    stage.add_argument("--target", choices=sorted(MODULE_TARGETS), default=DEFAULT_NATIVE_TARGET)
    stage.add_argument("--build-dir", required=True)
    native_target = sub.add_parser("native-target", help="(workflow step) print the module target a source builds")
    native_target.add_argument("--source", required=True)
    run = sub.add_parser("run", help="build products on GitHub and publish them into release/")
    run.add_argument("--target", choices=sorted(ALL_TARGETS), action="append", required=True)
    run.add_argument("--branch", default=None)
    args = parser.parse_args(argv)
    commands = {"manifest": _manifest_command, "stage-native": _stage_native_command,
                "native-target": _native_target_command, "run": _run_command}
    try:
        return commands[args.command](args)
    except RemoteBuildError as exc:
        print(f"[REMOTE-BUILD] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

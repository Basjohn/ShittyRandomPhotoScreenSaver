"""Core archive/Git engine for SRPSS GODZIP Foundry.

Stdlib-only by design.  The UI lives in ``godzip_foundry.py``; this module owns
all manifest, ZIP validation, Git ancestry, selective apply and /deleteme
semantics so those safety contracts remain testable without Qt.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence

FORMAT_NAME = "srpss-godzip"
FORMAT_VERSION = 1
MANIFEST_MEMBER = ".godzip/manifest.json"
MANIFEST_CANDIDATES = (
    MANIFEST_MEMBER,
    "godzip_manifest.json",
    ".godzip_manifest.json",
)
DEBRIS_MANIFEST_NAMES = (
    "godzip_debris.json",
    ".godzip_debris.json",
)
HEAVY_DEFAULT_PREFIXES = (
    "images/",
    "themes/",
    "golden/",
    "goldens/",
    "tests/golden/",
    "tests/goldens/",
    "tests/fixtures/",
    "tests/screenshots/",
)
FORBIDDEN_TARGET_PREFIXES = (".git/", ".godzip/", ".godzip_foundry/", "deleteme/")

RUN_ENTRYPOINTS = ("main.py", "main_mc.py")
RUN_DEFAULT_FLAGS = (
    "--debug",
    "--set",
    "--perf",
    "--usage",
    "--geo",
    "--life",
    "--viz",
    "--gpu-timing",
    "--cache",
    "--fresh",
)
RUN_FLAG_ALIASES = {
    "-d": "--debug",
    "-v": "--verbose",
    "--viz-diag": "--viz-diagnostics",
}
RUN_FLAG_DESCRIPTIONS = {
    "--debug": "Enable debug logging",
    "--verbose": "Enable full verbose log stream",
    "--perf": "Performance metrics/logging",
    "--gpu-timing": "Sampled owner-context GPU timing (implies --perf)",
    "--usage": "CPU/GPU/memory/thread usage telemetry",
    "--viz": "Visualizer diagnostics",
    "--geo": "Geometry/z-order/edit-layout diagnostics",
    "--set": "Settings mutation/import/schema diagnostics",
    "--life": "Widget/worker/engine lifecycle diagnostics",
    "--cache": "Image-cache/prefetch/cache-authority diagnostics",
    "--steam": "Steam widget-family diagnostics",
    "--noupdates": "Disable automatic Gmail/Reddit/Weather retrievals",
    "--viz-diagnostics": "Extra Spotify visualizer diagnostics",
    "--fresh": "Clear current logs before starting",
    "--devcurve": "Legacy compatibility no-op",
    "--devsteam": "Show unfinished Steam development cards",
    "--diag-pair-warm-finish": "Internal paired warm-finish diagnostics",
    "--diag-p4-stages": "Internal P4 stage diagnostics",
    "--diag-p4-no-perf-hud": "Internal P4 diagnostics without perf HUD",
}


class GodzipError(RuntimeError):
    """A user-facing GODZIP validation/apply failure."""


@dataclass(frozen=True, slots=True)
class RepoFile:
    path: str
    size: int
    status: str = ""
    default_selected: bool = True


@dataclass(frozen=True, slots=True)
class ArchiveFile:
    target_path: str
    member_name: str
    size: int
    sha256: str
    local_state: str
    local_dirty: bool
    default_selected: bool


@dataclass(frozen=True, slots=True)
class DebrisItem:
    path: str
    reason: str = ""
    exists: bool = False
    default_selected: bool = True


@dataclass(slots=True)
class ArchiveInspection:
    zip_path: Path
    manifest: dict | None
    manifest_member: str | None
    files: list[ArchiveFile] = field(default_factory=list)
    debris: list[DebrisItem] = field(default_factory=list)
    source_head: str = ""
    source_branch: str = ""
    dirty_worktree: bool = False
    relation: str = "unknown"
    relation_detail: str = "Archive baseline applicability cannot be proven."
    baseline_relation: str = "unknown"
    history_overlap_paths: list[str] = field(default_factory=list)
    legacy: bool = False
    legacy_common_prefix: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def has_manifest(self) -> bool:
        return self.manifest is not None

    @property
    def proven_older(self) -> bool:
        """Compatibility shim: baseline ancestry alone is no longer an apply blocker."""
        return False

    def selection_requires_history_ack(
        self,
        selected_targets: Sequence[str],
        selected_debris: Sequence[str] = (),
    ) -> bool:
        selected = {validate_repo_relpath(path).casefold() for path in selected_targets}
        selected.update(validate_debris_relpath(path).casefold() for path in selected_debris)
        if not selected:
            return False
        if self.baseline_relation in {"newer", "diverged"}:
            return True
        if self.baseline_relation != "older":
            return False
        overlap = {path.casefold() for path in self.history_overlap_paths}
        return bool(selected & overlap)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    replaced: int
    new_files: int
    unchanged_skipped: int
    debris_moved: int
    backup_dir: Path | None
    debris_dir: Path | None




@dataclass(frozen=True, slots=True)
class GodzipDiffResult:
    text: str
    changed_files: int
    added: int
    modified: int
    deleted: int
    binary: int
    baseline_head: str
    current_head: str
    baseline_dirty: bool
    current_dirty: bool

@dataclass(frozen=True, slots=True)
class GitChange:
    path: str
    status: str
    staged: bool = False
    unstaged: bool = False
    untracked: bool = False


@dataclass(frozen=True, slots=True)
class PullFile:
    path: str
    status: str
    old_path: str = ""
    local_dirty: bool = False

    @property
    def display_path(self) -> str:
        return f"{self.old_path} -> {self.path}" if self.old_path else self.path


@dataclass(slots=True)
class PullInspection:
    branch: str
    remote: str
    remote_ref: str
    local_head: str
    remote_head: str
    relation: str
    relation_detail: str
    files: list[PullFile] = field(default_factory=list)
    worktree_dirty: bool = False

    @property
    def fast_forward_possible(self) -> bool:
        return self.relation in {"same", "behind"}


@dataclass(frozen=True, slots=True)
class SelectiveSyncResult:
    written: int
    deleted: int
    backup_dir: Path | None


@dataclass(frozen=True, slots=True)
class LogzipResult:
    zip_path: Path
    files: tuple[str, ...]


def _hidden_subprocess_kwargs() -> dict[str, object]:
    """Hide internal console programs on Windows. RUN launches are handled separately."""
    if os.name != "nt":
        return {}
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    kwargs: dict[str, object] = {"creationflags": creationflags}
    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    if startupinfo_cls is not None:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            timeout=30,
            **_hidden_subprocess_kwargs(),
        )
    except FileNotFoundError as exc:
        raise GodzipError("git.exe is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GodzipError(f"Git command timed out: {' '.join(args)}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise GodzipError(detail or f"Git command failed: {' '.join(args)}") from exc


def _run_git_text(
    repo_root: Path,
    *args: str,
    check: bool = True,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_hidden_subprocess_kwargs(),
        )
    except FileNotFoundError as exc:
        raise GodzipError("git.exe is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GodzipError(f"Git command timed out: {' '.join(args)}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise GodzipError(detail or f"Git command failed: {' '.join(args)}") from exc


def discover_repo_root(start: Path) -> Path:
    start = start.expanduser().resolve()
    probe = start if start.is_dir() else start.parent
    result = _run_git(probe, "rev-parse", "--show-toplevel")
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        raise GodzipError(f"Not inside a Git worktree: {probe}")
    return Path(raw).resolve()


def git_head(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "HEAD").stdout.decode().strip()


def git_branch(repo_root: Path) -> str:
    result = _run_git(repo_root, "branch", "--show-current", check=False)
    return result.stdout.decode("utf-8", errors="replace").strip() or "DETACHED"


def git_dirty(repo_root: Path) -> bool:
    result = _run_git(repo_root, "status", "--porcelain", "--untracked-files=all")
    return bool(result.stdout.strip())


def _zlist(raw: bytes) -> list[str]:
    return [part.decode("utf-8", errors="surrogateescape") for part in raw.split(b"\0") if part]


def git_status_map(repo_root: Path) -> dict[str, str]:
    staged = set(_zlist(_run_git(repo_root, "diff", "--cached", "--name-only", "-z").stdout))
    modified = set(_zlist(_run_git(repo_root, "diff", "--name-only", "-z").stdout))
    untracked = set(_zlist(_run_git(repo_root, "ls-files", "--others", "--exclude-standard", "-z").stdout))
    result: dict[str, str] = {}
    for path in staged | modified | untracked:
        flags: list[str] = []
        if path in untracked:
            flags.append("NEW")
        if path in staged:
            flags.append("STAGED")
        if path in modified:
            flags.append("MODIFIED")
        result[path.replace("\\", "/")] = "+".join(flags)
    return result


def workflow_default_selected(path: str, status: str = "") -> bool:
    """Return the SRPSS workflow default for a Git-visible file.

    The transfer profile intentionally keeps all documentation and direct
    ``tests/*`` files because those are valuable handoff context, while
    excluding test fixture/subfolder payloads, themes, images and goldens.
    Gitignored files never reach this decision point.
    """
    lower = path.replace("\\", "/").lower().lstrip("./")
    if any(lower == prefix.rstrip("/") or lower.startswith(prefix) for prefix in HEAVY_DEFAULT_PREFIXES):
        return False
    if lower.startswith("tests/"):
        # Keep files directly inside /tests, but not any nested payload tree.
        return len(PurePosixPath(lower).parts) == 2
    # Docs are intentionally all-on, not changed-only.
    if lower.startswith("docs/"):
        return True
    return True


def collect_repo_files(repo_root: Path) -> list[RepoFile]:
    repo_root = repo_root.resolve()
    statuses = git_status_map(repo_root)
    raw = _run_git(repo_root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    files: list[RepoFile] = []
    seen: set[str] = set()
    for path in _zlist(raw):
        rel = path.replace("\\", "/")
        key = rel.casefold()
        if any(
            key == prefix.rstrip("/").casefold() or key.startswith(prefix.casefold())
            for prefix in FORBIDDEN_TARGET_PREFIXES
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        full = repo_root / Path(*PurePosixPath(rel).parts)
        if not full.is_file():
            continue
        try:
            size = full.stat().st_size
        except OSError:
            continue
        status = statuses.get(rel, "")
        files.append(
            RepoFile(
                path=rel,
                size=size,
                status=status,
                default_selected=workflow_default_selected(rel, status),
            )
        )
    files.sort(key=lambda item: item.path.casefold())
    return files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_member_sha256(archive: zipfile.ZipFile, member: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(member, "r") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_repo_relpath(raw: str, *, allow_metadata: bool = False) -> str:
    text = str(raw or "").replace("\\", "/").strip()
    if not text:
        raise GodzipError("Manifest contains an empty path")
    if text.startswith("/") or text.startswith("~") or ":" in text.split("/", 1)[0]:
        raise GodzipError(f"Absolute/drive path is forbidden: {raw!r}")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise GodzipError(f"Unsafe relative path: {raw!r}")
    normalized = pure.as_posix()
    lower = normalized.casefold()
    if not allow_metadata and any(lower == prefix.rstrip("/") or lower.startswith(prefix) for prefix in FORBIDDEN_TARGET_PREFIXES):
        raise GodzipError(f"Reserved path cannot be a repository target: {normalized}")
    return normalized

def validate_debris_relpath(raw: str) -> str:
    """Validate a reversible debris target, allowing stale .godzip metadata cleanup."""
    normalized = validate_repo_relpath(raw, allow_metadata=True)
    lower = normalized.casefold()
    forbidden = (".git/", ".git", ".godzip_foundry/", ".godzip_foundry", "deleteme/", "deleteme")
    if any(lower == item or lower.startswith(item) for item in forbidden):
        raise GodzipError(f"Reserved path cannot be moved as debris: {normalized}")
    return normalized


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _validate_archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    folded: set[str] = set()
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir():
            continue
        validate_repo_relpath(name, allow_metadata=True)
        if _is_zip_symlink(info):
            raise GodzipError(f"Symbolic links are not accepted in GODZIPs: {name}")
        key = name.casefold()
        if key in folded:
            raise GodzipError(f"Archive contains duplicate/case-colliding member: {name}")
        folded.add(key)
        members[name] = info
    return members


def _json_bytes(payload: Mapping) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8")


def suggested_godzip_name(repo_root: Path) -> str:
    short = git_head(repo_root)[:10]
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M")
    return f"GODZIP_{short}_{stamp}.zip"


def build_manifest(
    repo_root: Path,
    selected_paths: Sequence[str],
    *,
    debris_entries: Sequence[Mapping[str, str]] = (),
) -> dict:
    repo_root = repo_root.resolve()
    statuses = git_status_map(repo_root)
    records: list[dict] = []
    seen: set[str] = set()
    for raw in selected_paths:
        rel = validate_repo_relpath(raw)
        key = rel.casefold()
        if key in seen:
            continue
        seen.add(key)
        full = repo_root / Path(*PurePosixPath(rel).parts)
        if not full.is_file():
            raise GodzipError(f"Selected archive file does not exist: {rel}")
        records.append(
            {
                "path": rel,
                "action": "replace_file",
                "sha256": sha256_file(full),
                "size": full.stat().st_size,
                "source_status": statuses.get(rel, ""),
            }
        )
    records.sort(key=lambda item: item["path"].casefold())

    debris: list[dict] = []
    debris_seen: set[str] = set()
    for item in debris_entries:
        rel = validate_debris_relpath(str(item.get("path", "")))
        key = rel.casefold()
        if key in debris_seen:
            continue
        debris_seen.add(key)
        debris.append(
            {
                "path": rel,
                "action": "move_to_deleteme",
                "reason": str(item.get("reason", "") or ""),
            }
        )
    debris.sort(key=lambda item: item["path"].casefold())

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "generated_at_utc": now,
        "repo_name": repo_root.name,
        "source_head": git_head(repo_root),
        "source_branch": git_branch(repo_root),
        "dirty_worktree": git_dirty(repo_root),
        "archive_scope": "manifest_file_set",
        "omission_means_delete": False,
        "files": records,
        "debris": debris,
    }


def create_godzip(
    repo_root: Path,
    selected_paths: Sequence[str],
    output_path: Path,
    *,
    debris_entries: Sequence[Mapping[str, str]] = (),
    compresslevel: int = 6,
) -> dict:
    if not selected_paths and not debris_entries:
        raise GodzipError("Nothing is selected for this GODZIP")
    repo_root = repo_root.resolve()
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(repo_root, selected_paths, debris_entries=debris_entries)
    temp = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(
            temp,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=max(0, min(9, int(compresslevel))),
            allowZip64=True,
        ) as archive:
            for record in manifest["files"]:
                rel = record["path"]
                archive.write(repo_root / Path(*PurePosixPath(rel).parts), arcname=rel)
            archive.writestr(MANIFEST_MEMBER, _json_bytes(manifest))
        # Integrity test before publication.
        with zipfile.ZipFile(temp, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise GodzipError(f"Created archive failed CRC validation at {bad}")
        os.replace(temp, output_path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return manifest


def _git_commit_exists(repo_root: Path, sha: str) -> bool:
    if not sha:
        return False
    result = _run_git(repo_root, "cat-file", "-e", f"{sha}^{{commit}}", check=False)
    return result.returncode == 0


def compare_source_head(repo_root: Path, source_head: str) -> tuple[str, str]:
    """Compare baseline commits only; this does NOT decide whether archive bytes are stale."""
    source_head = str(source_head or "").strip()
    local_head = git_head(repo_root)
    if not source_head:
        return "unknown", "Archive has no baseline HEAD."
    if source_head == local_head:
        return "same", f"Archive baseline HEAD matches local HEAD ({local_head[:10]})."
    if not _git_commit_exists(repo_root, source_head):
        return "unknown", f"Archive baseline commit {source_head[:10]} is not known locally; ancestry cannot be proven."
    older = _run_git(repo_root, "merge-base", "--is-ancestor", source_head, local_head, check=False)
    if older.returncode == 0:
        return "older", f"Archive baseline {source_head[:10]} is an ancestor of local HEAD {local_head[:10]}."
    newer = _run_git(repo_root, "merge-base", "--is-ancestor", local_head, source_head, check=False)
    if newer.returncode == 0:
        return "newer", f"Archive baseline {source_head[:10]} is newer than local HEAD {local_head[:10]}."
    return "diverged", f"Archive baseline {source_head[:10]} and local HEAD {local_head[:10]} have diverged."


def _committed_changed_paths(repo_root: Path, base_head: str, local_head: str) -> set[str]:
    if not base_head or not local_head or base_head == local_head:
        return set()
    raw = _run_git(repo_root, "diff", "--name-only", "-z", f"{base_head}..{local_head}").stdout
    return {path.replace("\\", "/") for path in _zlist(raw)}


def _load_manifest_from_archive(
    archive: zipfile.ZipFile,
    members: Mapping[str, zipfile.ZipInfo],
) -> tuple[dict | None, str | None]:
    for name in MANIFEST_CANDIDATES:
        info = members.get(name)
        if info is None:
            continue
        try:
            payload = json.loads(archive.read(info).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise GodzipError(f"Invalid GODZIP manifest JSON: {name}") from exc
        if not isinstance(payload, dict):
            raise GodzipError("GODZIP manifest root must be a JSON object")
        return payload, name
    return None, None


def _validate_manifest_shape(manifest: Mapping) -> None:
    if manifest.get("format") != FORMAT_NAME:
        raise GodzipError(f"Unsupported manifest format: {manifest.get('format')!r}")
    try:
        version = int(manifest.get("version", 0))
    except (TypeError, ValueError) as exc:
        raise GodzipError("Manifest version is invalid") from exc
    if version != FORMAT_VERSION:
        raise GodzipError(f"Unsupported GODZIP manifest version {version}; expected {FORMAT_VERSION}")
    if manifest.get("omission_means_delete") is True:
        raise GodzipError("This tool refuses manifests where omission means deletion")
    files = manifest.get("files", [])
    debris = manifest.get("debris", [])
    if not isinstance(files, list) or not isinstance(debris, list):
        raise GodzipError("Manifest files/debris must be arrays")


def _common_top_folder(member_names: Sequence[str]) -> str:
    roots = {PurePosixPath(name).parts[0] for name in member_names if PurePosixPath(name).parts}
    if len(roots) != 1:
        return ""
    root = next(iter(roots))
    return root if any("/" in name for name in member_names) else ""


def inspect_godzip(
    repo_root: Path,
    zip_path: Path,
    *,
    strip_legacy_prefix: bool = False,
) -> ArchiveInspection:
    repo_root = repo_root.resolve()
    zip_path = zip_path.expanduser().resolve()
    if not zip_path.is_file():
        raise GodzipError(f"GODZIP does not exist: {zip_path}")
    try:
        archive = zipfile.ZipFile(zip_path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise GodzipError(f"Not a readable ZIP archive: {zip_path.name}") from exc

    statuses = git_status_map(repo_root)
    with archive:
        members = _validate_archive_members(archive)
        bad = archive.testzip()
        if bad:
            raise GodzipError(f"Archive CRC validation failed at {bad}")
        manifest, manifest_member = _load_manifest_from_archive(archive, members)
        inspection = ArchiveInspection(zip_path=zip_path, manifest=manifest, manifest_member=manifest_member)

        if manifest is None:
            inspection.legacy = True
            payload_members = [
                name
                for name in members
                if name not in MANIFEST_CANDIDATES
                and not name.startswith(".godzip/")
            ]
            inspection.legacy_common_prefix = _common_top_folder(payload_members)
            prefix = inspection.legacy_common_prefix if strip_legacy_prefix else ""
            for name in sorted(payload_members, key=str.casefold):
                target = name
                if prefix and target.startswith(prefix + "/"):
                    target = target[len(prefix) + 1 :]
                try:
                    target = validate_repo_relpath(target)
                except GodzipError:
                    inspection.warnings.append(f"Skipped unsafe legacy member: {name}")
                    continue
                info = members[name]
                digest = _zip_member_sha256(archive, info)
                full = repo_root / Path(*PurePosixPath(target).parts)
                local_digest = sha256_file(full) if full.is_file() else ""
                dirty = bool(statuses.get(target, ""))
                if full.is_file() and local_digest == digest:
                    state = "SAME"
                    selected = False
                elif not full.exists():
                    state = "NEW"
                    selected = workflow_default_selected(target, "NEW")
                elif dirty:
                    state = "LOCAL DIRTY"
                    selected = workflow_default_selected(target, statuses.get(target, ""))
                else:
                    state = "OVERWRITE"
                    selected = workflow_default_selected(target, "")
                inspection.files.append(
                    ArchiveFile(target, name, info.file_size, digest, state, dirty, selected)
                )
            inspection.relation = "unknown"
            inspection.relation_detail = "LEGACY / UNMANIFESTED archive: source HEAD and deletion intent are unknown."
            inspection.warnings.append("Legacy archives never infer deletion from missing files and cannot carry debris actions.")
            return inspection

        _validate_manifest_shape(manifest)
        inspection.source_head = str(manifest.get("source_head", "") or "")
        inspection.source_branch = str(manifest.get("source_branch", "") or "")
        inspection.dirty_worktree = bool(manifest.get("dirty_worktree", False))
        inspection.baseline_relation, baseline_detail = compare_source_head(repo_root, inspection.source_head)

        target_seen: set[str] = set()
        for record in manifest.get("files", []):
            if not isinstance(record, dict):
                raise GodzipError("Manifest file entry must be an object")
            if record.get("action", "replace_file") != "replace_file":
                raise GodzipError(f"Unsupported file action: {record.get('action')!r}")
            target = validate_repo_relpath(str(record.get("path", "")))
            key = target.casefold()
            if key in target_seen:
                raise GodzipError(f"Manifest contains duplicate target: {target}")
            target_seen.add(key)
            info = members.get(target)
            if info is None:
                raise GodzipError(f"Manifest target is missing from archive: {target}")
            expected_hash = str(record.get("sha256", "") or "").lower()
            actual_hash = _zip_member_sha256(archive, info)
            if not expected_hash or actual_hash != expected_hash:
                raise GodzipError(f"SHA-256 mismatch for archived file: {target}")
            expected_size = int(record.get("size", info.file_size))
            if info.file_size != expected_size:
                raise GodzipError(f"Size mismatch for archived file: {target}")
            full = repo_root / Path(*PurePosixPath(target).parts)
            local_hash = sha256_file(full) if full.is_file() else ""
            dirty = bool(statuses.get(target, ""))
            if full.is_file() and local_hash == actual_hash:
                state = "SAME"
                selected = False
            elif not full.exists():
                state = "NEW"
                selected = True
            elif dirty:
                state = "LOCAL DIRTY"
                selected = True
            else:
                state = "OVERWRITE"
                selected = True
            inspection.files.append(
                ArchiveFile(target, target, info.file_size, actual_hash, state, dirty, selected)
            )

        debris_seen: set[str] = set()
        for entry in manifest.get("debris", []):
            if not isinstance(entry, dict):
                raise GodzipError("Manifest debris entry must be an object")
            if entry.get("action", "move_to_deleteme") != "move_to_deleteme":
                raise GodzipError(f"Unsupported debris action: {entry.get('action')!r}")
            rel = validate_debris_relpath(str(entry.get("path", "")))
            key = rel.casefold()
            if key in debris_seen:
                continue
            debris_seen.add(key)
            exists = (repo_root / Path(*PurePosixPath(rel).parts)).exists()
            inspection.debris.append(
                DebrisItem(rel, str(entry.get("reason", "") or ""), exists, exists)
            )

        # A target cannot simultaneously be replaced and removed, including parent/child overlap.
        target_paths = [PurePosixPath(item.target_path) for item in inspection.files]
        for debris in inspection.debris:
            d = PurePosixPath(debris.path)
            for target in target_paths:
                if target == d or d in target.parents or target in d.parents:
                    raise GodzipError(
                        f"Manifest conflict: {debris.path} is debris but overlaps replacement {target.as_posix()}"
                    )
        local_head = git_head(repo_root)
        if inspection.baseline_relation == "same":
            inspection.relation = "same"
            inspection.relation_detail = baseline_detail
        elif inspection.baseline_relation == "older":
            changed = _committed_changed_paths(repo_root, inspection.source_head, local_head)
            archive_paths = {item.target_path for item in inspection.files} | {item.path for item in inspection.debris}
            overlap = sorted(archive_paths & changed, key=str.casefold)
            inspection.history_overlap_paths = overlap
            if overlap:
                inspection.relation = "conflict"
                inspection.relation_detail = (
                    f"Archive baseline {inspection.source_head[:10]} predates local HEAD {local_head[:10]}, "
                    f"and {len(overlap)} archive target(s) were also changed by newer local commits. "
                    "The archive itself is not assumed stale; review overlapping targets before applying."
                )
                preview = ", ".join(overlap[:5])
                if len(overlap) > 5:
                    preview += f", +{len(overlap) - 5} more"
                inspection.warnings.append(f"Committed-history overlap: {preview}")
            else:
                inspection.relation = "compatible"
                inspection.relation_detail = (
                    f"Archive baseline {inspection.source_head[:10]} predates local HEAD {local_head[:10]}, "
                    "but newer commits do not touch any file/debris target carried by this partial GODZIP. "
                    "No committed-history conflict was found."
                )
        elif inspection.baseline_relation == "newer":
            inspection.relation = "future"
            inspection.relation_detail = (
                f"Archive baseline {inspection.source_head[:10]} is newer than local HEAD {local_head[:10]}. "
                "Applying selected targets may depend on commits not present locally."
            )
        elif inspection.baseline_relation == "diverged":
            inspection.relation = "diverged"
            inspection.relation_detail = baseline_detail + " Review every selected target before applying."
        else:
            inspection.relation = "unknown"
            inspection.relation_detail = baseline_detail

        if inspection.dirty_worktree:
            inspection.warnings.append("Archive was produced from a dirty worktree; baseline HEAD identifies ancestry, not the archive file bytes.")
        return inspection


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.godzip-{os.getpid()}-{time.time_ns()}.tmp")
    try:
        shutil.copy2(source, temp)
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _unique_destination(base: Path) -> Path:
    if not base.exists():
        return base
    for index in range(1, 10000):
        candidate = base.with_name(f"{base.name}.{index}")
        if not candidate.exists():
            return candidate
    raise GodzipError(f"Could not allocate unique /deleteme destination for {base}")


def _timestamp_tag() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def apply_godzip(
    repo_root: Path,
    inspection: ArchiveInspection,
    selected_targets: Sequence[str],
    *,
    selected_debris: Sequence[str] = (),
    create_rollback_snapshot: bool = True,
    allow_history_conflict: bool = False,
) -> ApplyResult:
    repo_root = repo_root.resolve()
    if inspection.selection_requires_history_ack(selected_targets, selected_debris) and not allow_history_conflict:
        raise GodzipError("Selected GODZIP targets overlap incompatible/newer commit history; explicit review is required")

    file_by_target = {item.target_path: item for item in inspection.files}
    targets: list[ArchiveFile] = []
    target_seen: set[str] = set()
    for raw in selected_targets:
        rel = validate_repo_relpath(raw)
        if rel not in file_by_target:
            raise GodzipError(f"Selected target is not present in inspected archive: {rel}")
        if rel.casefold() not in target_seen:
            target_seen.add(rel.casefold())
            targets.append(file_by_target[rel])

    debris_map = {item.path: item for item in inspection.debris}
    debris_paths: list[str] = []
    debris_seen: set[str] = set()
    for raw in selected_debris:
        rel = validate_debris_relpath(raw)
        if rel not in debris_map:
            raise GodzipError(f"Selected debris entry is not present in manifest: {rel}")
        if rel.casefold() not in debris_seen:
            debris_seen.add(rel.casefold())
            debris_paths.append(rel)

    if not targets and not debris_paths:
        raise GodzipError("Nothing is selected to apply")

    # Re-inspect immediately before mutation so archive hashes and history applicability are not stale.
    fresh = inspect_godzip(
        repo_root,
        inspection.zip_path,
        strip_legacy_prefix=bool(inspection.legacy and inspection.legacy_common_prefix and any(
            item.target_path != item.member_name for item in inspection.files
        )),
    )
    if fresh.selection_requires_history_ack(selected_targets, selected_debris) and not allow_history_conflict:
        raise GodzipError("Selected GODZIP targets now overlap incompatible/newer commit history; explicit review is required")
    fresh_by_target = {item.target_path: item for item in fresh.files}
    fresh_debris = {item.path for item in fresh.debris}
    for rel in debris_paths:
        if rel not in fresh_debris:
            raise GodzipError(f"Archive debris manifest changed after inspection: {rel}")
    for item in targets:
        now = fresh_by_target.get(item.target_path)
        if now is None or now.sha256 != item.sha256 or now.member_name != item.member_name:
            raise GodzipError(f"Archive changed after inspection: {item.target_path}")

    deleteme_root = repo_root / "deleteme"
    tag = _timestamp_tag()
    persistent_backup = (
        _unique_destination(deleteme_root / f"GODZIP_BACKUP_{tag}")
        if create_rollback_snapshot
        else None
    )
    persistent_debris = (
        _unique_destination(deleteme_root / f"GODZIP_DEBRIS_{tag}")
        if debris_paths
        else None
    )

    replaced = 0
    new_files = 0
    unchanged = 0
    moved_debris = 0

    with tempfile.TemporaryDirectory(prefix="srpss-godzip-") as temp_raw:
        temp_root = Path(temp_raw)
        staged = temp_root / "staged"
        originals = temp_root / "originals"
        debris_hold = temp_root / "debris"
        existing_before: dict[str, bool] = {}

        with zipfile.ZipFile(inspection.zip_path, "r") as archive:
            members = _validate_archive_members(archive)
            for item in targets:
                info = members.get(item.member_name)
                if info is None:
                    raise GodzipError(f"Archive member vanished: {item.member_name}")
                dest = staged / Path(*PurePosixPath(item.target_path).parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(info, "r") as source, dest.open("wb") as out:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        out.write(chunk)
                if digest.hexdigest() != item.sha256:
                    raise GodzipError(f"SHA-256 changed during extraction: {item.target_path}")

        # Snapshot every target before any mutation, even if persistent backup is disabled.
        for item in targets:
            target = repo_root / Path(*PurePosixPath(item.target_path).parts)
            exists = target.is_file()
            existing_before[item.target_path] = exists
            if exists:
                snap = originals / Path(*PurePosixPath(item.target_path).parts)
                snap.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, snap)

        # Move debris into transaction hold first so failure can restore it exactly.
        held_debris: list[tuple[str, Path]] = []
        try:
            for rel in debris_paths:
                source = repo_root / Path(*PurePosixPath(rel).parts)
                if not source.exists():
                    continue
                hold = debris_hold / Path(*PurePosixPath(rel).parts)
                hold.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(hold))
                held_debris.append((rel, hold))

            for item in targets:
                source = staged / Path(*PurePosixPath(item.target_path).parts)
                target = repo_root / Path(*PurePosixPath(item.target_path).parts)
                if target.is_file() and sha256_file(target) == item.sha256:
                    unchanged += 1
                    continue
                existed = existing_before[item.target_path]
                _atomic_copy(source, target)
                if existed:
                    replaced += 1
                else:
                    new_files += 1

            if persistent_backup is not None:
                for item in targets:
                    snap = originals / Path(*PurePosixPath(item.target_path).parts)
                    if snap.is_file():
                        backup_target = persistent_backup / Path(*PurePosixPath(item.target_path).parts)
                        backup_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(snap, backup_target)

            if held_debris:
                assert persistent_debris is not None
                for rel, hold in held_debris:
                    destination = persistent_debris / Path(*PurePosixPath(rel).parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination = _unique_destination(destination)
                    shutil.move(str(hold), str(destination))
                    moved_debris += 1

        except Exception:
            # Roll back replacements.
            for item in reversed(targets):
                target = repo_root / Path(*PurePosixPath(item.target_path).parts)
                snap = originals / Path(*PurePosixPath(item.target_path).parts)
                try:
                    if snap.is_file():
                        _atomic_copy(snap, target)
                    elif not existing_before.get(item.target_path, False):
                        target.unlink(missing_ok=True)
                except OSError:
                    pass
            # Restore any debris still held in temp. Items already moved to persistent
            # /deleteme are restored from there below when possible.
            for rel, hold in held_debris:
                source = repo_root / Path(*PurePosixPath(rel).parts)
                try:
                    if hold.exists():
                        source.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(hold), str(source))
                    elif persistent_debris is not None:
                        persisted = persistent_debris / Path(*PurePosixPath(rel).parts)
                        if persisted.exists():
                            source.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(persisted), str(source))
                except OSError:
                    pass
            raise

    return ApplyResult(
        replaced=replaced,
        new_files=new_files,
        unchanged_skipped=unchanged,
        debris_moved=moved_debris,
        backup_dir=persistent_backup if persistent_backup and persistent_backup.exists() else None,
        debris_dir=persistent_debris if persistent_debris and persistent_debris.exists() else None,
    )


def move_paths_to_deleteme(
    repo_root: Path,
    paths: Sequence[str],
    *,
    label: str = "MANUAL",
) -> tuple[Path, int]:
    repo_root = repo_root.resolve()
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        rel = validate_debris_relpath(raw)
        key = rel.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(rel)
    if not normalized:
        raise GodzipError("No debris paths selected")
    root = repo_root / "deleteme" / f"{label.upper()}_{_timestamp_tag()}"
    count = 0
    for rel in normalized:
        source = repo_root / Path(*PurePosixPath(rel).parts)
        if not source.exists():
            continue
        destination = root / Path(*PurePosixPath(rel).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = _unique_destination(destination)
        shutil.move(str(source), str(destination))
        count += 1
    return root, count


def write_debris_manifest(path: Path, paths: Sequence[str], *, reasons: Mapping[str, str] | None = None) -> None:
    entries = []
    seen: set[str] = set()
    reasons = reasons or {}
    for raw in paths:
        rel = validate_debris_relpath(raw)
        if rel.casefold() in seen:
            continue
        seen.add(rel.casefold())
        entries.append({"path": rel, "action": "move_to_deleteme", "reason": reasons.get(rel, "")})
    payload = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "debris": entries,
    }
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_bytes(_json_bytes(payload))
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def read_debris_manifest(path: Path) -> list[dict[str, str]]:
    path = path.expanduser().resolve()
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            members = _validate_archive_members(archive)
            manifest, _ = _load_manifest_from_archive(archive, members)
            if manifest is None:
                raise GodzipError("ZIP has no GODZIP manifest/debris metadata")
            payload = manifest
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GodzipError(f"Cannot read debris manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise GodzipError("Debris manifest root must be an object")
    entries = payload.get("debris", [])
    if not isinstance(entries, list):
        raise GodzipError("Debris manifest 'debris' must be an array")
    result: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise GodzipError("Debris entry must be an object")
        rel = validate_debris_relpath(str(entry.get("path", "")))
        result.append({"path": rel, "reason": str(entry.get("reason", "") or "")})
    return result



def _parse_name_status_z(raw: bytes) -> list[tuple[str, str, str]]:
    """Parse ``git diff --name-status -z`` into (status, path, old_path)."""
    parts = _zlist(raw)
    result: list[tuple[str, str, str]] = []
    i = 0
    while i < len(parts):
        status = parts[i]
        i += 1
        if i >= len(parts):
            raise GodzipError("Unexpected truncated Git name-status output")
        if status.startswith(("R", "C")):
            old_path = parts[i].replace("\\", "/")
            i += 1
            if i >= len(parts):
                raise GodzipError("Unexpected truncated Git rename output")
            path = parts[i].replace("\\", "/")
            i += 1
        else:
            old_path = ""
            path = parts[i].replace("\\", "/")
            i += 1
        result.append((status, path, old_path))
    return result


def git_changes(repo_root: Path) -> list[GitChange]:
    """Return every current worktree/index change, including deletions."""
    repo_root = repo_root.resolve()
    staged_raw = _run_git(repo_root, "diff", "--cached", "--name-status", "-z").stdout
    unstaged_raw = _run_git(repo_root, "diff", "--name-status", "-z").stdout
    untracked_raw = _run_git(repo_root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    merged: dict[str, dict[str, object]] = {}

    def note(status: str, path: str, *, staged: bool = False, unstaged: bool = False) -> None:
        key = path.casefold()
        entry = merged.setdefault(
            key,
            {"path": path, "statuses": [], "staged": False, "unstaged": False, "untracked": False},
        )
        statuses = entry["statuses"]
        assert isinstance(statuses, list)
        statuses.append(status)
        entry["staged"] = bool(entry["staged"]) or staged
        entry["unstaged"] = bool(entry["unstaged"]) or unstaged

    for status, path, _old in _parse_name_status_z(staged_raw):
        note(status, path, staged=True)
    for status, path, _old in _parse_name_status_z(unstaged_raw):
        note(status, path, unstaged=True)
    for path in _zlist(untracked_raw):
        rel = path.replace("\\", "/")
        key = rel.casefold()
        entry = merged.setdefault(
            key,
            {"path": rel, "statuses": [], "staged": False, "unstaged": False, "untracked": False},
        )
        statuses = entry["statuses"]
        assert isinstance(statuses, list)
        statuses.append("?")
        entry["untracked"] = True

    result: list[GitChange] = []
    for entry in merged.values():
        statuses = entry["statuses"]
        assert isinstance(statuses, list)
        result.append(
            GitChange(
                path=str(entry["path"]),
                status="/".join(dict.fromkeys(str(item) for item in statuses)),
                staged=bool(entry["staged"]),
                unstaged=bool(entry["unstaged"]),
                untracked=bool(entry["untracked"]),
            )
        )
    result.sort(key=lambda item: item.path.casefold())
    return result


def git_commit_all(repo_root: Path, message: str) -> str:
    """Stage all Git-visible changes and create one commit. Returns new HEAD."""
    message = str(message or "").strip()
    if not message:
        raise GodzipError("Commit message is required")
    if not git_changes(repo_root):
        raise GodzipError("There are no Git changes to commit")
    _run_git_text(repo_root, "add", "-A")
    _run_git_text(repo_root, "commit", "-m", message, timeout=120)
    return git_head(repo_root)


def git_upstream(repo_root: Path) -> str:
    result = _run_git_text(
        repo_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_push_current(repo_root: Path) -> str:
    """Push current branch without force. Establish origin tracking if needed."""
    branch = git_branch(repo_root)
    if branch == "DETACHED":
        raise GodzipError("Cannot push from a detached HEAD")
    upstream = git_upstream(repo_root)
    if upstream:
        result = _run_git_text(repo_root, "push", timeout=180)
        return (result.stdout or result.stderr).strip()
    remotes = [line.strip() for line in _run_git_text(repo_root, "remote").stdout.splitlines() if line.strip()]
    if "origin" not in remotes:
        raise GodzipError("Current branch has no upstream and there is no 'origin' remote")
    result = _run_git_text(repo_root, "push", "--set-upstream", "origin", branch, timeout=180)
    return (result.stdout or result.stderr).strip()


def _split_remote_ref(upstream: str, branch: str) -> tuple[str, str]:
    if upstream and "/" in upstream:
        remote, remote_branch = upstream.split("/", 1)
        return remote, remote_branch
    return "origin", branch


def inspect_pull(repo_root: Path, *, fetch: bool = True) -> PullInspection:
    """Fetch and inspect incoming changes without mutating HEAD/worktree."""
    repo_root = repo_root.resolve()
    branch = git_branch(repo_root)
    if branch == "DETACHED":
        raise GodzipError("PULL is disabled on a detached HEAD")
    upstream = git_upstream(repo_root)
    remote, remote_branch = _split_remote_ref(upstream, branch)
    remotes = [line.strip() for line in _run_git_text(repo_root, "remote").stdout.splitlines() if line.strip()]
    if remote not in remotes:
        raise GodzipError(f"Remote {remote!r} is not configured")
    if fetch:
        _run_git_text(repo_root, "fetch", "--prune", remote, timeout=180)
    remote_ref = upstream or f"{remote}/{remote_branch}"
    probe = _run_git(repo_root, "rev-parse", "--verify", remote_ref, check=False)
    if probe.returncode != 0:
        raise GodzipError(f"Remote tracking ref does not exist after fetch: {remote_ref}")
    local_head = git_head(repo_root)
    remote_head = probe.stdout.decode("utf-8", errors="replace").strip()
    if local_head == remote_head:
        relation = "same"
        detail = f"Local HEAD already matches {remote_ref} ({local_head[:10]})."
    elif _run_git(repo_root, "merge-base", "--is-ancestor", local_head, remote_head, check=False).returncode == 0:
        relation = "behind"
        count = _run_git_text(repo_root, "rev-list", "--count", f"{local_head}..{remote_head}").stdout.strip()
        detail = f"Local HEAD is behind {remote_ref} by {count or '?'} commit(s); fast-forward is possible."
    elif _run_git(repo_root, "merge-base", "--is-ancestor", remote_head, local_head, check=False).returncode == 0:
        relation = "ahead"
        detail = f"Local HEAD is ahead of {remote_ref}; there is nothing to pull."
    else:
        relation = "diverged"
        detail = f"Local HEAD and {remote_ref} have diverged. GODZIP Foundry will not merge/rebase automatically."

    statuses = git_status_map(repo_root)
    incoming_raw = _run_git(
        repo_root,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        local_head,
        remote_head,
    ).stdout
    files: list[PullFile] = []
    for status, path, old_path in _parse_name_status_z(incoming_raw):
        dirty = bool(statuses.get(path, "") or (old_path and statuses.get(old_path, "")))
        files.append(PullFile(path=path, status=status, old_path=old_path, local_dirty=dirty))
    files.sort(key=lambda item: item.display_path.casefold())
    return PullInspection(
        branch=branch,
        remote=remote,
        remote_ref=remote_ref,
        local_head=local_head,
        remote_head=remote_head,
        relation=relation,
        relation_detail=detail,
        files=files,
        worktree_dirty=git_dirty(repo_root),
    )


def git_pull_ff_only(repo_root: Path, inspection: PullInspection) -> str:
    """Apply the already-reviewed remote update as a strict fast-forward."""
    fresh = inspect_pull(repo_root, fetch=False)
    if fresh.local_head != inspection.local_head or fresh.remote_head != inspection.remote_head:
        raise GodzipError("Local or remote HEAD changed after PULL inspection; refresh and review again")
    if fresh.relation == "same":
        return "Already up to date."
    if fresh.relation != "behind":
        raise GodzipError(f"Fast-forward pull is not possible: {fresh.relation}")
    if fresh.worktree_dirty:
        raise GodzipError("Full PULL requires a clean worktree. Commit/stash or use SELECTIVE SYNC.")
    result = _run_git_text(repo_root, "merge", "--ff-only", fresh.remote_ref, timeout=180)
    return (result.stdout or result.stderr).strip()


def _git_blob_bytes(repo_root: Path, remote_head: str, path: str) -> bytes:
    result = _run_git(repo_root, "show", f"{remote_head}:{path}", check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GodzipError(detail or f"Cannot read {path} from {remote_head[:10]}")
    return result.stdout


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.sync")
    try:
        temp.write_bytes(data)
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def selective_sync_from_remote(
    repo_root: Path,
    inspection: PullInspection,
    selected_paths: Sequence[str],
) -> SelectiveSyncResult:
    """Copy selected remote file states into the worktree without advancing HEAD.

    Existing local targets/deleted rename sources are backed up under /deleteme.
    This operation intentionally leaves the worktree dirty relative to local HEAD.
    """
    repo_root = repo_root.resolve()
    fresh = inspect_pull(repo_root, fetch=False)
    if fresh.local_head != inspection.local_head or fresh.remote_head != inspection.remote_head:
        raise GodzipError("Local or remote HEAD changed after PULL inspection; refresh and review again")
    available = {item.path: item for item in fresh.files}
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in selected_paths:
        rel = validate_repo_relpath(raw)
        if rel not in available:
            raise GodzipError(f"Selected incoming path is no longer present: {rel}")
        if rel.casefold() not in seen:
            seen.add(rel.casefold())
            normalized.append(rel)
    if not normalized:
        raise GodzipError("No incoming paths selected")

    tag = _timestamp_tag()
    backup_root = _unique_destination(repo_root / "deleteme" / f"PULL_SYNC_BACKUP_{tag}")
    written = 0
    deleted = 0
    backed_any = False

    def backup(path_rel: str) -> None:
        nonlocal backed_any
        source = repo_root / Path(*PurePosixPath(path_rel).parts)
        if not source.exists():
            return
        dest = backup_root / Path(*PurePosixPath(path_rel).parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(source, dest)
        backed_any = True

    for rel in normalized:
        item = available[rel]
        code = item.status[:1]
        target = repo_root / Path(*PurePosixPath(item.path).parts)
        if code in {"D"}:
            backup(item.path)
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            deleted += 1
            continue
        if code in {"R"} and item.old_path:
            old_rel = validate_repo_relpath(item.old_path)
            old_target = repo_root / Path(*PurePosixPath(old_rel).parts)
            backup(old_rel)
            if old_target.is_dir():
                shutil.rmtree(old_target)
            else:
                old_target.unlink(missing_ok=True)
            deleted += 1
        backup(item.path)
        data = _git_blob_bytes(repo_root, fresh.remote_head, item.path)
        _atomic_write_bytes(target, data)
        written += 1

    if not backed_any:
        try:
            backup_root.rmdir()
        except OSError:
            pass
    return SelectiveSyncResult(
        written=written,
        deleted=deleted,
        backup_dir=backup_root if backup_root.exists() else None,
    )


def collect_log_files(repo_root: Path) -> list[Path]:
    """Return direct loose files in /logs, excluding ZIPs and subfolders."""
    logs = repo_root.resolve() / "logs"
    if not logs.is_dir():
        return []
    result = [path for path in logs.iterdir() if path.is_file() and path.suffix.lower() != ".zip"]
    result.sort(key=lambda path: path.name.casefold())
    return result


def _zip_member_names(path: Path) -> tuple[str, ...]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return tuple(name.replace("\\", "/").lstrip("/") for name in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return ()


def is_probable_srpss_zip(path: Path) -> bool:
    """Return whether a direct ZIP looks related to this SRPSS GODZIP workflow.

    A valid GODZIP manifest is authoritative when present, but discovery does
    not *require* manifests so older/legacy archives remain usable.  Named
    GODZIPs are accepted, while unnamed legacy archives need a small SRPSS
    structural fingerprint.  This keeps a personal download folder useful
    without flooding it with unrelated ZIPs.
    """
    path = Path(path)
    if path.suffix.lower() != ".zip":
        return False
    names = _zip_member_names(path)
    if not names:
        return "godzip" in path.name.casefold()

    by_fold = {name.casefold(): name for name in names}
    for candidate in MANIFEST_CANDIDATES:
        actual = by_fold.get(candidate.casefold())
        if not actual:
            continue
        try:
            with zipfile.ZipFile(path, "r") as archive:
                payload = json.loads(archive.read(actual).decode("utf-8"))
            if isinstance(payload, dict) and payload.get("format") == FORMAT_NAME:
                return True
        except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile):
            pass

    if "godzip" in path.name.casefold():
        return True

    folded = tuple(name.casefold() for name in names)
    def has_path_or_wrapped(target: str) -> bool:
        target = target.casefold().strip("/")
        return any(name == target or name.endswith("/" + target) for name in folded)

    def has_dir(name: str) -> bool:
        token = "/" + name.casefold().strip("/") + "/"
        prefix = name.casefold().strip("/") + "/"
        return any(item.startswith(prefix) or token in "/" + item for item in folded)

    anchors = sum(
        (
            has_dir("core"),
            has_dir("rendering"),
            has_dir("widgets"),
            has_dir("tools"),
            has_path_or_wrapped("Current_Plan.md"),
            has_path_or_wrapped("versioning.py"),
        )
    )
    return bool(has_path_or_wrapped("main.py") and anchors >= 1) or anchors >= 3


def discover_zip_candidates(
    search_dirs: Iterable[Path],
    *,
    limit: int = 40,
    project_only: bool = True,
) -> list[Path]:
    """Return newest direct ZIP files from supplied directories.

    Discovery is intentionally shallow and sorted by filesystem modified time.
    The cheap pass only stats directory entries.  In project-only mode,
    GODZIP-named files are admitted without opening them and only a bounded set
    of recent opaque-name ZIPs are inspected for manifest/legacy fingerprints.
    This keeps a large personal download folder from becoming an archive-I/O
    benchmark.
    """
    found: dict[str, tuple[float, Path]] = {}
    for raw_dir in search_dirs:
        directory = Path(raw_dir).expanduser()
        try:
            if not directory.is_dir():
                continue
            for entry in directory.iterdir():
                try:
                    if not entry.is_file() or entry.suffix.lower() != ".zip":
                        continue
                    stamp = entry.stat().st_mtime
                    resolved = entry.resolve()
                except OSError:
                    continue
                key = os.path.normcase(str(resolved))
                current = found.get(key)
                if current is None or stamp > current[0]:
                    found[key] = (stamp, resolved)
        except OSError:
            continue

    ordered = sorted(found.values(), key=lambda item: (-item[0], item[1].name.casefold()))
    cap = max(0, int(limit))
    if not project_only:
        return [path for _stamp, path in ordered[:cap]]

    accepted: dict[str, tuple[float, Path]] = {}
    for stamp, path in ordered:
        if "godzip" in path.name.casefold():
            accepted[os.path.normcase(str(path))] = (stamp, path)

    opaque_budget = max(120, cap * 3) if cap else 0
    inspected = 0
    for stamp, path in ordered:
        if "godzip" in path.name.casefold():
            continue
        if inspected >= opaque_budget:
            break
        inspected += 1
        if is_probable_srpss_zip(path):
            accepted[os.path.normcase(str(path))] = (stamp, path)

    project = sorted(accepted.values(), key=lambda item: (-item[0], item[1].name.casefold()))
    return [path for _stamp, path in project[:cap]]


def suggested_logzip_path(repo_root: Path, output_dir: Path | None = None) -> Path:
    destination = Path(output_dir).expanduser().resolve() if output_dir is not None else repo_root.resolve().parent
    destination.mkdir(parents=True, exist_ok=True)
    base = f"logs{git_head(repo_root)[:10]}"
    candidate = destination / f"{base}.zip"
    index = 2
    while candidate.exists():
        candidate = destination / f"{base}{index}.zip"
        index += 1
    return candidate


def create_logzip(
    repo_root: Path,
    selected_names: Sequence[str] | None = None,
    *,
    output_dir: Path | None = None,
) -> LogzipResult:
    """Create a verified ZIP from direct loose /logs files without deleting sources."""
    repo_root = repo_root.resolve()
    files = collect_log_files(repo_root)
    by_name = {path.name: path for path in files}
    if selected_names is None:
        selected = files
    else:
        selected = []
        seen: set[str] = set()
        for raw in selected_names:
            name = Path(str(raw)).name
            if name != str(raw) or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            path = by_name.get(name)
            if path is not None:
                selected.append(path)
    if not selected:
        raise GodzipError("No loose /logs files selected")
    output = suggested_logzip_path(repo_root, output_dir)
    temp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for path in selected:
                archive.write(path, arcname=path.name)
        with zipfile.ZipFile(temp, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise GodzipError(f"LOGZIP CRC validation failed at {bad}")
        os.replace(temp, output)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return LogzipResult(zip_path=output, files=tuple(path.name for path in selected))


def discover_run_flags(repo_root: Path) -> tuple[str, ...]:
    """Read the canonical long-form runtime switches accepted by ``main.py``.

    ``parse_screensaver_args`` owns the filter set for diagnostic/developer
    switches.  Reading that AST keeps GODZIP Foundry from fossilising a second
    copy of the CLI surface while avoiding importing the Qt-heavy entrypoint.
    """
    source_path = Path(repo_root) / "main.py"
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        raise GodzipError(f"Cannot inspect runtime CLI surface: {exc}") from exc

    raw_flags: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "parse_screensaver_args":
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "_filtered" for target in child.targets):
                continue
            value = child.value
            if not isinstance(value, (ast.Set, ast.Tuple, ast.List)):
                continue
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    raw_flags.append(elt.value)
        break

    if not raw_flags:
        raise GodzipError("main.py parse_screensaver_args() exposes no diagnostic CLI filter set")

    canonical: list[str] = []
    seen: set[str] = set()
    for raw in raw_flags:
        flag = RUN_FLAG_ALIASES.get(raw, raw)
        if not flag.startswith("--") or flag in seen:
            continue
        seen.add(flag)
        canonical.append(flag)
    return tuple(canonical)


def run_flag_description(flag: str) -> str:
    return RUN_FLAG_DESCRIPTIONS.get(str(flag), "Runtime/developer switch accepted by main.py")



def _git_commit_exists(repo_root: Path, revision: str) -> bool:
    revision = str(revision or "").strip()
    if not revision:
        return False
    return _run_git(repo_root, "cat-file", "-e", f"{revision}^{{commit}}", check=False).returncode == 0


def _git_blob_at_revision(repo_root: Path, revision: str, path: str) -> bytes | None:
    if not revision:
        return None
    result = _run_git(repo_root, "show", f"{revision}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def _current_repo_bytes(repo_root: Path, rel: str) -> bytes | None:
    rel = validate_repo_relpath(rel)
    target = repo_root.resolve() / Path(rel)
    try:
        if target.is_symlink():
            return ("SYMLINK->" + os.readlink(target)).encode("utf-8")
        if not target.is_file():
            return None
        return target.read_bytes()
    except OSError as exc:
        raise GodzipError(f"Cannot read current repo file for DIFF: {rel}: {exc}") from exc


def _decode_diff_text(data: bytes) -> str | None:
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _bytes_digest(data: bytes | None) -> str:
    if data is None:
        return "missing"
    return hashlib.sha256(data).hexdigest()[:16]


def _changed_paths_since(repo_root: Path, source_head: str) -> set[str]:
    paths: set[str] = set()
    if source_head and _git_commit_exists(repo_root, source_head):
        current_head = git_head(repo_root)
        raw = _run_git(repo_root, "diff", "--name-only", "-z", source_head, current_head).stdout
        paths.update(item.replace("\\", "/") for item in _zlist(raw))
    for change in git_changes(repo_root):
        paths.add(change.path.replace("\\", "/"))
    return paths


def generate_godzip_diff(repo_root: Path, zip_path: Path) -> GodzipDiffResult:
    """Compare current repo state against a chosen GODZIP baseline.

    The baseline uses archived bytes for every file actually carried by the
    GODZIP (so dirty-worktree snapshots remain exact).  When the manifest's
    source HEAD is available locally, committed changes since that HEAD plus
    current non-ignored worktree changes extend the candidate set, allowing new
    files that were created after the GODZIP to appear without treating every
    archive omission as an addition.
    """
    root = Path(repo_root).resolve()
    inspection = inspect_godzip(root, Path(zip_path))
    archived = {item.target_path: item.member_name for item in inspection.files}
    candidates = set(archived)
    source_head = inspection.source_head if _git_commit_exists(root, inspection.source_head) else ""
    candidates.update(_changed_paths_since(root, source_head))

    # Ignore Foundry/runtime-private targets even if a malformed legacy archive
    # somehow carried them.  validate_repo_relpath is still the final fence.
    clean_candidates: list[str] = []
    for raw in candidates:
        rel = raw.replace("\\", "/")
        try:
            clean_candidates.append(validate_repo_relpath(rel))
        except GodzipError:
            continue
    clean_candidates = sorted(set(clean_candidates), key=str.casefold)

    archive_bytes: dict[str, bytes] = {}
    with zipfile.ZipFile(inspection.zip_path, "r") as archive:
        for rel, member in archived.items():
            archive_bytes[rel] = archive.read(member)

    chunks: list[str] = []
    added = modified = deleted = binary = 0
    for rel in clean_candidates:
        before = archive_bytes.get(rel)
        if before is None and source_head:
            before = _git_blob_at_revision(root, source_head, rel)
        after = _current_repo_bytes(root, rel)
        if before == after:
            continue
        if before is None and after is not None:
            kind = "added"
            added += 1
        elif before is not None and after is None:
            kind = "deleted"
            deleted += 1
        else:
            kind = "modified"
            modified += 1

        before_text = _decode_diff_text(before) if before is not None else ""
        after_text = _decode_diff_text(after) if after is not None else ""
        chunks.append(f"diff --godzip {kind} {rel}\n")
        if before_text is None or after_text is None:
            binary += 1
            chunks.append(
                "Binary content differs "
                f"(GODZIP={_bytes_digest(before)} size={len(before) if before is not None else 0}; "
                f"CURRENT={_bytes_digest(after)} size={len(after) if after is not None else 0})\n\n"
            )
            continue

        fromfile = f"GODZIP/{rel}" if before is not None else "/dev/null"
        tofile = f"CURRENT/{rel}" if after is not None else "/dev/null"
        delta = difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="\n",
        )
        rendered = "".join(delta)
        chunks.append(rendered)
        if rendered and not rendered.endswith("\n"):
            chunks.append("\n")
        chunks.append("\n")

    current_head = git_head(root)
    changed = added + modified + deleted
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    header = [
        "# SRPSS GODZIP DIFF",
        f"# Baseline ZIP: {inspection.zip_path.name}",
        f"# Baseline HEAD: {inspection.source_head or 'unknown'}",
        f"# Baseline archive dirty: {'yes' if inspection.dirty_worktree else 'no/unknown'}",
        f"# Current HEAD: {current_head}",
        f"# Current worktree dirty: {'yes' if git_dirty(root) else 'no'}",
        f"# Generated: {generated}",
        "# Scope: exact archived bytes + Git changes since baseline HEAD + current non-ignored worktree changes",
        f"# Summary: {changed} changed file(s) | {added} added | {modified} modified | {deleted} deleted | {binary} binary",
        "",
    ]
    body = "".join(chunks) if chunks else "# No differences found in the resolved comparison scope.\n"
    return GodzipDiffResult(
        text="\n".join(header) + body,
        changed_files=changed,
        added=added,
        modified=modified,
        deleted=deleted,
        binary=binary,
        baseline_head=inspection.source_head,
        current_head=current_head,
        baseline_dirty=inspection.dirty_worktree,
        current_dirty=git_dirty(root),
    )


def repo_venv_python(repo_root: Path) -> Path:
    root = Path(repo_root)
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def build_run_command(
    repo_root: Path,
    entrypoint: str,
    flags: Sequence[str],
) -> tuple[str, ...]:
    root = Path(repo_root).resolve()
    entrypoint = str(entrypoint).strip()
    if entrypoint not in RUN_ENTRYPOINTS:
        raise GodzipError(f"Unsupported RUN entrypoint: {entrypoint}")
    script = root / entrypoint
    if not script.is_file():
        raise GodzipError(f"RUN entrypoint does not exist: {script}")
    python_exe = repo_venv_python(root)
    if not python_exe.is_file():
        raise GodzipError(f"Repo venv Python is missing: {python_exe}")

    accepted = set(discover_run_flags(root))
    chosen: list[str] = []
    seen: set[str] = set()
    for raw in flags:
        flag = RUN_FLAG_ALIASES.get(str(raw).strip(), str(raw).strip())
        if flag not in accepted:
            raise GodzipError(f"RUN flag is not accepted by current main.py: {flag}")
        if flag in seen:
            continue
        seen.add(flag)
        chosen.append(flag)
    return (str(python_exe), str(script), *chosen)


def launch_run_command(
    repo_root: Path,
    entrypoint: str,
    flags: Sequence[str],
    *,
    keep_console_open: bool = False,
) -> subprocess.Popen:
    """Launch SRPSS in an independent console and return immediately.

    On Windows, the normal path launches Python directly with CREATE_NEW_CONSOLE;
    that console therefore closes naturally when SRPSS exits.  The opt-in
    keep-open path uses ``cmd /k`` so the console deliberately survives.
    """
    root = Path(repo_root).resolve()
    command = build_run_command(root, entrypoint, flags)
    kwargs: dict = {"cwd": str(root)}
    if os.name == "nt":
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010))
        if keep_console_open:
            command_line = subprocess.list2cmdline(list(command))
            return subprocess.Popen(["cmd.exe", "/d", "/k", command_line], **kwargs)
    return subprocess.Popen(list(command), **kwargs)


__all__ = [
    "ArchiveFile",
    "ArchiveInspection",
    "ApplyResult",
    "DebrisItem",
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "GitChange",
    "GodzipDiffResult",
    "GodzipError",
    "LogzipResult",
    "MANIFEST_MEMBER",
    "PullFile",
    "PullInspection",
    "RepoFile",
    "RUN_DEFAULT_FLAGS",
    "RUN_ENTRYPOINTS",
    "RUN_FLAG_DESCRIPTIONS",
    "SelectiveSyncResult",
    "apply_godzip",
    "build_run_command",
    "collect_log_files",
    "collect_repo_files",
    "compare_source_head",
    "create_godzip",
    "create_logzip",
    "discover_repo_root",
    "discover_run_flags",
    "discover_zip_candidates",
    "generate_godzip_diff",
    "git_branch",
    "git_changes",
    "git_commit_all",
    "git_dirty",
    "git_head",
    "git_pull_ff_only",
    "git_push_current",
    "git_status_map",
    "git_upstream",
    "inspect_godzip",
    "inspect_pull",
    "is_probable_srpss_zip",
    "launch_run_command",
    "move_paths_to_deleteme",
    "read_debris_manifest",
    "repo_venv_python",
    "run_flag_description",
    "selective_sync_from_remote",
    "sha256_file",
    "suggested_godzip_name",
    "suggested_logzip_path",
    "validate_repo_relpath",
    "workflow_default_selected",
    "write_debris_manifest",
]

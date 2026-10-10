"""Make a portable operator-build evidence bundle, never invoking a compiler.

The Build Runner supplies an opaque run token to its child PowerShell worker.
Only reports with *that exact token* are collected: no stale/latest globbing.
The bundle deliberately excludes binaries; an artifact hash identifies them.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile


STEMS = {
    "standard": "build_nuitka",
    "media_center": "build_nuitka_mc_onedir",
    "reddit_helper": "build_reddit_helper",
}
RUN_TOKEN = re.compile(r"^\d{8}_\d{6}_\d{6}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def evidence_files(job_key: str, token: str) -> tuple[str, ...]:
    """Explicit names prevent mixing reports from unrelated or older builds."""
    stem = STEMS.get(job_key)
    if stem is None:
        return ()
    return (
        f"{stem}_{token}.log",
        f"{stem}_report_{token}.xml",
        f"{stem}_footprint_{token}.json",
        f"{stem}_frozen_audit_{token}.json",
    )


def _artifact_identity(artifact: Path, receipt: object) -> dict:
    published = {"path": str(artifact), "exists": artifact.is_file()}
    if artifact.is_file():
        published.update({"bytes": artifact.stat().st_size, "sha256": sha256_file(artifact)})
    if isinstance(receipt, dict) and isinstance(receipt.get("artifact_sha256"), str):
        published["matches_compiled_artifact_sha256"] = (
            published.get("sha256") == receipt["artifact_sha256"]
        ) if published["exists"] else False
    return published


def write_build_evidence(
    log_dir: Path, job_key: str, token: str, runner_log: Path,
    artifact: Path, returncode: int, *, companions: tuple[Path, ...] = (), retain: int = 8,
) -> Path:
    """Bundle the completed run and its exact artifact identity, including failures.

    The caller must close/flush the runner log before invoking this function.
    No guessed latest report, executable payload, build launch, or threads.
    """
    if not RUN_TOKEN.fullmatch(token):
        raise ValueError(f"Invalid build run token: {token!r}")
    if not re.fullmatch(r"[a-z0-9_]+", job_key):
        raise ValueError(f"Invalid build job key: {job_key!r}")
    log_dir = log_dir.resolve()
    bundle = log_dir / f"build_evidence_{job_key}_{token}.zip"
    candidates = (runner_log, *(log_dir / name for name in evidence_files(job_key, token)))
    files = [p for p in candidates if p.is_file() and p.resolve().parent == log_dir]
    expected = [p.name for p in candidates]
    frozen_name = (f"{STEMS[job_key]}_frozen_audit_{token}.json" if job_key in STEMS else None)
    receipt = None
    if frozen_name and (log_dir / frozen_name).is_file():
        try:
            receipt = json.loads((log_dir / frozen_name).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            receipt = None
    published = _artifact_identity(artifact, receipt)

    manifest = {
        "schema_version": 1,
        "job": job_key,
        "run_id": token,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "runner_exit_code": returncode,
        "published_artifact": published,
        # The same compiled binary published under further names (the diagnostic copy).
        "companion_artifacts": [_artifact_identity(path, receipt) for path in companions],
        "included_files": {p.name: {"size": p.stat().st_size, "sha256": sha256_file(p)} for p in files},
        "missing_files": [name for name in expected if name not in {p.name for p in files}],
        "note": "An absent report is recorded, never substituted with another run's report."
    }
    temporary = bundle.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("evidence.json", json.dumps(manifest, indent=2) + "\n")
            for path in files:
                archive.write(path, arcname=path.name)
        temporary.replace(bundle)
    finally:
        temporary.unlink(missing_ok=True)

    if retain >= 0:
        older = sorted(
            log_dir.glob(f"build_evidence_{job_key}_*.zip"),
            key=lambda path: path.stat().st_mtime_ns, reverse=True,
        )
        for path in older[max(1, retain):]:
            try:
                path.unlink()
            except OSError:
                pass
    return bundle

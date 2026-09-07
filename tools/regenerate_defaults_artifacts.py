"""Regenerate every checked-in defaults artifact from canonical sources.

Safety properties:
- never constructs SettingsManager or opens installed profile storage;
- builds and validates every requested artifact before replacing any target;
- one multi-file atomic transaction with rollback on failure;
- deterministic JSON bytes;
- --check and --dry-run perform zero writes;
- credential/private-field leakage is a hard failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.defaults_foundry_core import (  # noqa: E402
    atomic_write_many,
    sha256_bytes,
    stable_json_bytes,
    validate_no_private_fields,
)

DEFAULTS_JSON_PATH = REPO_ROOT / "core" / "settings" / "defaults_snapshot.json"
DOCS_DIR = REPO_ROOT / "Docs"
EXPORT_TARGETS: tuple[tuple[str, str], ...] = (
    ("Screensaver", "SRPSS_Settings_Screensaver.sst"),
    ("Screensaver_MC", "SRPSS_Settings_Screensaver_MC.sst"),
)
GENERATED_METADATA = {
    "artifact_kind": "canonical_defaults",
    # Keep historical metadata stable so adopting the unified transaction does
    # not churn checked-in SST bytes for bookkeeping alone.
    "generator": "tools/regenerate_sst_defaults.py",
    "source": "core.settings.defaults_snapshot_builder.build_sst_defaults_snapshot",
}


def _runtime_builders():
    # Lazy import keeps module discovery/help free of SettingsManager creation.
    # The imported package may load Qt symbols, but this tool never constructs
    # SettingsManager, QSettings, JsonSettingsStore, or profile storage owners.
    from core.settings.defaults_snapshot_builder import (
        build_defaults_snapshot,
        build_sst_defaults_snapshot,
    )
    from core.settings.sst_io import SNAPSHOT_VERSION

    return build_defaults_snapshot, build_sst_defaults_snapshot, SNAPSHOT_VERSION


def _build_sst_payload(application: str) -> dict[str, Any]:
    # Single source of truth: the SST document is built by the one authority in
    # core.settings.defaults_snapshot_builder, not a second divergent payload
    # (which only differed by a metadata.generator string and drove spurious
    # snapshot-stale reports).
    from core.settings.defaults_snapshot_builder import (
        build_sst_defaults_document,
        build_sst_defaults_snapshot,
    )

    validate_no_private_fields(
        build_sst_defaults_snapshot(application),
        label=f"{application} canonical SST snapshot",
    )
    return build_sst_defaults_document(application)


def _validate_sst_payload(payload: Mapping[str, Any], application: str) -> None:
    if payload.get("application") != application or payload.get("profile") != application:
        raise ValueError(f"Generated SST profile mismatch for {application}")
    if payload.get("metadata") != GENERATED_METADATA:
        raise ValueError(f"Generated SST metadata is not deterministic for {application}")
    _build_defaults_snapshot, build_sst_defaults_snapshot, _snapshot_version = _runtime_builders()
    expected = build_sst_defaults_snapshot(application)
    if payload.get("snapshot") != expected:
        raise ValueError(f"Generated SST snapshot drifted from canonical {application} defaults")
    validate_no_private_fields(payload.get("snapshot", {}), label=f"{application} generated SST")


def build_artifact_bytes(
    *,
    defaults_json_path: Path = DEFAULTS_JSON_PATH,
    docs_dir: Path = DOCS_DIR,
    include_json: bool = True,
    include_sst: bool = True,
) -> dict[Path, bytes]:
    """Build and validate requested artifacts entirely in memory.

    Serialization is delegated to the single authority in
    ``core.settings.defaults_snapshot_builder`` so this tool, the runtime
    ``write_defaults_snapshot``/``write_sst_defaults_documents`` writers, and the
    ``defaults_authority_audit`` / parity tests all produce byte-identical
    artifacts. There is deliberately no second snapshot/SST serializer here -- a
    divergent format was exactly what made the checked-in snapshot flap between
    "stale" and GREEN depending on which tool wrote it last.
    """
    from core.settings.defaults_snapshot_builder import (
        build_defaults_snapshot,
        build_sst_defaults_snapshot,
        serialize_defaults_snapshot,
        serialize_sst_defaults_document,
    )

    payloads: dict[Path, bytes] = {}

    if include_json:
        validate_no_private_fields(
            build_defaults_snapshot("Screensaver"),
            label="canonical defaults JSON snapshot",
        )
        payloads[Path(defaults_json_path)] = serialize_defaults_snapshot().encode("utf-8")

    if include_sst:
        for application, filename in EXPORT_TARGETS:
            validate_no_private_fields(
                build_sst_defaults_snapshot(application),
                label=f"{application} canonical SST snapshot",
            )
            payloads[Path(docs_dir) / filename] = (
                serialize_sst_defaults_document(application).encode("utf-8")
            )

    return payloads


def _drift(payloads: Mapping[Path, bytes]) -> tuple[Path, ...]:
    return tuple(
        path
        for path, data in payloads.items()
        if not path.exists() or path.read_bytes() != data
    )


def regenerate_defaults_artifacts(
    *,
    defaults_json_path: Path = DEFAULTS_JSON_PATH,
    docs_dir: Path = DOCS_DIR,
    include_json: bool = True,
    include_sst: bool = True,
) -> tuple[Path, ...]:
    payloads = build_artifact_bytes(
        defaults_json_path=defaults_json_path,
        docs_dir=docs_dir,
        include_json=include_json,
        include_sst=include_sst,
    )
    result = atomic_write_many(payloads)
    return result.changed_paths


def _describe(payloads: Mapping[Path, bytes]) -> list[str]:
    lines: list[str] = []
    for path, data in payloads.items():
        status = "DRIFT" if not path.exists() or path.read_bytes() != data else "OK"
        lines.append(
            f"[{status}] {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path} "
            f"bytes={len(data)} sha256={sha256_bytes(data)}"
        )
    return lines


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate canonical SRPSS defaults artifacts safely")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail if checked-in artifacts drift; write nothing")
    mode.add_argument("--dry-run", action="store_true", help="Show generated hashes/drift; write nothing")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--json-only", action="store_true", help="Only handle core/settings/defaults_snapshot.json")
    scope.add_argument("--sst-only", action="store_true", help="Only handle the two Docs SST artifacts")
    parser.add_argument("--defaults-json", default=str(DEFAULTS_JSON_PATH))
    parser.add_argument("--docs-dir", default=str(DOCS_DIR))
    args = parser.parse_args(list(argv) if argv is not None else None)

    include_json = not args.sst_only
    include_sst = not args.json_only
    payloads = build_artifact_bytes(
        defaults_json_path=Path(args.defaults_json),
        docs_dir=Path(args.docs_dir),
        include_json=include_json,
        include_sst=include_sst,
    )
    for line in _describe(payloads):
        print(line)

    drift = _drift(payloads)
    if args.check:
        if drift:
            print("[DEFAULTS_ARTIFACTS][CHECK] drift=" + ", ".join(str(path) for path in drift), file=sys.stderr)
            return 1
        print("[DEFAULTS_ARTIFACTS][CHECK] GREEN")
        return 0
    if args.dry_run:
        print(f"[DEFAULTS_ARTIFACTS][DRY_RUN] changed={len(drift)} writes=0")
        return 0

    result = atomic_write_many(payloads)
    print(
        f"[DEFAULTS_ARTIFACTS][WRITE] targets={len(result.paths)} changed={len(result.changed_paths)} transactional=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

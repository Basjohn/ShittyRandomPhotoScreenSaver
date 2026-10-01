"""Regenerate SRPSS binary Qt resource packs through one selected PySide toolchain.

The QRC manifests and their referenced source assets remain the authoring source of
truth. Build Foundry and the standalone build workers compile those manifests into
raw binary ``.rcc`` packs. Runtime registers the packs with ``QResource`` so the
existing ``:/srpss/...`` namespace is unchanged without embedding tens of megabytes
of escaped resource bytes in generated Python source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
QRC_PATH = ROOT / "ui" / "resources" / "assets.qrc"
OUTPUT_PATH = ROOT / "ui" / "resources" / "assets.rcc"
_PROVENANCE_SCHEMA = 2
_IDENTITY_PROBE = (
    "from importlib.metadata import version; from pathlib import Path; import PySide6; "
    "from PySide6.QtCore import qVersion; "
    "print(';'.join(f'{name}={version(name)}' for name in "
    "('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6')) + "
    "f';Qt={qVersion()};rcc={Path(PySide6.__file__).parent / \"rcc.exe\"}')"
)
_QT_DISTRIBUTIONS = ("PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6")


class QrcRegenerationError(RuntimeError):
    """The selected Qt toolchain could not produce a usable binary resource pack."""


@dataclass(frozen=True)
class QrcStatus:
    current: bool
    reason: str
    input_paths: tuple[Path, ...]


@dataclass(frozen=True)
class QrcTarget:
    qrc_path: Path
    output_path: Path

    @property
    def provenance_path(self) -> Path:
        return self.output_path.with_name(self.output_path.name + ".provenance.json")


@dataclass(frozen=True)
class QrcToolchain:
    identity: str
    rcc_executable: Path


def resource_targets(repo_root: Path = ROOT) -> tuple[QrcTarget, ...]:
    """Return the ordinary and lazy-onboarding binary resource packs."""
    resource_root = repo_root / "ui" / "resources"
    return (
        QrcTarget(resource_root / "assets.qrc", resource_root / "assets.rcc"),
        QrcTarget(resource_root / "onboarding_assets.qrc", resource_root / "onboarding_assets.rcc"),
    )


def qrc_input_paths(qrc_path: Path = QRC_PATH) -> tuple[Path, ...]:
    """Return the manifest and every local source file it embeds."""
    if not qrc_path.is_file():
        raise QrcRegenerationError(f"QRC manifest is missing: {qrc_path}")
    try:
        root = ET.parse(qrc_path).getroot()
    except ET.ParseError as exc:
        raise QrcRegenerationError(f"QRC manifest is invalid: {qrc_path}: {exc}") from exc
    if root.tag != "RCC":
        raise QrcRegenerationError(f"QRC manifest root must be RCC: {qrc_path}")

    paths: list[Path] = [qrc_path]
    for entry in root.findall(".//file"):
        relative = (entry.text or "").strip()
        if not relative:
            raise QrcRegenerationError(f"QRC manifest has an empty <file>: {qrc_path}")
        source = (qrc_path.parent / relative).resolve()
        if not source.is_file():
            raise QrcRegenerationError(
                f"QRC source asset is missing or not a file: {source} (from {qrc_path})"
            )
        paths.append(source)
    if len(paths) == 1:
        raise QrcRegenerationError(f"QRC manifest declares no source assets: {qrc_path}")
    return tuple(paths)


def _digest_inputs(qrc_path: Path, input_paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in input_paths:
        relative = os.path.relpath(path, start=qrc_path.parent).replace("\\", "/")
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError as exc:
            raise QrcRegenerationError(f"Could not hash QRC input {path}: {exc}") from exc
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise QrcRegenerationError(f"Could not hash generated resource pack {path}: {exc}") from exc
    return digest.hexdigest()


def _read_provenance(target: QrcTarget) -> dict[str, object] | None:
    try:
        payload = json.loads(target.provenance_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def qrc_status(
    qrc_path: Path = QRC_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    toolchain_identity: str | None = None,
) -> QrcStatus:
    """Check content provenance for a raw binary ``.rcc`` pack."""
    target = QrcTarget(qrc_path, output_path)
    inputs = qrc_input_paths(qrc_path)
    if not output_path.is_file():
        return QrcStatus(False, f"Generated binary resource pack is missing: {output_path}", inputs)
    provenance = _read_provenance(target)
    if provenance is None:
        return QrcStatus(False, "Generated binary resource pack has no trusted provenance", inputs)
    if provenance.get("schema") != _PROVENANCE_SCHEMA:
        return QrcStatus(False, "Generated binary resource pack uses an unsupported provenance schema", inputs)
    if provenance.get("inputs_sha256") != _digest_inputs(qrc_path, inputs):
        return QrcStatus(False, "QRC manifest or source content changed", inputs)
    if toolchain_identity is not None:
        expected_toolchain = hashlib.sha256(toolchain_identity.encode("utf-8")).hexdigest()
        if provenance.get("toolchain_sha256") != expected_toolchain:
            return QrcStatus(False, "Selected PySide6 toolchain changed", inputs)
    if provenance.get("pack_sha256") != _sha256_file(output_path):
        return QrcStatus(False, "Generated binary resource pack content changed", inputs)
    try:
        expected_size = int(provenance.get("pack_bytes", -1))
    except (TypeError, ValueError):
        expected_size = -1
    if expected_size != output_path.stat().st_size:
        return QrcStatus(False, "Generated binary resource pack size changed", inputs)
    return QrcStatus(True, "QRC binary resource pack provenance is current", inputs)


def _temporary_output_path(output_path: Path) -> Path:
    return output_path.with_name(f".{output_path.name}.{os.getpid()}.qrc.tmp")


def _temporary_provenance_path(target: QrcTarget) -> Path:
    return target.provenance_path.with_name(f".{target.provenance_path.name}.{os.getpid()}.tmp")


def _selected_toolchain_identity(
    python_path: Path,
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> QrcToolchain:
    try:
        completed = run(
            [str(python_path), "-c", _IDENTITY_PROBE],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise QrcRegenerationError(
            f"Could not launch selected PySide6 toolchain {python_path}: {exc}"
        ) from exc
    identity = completed.stdout.strip()
    parts = dict(token.split("=", 1) for token in identity.split(";") if "=" in token)
    expected_version = _required_qt_version()
    expected_parts = (*_QT_DISTRIBUTIONS, "Qt")
    if (
        completed.returncode != 0
        or any(not parts.get(name) for name in expected_parts)
        or not parts.get("rcc")
        or any(parts[name] != expected_version for name in expected_parts)
    ):
        detail = completed.stderr.strip() or identity
        raise QrcRegenerationError(
            f"Selected Python does not satisfy pinned Qt {expected_version}: {python_path}"
            + (f": {detail}" if detail else "")
        )
    rcc_executable = Path(parts["rcc"])
    if not rcc_executable.is_file():
        raise QrcRegenerationError(
            f"Selected PySide6 rcc executable is missing: {rcc_executable}"
        )
    provenance_identity = ";".join(f"{name}={parts[name]}" for name in (*_QT_DISTRIBUTIONS, "Qt"))
    return QrcToolchain(provenance_identity, rcc_executable)


def _required_qt_version(requirements_path: Path = ROOT / "requirements.txt") -> str:
    """Read the single Qt pin authoritative for source and frozen workers."""
    if not requirements_path.is_file():
        raise QrcRegenerationError(f"Pinned requirements are missing: {requirements_path}")
    expected: dict[str, str] = {}
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if "==" not in line:
            continue
        name, version = (part.strip() for part in line.split("==", 1))
        if name in _QT_DISTRIBUTIONS:
            expected[name] = version
    missing = [name for name in _QT_DISTRIBUTIONS if name not in expected]
    versions = set(expected.values())
    if missing or len(versions) != 1:
        detail = ", ".join(missing) if missing else ", ".join(sorted(versions))
        raise QrcRegenerationError(f"requirements.txt has no coherent Qt pin: {detail}")
    return versions.pop()


def _compile_target(
    target: QrcTarget,
    *,
    toolchain: QrcToolchain,
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[Path, Path, str]:
    inputs = qrc_input_paths(target.qrc_path)
    input_digest = _digest_inputs(target.qrc_path, inputs)
    temporary_output = _temporary_output_path(target.output_path)
    temporary_provenance = _temporary_provenance_path(target)
    try:
        temporary_output.unlink(missing_ok=True)
        temporary_provenance.unlink(missing_ok=True)
        command = [
            str(toolchain.rcc_executable),
            "-binary",
            str(target.qrc_path),
            "-o",
            str(temporary_output),
        ]
        try:
            completed = run(
                command,
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise QrcRegenerationError(
                f"Could not launch selected PySide6 rcc toolchain {toolchain.rcc_executable}: {exc}"
            ) from exc
        if completed.returncode != 0:
            output = "\n".join(
                part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
            )
            raise QrcRegenerationError(
                f"PySide6 rcc failed with exit {completed.returncode} using {toolchain.rcc_executable}"
                + (f": {output}" if output else "")
            )
        if not temporary_output.is_file() or temporary_output.stat().st_size <= 0:
            raise QrcRegenerationError(
                f"PySide6 rcc reported success but produced no binary pack: {temporary_output}"
            )
        pack_sha256 = _sha256_file(temporary_output)
        provenance = {
            "schema": _PROVENANCE_SCHEMA,
            "qrc": target.qrc_path.name,
            "inputs_sha256": input_digest,
            "toolchain_sha256": hashlib.sha256(toolchain.identity.encode("utf-8")).hexdigest(),
            "pack_sha256": pack_sha256,
            "pack_bytes": temporary_output.stat().st_size,
        }
        temporary_provenance.write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return temporary_output, temporary_provenance, input_digest
    except Exception:
        temporary_output.unlink(missing_ok=True)
        temporary_provenance.unlink(missing_ok=True)
        raise


def ensure_qrc_targets_current(
    *,
    python_executable: Path | str,
    targets: Sequence[QrcTarget],
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[QrcStatus, ...]:
    """Compile every stale pack first, then publish the completed set.

    Compiler failure or an input mutation leaves all previous packs untouched.
    The provenance sidecar also hashes the final pack, so a partial filesystem
    publish is detected and repaired on the next invocation rather than trusted.
    """
    python_path = Path(python_executable)
    if not python_path.is_file():
        raise QrcRegenerationError(f"Selected Python toolchain is missing: {python_path}")
    toolchain = _selected_toolchain_identity(python_path, run)
    statuses = tuple(
        qrc_status(target.qrc_path, target.output_path, toolchain_identity=toolchain.identity)
        for target in targets
    )
    stale_targets = tuple(target for target, status in zip(targets, statuses) if not status.current)
    if not stale_targets:
        return statuses

    temporary_outputs: list[tuple[QrcTarget, Path, Path, str]] = []
    try:
        for target in stale_targets:
            target.output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_output, temporary_provenance, input_digest = _compile_target(
                target,
                toolchain=toolchain,
                run=run,
            )
            temporary_outputs.append((target, temporary_output, temporary_provenance, input_digest))
        for target, _temporary_output, _temporary_provenance, compiled_input_digest in temporary_outputs:
            current_input_digest = _digest_inputs(target.qrc_path, qrc_input_paths(target.qrc_path))
            if current_input_digest != compiled_input_digest:
                raise QrcRegenerationError(
                    f"QRC inputs changed during regeneration: {target.qrc_path}"
                )
        for target, temporary_output, temporary_provenance, _compiled_input_digest in temporary_outputs:
            temporary_output.replace(target.output_path)
            temporary_provenance.replace(target.provenance_path)
    finally:
        for _target, temporary_output, temporary_provenance, _compiled_input_digest in temporary_outputs:
            for path in (temporary_output, temporary_provenance):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
    final_statuses = tuple(
        qrc_status(target.qrc_path, target.output_path, toolchain_identity=toolchain.identity)
        for target in targets
    )
    stale = next((status for status in final_statuses if not status.current), None)
    if stale is not None:
        raise QrcRegenerationError(
            f"QRC regeneration did not establish current binary provenance: {stale.reason}"
        )
    return final_statuses


def regenerate_qrc(
    *,
    python_executable: Path | str,
    qrc_path: Path = QRC_PATH,
    output_path: Path = OUTPUT_PATH,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> QrcStatus:
    return ensure_qrc_targets_current(
        python_executable=python_executable,
        targets=(QrcTarget(qrc_path, output_path),),
        run=run,
    )[0]


def ensure_qrc_current(
    *,
    python_executable: Path | str,
    qrc_path: Path = QRC_PATH,
    output_path: Path = OUTPUT_PATH,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> QrcStatus:
    return regenerate_qrc(
        python_executable=python_executable,
        qrc_path=qrc_path,
        output_path=output_path,
        run=run,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--qrc", type=Path, help="operate on one explicit manifest")
    parser.add_argument("--output", type=Path, help="binary .rcc output for --qrc")
    parser.add_argument("--check", action="store_true", help="fail if regeneration is needed")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.qrc is None and args.output is not None:
        print("QRC regeneration failed: --output requires --qrc", file=sys.stderr)
        return 2
    targets = (
        (QrcTarget(args.qrc, args.output or OUTPUT_PATH),)
        if args.qrc is not None
        else resource_targets()
    )
    try:
        if args.check:
            python_path = Path(args.python)
            toolchain = _selected_toolchain_identity(python_path, subprocess.run)
            statuses = tuple(
                qrc_status(target.qrc_path, target.output_path, toolchain_identity=toolchain.identity)
                for target in targets
            )
            stale = next((status for status in statuses if not status.current), None)
            if stale is not None:
                print(stale.reason, file=sys.stderr)
                return 1
        else:
            statuses = ensure_qrc_targets_current(
                python_executable=args.python,
                targets=targets,
            )
    except QrcRegenerationError as exc:
        print(f"QRC regeneration failed: {exc}", file=sys.stderr)
        return 1
    asset_count = sum(len(status.input_paths) - 1 for status in statuses)
    print(f"QRC binary resource packs are current; {len(statuses)} packs, {asset_count} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

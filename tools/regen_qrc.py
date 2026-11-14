"""Regenerate SRPSS binary Qt resource packs through one selected PySide toolchain.

The QRC manifests and their referenced source assets remain the authoring source of
truth. Build Foundry and the standalone build workers compile those manifests into
raw binary ``.rcc`` packs. Runtime registers the packs with ``QResource`` so the
existing ``:/srpss/...`` namespace is unchanged without embedding tens of megabytes
of escaped resource bytes in generated Python source.

``--shaders`` bakes the Qt Quick shader packs instead (``rendering/quick/qml/shaders``:
every ``.vert``/``.frag`` there, discovered, its ``.qsb`` beside it, committed) with the
same toolchain's ``qsb``, for every target the product ships: SPIR-V (Vulkan), the GLSL
of the product's OpenGL 4.6 context, and the shipped targets of
``tools/vulkan_shader_readiness.py`` (GLSL 430, HLSL 5.0, MSL 1.2). ``--shaders --check``
fails when a committed pack is not what its source bakes to.
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
# The probe runs inside the selected interpreter, so it names that interpreter's wheel layout:
# Windows wheels ship ``PySide6/rcc.exe``; Linux wheels ship ``PySide6/Qt/libexec/rcc``.
_IDENTITY_PROBE = (
    "import sys; from importlib.metadata import version; from pathlib import Path; import PySide6; "
    "from PySide6.QtCore import qVersion; "
    "rcc_rel = 'rcc.exe' if sys.platform == 'win32' else 'Qt/libexec/rcc'; "
    "print(';'.join(f'{name}={version(name)}' for name in "
    "('PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6')) + "
    "f';Qt={qVersion()};rcc={Path(PySide6.__file__).parent / rcc_rel}')"
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


# ---- the Qt Quick shader packs ---------------------------------------------------------------------------------------

QUICK_SHADER_SUFFIXES = (".vert", ".frag")


@dataclass(frozen=True)
class QuickShaderStatus:
    source: Path
    pack: Path
    current: bool
    reason: str


def quick_shader_dir(repo_root: Path = ROOT) -> Path:
    """Where the Qt Quick ``ShaderEffect`` sources live; each pack (``<source>.qsb``) is committed beside its source."""
    return repo_root / "rendering" / "quick" / "qml" / "shaders"


def mode_shader_dir(repo_root: Path = ROOT) -> Path:
    """Where the Visualizer modes' fragment shaders live (the Python renderers compile them there; the native core
    loads their packs at run time, N2.5's standing port rule): each pack (``<source>.qsb``) committed beside it."""
    return repo_root / "widgets" / "spotify_visualizer" / "shaders"


def quick_shader_sources(shader_dir: Path | None = None) -> tuple[Path, ...]:
    """Every shader source the product bakes (discovered, never listed): the Qt Quick ``ShaderEffect`` sources and
    the Visualizer modes' fragment shaders; ``shader_dir``: one folder's instead."""
    if shader_dir is not None:
        folders = (Path(shader_dir),)
    else:
        folders = (quick_shader_dir(), mode_shader_dir())
    return tuple(sorted(path for folder in folders for path in folder.iterdir()
                        if path.suffix in QUICK_SHADER_SUFFIXES))


def quick_shader_targets() -> tuple[str, ...]:
    """The ``qsb`` target arguments of every Qt Quick shader pack.

    SPIR-V is qsb's own and always baked (Vulkan). Then the GLSL of the product's OpenGL context (4.6 core,
    ``rendering.quick.bootstrap.QUICK_GLSL_VERSION``) first: Qt's OpenGL backend draws with the highest GLSL a pack
    holds that its context runs, so the product's OpenGL path keeps the variant it drew with before every other
    target was added. Then the shipped backends' targets of ``tools/vulkan_shader_readiness.py`` (GLSL 430, HLSL 5.0,
    MSL 1.2), from that one source.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from rendering.quick.bootstrap import QUICK_GLSL_VERSION
    from tools.vulkan_shader_readiness import QSB_TARGETS

    shipped = dict(zip(QSB_TARGETS[0::2], QSB_TARGETS[1::2]))
    product_glsl = f"{QUICK_GLSL_VERSION[0]}{QUICK_GLSL_VERSION[1]:02d}"
    glsl = ",".join(dict.fromkeys((product_glsl, *shipped.pop("--glsl", "").split(","))))
    targets = ["--glsl", glsl]
    for flag, versions in shipped.items():
        targets += [flag, versions]
    return tuple(targets)


def quick_shader_baker(
    python_executable: Path | str,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    """The ``qsb`` of the selected (pinned) PySide6 toolchain, beside its ``rcc``."""
    toolchain = _selected_toolchain_identity(Path(python_executable), run)
    qsb = toolchain.rcc_executable.with_name("qsb" + toolchain.rcc_executable.suffix)
    if not qsb.is_file():
        raise QrcRegenerationError(f"Selected PySide6 qsb executable is missing: {qsb}")
    return qsb


def _composed_shader(source: Path, folder: Path) -> Path:
    """``source`` as it compiles (its ``#include`` lines and conventions marker expanded,
    ``widgets.spotify_visualizer.shaders.compose_shader_source``), written into ``folder`` under its own name: qsb
    has no include path. A source with neither is baked as it is."""
    text = source.read_text(encoding="utf-8")
    if "//@srpss_conventions" not in text and "#include" not in text:
        return source
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from widgets.spotify_visualizer.shaders import compose_shader_source

    composed = Path(folder) / "composed" / source.name
    composed.parent.mkdir(parents=True, exist_ok=True)
    composed.write_text(compose_shader_source(source), encoding="utf-8")
    return composed


def _bake_quick_shader(
    qsb: Path,
    source: Path,
    output: Path,
    targets: Sequence[str],
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    import tempfile

    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="srpss_compose_") as folder:
        baked = _composed_shader(source, Path(folder))
        completed = run([str(qsb), *targets, str(baked), "-o", str(output)], cwd=str(ROOT), check=False,
                        capture_output=True, text=True)
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
        detail = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part and part.strip())
        raise QrcRegenerationError(f"qsb failed for {source.name} (exit {completed.returncode})"
                                   + (f": {detail}" if detail else ""))


def quick_shader_status(
    *,
    qsb: Path,
    shader_dir: Path | None = None,
    targets: Sequence[str] | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[QuickShaderStatus, ...]:
    """Whether each committed pack is exactly what its source bakes to (qsb is deterministic)."""
    import tempfile

    targets = tuple(quick_shader_targets() if targets is None else targets)
    statuses = []
    with tempfile.TemporaryDirectory(prefix="srpss_qsb_") as folder:
        for source in quick_shader_sources(shader_dir):
            pack = source.with_name(source.name + ".qsb")
            fresh = Path(folder) / pack.name
            _bake_quick_shader(qsb, source, fresh, targets, run)
            if not pack.is_file():
                statuses.append(QuickShaderStatus(source, pack, False, "the pack is missing"))
            elif pack.read_bytes() != fresh.read_bytes():
                statuses.append(QuickShaderStatus(source, pack, False,
                                                  "the pack is not what its source bakes to for every target"))
            else:
                statuses.append(QuickShaderStatus(source, pack, True, "current"))
    return tuple(statuses)


def bake_quick_shaders(
    *,
    qsb: Path,
    shader_dir: Path | None = None,
    targets: Sequence[str] | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[QuickShaderStatus, ...]:
    """Bake every stale pack beside its source (a temporary file replaced into place); returns the final status."""
    targets = tuple(quick_shader_targets() if targets is None else targets)
    for status in quick_shader_status(qsb=qsb, shader_dir=shader_dir, targets=targets, run=run):
        if status.current:
            continue
        temporary = status.pack.with_name(f".{status.pack.name}.{os.getpid()}.tmp")
        try:
            _bake_quick_shader(qsb, status.source, temporary, targets, run)
            temporary.replace(status.pack)
        finally:
            temporary.unlink(missing_ok=True)
    final = quick_shader_status(qsb=qsb, shader_dir=shader_dir, targets=targets, run=run)
    stale = next((status for status in final if not status.current), None)
    if stale is not None:
        raise QrcRegenerationError(f"{stale.pack.name}: {stale.reason} after its bake")
    return final


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--qrc", type=Path, help="operate on one explicit manifest")
    parser.add_argument("--output", type=Path, help="binary .rcc output for --qrc")
    parser.add_argument("--check", action="store_true", help="fail if regeneration is needed")
    parser.add_argument("--shaders", action="store_true",
                        help="the shader packs (rendering/quick/qml/shaders and the Visualizer modes' "
                             "widgets/spotify_visualizer/shaders) instead of the .rcc packs")
    return parser.parse_args(argv)


def _main_shaders(args: argparse.Namespace) -> int:
    try:
        qsb = quick_shader_baker(args.python)
        if args.check:
            stale = [status for status in quick_shader_status(qsb=qsb) if not status.current]
            for status in stale:
                print(f"{status.pack.name}: {status.reason}", file=sys.stderr)
            if stale:
                return 1
            statuses = quick_shader_status(qsb=qsb)
        else:
            statuses = bake_quick_shaders(qsb=qsb)
    except QrcRegenerationError as exc:
        print(f"Quick shader bake failed: {exc}", file=sys.stderr)
        return 1
    print(f"Quick shader packs are current for {' '.join(quick_shader_targets())} (and SPIR-V); "
          f"{len(statuses)} packs")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.shaders:
        if args.qrc is not None or args.output is not None:
            print("Quick shader bake failed: --shaders takes no --qrc or --output", file=sys.stderr)
            return 2
        return _main_shaders(args)
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

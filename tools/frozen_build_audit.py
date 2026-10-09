"""Operator-build-only frozen module audit and deterministic source provenance.

No imports from the application or Qt; this tool runs from the build scripts,
never inside the screensaver. It deliberately cannot attest to physical runtime
behaviour or identify a Windows-installed copy of an SCR.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Only material that can contribute to a frozen runtime belongs here. Generated
# build outputs, caches, tests, log files and the .venv must not influence identity.
_SOURCE_ROOTS = (
    "core", "engine", "helpers", "rendering", "sources", "ui", "utilities",
    "utils", "weather", "widgets", "presets", "themes", "resources",
)
_SOURCE_SUFFIXES = frozenset({
    ".py", ".qml", ".js", ".json", ".qrc", ".rcc", ".frag", ".vert",
    ".geom", ".glsl", ".png", ".svg", ".jpg", ".jpeg", ".webp",
    ".ogg", ".mp3", ".ico", ".ttf", ".otf", ".wav", ".xml",
})
_ROOT_SOURCES = ("main.py", "main_mc.py", "main_diagnostic.py", "versioning.py", "SRPSS.ico")
_REQUIRED_MODULES = frozenset({
    "rendering.quick.context_menu",
    "engine.display_manager",
    "engine.screensaver_engine",
    "engine.image_queue",
    "core.sources.image_bans",
})


def _tracked_sources(root: Path) -> list[Path]:
    result = [root / name for name in _ROOT_SOURCES if (root / name).is_file()]
    for directory in _SOURCE_ROOTS:
        base = root / directory
        if base.is_dir():
            result.extend(
                p for p in base.rglob("*")
                if p.is_file() and p.suffix.lower() in _SOURCE_SUFFIXES
                and not any(part in {"__pycache__", ".venv", "cache", "build", "release"} for part in p.relative_to(root).parts)
            )
    # Critical build configuration participates in the runtime identity.
    result.extend(
        p for p in (
            root / "requirements.txt",
            root / "scripts" / "venv" / "build_nuitka.ps1",
            root / "scripts" / "venv" / "build_nuitka_mc_onedir.ps1",
            root / "tools" / "build_layout.ps1",
            root / "tools" / "frozen_build_audit.py",
        ) if p.is_file()
    )
    return sorted(set(result), key=lambda p: p.relative_to(root).as_posix())


def source_fingerprint(root: Path) -> tuple[str, int]:
    files = _tracked_sources(root)
    if not files or not (root / "main.py").is_file():
        raise ValueError("A valid SRPSS source tree containing main.py is required")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        contents = path.read_bytes()
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(hashlib.sha256(contents).digest())
    return digest.hexdigest(), len(files)


def included_modules(report: Path) -> set[str]:
    # iterparse does not materialize a large Nuitka XML tree in memory.
    names: set[str] = set()
    with report.open("rb") as stream:
        for _, element in ET.iterparse(stream, events=("start",)):
            if element.tag == "module" and element.get("name"):
                names.add(element.attrib["name"])
    return names


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_report(root: Path, report: Path, expected: str) -> dict[str, object]:
    fingerprint, file_count = source_fingerprint(root)
    if fingerprint[:20] != expected:
        raise ValueError("The source changed while Nuitka was compiling; refusing publication")
    present = included_modules(report)
    absent = sorted(_REQUIRED_MODULES - present)
    if absent:
        raise ValueError("Nuitka omitted critical SRPSS runtime modules: " + ", ".join(absent))
    return {
        "schema_version": 1,
        "source_sha256": fingerprint,
        "source_file_count": file_count,
        "required_compiled_modules": sorted(_REQUIRED_MODULES),
        "nuitka_report_sha256": _sha256_file(report),
        "nuitka_report_path": str(report),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fingerprint", "verify", "compare"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--expected", default="")
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            if args.receipt is None or args.artifact is None:
                parser.error("compare requires --receipt and --artifact")
            receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
            expected_hash = receipt.get("artifact_sha256")
            if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                raise ValueError("Frozen receipt does not contain a valid artifact SHA-256")
            actual_hash = _sha256_file(args.artifact)
            if actual_hash != expected_hash:
                print(f"[FROZEN-AUDIT] MISMATCH: {args.artifact} differs from build receipt", file=sys.stderr)
                print(f"[FROZEN-AUDIT] Expected: {expected_hash}", file=sys.stderr)
                print(f"[FROZEN-AUDIT] Actual:   {actual_hash}", file=sys.stderr)
                return 1
            print(f"[FROZEN-AUDIT] MATCH: {args.artifact} has the compiled build's exact SHA-256")
            return 0
        if args.root is None:
            parser.error(f"{args.command} requires --root")
        root = args.root.resolve(strict=True)
        if args.command == "fingerprint":
            print(source_fingerprint(root)[0][:20])
            return 0
        if not args.report or not args.expected or not args.artifact or not args.receipt:
            parser.error("verify requires --report, --expected, --artifact and --receipt")
        proof = verify_report(root, args.report, args.expected)
        proof["artifact_path"] = str(args.artifact.resolve(strict=True))
        proof["artifact_sha256"] = _sha256_file(args.artifact)
        proof["artifact_bytes"] = args.artifact.stat().st_size
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        print("[FROZEN-AUDIT] Critical menu/image-ban modules included; source and artifact fingerprint recorded")
        print(f"[FROZEN-AUDIT] Receipt: {args.receipt}")
        return 0
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"[FROZEN-AUDIT] FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

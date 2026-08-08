"""CLI for deterministic visualizer replay, protected goldens, and review art."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from widgets.spotify_visualizer.feature_frame import (  # noqa: E402
    canonical_json,
)
from widgets.spotify_visualizer.replay_runtime import (  # noqa: E402
    BASELINE_BEHAVIOR_COMMIT,
    MODE_ORDER,
    REPLAY_SCHEMA_VERSION,
    replay_v1_authored_preset_payload,
    replay_directory,
)


DEFAULT_INPUTS = ROOT / "tests" / "fixtures" / "visualizer_replay" / "v1"
DEFAULT_GOLDENS = ROOT / "tests" / "goldens" / "visualizer_replay" / "v1"
DEFAULT_ARTIFACTS = ROOT / "Docs" / "phase_reports" / "artifacts" / "P02"
GOLDEN_MANIFEST_NAME = "manifest.json"
GOLDEN_SCHEMA_VERSION = 1
CAPTURE_CHECKPOINT = "5ad5781de8d8fdbbdc43c761d5b047d386d784db"
FLOAT_NORMALIZATION_DIGITS = 7


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload) + b"\n")


def _golden_path(root: Path, name: str) -> Path:
    return root / f"{name}.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authored_preset_hashes() -> dict[str, str]:
    hashes = {}
    for mode in MODE_ORDER:
        hashes[mode] = hashlib.sha256(
            canonical_json(replay_v1_authored_preset_payload(mode))
        ).hexdigest()
    return hashes


def build_golden_manifest(
    outputs: Mapping[str, Any],
    *,
    input_dir: Path | None = None,
) -> dict[str, Any]:
    fixture_manifest = input_dir / "manifest.json" if input_dir else None
    output_entries = []
    for name, output in sorted(outputs.items()):
        modes = sorted(
            {
                str(frame.get("mode", ""))
                for frame in output.get("frames", [])
            }
        )
        output_entries.append(
            {
                "name": name,
                "source_clip": output.get("source_clip", name),
                "input_sha256": output.get("input_sha256", ""),
                "effective_input_sha256": output.get(
                    "effective_input_sha256",
                    "",
                ),
                "logical_digest": output.get("digest", ""),
                "frames": len(output.get("frames", [])),
                "modes": modes,
            }
        )

    return {
        "golden_schema_version": GOLDEN_SCHEMA_VERSION,
        "replay_schema_version": REPLAY_SCHEMA_VERSION,
        "baseline_behavior_commit": BASELINE_BEHAVIOR_COMMIT,
        "capture_checkpoint": CAPTURE_CHECKPOINT,
        "comparison_policy": {
            "float_normalization_digits": FLOAT_NORMALIZATION_DIGITS,
            "comparison": "exact canonical JSON after normalization",
        },
        "fixture_manifest_sha256": (
            _sha256_file(fixture_manifest)
            if fixture_manifest is not None and fixture_manifest.is_file()
            else ""
        ),
        "authored_preset_zero_sha256": _authored_preset_hashes(),
        "outputs": output_entries,
    }


def verify_outputs(
    outputs: Mapping[str, Any],
    golden_dir: Path,
) -> list[str]:
    """Compare output files without writing and return drift descriptions."""
    errors: list[str] = []
    for name, output in sorted(outputs.items()):
        path = _golden_path(golden_dir, name)
        if not path.is_file():
            errors.append(f"{name}: missing golden {path}")
            continue
        try:
            expected = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{name}: invalid golden: {exc}")
            continue
        if expected != output:
            errors.append(
                f"{name}: golden drift "
                f"expected={expected.get('digest', '<none>')} "
                f"actual={output.get('digest', '<none>')}"
            )

    expected_names = set(outputs)
    extras = sorted(
        path.stem
        for path in golden_dir.glob("*.json")
        if path.name != GOLDEN_MANIFEST_NAME and path.stem not in expected_names
    )
    errors.extend(
        f"{name}: golden has no matching input fixture" for name in extras
    )
    return errors


def verify_golden_manifest(
    outputs: Mapping[str, Any],
    golden_dir: Path,
    *,
    input_dir: Path | None = None,
) -> list[str]:
    path = golden_dir / GOLDEN_MANIFEST_NAME
    if not path.is_file():
        return [f"missing golden manifest: {path}"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid golden manifest: {exc}"]
    expected = build_golden_manifest(outputs, input_dir=input_dir)
    if actual != expected:
        return ["golden manifest drift"]
    return []


def bootstrap_goldens(
    outputs: Mapping[str, Any],
    golden_dir: Path,
    *,
    baseline_acknowledged: bool,
    input_dir: Path | None = None,
) -> None:
    if not baseline_acknowledged:
        raise PermissionError("bootstrap requires --acknowledge-baseline")
    if golden_dir.exists() and any(golden_dir.iterdir()):
        raise FileExistsError(
            f"bootstrap refuses to overwrite non-empty directory: {golden_dir}"
        )

    for name, output in sorted(outputs.items()):
        _write_json(_golden_path(golden_dir, name), output)
    _write_json(
        golden_dir / GOLDEN_MANIFEST_NAME,
        build_golden_manifest(outputs, input_dir=input_dir),
    )


def _approved_change_declaration(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    fields = {
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
    }
    return "approved: true" in fields and "goldens: true" in fields


def update_goldens(
    outputs: Mapping[str, Any],
    golden_dir: Path,
    *,
    behavior_change_acknowledged: bool,
    change_declaration: Path | None,
    input_dir: Path | None = None,
) -> None:
    if not behavior_change_acknowledged:
        raise PermissionError("update requires --acknowledge-behavior-change")
    if not _approved_change_declaration(change_declaration):
        raise PermissionError(
            "update requires an approved change declaration containing "
            "exact lines 'approved: true' and 'goldens: true'"
        )

    for name, output in sorted(outputs.items()):
        _write_json(_golden_path(golden_dir, name), output)
    _write_json(
        golden_dir / GOLDEN_MANIFEST_NAME,
        build_golden_manifest(outputs, input_dir=input_dir),
    )


def _select_output(
    outputs: Mapping[str, Any],
    *,
    mode: str,
) -> tuple[str, Mapping[str, Any]]:
    preferred = f"representative_music_features__{mode}"
    if preferred in outputs:
        return preferred, outputs[preferred]
    for name, output in sorted(outputs.items()):
        if name.endswith(f"__{mode}"):
            return name, output
    raise ValueError(f"no {mode} replay output is available")


def _sample_frames(
    output: Mapping[str, Any],
    count: int = 12,
) -> list[Mapping[str, Any]]:
    frames = list(output.get("frames", []))
    if len(frames) <= count:
        return frames
    return [
        frames[round(index * (len(frames) - 1) / (count - 1))]
        for index in range(count)
    ]


def _new_contact_sheet() -> tuple[QImage, QPainter]:
    """Create a font-independent sheet for deterministic offscreen rendering."""
    image = QImage(1200, 560, QImage.Format_ARGB32)
    image.fill(QColor("#101014"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    return image, painter


def _cell_rect(index: int) -> QRectF:
    column = index % 4
    row = index // 4
    return QRectF(24 + column * 292, 12 + row * 180, 276, 164)


def _draw_spectrum_sheet(
    name: str,
    output: Mapping[str, Any],
    path: Path,
) -> None:
    image, painter = _new_contact_sheet()
    for index, frame in enumerate(_sample_frames(output)):
        rect = _cell_rect(index)
        painter.fillRect(rect, QColor("#191923"))
        bars = list(frame.get("overlay", {}).get("bars", []))
        if bars:
            gap = 1.0
            width = max(1.0, (rect.width() - gap * (len(bars) - 1)) / len(bars))
            for bar_index, value in enumerate(bars):
                height = max(0.0, min(1.0, float(value))) * (rect.height() - 22)
                bar_rect = QRectF(
                    rect.left() + bar_index * (width + gap),
                    rect.bottom() - height - 16,
                    width,
                    height,
                )
                painter.fillRect(bar_rect, QColor("#73d5ff"))

    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise OSError(f"failed to write artifact: {path}")


def _draw_bubble_sheet(
    name: str,
    output: Mapping[str, Any],
    path: Path,
) -> None:
    image, painter = _new_contact_sheet()
    painter.setBrush(QColor(80, 190, 255, 38))
    painter.setPen(QPen(QColor("#9de4ff"), 1.0))
    for index, frame in enumerate(_sample_frames(output)):
        rect = _cell_rect(index)
        painter.fillRect(rect, QColor("#191923"))
        particles = frame.get("bubble_simulation", {}).get("particles", [])
        for particle in particles:
            x = max(-0.1, min(1.1, float(particle.get("x", 0.5))))
            y = max(-0.1, min(1.1, float(particle.get("y", 0.5))))
            radius = max(
                float(particle.get("radius", 0.0)),
                float(particle.get("display_radius", 0.0)),
            )
            radius_px = max(1.5, min(22.0, radius * rect.height() * 3.2))
            center_x = rect.left() + x * rect.width()
            center_y = rect.top() + y * rect.height()
            painter.drawEllipse(
                QRectF(
                    center_x - radius_px,
                    center_y - radius_px,
                    radius_px * 2.0,
                    radius_px * 2.0,
                )
            )

    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise OSError(f"failed to write artifact: {path}")


def write_artifacts(
    outputs: Mapping[str, Any],
    output_dir: Path,
) -> list[Path]:
    """Write deterministic logical Spectrum/Bubble review contact sheets."""
    spectrum_name, spectrum = _select_output(outputs, mode="spectrum")
    bubble_name, bubble = _select_output(outputs, mode="bubble")
    spectrum_path = output_dir / "spectrum_logical_contact_sheet.png"
    bubble_path = output_dir / "bubble_logical_contact_sheet.png"
    _draw_spectrum_sheet(spectrum_name, spectrum, spectrum_path)
    _draw_bubble_sheet(bubble_name, bubble, bubble_path)

    html_path = output_dir / "spectrum_bubble_review.html"
    document = (
        "<!doctype html><meta charset='utf-8'>"
        "<title>SRPSS Phase 2 visualizer baseline</title>"
        "<style>body{background:#101014;color:#eee;font:14px system-ui}"
        "img{display:block;max-width:100%;margin:16px 0}</style>"
        "<h1>SRPSS Phase 2 logical-state review</h1>"
        "<p>These contact sheets render captured production logical state. "
        "They are not OpenGL shader screenshots. Frames are sampled "
        "chronologically, left-to-right and top-to-bottom.</p>"
        f"<h2>{html.escape(spectrum_name)}</h2>"
        f"<img src='{spectrum_path.name}'>"
        f"<h2>{html.escape(bubble_name)}</h2>"
        f"<img src='{bubble_path.name}'>"
    )
    html_path.write_text(document, encoding="utf-8")
    return [spectrum_path, bubble_path, html_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "verify",
            "bootstrap-goldens",
            "update-goldens",
            "artifacts",
            "metrics",
        ),
    )
    parser.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--goldens", type=Path, default=DEFAULT_GOLDENS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--acknowledge-baseline", action="store_true")
    parser.add_argument("--acknowledge-behavior-change", action="store_true")
    parser.add_argument("--change-declaration", type=Path)
    return parser


def _validate_mutating_command(arguments: argparse.Namespace) -> None:
    if (
        arguments.command == "bootstrap-goldens"
        and not arguments.acknowledge_baseline
    ):
        raise PermissionError("bootstrap requires --acknowledge-baseline")
    if arguments.command == "update-goldens":
        if not arguments.acknowledge_behavior_change:
            raise PermissionError(
                "update requires --acknowledge-behavior-change"
            )
        if not _approved_change_declaration(arguments.change_declaration):
            raise PermissionError(
                "update requires an approved change declaration containing "
                "exact lines 'approved: true' and 'goldens: true'"
            )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        _validate_mutating_command(arguments)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    outputs = replay_directory(arguments.inputs)
    if not outputs:
        print(f"No .jsonl fixtures found in {arguments.inputs}", file=sys.stderr)
        return 2

    try:
        if arguments.command == "verify":
            errors = verify_outputs(outputs, arguments.goldens)
            errors.extend(
                verify_golden_manifest(
                    outputs,
                    arguments.goldens,
                    input_dir=arguments.inputs,
                )
            )
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            print(f"verified {len(outputs)} replay goldens and manifest")
        elif arguments.command == "bootstrap-goldens":
            bootstrap_goldens(
                outputs,
                arguments.goldens,
                baseline_acknowledged=arguments.acknowledge_baseline,
                input_dir=arguments.inputs,
            )
            print(f"bootstrapped {len(outputs)} replay goldens")
        elif arguments.command == "update-goldens":
            update_goldens(
                outputs,
                arguments.goldens,
                behavior_change_acknowledged=(
                    arguments.acknowledge_behavior_change
                ),
                change_declaration=arguments.change_declaration,
                input_dir=arguments.inputs,
            )
            print(f"updated {len(outputs)} replay goldens")
        elif arguments.command == "artifacts":
            for path in write_artifacts(outputs, arguments.output_dir):
                print(path)
        else:
            metrics = {
                name: output["metrics"]
                for name, output in sorted(outputs.items())
            }
            print(json.dumps(metrics, indent=2, sort_keys=True))
    except (PermissionError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""SRPSS recovery evidence parser compatibility front-end, parser 1.21.

This intentionally reuses the repository's parser 1.20 for all established
telemetry parsing and adds compatibility for the polished ``screensaver.log``
presentation introduced by the logging-only formatting change.

Run exactly like the existing parser, for example:

    python tools/recovery_evidence_parser_1_21.py --source logs --output-dir analysis

Old canonical logs remain supported because parser 1.20 remains the underlying
authority.  The compatibility layer only:
  * recognizes fancy WARNING / ERROR / CRITICAL cards in screensaver.log;
  * reconstructs their canonical logical record for errors_and_warnings.txt;
  * removes presentation-only borders/header rows from unknown_lines.txt;
  * reports parser_version=1.21.

All PERF, usage, lifecycle, cache, visualizer and Phase-5 telemetry remains parsed
by the existing repository parser without semantic changes.
"""
from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from typing import Mapping, Sequence

try:
    # Running directly from tools/.
    import recovery_evidence_parser as _base
except ImportError:  # pragma: no cover - package/module invocation fallback
    from tools import recovery_evidence_parser as _base  # type: ignore


PARSER_VERSION = "1.21"

_FANCY_HEADER_RE = re.compile(
    r"^[╭╔][─═]{3}\s+"
    r"(?:(?P<warning>⚠\s+WARNING)|(?P<error>✖\s+ERROR)|(?P<critical>☠\s+CRITICAL))"
)
_FANCY_META_RE = re.compile(
    r"^│\s{2}(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+·\s+(?P<source>.+?)\s*$"
)
_OLD_ERROR_PREFIX_RE = re.compile(r"^(?P<source>.+?):(?P<line>\d+): ")
_UNKNOWN_PREFIX_RE = _OLD_ERROR_PREFIX_RE

_RULE_CHARS = frozenset("━═─╭╮╰╯╔╗╚╝├┤╠╣│ ")
_COLUMN_HEADER = "TIME                │ LEVEL    │ SOURCE                         │ EVENT"


def _severity_from_header(line: str) -> str | None:
    match = _FANCY_HEADER_RE.match(line)
    if not match:
        return None
    if match.group("critical"):
        return "CRITICAL"
    if match.group("error"):
        return "ERROR"
    return "WARNING"


def _is_presentation_only_line(line: str) -> bool:
    """Return True only for human decoration, never for diagnostic payload."""

    stripped = line.strip()
    if not stripped:
        return True
    if stripped == _COLUMN_HEADER.strip():
        return True
    if "SRPSS MAIN LOG" in stripped and stripped.startswith("━"):
        return True
    # Pure box/rule rows have no alphanumeric payload.
    if set(stripped) <= _RULE_CHARS:
        return True
    return False


def _parse_prefixed_reference(value: str) -> tuple[str, int] | None:
    match = _OLD_ERROR_PREFIX_RE.match(value)
    if not match:
        return None
    return match.group("source"), int(match.group("line"))


def _collect_fancy_main_cards(
    logs: Mapping[str, Sequence[str]],
) -> tuple[list[str], set[tuple[str, int]], set[tuple[str, int]]]:
    """Collect fancy severity cards and all presentation-owned line references.

    Returns:
        normalized_errors:
            Canonical logical warning/error records suitable for the existing
            ``errors_and_warnings.txt`` artifact.
        card_lines:
            Every physical line owned by a parsed severity card.
        presentation_lines:
            Card lines plus decorative main-log banner/header/rule rows.
    """

    normalized_errors: list[str] = []
    card_lines: set[tuple[str, int]] = set()
    presentation_lines: set[tuple[str, int]] = set()

    for log_name, lines in logs.items():
        if log_name != "screensaver.log":
            continue

        for line_number, line in enumerate(lines, 1):
            if _is_presentation_only_line(line):
                presentation_lines.add((log_name, line_number))

        index = 0
        while index < len(lines):
            header = lines[index]
            level = _severity_from_header(header)
            if level is None:
                index += 1
                continue

            start_index = index
            start_line = start_index + 1
            refs: list[tuple[str, int]] = [(log_name, start_line)]

            # Meta line should immediately follow the header.
            meta_index = index + 1
            if meta_index >= len(lines):
                index += 1
                continue
            meta = _FANCY_META_RE.match(lines[meta_index])
            if meta is None:
                index += 1
                continue
            refs.append((log_name, meta_index + 1))

            timestamp = meta.group("timestamp")
            source = meta.group("source").strip()

            # Divider.
            divider_index = meta_index + 1
            if divider_index >= len(lines) or not lines[divider_index].startswith(("├", "╠")):
                index += 1
                continue
            refs.append((log_name, divider_index + 1))

            body: list[str] = []
            cursor = divider_index + 1
            footer_found = False
            while cursor < len(lines):
                candidate = lines[cursor]
                refs.append((log_name, cursor + 1))
                if candidate.startswith(("╰", "╚")):
                    footer_found = True
                    cursor += 1
                    break
                if candidate.startswith("│  "):
                    body.append(candidate[3:])
                elif candidate.startswith("│"):
                    body.append(candidate[1:].lstrip())
                else:
                    # A malformed/incomplete card should not swallow unrelated
                    # following records.  Leave it to the legacy unknown/error
                    # handling instead.
                    break
                cursor += 1

            if not footer_found:
                index += 1
                continue

            card_lines.update(refs)
            presentation_lines.update(refs)

            payload = "\n".join(body).rstrip()
            canonical = (
                f"{timestamp} - {source:<30} - {level:<8} - {payload}"
            )
            normalized_errors.append(
                f"{log_name}:{start_line}: {canonical}"
            )
            index = cursor

    return normalized_errors, card_lines, presentation_lines


def _merge_errors(
    legacy_errors: Sequence[str],
    fancy_errors: Sequence[str],
    fancy_card_lines: set[tuple[str, int]],
) -> list[str]:
    """Keep old-format findings and replace card-internal fragments with one card."""

    merged: list[str] = []
    seen: set[str] = set()

    for value in legacy_errors:
        ref = _parse_prefixed_reference(value)
        if ref is not None and ref in fancy_card_lines:
            continue
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(value)

    for value in fancy_errors:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(value)

    return merged


def _filter_unknown_lines(
    legacy_unknown: Sequence[str],
    presentation_lines: set[tuple[str, int]],
) -> list[str]:
    filtered: list[str] = []
    for value in legacy_unknown:
        ref = _parse_prefixed_reference(value)
        if ref is not None and ref in presentation_lines:
            continue
        filtered.append(value)
    return filtered


def analyze_evidence_source(path: Path):
    """Run parser 1.20 semantics plus main-log presentation compatibility."""

    resolved = path.resolve()
    analysis = _base.analyze_evidence_source(resolved)

    # Re-read through the base parser's exact source/rotation logic so the
    # compatibility layer sees the same bytes and physical line numbering.
    logs, _sizes, _source_hash = _base._read_source(resolved)

    fancy_errors, fancy_card_lines, presentation_lines = _collect_fancy_main_cards(logs)
    errors = _merge_errors(
        analysis.errors_and_warnings,
        fancy_errors,
        fancy_card_lines,
    )
    unknown = _filter_unknown_lines(
        analysis.unknown_lines,
        presentation_lines,
    )

    summary = dict(analysis.summary)
    summary["parser_version"] = PARSER_VERSION

    assumptions = list(summary.get("assumptions", []))
    assumptions.append(
        "Polished screensaver.log presentation is normalized for severity cards; "
        "decorative banner/card rows are excluded from unknown_lines."
    )
    summary["assumptions"] = assumptions

    counts = dict(summary.get("counts", {}))
    counts["deduplicated_errors_and_warnings"] = len(errors)
    counts["unknown_lines"] = len(unknown)
    summary["counts"] = counts

    return _base.ArchiveAnalysis(
        summary=summary,
        frame_rows=analysis.frame_rows,
        task_rows=analysis.task_rows,
        memory_rows=analysis.memory_rows,
        gpu_rows=analysis.gpu_rows,
        event_loop_rows=analysis.event_loop_rows,
        resource_rows=analysis.resource_rows,
        lifecycle_rows=analysis.lifecycle_rows,
        visualizer_rows=analysis.visualizer_rows,
        phase5_rows=analysis.phase5_rows,
        errors_and_warnings=errors,
        unknown_lines=unknown,
    )


def analyze_archive(path: Path):
    """Backward-compatible alias matching the repository parser."""
    return analyze_evidence_source(path)


def write_analysis(analysis, output_dir: Path) -> None:
    _base.write_analysis(analysis, output_dir)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse an SRPSS live logs directory, evidence subfolder, "
            "or legacy ZIP archive (parser 1.21 fancy-main-log compatible)."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source",
        type=Path,
        help="Live logs directory, evidence subfolder, or legacy ZIP archive.",
    )
    source.add_argument(
        "--archive",
        type=Path,
        help="Legacy alias for a ZIP evidence source.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    source = args.source or args.archive
    if source is None or not source.exists():
        print(f"Evidence source not found: {source}")
        return 1
    try:
        analysis = analyze_evidence_source(source)
        write_analysis(analysis, args.output_dir)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Failed to parse evidence source: {exc}")
        return 1
    print(
        f"Wrote recovery evidence artifacts to {args.output_dir} "
        f"(parser={PARSER_VERSION}, sha256={analysis.summary['source_sha256']})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

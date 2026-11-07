"""One-off: move the pre-layout evidence (flat ``.artifacts/evidence/<ad-hoc>`` folders and ``logs/evidence_chest``)
into the evidence layout owned by ``tools/artifact_paths.py``, and rewrite the references to it.

    python tools/artifact_migration.py plan  --source .artifacts/evidence_legacy --table T.md   # dry run
    python tools/artifact_migration.py refs  --source .artifacts/evidence_legacy                # dry run
    python tools/artifact_migration.py apply --source .artifacts/evidence_legacy                # the real move

* ``plan`` writes the mapping table: every legacy folder and every WebP, old -> new.
* ``apply`` first rewrites the references (below) from the same plan, then moves unit by unit: copy (across
  drives when the layout roots are junctions), verify every file's size and the count, and only then delete
  the source. Re-running resumes: files already copied with the same size are skipped. Folders named in
  ``HELD`` are never touched.
* ``refs`` (dry run) / ``apply`` rewrite ``.artifacts/evidence/<legacy>/...`` and ``logs/evidence_chest/...`` references in
  ``Docs/``, ``Current_Plan.md`` and ``tools/`` to the layout paths (always repo-relative ``.artifacts/...``,
  never a junction target). A ``.png`` (or a frame folder) that the 7 Nov conversion replaced with a WebP is
  rewritten to that WebP. References that resolve to nothing are listed. ``tests/goldens`` is never touched.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402

# Legacy folder -> (area, topic, label); label None = split: each child folder is its own unit, named by the
# child (its ``_YYYYMMDD`` suffix becomes the date).
LEGACY = {
    "ac12": ("lifecycle", "ac12", "ac12"),
    "architecture_audit_20261106": ("architecture", "audit", "audit"),
    "bubble": ("visualizers/bubble", None, None),
    "cleanup_20261105": ("architecture", "cleanup", "cleanup"),
    "combobox_double_border": ("settings", "combobox_double_border", "combobox"),
    "devcurve": ("visualizers/devcurve", None, None),
    "display_power": ("display", "display_power", "display_power"),
    "eb_logical_tick": ("visualizers/extruded_bubble", "logical_tick", "logical_tick"),
    "extruded_bubble": ("visualizers/extruded_bubble", None, None),
    "extruded_spectrum": ("visualizers/extruded_spectrum", None, None),
    "gc_gen2": ("memory", "gc_gen2", "gc_gen2"),
    "live_20261106": ("performance", "live_check", "live"),
    "live_check_quiet_20261106": ("performance", "live_check", "quiet"),
    "neon_lake": ("visualizers/shockwave_grid", None, None),
    "operator_throwaway_saves_20261107": ("settings", "operator_throwaway_saves", "saves"),
    "overhead": ("performance", "overhead", "overhead"),
    "preset_cross_mode_write_20261106": ("settings", "preset_cross_mode_write", "preset_write"),
    "quiet_session_20261107": ("performance", "quiet_session", "quiet_session"),
    "ribbon_material": ("visualizers/waveform_ribbon", "ribbon_material", "ribbon_material"),
    "settings_layout_tab": ("settings", "layout_tab", "layout_tab"),
    "settings_roundtrip_memory": ("memory", "settings_roundtrip", "settings_roundtrip"),
    "slow_startup_20261106": ("lifecycle", "slow_startup", "slow_startup"),
    "spectrum": ("visualizers/spectrum", None, None),
    "spectrum_presets_20261107": ("visualizers/spectrum", "presets", "agent"),
    "spectrum_presets_lead_20261107": ("visualizers/spectrum", "presets", "lead"),
    "spectrum_smoothing_20261106": ("visualizers/spectrum", "smoothing", "smoothing"),
    "sphere": ("visualizers/sphere", None, None),
    "studio_chrome": ("studio", "chrome", "chrome"),
    "studio_clip_loop_20261106": ("studio", "clip_loop", "clip_loop"),
    "studio_completion_20261106": ("studio", "completion", "completion"),
    "studio_drag": ("studio", "drag", "drag"),
    "studio_exit_stall_20261106": ("studio", "exit_stall", "exit_stall"),
    "studio_followups": ("studio", "followups", "followups"),
    "waveform_followups": ("visualizers/waveform_ribbon", "followups", "followups"),
    "waveform_logical_tick": ("visualizers/waveform_ribbon", "logical_tick", "logical_tick"),
    "waveform_ribbon": ("visualizers/waveform_ribbon", None, None),
    "widget_surfaces_20261106": ("widgets", "surfaces", "surfaces"),
    "widget_surfaces_style_20261106": ("widgets", "surfaces_style", "surfaces_style"),
    "frame_webps_20261107.md": ("architecture", "frame_webps", "conversion"),
}
CHEST = ("lifecycle", "log_archives", "evidence_chest")
# Folders a running session is still writing: never moved until released. (The 7 Nov measurement session ended.)
HELD: set[str] = set()

_DATED = re.compile(r"^(?P<stem>.*?)_?(?P<date>20\d{6})$")


@dataclass
class Unit:
    legacy: str                       # repo-relative legacy path, forward slashes (".artifacts/evidence/x/y")
    source: Path
    dest: Path                        # evidence folder (or file, for a loose legacy file)
    held: bool = False
    files: list[tuple[Path, Path]] = field(default_factory=list)
    webps: list[tuple[Path, Path]] = field(default_factory=list)


def _newest_date(path: Path) -> str:
    stamps = [path.stat().st_mtime] + [item.stat().st_mtime for item in path.rglob("*") if item.is_file()]
    return time.strftime("%Y%m%d", time.localtime(max(stamps)))


def _split_name(name: str, path: Path) -> tuple[str, str]:
    """(topic/label stem, date) from ``name_YYYYMMDD`` or the newest file date."""
    match = _DATED.match(name)
    if match and match.group("stem"):
        return artifact_paths.slug(match.group("stem")), match.group("date")
    return artifact_paths.slug(Path(name).stem), _newest_date(path)


def _fill(unit: Unit, area: str, topic: str, prefix: str) -> None:
    if unit.source.is_file():
        unit.files.append((unit.source, unit.dest))
        return
    webp_dir = artifact_paths.WEBP_ROOT.joinpath(*artifact_paths.area_parts(area), topic)
    for path in sorted(unit.source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(unit.source)
        if path.suffix.lower() == ".webp":
            name = "_".join((prefix, *relative.with_suffix("").parts))
            unit.webps.append((path, webp_dir / f"{artifact_paths.slug(name)}.webp"))
        else:
            unit.files.append((path, unit.dest / relative))


def plan(source: Path, chest: Path | None) -> list[Unit]:
    units: list[Unit] = []
    taken: set[Path] = set()

    def add(legacy: str, path: Path, area: str, topic: str, label: str, date: str, held: bool) -> None:
        dest = artifact_paths.evidence_dir(area, topic, label, date=date)
        if path.is_file():
            dest = dest / path.name
        base, index = dest, 2
        while dest in taken:
            dest = base.with_name(f"{base.name}_{index}")
            index += 1
        taken.add(dest)
        unit = Unit(legacy, path, dest, held=held)
        _fill(unit, area, topic, dest.name if not path.is_file() else f"{date}_{label}")
        units.append(unit)

    for path in sorted(source.iterdir()):
        legacy = f".artifacts/evidence/{path.name}"
        spec = LEGACY.get(path.name)
        if spec is None:
            units.append(Unit(legacy, path, Path("UNMAPPED")))
            continue
        area, topic, label = spec
        held = path.name in HELD
        if topic is not None:
            _stem, date = _split_name(path.name, path)
            add(legacy, path, area, topic, label, date, held)
            continue
        loose = [child for child in path.iterdir() if child.is_file()]
        for child in sorted(child for child in path.iterdir() if child.is_dir()):
            stem, date = _split_name(child.name, child)
            add(f"{legacy}/{child.name}", child, area, stem, stem, date, held)
        for child in loose:
            add(f"{legacy}/{child.name}", child, area, "notes", artifact_paths.slug(path.name),
                _newest_date(child), held)
    if chest is not None and chest.is_dir():
        area, topic, label = CHEST
        for child in sorted(chest.iterdir()):
            add(f"logs/evidence_chest/{child.name}", child, area, topic, label, _newest_date(child), False)
    return units


def _rel(path: Path) -> str:
    try:
        return "/".join((".artifacts", *path.relative_to(artifact_paths.ARTIFACTS_ROOT).parts))
    except ValueError:
        return str(path)


def write_table(units: list[Unit], out) -> None:
    total = sum(len(u.files) + len(u.webps) for u in units)
    out.write("# Evidence migration plan (dry run)\n\n")
    out.write(f"{len(units)} units, {total} files. Nothing has been moved.\n\n## Folders\n\n")
    out.write("| Old | New | Files | WebPs | Note |\n| --- | --- | ---: | ---: | --- |\n")
    for unit in units:
        note = "UNMAPPED" if unit.dest == Path("UNMAPPED") else ("HELD (not moved until released)" if unit.held else "")
        out.write(f"| `{unit.legacy}` | `{_rel(unit.dest)}` | {len(unit.files)} | {len(unit.webps)} | {note} |\n")
    out.write("\n## WebPs\n\n| Old | New |\n| --- | --- |\n")
    for unit in units:
        for source, dest in unit.webps:
            old = unit.legacy + "/" + source.relative_to(unit.source).as_posix()
            out.write(f"| `{old}` | `{_rel(dest)}` |\n")


def apply(units: list[Unit]) -> None:
    for unit in units:
        if unit.held or unit.dest == Path("UNMAPPED"):
            print(f"skip   {unit.legacy} ({'held' if unit.held else 'unmapped'})")
            continue
        pairs = unit.files + unit.webps
        for source, dest in pairs:
            if dest.exists() and dest.stat().st_size == source.stat().st_size:
                continue                                   # resumed: already copied
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_name(dest.name + ".partial")
            shutil.copy2(source, partial)
            os.replace(partial, dest)
        missing = [str(d) for s, d in pairs if not d.is_file() or d.stat().st_size != s.stat().st_size]
        if missing:
            raise RuntimeError(f"verify failed for {unit.legacy}; source kept: {missing[:5]}")
        for source, _dest in pairs:                        # verified: only now delete the source
            source.unlink()
        if unit.source.is_dir():
            for folder in sorted((p for p in unit.source.rglob("*") if p.is_dir()), reverse=True):
                folder.rmdir()
            unit.source.rmdir()
        print(f"moved  {unit.legacy} -> {_rel(unit.dest)} ({len(pairs)} files, verified)")


# -- references -----------------------------------------------------------------------------------------------

_REF = re.compile(r"(?:\.artifacts[\\/]+evidence|logs[\\/]+evidence_chest)(?:[\\/]+[^\s`'\"()\[\]{}|<>,;*\\/]*)*")


def _ref_files(root: Path) -> list[Path]:
    files = [root / "Current_Plan.md", *sorted((root / "Docs").rglob("*.md")), *sorted((root / "tools").rglob("*.py"))]
    return [path for path in files if path.is_file() and "goldens" not in path.parts
            and path.name not in {"artifact_migration.py", "artifact_paths.py"}]


def resolve_reference(text: str, units: list[Unit]) -> tuple[str | None, bool]:
    """(layout path, exists) for one legacy reference; (None, False) when it names no legacy unit.

    A path below a moved unit whose tail no longer exists (a deleted file, a ``{a,b}`` brace pattern) still
    gets the unit's new prefix and is reported as not existing.
    """
    parts = [part for part in re.split(r"[\\/]+", text) if part not in ("", ".")]
    normalized = "/".join(parts)
    candidates = sorted((u for u in units if u.dest != Path("UNMAPPED")), key=lambda u: len(u.legacy), reverse=True)
    for unit in candidates:
        if normalized != unit.legacy and not normalized.startswith(unit.legacy + "/"):
            continue
        remainder = normalized[len(unit.legacy):].lstrip("/")
        if not remainder:
            return _rel(unit.dest), True
        tail = Path(remainder)
        for webp_source, webp_dest in unit.webps:
            relative = webp_source.relative_to(unit.source)
            if tail in {relative, relative.with_suffix(".png"), relative.with_suffix("")}:  # PNG or frame folder
                return _rel(webp_dest), True
        for source, dest in unit.files:
            relative = source.relative_to(unit.source) if unit.source.is_dir() else Path(source.name)
            if relative == tail:
                return _rel(dest), True
            if tail in relative.parents:
                return _rel(unit.dest / tail), True
        return _rel(unit.dest / tail), False
    # A split legacy parent (``.artifacts/evidence/waveform_ribbon/``) becomes its area folder.
    if len(parts) == 3 and parts[:2] == [".artifacts", "evidence"]:
        spec = LEGACY.get(parts[2])
        if spec is not None and spec[1] is None:
            return _rel(artifact_paths.EVIDENCE_ROOT.joinpath(*artifact_paths.area_parts(spec[0]))), True
    return None, False


def rewrite_references(root: Path, units: list[Unit], *, write: bool) -> tuple[int, int, list[str]]:
    """Rewrite legacy references; returns (files changed, references rewritten, report lines)."""
    changed, rewritten, report = 0, 0, []
    for path in _ref_files(root):
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(root).as_posix()

        def substitute(match: re.Match) -> str:
            nonlocal rewritten
            parts = [part for part in re.split(r"[\\/]+", match.group(0)) if part]
            if len(parts) <= 2:
                return match.group(0)                      # the bare root: unchanged by the layout
            if parts[1] == "evidence" and parts[2] in artifact_paths.AREAS and parts[2] not in LEGACY:
                return match.group(0)                      # already a layout path
            new, exists = resolve_reference(match.group(0), units)
            if new is None:
                report.append(f"DEAD (no such legacy folder; left unchanged) {where}: {match.group(0)}")
                return match.group(0)
            if not exists:
                report.append(f"MISSING (prefix rewritten; the tail does not exist) {where}: {match.group(0)} -> {new}")
            rewritten += 1
            trailing = match.group(0).endswith(("/", "\\")) and not new.endswith(".webp")
            return new + ("/" if trailing else "")

        new_text = _REF.sub(substitute, text)
        if new_text != text:
            changed += 1
            if write:
                path.write_text(new_text, encoding="utf-8")
    return changed, rewritten, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "apply", "refs"))
    parser.add_argument("--source", type=Path, default=artifact_paths.ARTIFACTS_ROOT / "evidence_legacy",
                        help="the renamed flat evidence root")
    parser.add_argument("--chest", type=Path, default=artifact_paths.main_checkout() / "logs" / "evidence_chest")
    parser.add_argument("--table", type=Path, help="plan: write the mapping table here (default: stdout)")
    args = parser.parse_args(argv)
    units = plan(args.source.resolve(), args.chest.resolve() if args.chest else None)
    if args.command == "plan":
        if args.table:
            with args.table.open("w", encoding="utf-8") as handle:
                write_table(units, handle)
            print(f"plan written to {args.table}")
        else:
            write_table(units, sys.stdout)
        unmapped = [u.legacy for u in units if u.dest == Path("UNMAPPED")]
        if unmapped:
            print("UNMAPPED:", *unmapped, sep="\n  ")
        return 1 if unmapped else 0
    # One plan for both steps: references are rewritten from the same mapping the move uses.
    write = args.command == "apply"
    changed, rewritten, report = rewrite_references(artifact_paths.REPO_ROOT, units, write=write)
    print(f"references: {rewritten} in {changed} files {'rewritten' if write else 'would be rewritten'}")
    for line in report:
        print(line)
    if write:
        apply(units)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

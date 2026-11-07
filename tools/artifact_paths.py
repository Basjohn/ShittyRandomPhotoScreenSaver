"""The one owner of every path a tool writes evidence or scratch to.

Layout (Docs/Guardrails.md "Evidence and scratch hygiene"):

    .artifacts/
      webp/<area>/<topic>/<YYYYMMDD>_<label>.webp   visual evidence only (animated 24 fps < 10 MB, or a still)
      evidence/<area>/<topic>/<YYYYMMDD>_<label>/   data: summaries, json/csv, traces, logs, run settings
      scratch/<owner>/                              temporary; its owner deletes it; safe to wipe when no agent runs

``<area>`` comes from the declared vocabulary below (``AREAS``; ``visualizers/<mode>`` takes a registered or
retired mode id, ``transitions/<name>`` any slug). An unknown area raises. ``<topic>`` and ``<label>`` are slugs.

Visualizer folders are named by mode id. The product name is accepted too and resolves to the id (the slug of
the registry's display name, plus the Studio title ``neon_lake``), so ``visualizers/neon_lake_basin`` and
``visualizers/neon_lake`` both write to ``visualizers/shockwave_grid``. Mode ids with their product names
(``python tools/artifact_paths.py areas`` prints the current list):

    spectrum (Spectrum)                 oscilloscope (Oscilloscope)       bubble (Bubble)
    devcurve (Spline Curve)             sphere (Voxel Sphere)             extruded_spectrum (Extruded Spectrum)
    shockwave_grid (Neon Lake Basin)    extruded_bubble (Extruded Bubble) waveform_ribbon (Waveform Ribbon)
    shared (cross-mode infrastructure); retired: blob, sine_wave

Prevention: a tool takes its default destination from here, and passes any explicit output path given on its
command line through ``checked_output``, which refuses everything outside this layout: elsewhere in the
repository, ``%TEMP%``, a Claude session scratchpad, another drive (14.7 GB of agent output piled up in
``%TEMP%`` by 7 Nov 2026). Programmatic APIs that tests call may still take ``tmp_path``; tests redirect the
whole layout with ``use_root``. PNG frames exist only in owner scratch (``scratch()``, ``run_scratch``): deleted
when the tool succeeds, KEPT when it fails (its path is printed for debugging) until ``prune-scratch`` clears it.
``tests/test_artifact_paths_contract.py`` keeps tools honest.

One layout per clone: in a linked git worktree (an agent's checkout) the layout resolves to the MAIN checkout's
``.artifacts``, so evidence survives the worktree and every agent's output lands in one place.

Not evidence, and not owned here: product assets (``assets/``, ``release/``, ``presets/``), test fixtures
(``tests/goldens``, ``tests/fixtures``), the application's own logs (``logs/*.log``, the frame trace) and the
operator's recordings (``logs/visualizer_recordings``).
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]


def main_checkout(repo: Path = REPO_ROOT) -> Path:
    """The main checkout of ``repo``'s clone (``repo`` itself unless it is a linked worktree)."""
    marker = repo / ".git"
    try:
        if marker.is_file():
            gitdir = Path(marker.read_text(encoding="utf-8").split("gitdir:", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (repo / gitdir).resolve()
            common = gitdir
            commondir = gitdir / "commondir"
            if commondir.is_file():
                common = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve()
            if common.name == ".git":
                return common.parent
    except (OSError, IndexError):
        pass
    return repo


ARTIFACTS_ROOT = main_checkout() / ".artifacts"
WEBP_ROOT = ARTIFACTS_ROOT / "webp"
EVIDENCE_ROOT = ARTIFACTS_ROOT / "evidence"
SCRATCH_ROOT = ARTIFACTS_ROOT / "scratch"
LAYOUT_ROOTS = (WEBP_ROOT, EVIDENCE_ROOT, SCRATCH_ROOT)


@contextlib.contextmanager
def use_root(artifacts_root: Path) -> Iterator[Path]:
    """Tests: redirect the whole layout under ``artifacts_root`` (e.g. ``tmp_path``) for the block."""
    global ARTIFACTS_ROOT, WEBP_ROOT, EVIDENCE_ROOT, SCRATCH_ROOT, LAYOUT_ROOTS
    saved = (ARTIFACTS_ROOT, WEBP_ROOT, EVIDENCE_ROOT, SCRATCH_ROOT, LAYOUT_ROOTS)
    ARTIFACTS_ROOT = Path(artifacts_root).resolve()
    WEBP_ROOT = ARTIFACTS_ROOT / "webp"
    EVIDENCE_ROOT = ARTIFACTS_ROOT / "evidence"
    SCRATCH_ROOT = ARTIFACTS_ROOT / "scratch"
    LAYOUT_ROOTS = (WEBP_ROOT, EVIDENCE_ROOT, SCRATCH_ROOT)
    try:
        yield ARTIFACTS_ROOT
    finally:
        ARTIFACTS_ROOT, WEBP_ROOT, EVIDENCE_ROOT, SCRATCH_ROOT, LAYOUT_ROOTS = saved

# Top-level areas. "visualizers" and "transitions" take one sub-name (``visualizers/<mode>``).
AREAS = frozenset({
    "visualizers",
    "transitions",
    "settings",
    "widgets",
    "studio",
    "display",
    "performance",
    "memory",
    "lifecycle",
    "media",
    "input",
    "network",
    "build",
    "onboarding",
    "themes",
    "tests",
    "architecture",
})
_NAMED_AREAS = frozenset({"visualizers", "transitions"})
# Not a mode id: shared visualizer infrastructure (DSP, audio, cross-mode comparisons).
_VISUALIZER_SHARED = frozenset({"shared"})

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class ArtifactPathError(ValueError):
    """A path outside the declared evidence layout, or an undeclared area."""


# Product names the registry cannot derive; everything else comes from each mode's display name.
_HAND_ALIASES = {"neon_lake": "shockwave_grid"}   # the Neon Lake Studio's title (ui/studio/registry.py)


def _ensure_repo_importable() -> None:
    """The mode registry lives in ``core``; a script run from ``tools/`` has only ``tools/`` on its path."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def _visualizer_modes() -> frozenset[str]:
    _ensure_repo_importable()
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    from core.settings.visualizer_retired_modes import RETIRED_VISUALIZER_MODE_IDS

    return frozenset(VISUALIZER_MODE_IDS) | frozenset(RETIRED_VISUALIZER_MODE_IDS) | _VISUALIZER_SHARED


def visualizer_product_names() -> dict[str, str]:
    """Registered mode id -> product (display) name."""
    _ensure_repo_importable()
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_visualizer_mode_descriptor

    return {mode: get_visualizer_mode_descriptor(mode).display_name for mode in VISUALIZER_MODE_IDS}


def _visualizer_aliases() -> dict[str, str]:
    """Accepted name -> mode id: every id, the slug of every display name, and ``_HAND_ALIASES``."""
    aliases = {mode: mode for mode in _visualizer_modes()}
    for mode, name in visualizer_product_names().items():
        aliases.setdefault(slug(name), mode)
    for name, mode in _HAND_ALIASES.items():
        aliases.setdefault(name, mode)
    return aliases


def slug(value: str) -> str:
    """``value`` as a lower-case path slug (spaces and separators become ``_``)."""
    text = re.sub(r"[^a-z0-9_.-]+", "_", str(value).strip().lower()).strip("_.-")
    if not text:
        raise ArtifactPathError(f"empty slug from {value!r}")
    return text


def _require_slug(kind: str, value: str) -> str:
    if not isinstance(value, str) or not _SLUG.match(value) or ".." in value:
        raise ArtifactPathError(f"{kind} must be a lower-case slug, got {value!r}")
    return value


def area_parts(area: str) -> tuple[str, ...]:
    """Validate ``area`` against the vocabulary; returns its path parts (a visualizer product name as its id)."""
    parts = tuple(str(area).split("/"))
    head = parts[0]
    if head not in AREAS:
        raise ArtifactPathError(f"unknown evidence area {area!r}; declared: {sorted(AREAS)}")
    if head in _NAMED_AREAS:
        if len(parts) != 2:
            raise ArtifactPathError(f"area {head!r} takes one name: '{head}/<name>', got {area!r}")
        _require_slug("area name", parts[1])
        if head == "visualizers":
            mode = _visualizer_aliases().get(parts[1])
            if mode is None:
                names = visualizer_product_names()
                listing = ", ".join(f"{mode} ({names[mode]})" if mode in names else mode
                                    for mode in sorted(_visualizer_modes()))
                raise ArtifactPathError(f"unknown visualizer mode {parts[1]!r}; declared: {listing}")
            parts = (head, mode)
    elif len(parts) != 1:
        raise ArtifactPathError(f"area {head!r} takes no sub-name, got {area!r}")
    return parts


def today() -> str:
    return time.strftime("%Y%m%d")


def _stamped(label: str, date: str | None) -> str:
    stamp = date or today()
    if not re.fullmatch(r"\d{8}", stamp):
        raise ArtifactPathError(f"date must be YYYYMMDD, got {stamp!r}")
    return f"{stamp}_{_require_slug('label', label)}"


def evidence_dir(area: str, topic: str, label: str, *, date: str | None = None) -> Path:
    """``.artifacts/evidence/<area>/<topic>/<YYYYMMDD>_<label>/`` (not created)."""
    return EVIDENCE_ROOT.joinpath(*area_parts(area), _require_slug("topic", topic), _stamped(label, date))


def webp_path(area: str, topic: str, label: str, *, date: str | None = None) -> Path:
    """``.artifacts/webp/<area>/<topic>/<YYYYMMDD>_<label>.webp`` (parent not created)."""
    return WEBP_ROOT.joinpath(*area_parts(area), _require_slug("topic", topic), _stamped(label, date) + ".webp")


def scratch_root(owner: str) -> Path:
    """``.artifacts/scratch/<owner>/`` (not created)."""
    return SCRATCH_ROOT / _require_slug("scratch owner", owner)


@contextlib.contextmanager
def scratch(owner: str) -> Iterator[Path]:
    """A fresh folder under ``.artifacts/scratch/<owner>/``: deleted when the block succeeds, KEPT when it
    fails (its path is printed, for debugging; ``prune-scratch`` clears it later)."""
    folder = scratch_root(owner) / f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        yield folder
    except BaseException:
        print(f"failed; scratch kept for debugging: {folder}", file=sys.stderr)
        raise
    shutil.rmtree(folder)
    with contextlib.suppress(OSError):
        folder.parent.rmdir()              # only when no other scratch of this owner is left


def run_scratch(owner: str, name: str) -> Path:
    """``.artifacts/scratch/<owner>/<pid>_<name>`` (not created) for a tool that cannot use ``scratch()``
    as a block; the tool calls ``discard_run_scratch(owner)`` when it succeeds."""
    return scratch_root(owner) / f"{os.getpid()}_{_require_slug('name', slug(name))}"


def discard_run_scratch(owner: str) -> None:
    """Delete this process's ``run_scratch`` folders of ``owner`` (call on success only)."""
    root = scratch_root(owner)
    if not root.is_dir():
        return
    for folder in root.glob(f"{os.getpid()}_*"):
        shutil.rmtree(folder)
    with contextlib.suppress(OSError):
        root.rmdir()


def _key(path: Path) -> tuple[str, ...]:
    return tuple(os.path.normcase(part) for part in path.parts)


def _relative_to_root(path: Path, root: Path) -> tuple[str, ...] | None:
    """``path``'s parts below ``root`` (both already resolved), case-insensitive where the OS is; else None."""
    path_key, root_key = _key(path), _key(root)
    if len(path_key) > len(root_key) and path_key[: len(root_key)] == root_key:
        return path.parts[len(root_key):]
    return None


def checked_output(path: str | Path, *, kind: str = "evidence") -> Path:
    """An output path given on a tool's command line; refused unless it lies inside the layout.

    ``kind`` is ``"evidence"`` (a data folder or file under ``.artifacts/evidence``), ``"webp"`` (a WebP under
    ``.artifacts/webp``) or ``"any"``; each also accepts ``.artifacts/scratch/<owner>/...``. Anything else is
    refused: the rest of the repository, ``%TEMP%``, a session scratchpad, another drive.
    """
    # Both sides are resolved, so a layout root that is a directory junction or symlink to another drive
    # (the archive on a large HDD, scratch on a fast NVMe) still contains the paths written through it.
    resolved = Path(path).expanduser().resolve()
    roots = {"evidence": (EVIDENCE_ROOT, SCRATCH_ROOT), "webp": (WEBP_ROOT, SCRATCH_ROOT),
             "any": LAYOUT_ROOTS}.get(kind)
    if roots is None:
        raise ArtifactPathError(f"unknown output kind {kind!r}")
    for root in roots:
        relative = _relative_to_root(resolved, root.resolve())
        if relative is None:
            continue
        if root is SCRATCH_ROOT:
            return resolved
        if _layout_shaped(relative):
            depth = 2 if relative[0] in _NAMED_AREAS else 1
            # A visualizer product name in the path lands in its mode id's folder.
            return root.resolve().joinpath(*area_parts("/".join(relative[:depth])), *relative[depth:])
        break
    raise ArtifactPathError(
        f"refusing to write {resolved}: tool output goes only to the evidence layout under {ARTIFACTS_ROOT} "
        f"(tools/artifact_paths.py): evidence/<area>/<topic>/<YYYYMMDD>_<label>/, "
        f"webp/<area>/<topic>/<YYYYMMDD>_<label>.webp or scratch/<owner>/ -- never elsewhere in the "
        f"repository, %TEMP% or a session scratchpad"
    )


def in_scratch(path: str | Path) -> bool:
    """True when ``path`` lies under ``.artifacts/scratch/<owner>/`` (junction-safe)."""
    return _relative_to_root(Path(path).expanduser().resolve(), SCRATCH_ROOT.resolve()) is not None


def _layout_shaped(relative: tuple[str, ...]) -> bool:
    """``<area...>/<topic>/<YYYYMMDD>_<label>[/...]`` with a declared area."""
    if not relative:
        return False
    head = relative[0]
    depth = 2 if head in _NAMED_AREAS else 1
    if len(relative) < depth + 2:
        return False
    try:
        area_parts("/".join(relative[:depth]))
        _require_slug("topic", relative[depth])
    except ArtifactPathError:
        return False
    leaf = relative[depth + 1]
    if leaf.endswith(".webp"):
        leaf = leaf[: -len(".webp")]
    return bool(re.fullmatch(r"\d{8}_[a-z0-9][a-z0-9_.-]*", leaf))


def output_dir(
    explicit: str | Path | None, area: str, topic: str, label: str, *, date: str | None = None,
    create: bool = True,
) -> Path:
    """A tool's evidence folder: ``explicit`` (checked) or the layout default; created unless ``create=False``."""
    folder = checked_output(explicit) if explicit is not None else evidence_dir(area, topic, label, date=date)
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def output_webp(
    explicit: str | Path | None, area: str, topic: str, label: str, *, date: str | None = None,
) -> Path:
    """A tool's WebP path: ``explicit`` (checked) or the layout default; its parent is created."""
    path = checked_output(explicit, kind="webp") if explicit is not None else webp_path(area, topic, label, date=date)
    if path.suffix.lower() != ".webp":
        raise ArtifactPathError(f"visual evidence is WebP: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def evidence_arg(value: str) -> Path:
    """argparse ``type=`` for an evidence output (folder or file): ``checked_output`` with a usage error."""
    import argparse

    try:
        return checked_output(value, kind="evidence")
    except ArtifactPathError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def webp_arg(value: str) -> Path:
    """argparse ``type=`` for a WebP output path."""
    import argparse

    try:
        path = checked_output(value, kind="webp")
    except ArtifactPathError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None
    if path.suffix.lower() != ".webp":
        raise argparse.ArgumentTypeError(f"visual evidence is WebP: {path}")
    return path


def default_evidence(area: str, topic: str, label: str = "run") -> str:
    """A parser default: today's evidence folder for ``area``/``topic``, labelled ``label`` plus the time."""
    return str(evidence_dir(area, topic, run_label(label)))


def default_webp(area: str, topic: str, label: str = "run") -> str:
    return str(webp_path(area, topic, run_label(label)))


def run_label(*parts: object) -> str:
    """A label from parts plus the time of day, e.g. ``bubble_p1_143005``."""
    return slug("_".join(str(part) for part in (*parts, time.strftime("%H%M%S")) if part not in (None, "")))


# -- prune-scratch: the lead runs it at milestones (no timer, no scheduled task) ---------------------------

DEFAULT_PRUNE_AGE_H = 24.0
OVERSIZED_WEBP_BYTES = 10 * 1024 * 1024


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == 259                           # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _tree_size_and_newest(folder: Path) -> tuple[int, float]:
    size, newest = 0, folder.stat().st_mtime
    for path in folder.rglob("*"):
        with contextlib.suppress(OSError):
            stat = path.stat()
            newest = max(newest, stat.st_mtime)
            if path.is_file():
                size += stat.st_size
    return size, newest


def scan(*, max_age_h: float = DEFAULT_PRUNE_AGE_H, now: float | None = None) -> dict:
    """What ``prune-scratch`` would do: scratch runs to delete or keep, and oversized evidence to report.

    A scratch run is ``scratch/<owner>/<pid>_<id>/``; it is deletable when its newest file is older than
    ``max_age_h`` and its process is no longer running. Anything else in ``scratch/<owner>/`` (a tool's own
    folder) ages the same way, without the process check.
    """
    now = time.time() if now is None else now
    runs = []
    if SCRATCH_ROOT.exists():
        for owner in sorted(path for path in SCRATCH_ROOT.iterdir() if path.is_dir()):
            for run in sorted(path for path in owner.iterdir() if path.is_dir()):
                size, newest = _tree_size_and_newest(run)
                age_h = (now - newest) / 3600.0
                pid_text = run.name.split("_", 1)[0]
                running = pid_text.isdigit() and _pid_alive(int(pid_text))
                runs.append({"path": str(run), "owner": owner.name, "bytes": size, "age_h": round(age_h, 1),
                             "running": running, "delete": age_h >= max_age_h and not running})
    oversized = []
    for root in (EVIDENCE_ROOT, WEBP_ROOT):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            with contextlib.suppress(OSError):
                if path.is_dir() and path.name == "profile":
                    oversized.append({"path": str(path), "why": "profile copy in evidence"})
                elif path.suffix.lower() == ".png":
                    oversized.append({"path": str(path), "why": "PNG evidence (use WebP)"})
                elif path.suffix.lower() == ".webp" and path.stat().st_size > OVERSIZED_WEBP_BYTES:
                    oversized.append({"path": str(path), "why": f"WebP over {OVERSIZED_WEBP_BYTES} bytes"})
    return {"scratch": runs, "oversized": oversized}


def prune_scratch(*, apply: bool = False, max_age_h: float = DEFAULT_PRUNE_AGE_H, now: float | None = None) -> dict:
    """Dry run unless ``apply``: delete stale scratch runs (never anything outside ``scratch/``)."""
    report = scan(max_age_h=max_age_h, now=now)
    scratch_root_resolved = SCRATCH_ROOT.resolve()
    for run in report["scratch"]:
        if apply and run["delete"]:
            path = Path(run["path"])
            if _relative_to_root(path.resolve(), scratch_root_resolved) is None:
                raise ArtifactPathError(f"refusing to delete outside scratch: {path}")
            shutil.rmtree(path)
            run["deleted"] = True
    return report


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The evidence layout owner.")
    sub = parser.add_subparsers(dest="command", required=True)
    prune = sub.add_parser("prune-scratch", help="list scratch runs; with --apply delete stale ones")
    prune.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    prune.add_argument("--max-age-h", type=float, default=DEFAULT_PRUNE_AGE_H)
    sub.add_parser("areas", help="list the declared areas (visualizer mode ids with their product names)")
    args = parser.parse_args(argv)
    if args.command == "areas":
        names = visualizer_product_names()
        aliases = _visualizer_aliases()
        for area in sorted(AREAS):
            if area != "visualizers":
                print(area + ("/<name>" if area in _NAMED_AREAS else ""))
                continue
            for mode in sorted(_visualizer_modes()):
                accepted = sorted(name for name, target in aliases.items() if target == mode and name != mode)
                print(f"visualizers/{mode}" + (f" ({names[mode]})" if mode in names else "")
                      + (f"  also: {', '.join(accepted)}" if accepted else ""))
        return 0
    report = prune_scratch(apply=args.apply, max_age_h=args.max_age_h)
    total = 0
    for run in report["scratch"]:
        total += run["bytes"]
        action = ("DELETED" if run.get("deleted") else "delete") if run["delete"] else (
            "running" if run["running"] else "keep")
        print(f"{action:8s} {run['bytes'] / 1e6:10.1f} MB {run['age_h']:8.1f} h  {run['path']}")
    print(f"scratch total {total / 1e6:.1f} MB under {SCRATCH_ROOT}" + ("" if args.apply else " (dry run)"))
    for item in report["oversized"]:
        print(f"REPORT   {item['why']}: {item['path']}")
    return 0


__all__ = [
    "AREAS",
    "ARTIFACTS_ROOT",
    "ArtifactPathError",
    "EVIDENCE_ROOT",
    "LAYOUT_ROOTS",
    "REPO_ROOT",
    "SCRATCH_ROOT",
    "WEBP_ROOT",
    "area_parts",
    "checked_output",
    "default_evidence",
    "default_webp",
    "evidence_arg",
    "evidence_dir",
    "main_checkout",
    "output_dir",
    "output_webp",
    "prune_scratch",
    "scan",
    "run_label",
    "scratch",
    "scratch_root",
    "slug",
    "today",
    "use_root",
    "webp_arg",
    "webp_path",
]


if __name__ == "__main__":
    raise SystemExit(_cli())

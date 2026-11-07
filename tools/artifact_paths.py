"""The one owner of every path a tool writes evidence or scratch to.

Layout (Docs/Guardrails.md "Evidence and scratch hygiene"):

    .artifacts/
      webp/<area>/<topic>/<YYYYMMDD>_<label>.webp   visual evidence only (animated 24 fps < 10 MB, or a still)
      evidence/<area>/<topic>/<YYYYMMDD>_<label>/   data: summaries, json/csv, traces, logs, run settings
      scratch/<owner>/                              temporary; its owner deletes it; safe to wipe when no agent runs

``<area>`` comes from the declared vocabulary below (``AREAS``; ``visualizers/<mode>`` takes a registered or
retired mode id, ``transitions/<name>`` any slug). An unknown area raises. ``<topic>`` and ``<label>`` are slugs.

Prevention: a tool takes its default destination from here, and passes any explicit output path given on its
command line through ``checked_output``, which refuses everything outside this layout: elsewhere in the
repository, ``%TEMP%``, a Claude session scratchpad, another drive (14.7 GB of agent output piled up in
``%TEMP%`` by 7 Nov 2026). Programmatic APIs that tests call may still take ``tmp_path``; tests redirect the
whole layout with ``use_root``. PNG frames exist only inside ``scratch()``, which deletes them on success and
on exceptions. ``tests/test_artifact_paths_contract.py`` keeps tools honest.

One layout per clone: in a linked git worktree (an agent's checkout) the layout resolves to the MAIN checkout's
``.artifacts``, so evidence survives the worktree and every agent's output lands in one place.

Not evidence, and not owned here: product assets (``assets/``, ``release/``, ``presets/``), test fixtures
(``tests/goldens``, ``tests/fixtures``), the application's own logs (``logs/*.log``, the frame trace) and the
operator's recordings (``logs/visualizer_recordings``).
"""
from __future__ import annotations

import contextlib
import re
import shutil
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


def _visualizer_modes() -> frozenset[str]:
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    from core.settings.visualizer_retired_modes import RETIRED_VISUALIZER_MODE_IDS

    return frozenset(VISUALIZER_MODE_IDS) | frozenset(RETIRED_VISUALIZER_MODE_IDS) | _VISUALIZER_SHARED


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
    """Validate ``area`` against the vocabulary; returns its path parts."""
    parts = tuple(str(area).split("/"))
    head = parts[0]
    if head not in AREAS:
        raise ArtifactPathError(f"unknown evidence area {area!r}; declared: {sorted(AREAS)}")
    if head in _NAMED_AREAS:
        if len(parts) != 2:
            raise ArtifactPathError(f"area {head!r} takes one name: '{head}/<name>', got {area!r}")
        _require_slug("area name", parts[1])
        if head == "visualizers" and parts[1] not in _visualizer_modes():
            raise ArtifactPathError(
                f"unknown visualizer mode {parts[1]!r}; declared: {sorted(_visualizer_modes())}"
            )
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
    """A fresh folder under ``.artifacts/scratch/<owner>/``, deleted on exit (success or exception)."""
    folder = scratch_root(owner) / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True, exist_ok=False)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        with contextlib.suppress(OSError):
            folder.parent.rmdir()          # only when no other scratch of this owner is live


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def checked_output(path: str | Path, *, kind: str = "evidence") -> Path:
    """An output path given on a tool's command line; refused unless it lies inside the layout.

    ``kind`` is ``"evidence"`` (a data folder or file under ``.artifacts/evidence``), ``"webp"`` (a WebP under
    ``.artifacts/webp``) or ``"any"``; each also accepts ``.artifacts/scratch/<owner>/...``. Anything else is
    refused: the rest of the repository, ``%TEMP%``, a session scratchpad, another drive.
    """
    resolved = Path(path).expanduser().resolve()
    roots = {"evidence": (EVIDENCE_ROOT, SCRATCH_ROOT), "webp": (WEBP_ROOT, SCRATCH_ROOT),
             "any": LAYOUT_ROOTS}.get(kind)
    if roots is None:
        raise ArtifactPathError(f"unknown output kind {kind!r}")
    for root in roots:
        if _inside(resolved, root) and resolved != root:
            relative = resolved.relative_to(root).parts
            if root is SCRATCH_ROOT or _layout_shaped(relative):
                return resolved
            break
    raise ArtifactPathError(
        f"refusing to write {resolved}: tool output goes only to the evidence layout under {ARTIFACTS_ROOT} "
        f"(tools/artifact_paths.py): evidence/<area>/<topic>/<YYYYMMDD>_<label>/, "
        f"webp/<area>/<topic>/<YYYYMMDD>_<label>.webp or scratch/<owner>/ -- never elsewhere in the "
        f"repository, %TEMP% or a session scratchpad"
    )


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


def run_label(*parts: object) -> str:
    """A label from parts plus the time of day, e.g. ``bubble_p1_143005``."""
    return slug("_".join(str(part) for part in (*parts, time.strftime("%H%M%S")) if part not in (None, "")))


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
    "evidence_dir",
    "main_checkout",
    "output_dir",
    "output_webp",
    "run_label",
    "scratch",
    "scratch_root",
    "slug",
    "today",
    "use_root",
    "webp_path",
]

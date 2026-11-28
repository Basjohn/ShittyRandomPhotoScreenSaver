"""The Python transition and background references, cached once before N5.2h deletes the Python renderers
(Current_Plan.md, the switch's caller list point 1; ``Docs/Guides/Native_Parity_And_Timing_Proof.md`` section 3, "A
transition port"). The four checks that judged rule (a) against a live Python draw (``transition_route_check``,
``fullscreen_pass_check``, ``background_layer_check``, ``backdrop_pyramid_check``) read their references from here.

Keyed like the Visualizer references (``tools/visualizer_replay/python_references.py``): an entry's key is a digest of
what it was made of: the check, the case (variant, progress, dpr, placement, sizes), a digest of the input pictures as
the product's worker processed them, and the run's parameters as the transitions' value owners give them (those stay
after the deletion). A changed input, a changed value or a changed case makes a new key. That key then has no entry, and
the check refuses it; it never meets a stale frame. The Python drawing code is not in the key, because after the
deletion nothing can hash it; the commit that drew the entry is recorded instead (``made_at``).

Each entry is ``<root>/<check>/<key>.npz`` (its frames) beside ``<key>.json`` (what it was made of, the frames' digest
and any plain values, such as ``block_values``). A read checks both. A missing or corrupted entry is refused with the
case named (``MissingReference``), never drawn again in its place.

The Python renderer's ``--cost`` figures (timings, so never a frame) are stored baselines instead:
``tools/baselines/preflip/python_cost_<check>.json`` (``cost_figures``), keyed the same way and refused the same way.

Modes (``--python-references``):
- ``cache`` (the default): every reference is read from the cache.
- ``record``: drawn live by the Python renderer and stored. This needs a checkout that still holds the Python
  renderers, so it runs once before the deletion; the run's verdict is the live one.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

#: The cache's default folder (the drive layout's scratch, never the repository or X:).
DEFAULT_ROOT = Path(r"D:\Temp\Scratch\SRPSS\fast_proof\transition_references")
#: The layout of a stored entry (a change makes old ones unreadable, never misread).
FORMAT = 1
MODES = ("cache", "record")
ROOT = Path(__file__).resolve().parents[3]

_settings: dict = {"mode": "cache", "root": DEFAULT_ROOT}


class MissingReference(RuntimeError):
    """A reference the cache does not hold whole (missing, made of something else, or corrupted)."""


def configure(mode: str, root: Path | str | None = None) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown reference mode {mode!r} (one of {MODES})")
    _settings["mode"] = mode
    _settings["root"] = Path(root) if root else DEFAULT_ROOT


def mode() -> str:
    return _settings["mode"]


def add_arguments(parser) -> None:
    parser.add_argument("--python-references", choices=MODES, default="cache",
                        help="cache: read the Python references from the cache (the default); record: draw them live "
                             "and store them (before the Python renderers are deleted)")
    parser.add_argument("--references-root", type=Path, default=DEFAULT_ROOT, help="the reference cache's folder")


def child_arguments(args) -> list[str]:
    """The parent's reference options, forwarded to a child process."""
    return ["--python-references", args.python_references, "--references-root", str(args.references_root)]


def configure_from(args) -> None:
    configure(args.python_references, args.references_root)


def arrays_digest(arrays) -> str:
    """A digest of pictures (dtype, shape and bytes of each, in order)."""
    import numpy as np

    digest = hashlib.sha256()
    for array in arrays:
        array = np.ascontiguousarray(array)
        digest.update(f"{array.dtype.str}{array.shape}".encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def plain(value: Any) -> Any:
    """``value`` with its tuples, numbers and strings as the key's JSON gives them (numpy scalars made plain)."""
    return json.loads(json.dumps(value, sort_keys=True, default=lambda v: v.item() if hasattr(v, "item") else str(v)))


def case_key(check: str, case: dict) -> tuple[str, dict]:
    """(the entry's name, what it was made of)."""
    made_of = {"format": FORMAT, "check": check, **plain(case)}
    text = json.dumps(made_of, sort_keys=True)
    return f"{hashlib.sha256(text.encode()).hexdigest()[:32]}", made_of


def _made_at() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _split(payload: dict) -> tuple[dict, dict]:
    import numpy as np

    arrays = {name: value for name, value in payload.items() if isinstance(value, np.ndarray)}
    extra = {name: value for name, value in payload.items() if name not in arrays}
    return arrays, extra


def store(root: Path, check: str, case: dict, payload: dict, made_at: str = "") -> Path:
    """Write one entry (its frames, then its index: a killed write leaves no index, so no entry)."""
    import numpy as np

    name, made_of = case_key(check, case)
    folder = Path(root) / check
    folder.mkdir(parents=True, exist_ok=True)
    arrays, extra = _split(payload)
    frames_path = folder / f"{name}.npz"
    partial = folder / f"{name}.partial.npz"
    np.savez_compressed(partial, **arrays)
    partial.replace(frames_path)
    index = {"made_of": made_of, "made_at": made_at, "arrays": sorted(arrays),
             "digest": arrays_digest(arrays[k] for k in sorted(arrays)), "extra": repr(extra)}
    (folder / f"{name}.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return frames_path


def load(root: Path, check: str, case: dict) -> dict:
    """One entry's payload, or ``MissingReference`` naming the case."""
    import numpy as np

    name, made_of = case_key(check, case)
    folder = Path(root) / check
    index_path, frames_path = folder / f"{name}.json", folder / f"{name}.npz"
    if not index_path.is_file() or not frames_path.is_file():
        raise MissingReference(f"{check}: no cached Python reference for {made_of} (entry {name} in {folder})")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if index.get("made_of") != made_of:
            raise MissingReference(f"{check}: the cached entry {name} was made of something else")
        with np.load(frames_path) as stored:
            arrays = {k: stored[k] for k in index["arrays"]}
        extra = ast.literal_eval(index["extra"])
    except MissingReference:
        raise
    except Exception as exc:  # an unreadable entry is a corrupted one
        raise MissingReference(f"{check}: the cached entry {name} for {made_of} is unreadable ({exc})") from exc
    if arrays_digest(arrays[k] for k in sorted(arrays)) != index.get("digest"):
        raise MissingReference(f"{check}: the cached entry {name} for {made_of} is corrupted (its frames' digest "
                               "differs from the one stored with it)")
    return {**arrays, **extra}


def references(check: str, cases: dict, draw: Callable[[], dict]) -> dict:
    """The payload of every case: ``cases`` maps the check's own key to the case's description; ``draw()`` (record
    mode only) draws them all live, as the same keys. Cache mode reads each and refuses the first it does not hold,
    with how many of the check's cases are missing."""
    root = _settings["root"]
    if _settings["mode"] == "record":
        drawn = draw()
        made_at = _made_at()
        for local, case in cases.items():
            store(root, check, case, drawn[local], made_at)
        return drawn
    out, missing = {}, []
    for local, case in cases.items():
        try:
            out[local] = load(root, check, case)
        except MissingReference as exc:
            missing.append(str(exc))
    if missing:
        raise MissingReference(f"{len(missing)} of {len(cases)} cached Python references missing or corrupted; the "
                               f"first: {missing[0]}. Record them with --python-references record on a checkout that "
                               "still holds the Python renderers")
    return out


#: The Python ``--cost`` figures' stored baselines (in the repository, beside the other pre-flip baselines): one file
#: per check, ``python_cost_<check>.json``, an entry per case.
COST_BASELINES = ROOT / "tools" / "baselines" / "preflip"


def _figures_digest(figures: dict) -> str:
    return hashlib.sha256(json.dumps(plain(figures), sort_keys=True).encode()).hexdigest()


def cost_baseline(check: str) -> Path:
    return COST_BASELINES / f"python_cost_{check}.json"


def cost_figures(check: str, cases: dict, measured: Callable[[], dict]) -> dict:
    """The Python renderer's ``--cost`` figures per case (``cases`` as in ``references``). Record mode: ``measured()``
    gives them (timed live in the same session as the native figures) and they are stored, an entry per case, in
    ``cost_baseline(check)``; the run's figures are the live ones. Cache mode: each is read from the baseline, and a
    missing case, one made of something else, or one whose figures differ from their stored digest is refused."""
    path = cost_baseline(check)
    if _settings["mode"] == "record":
        figures = measured()
        try:
            stored = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except ValueError:
            stored = {}
        made_at = _made_at()
        for local, case in cases.items():
            name, made_of = case_key(check, case)
            stored[name] = {"made_of": made_of, "made_at": made_at, "figures": plain(figures[local]),
                            "digest": _figures_digest(figures[local])}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stored, indent=1, sort_keys=True), encoding="utf-8")
        return figures
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MissingReference(f"{check}: no readable Python cost baseline at {path} ({exc}). Record it with "
                               "--python-references record on a checkout that still holds the Python renderers") from exc
    out, missing = {}, []
    for local, case in cases.items():
        name, made_of = case_key(check, case)
        entry = stored.get(name)
        if entry is None or entry.get("made_of") != made_of:
            missing.append(f"no stored Python cost for {made_of}")
        elif _figures_digest(entry.get("figures")) != entry.get("digest"):
            missing.append(f"the stored Python cost for {made_of} is corrupted (its digest differs)")
        else:
            out[local] = entry["figures"]
    if missing:
        raise MissingReference(f"{check}: {len(missing)} of {len(cases)} stored Python cost figures missing or "
                               f"corrupted in {path}; the first: {missing[0]}. Record them with --python-references "
                               "record on a checkout that still holds the Python renderers")
    return out


__all__ = ["COST_BASELINES", "DEFAULT_ROOT", "MODES", "MissingReference", "add_arguments", "arrays_digest", "case_key",
           "child_arguments", "configure", "configure_from", "cost_baseline", "cost_figures", "load", "mode",
           "references", "store"]

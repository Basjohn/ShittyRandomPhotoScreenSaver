"""Cached Python references for rule (a) (fast long-clip proof, part 2 step 3; ``Docs/Guides/Native_Parity_And_Timing_
Proof.md`` section 3: the Python renderers are frozen until N5.2h deletes them, so their frames are drawn once per take,
mode, variant and placement and kept).

A reference is what ``owner_render_parity.native_parity`` draws on the Python side of one run: the Python run (its frame
records, its frames, its logical digests, its Spectrum window maps) and the backdrop run's translucency masks. It is
stored under ``root/<key>/`` where the key is the run's inputs (the mode, the run's settings, the clip: its name and a
digest of its frames, the placement, the device pixel ratio), and it is read only while what drew it is unchanged
(lead, 28 Nov, N5.6):

- ``drawing``: the repository modules the drawing actually used (``recording``: every repository file whose code ran
  during the draw, every module an import statement named during it, and their modules' own top-level imports), with
  the digest of their bytes. The set is recorded with the reference and a lookup hashes that set again: an edit to any
  of them makes the reference stale, and a file the drawing never used (the native core's Python side, the native
  route) never enters, so a native-only edit keeps every reference. A new import arrives through an importer whose
  bytes changed, so the recorded set cannot miss it.
- ``shared_source_hash``: the composed text of every shader the modes compose, every QML file of the scene with its
  shaders and the harness's drawing, mask and capture code (as before);
- and, checked at use, the native run's own logical digests against the reference's (``native_parity``): a changed
  simulation never meets a stale reference, it is drawn again.

Frames are kept as the run kept them (zlib, one file) and read back by index; masks bit-packed. A 60 s take is about
2 GB, so the default root is the scratch drive's (``DEFAULT_ROOT``), never the repository's.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The references' default folder (the drive layout's scratch, never the repository or X:).
DEFAULT_ROOT = Path(r"D:\Temp\Scratch\SRPSS\fast_proof\references")
#: The layout of a stored reference (a change makes old ones unreadable, never misread). 2: keyed on the run's inputs,
#: read while its recorded ``drawing`` sources are unchanged (format 1 hashed the whole visualizer package).
FORMAT = 2
ROOT = Path(__file__).resolve().parents[2]


#: The shader stages the Python renderers compile (composed with their includes and the conventions spliced in).
_STAGES = (".frag", ".vert", ".comp")


def _source_files() -> list[Path]:
    """The scene's files every reference shares, hashed by their bytes: its QML and its QML shaders (their sources and
    packs). The Python modules are each reference's own recorded ``drawing`` set (``recording``)."""
    from rendering.quick.bootstrap import quick_qml_root

    files = sorted(quick_qml_root().rglob("*.qml"))
    files += sorted(p for p in (quick_qml_root() / "shaders").rglob("*") if p.is_file())
    return files


#: Repository folders whose modules are never a reference's drawing source: the harness (its drawing, mask and capture
#: code is hashed piece by piece, ``_harness_sources``, so a judge change keeps the cache), the tests and evidence.
_NOT_DRAWING = ("tools", "tests", ".artifacts", ".claude")
#: The ``sys.monitoring`` tool ids ``recording`` may take (3 and 4 are unassigned by CPython).
_TOOL_IDS = (3, 4)


def _drawing_file(path) -> str | None:
    """``path`` as a drawing source (its repository-relative name), or None: outside the repository, not a Python
    file on disk, or under ``_NOT_DRAWING``."""
    if not path:
        return None
    try:
        resolved = Path(path).resolve()
        rel = resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return None
    if resolved.suffix != ".py" or not rel.parts or rel.parts[0] in _NOT_DRAWING or not resolved.is_file():
        return None
    return rel.as_posix()


def _top_level_imports(rel: str) -> set[str]:
    """The module names ``rel``'s top-level import statements name (its body runs them whenever it is imported), with
    each ``from X import y``'s ``X.y`` as well (``y`` may be a submodule)."""
    import ast

    path = ROOT / rel
    package = ".".join(Path(rel).with_suffix("").parts)
    if path.name == "__init__.py":
        package = package.rsplit(".", 1)[0] if "." in package else package
    else:
        package = package.rsplit(".", 1)[0] if "." in package else ""
    names: set[str] = set()
    try:
        tree = ast.parse(path.read_bytes())
    except (OSError, SyntaxError, ValueError):
        return names
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[:len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts + ([base] if base else []))
            if base:
                names.add(base)
                names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def _module_file(name: str) -> str | None:
    module = sys.modules.get(name)
    return None if module is None else _drawing_file(getattr(module, "__file__", None))


class recording:
    """Records what a drawing uses, while it holds (``with recording() as used: ...; used.files()``): every repository
    file whose code starts running (``sys.monitoring``'s ``PY_START``, once per code object), every module an import
    statement names (``builtins.__import__``, also when the module was already loaded), and the top-level imports of
    each, closed over the repository's modules. Whatever else the process imported (the native core's side in a native
    run, the harness) does not enter unless the drawing used it."""

    def __init__(self) -> None:
        self._ran: set[str] = set()
        self._imported: set[str] = set()
        self._tool: int | None = None
        self._import = None

    def __enter__(self) -> "recording":
        import builtins

        monitoring = sys.monitoring
        for tool in _TOOL_IDS:
            if monitoring.get_tool(tool) is None:
                monitoring.use_tool_id(tool, "srpss-python-references")
                self._tool = tool
                break
        if self._tool is None:
            raise RuntimeError(f"no free sys.monitoring tool id among {_TOOL_IDS}")
        ran = self._ran

        def started(code, _offset):
            ran.add(code.co_filename)
            return monitoring.DISABLE

        monitoring.register_callback(self._tool, monitoring.events.PY_START, started)
        monitoring.restart_events()                      # a code object disabled by an earlier recording runs again
        monitoring.set_events(self._tool, monitoring.events.PY_START)
        original = self._import = builtins.__import__
        imported = self._imported

        def recorded_import(name, globals=None, locals=None, fromlist=(), level=0):
            module = original(name, globals, locals, fromlist, level)
            if level == 0:
                imported.add(name)
                imported.update(f"{name}.{item}" for item in (fromlist or ()) if isinstance(item, str))
            else:
                base = getattr(module, "__name__", None)
                if base:
                    imported.add(base)
                    imported.update(f"{base}.{item}" for item in (fromlist or ()) if isinstance(item, str))
            return module

        builtins.__import__ = recorded_import
        return self

    def __exit__(self, *exc) -> None:
        import builtins

        builtins.__import__ = self._import
        monitoring = sys.monitoring
        monitoring.set_events(self._tool, 0)
        monitoring.register_callback(self._tool, monitoring.events.PY_START, None)
        monitoring.free_tool_id(self._tool)

    def files(self) -> list[str]:
        """The drawing's repository files, sorted (closed over their top-level imports)."""
        found = {rel for rel in map(_drawing_file, self._ran) if rel}
        found |= {rel for rel in map(_module_file, self._imported) if rel}
        pending = list(found)
        while pending:
            current = pending.pop()
            names = _top_level_imports(current)
            # Its packages: importing a module runs each enclosing package's ``__init__`` first.
            parts = Path(current).parent.parts
            names |= {".".join(parts[:n]) for n in range(1, len(parts) + 1)}
            for name in names:
                rel = _module_file(name)
                if rel and rel not in found:
                    found.add(rel)
                    pending.append(rel)
        return sorted(found)

    def drawing(self) -> dict:
        """What ``store`` keeps: the files and their digest (``drawing_digest``)."""
        files = self.files()
        return {"files": files, "digest": drawing_digest(files)}


def drawing_digest(files) -> str | None:
    """The digest of ``files`` (repository-relative) by name and bytes, or None when one no longer exists."""
    digest = hashlib.sha256()
    for rel in files:
        path = ROOT / rel
        if not path.is_file():
            return None
        digest.update(rel.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _composed_shaders() -> list[tuple[str, str]]:
    """(name, the text it compiles as) of every shader the Python renderers compile: the composer's own output, so the
    includes and the conventions it splices (``rendering/gl_programs/conventions.py``) are in the key as compiled."""
    from widgets.spotify_visualizer import shaders

    folder = Path(shaders.__file__).resolve().parent
    return [(p.name, shaders.compose_shader_source(p)) for p in sorted(folder.iterdir())
            if p.is_file() and p.suffix in _STAGES]


def _harness_sources() -> list[tuple[str, str]]:
    """The harness code that draws, masks and captures a reference (its sources, not its whole modules, so a judge
    change keeps the cache)."""
    import inspect

    import tools.expanded_visualizer_evidence as evidence
    from tools import pixel_tolerance
    from tools.visualizer_replay import owner_render_parity as parity

    pieces = [parity.SceneMirror, parity._SpilledFrames, parity.drawn_run, parity._python_mappings_run,
              parity._python_reference, parity._python_masks, parity._recorded_python_reference,
              parity.content_backdrop,
              parity._read_bound_framebuffer, parity.rule_a_masks,
              parity.single_sample_scene_targets, parity.card_placement, parity.parity_script,
              pixel_tolerance.translucent_by_backgrounds, evidence.HiddenDisplayHost]
    return [(f"{piece.__module__}.{piece.__qualname__}", inspect.getsource(piece)) for piece in pieces]


def shared_source_hash() -> str:
    """A digest of what every Python reference shares (audit 9 M1): the scene's QML files (``_source_files``), the
    composed text of every shader the renderers compile (``_composed_shaders``) and the harness's drawing, mask and
    capture code (``_harness_sources``). Each reference's own Python modules are its ``drawing`` set."""
    digest = hashlib.sha256()
    for path in _source_files():
        digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    for name, text in _composed_shaders() + _harness_sources():
        digest.update(name.encode() + b"\0" + text.encode() + b"\0")
    return digest.hexdigest()


def clip_digest(frames) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(repr(frame).encode())
    return digest.hexdigest()


#: ``made_of``'s keys that name the folder: the run's inputs (the sources are checked at ``load``, so a source change
#: replaces the reference in its folder instead of leaving the old one beside it).
_RUN_INPUTS = ("format", "mode", "run", "settings", "clip", "clip_digest", "placement", "dpr")


def reference_key(mode: str, suffix: str, settings: dict, clip_name: str, clip_frames, placement: str,
                  dpr: float) -> tuple[str, dict]:
    """(the folder name, what it is made of): the run's inputs and ``shared_sources``; ``store`` adds the drawing's
    recorded sources."""
    made_of = {"format": FORMAT, "mode": mode, "run": suffix, "settings": settings, "clip": clip_name,
               "clip_digest": clip_digest(clip_frames), "placement": placement, "dpr": float(dpr),
               "shared_sources": shared_source_hash()}
    inputs = {name: made_of[name] for name in _RUN_INPUTS}
    text = json.dumps(inputs, sort_keys=True, default=str)
    return f"{mode}_{hashlib.sha256(text.encode()).hexdigest()[:24]}", made_of


class StoredFrames:
    """A stored run's frames, ``(shape, zlib bytes)`` by index, read from its file on demand."""

    def __init__(self, path: Path, entries: list) -> None:
        self._path = path
        self._entries = [(tuple(shape), int(offset), int(size)) for shape, offset, size in entries]
        self._file: Any = None

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int):
        shape, offset, size = self._entries[index]
        if self._file is None:
            self._file = self._path.open("rb")
        self._file.seek(offset)
        return shape, self._file.read(size)

    def __iter__(self):
        return (self[index] for index in range(len(self)))

    def close(self) -> None:
        """The frames file's handle released (before the reference is replaced: Windows keeps an open file)."""
        if self._file is not None:
            self._file.close()
            self._file = None


def release(loaded: tuple | None) -> None:
    """Close what a loaded reference holds open (``load``'s result)."""
    if loaded is None:
        return
    frames = loaded[0].get("frames")
    if hasattr(frames, "close"):
        frames.close()


class StoredMasks(Mapping):
    """A stored run's masks by input (bool arrays), decoded on demand."""

    def __init__(self, path: Path, entries: dict) -> None:
        self._path = path
        self._entries = {int(k): v for k, v in entries.items()}

    def __getitem__(self, index: int):
        import numpy as np

        shape, offset, size = self._entries[int(index)]
        with self._path.open("rb") as stream:
            stream.seek(offset)
            bits = np.frombuffer(zlib.decompress(stream.read(size)), np.uint8)
        count = int(shape[0]) * int(shape[1])
        return np.unpackbits(bits, count=count).astype(bool).reshape(shape)

    def __iter__(self):
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


#: The Python run's report keys a reference keeps (besides its frames).
_KEPT = ("pixels", "digests", "inputs", "final_mode", "phase", "phases", "on_worker", "worker", "mode", "modes")


def store(folder: Path, made_of: dict, python: dict, masks: Mapping, mappings: list,
          backdrop_frames: int, *, drawing: dict) -> None:
    """Write a reference (into a new folder, renamed into place once whole: a killed write leaves no reference).
    ``drawing``: what drew it (``recording.drawing()``), kept with ``made_of`` and checked by ``load``."""
    import numpy as np

    if not drawing.get("files") or drawing.get("digest") is None:
        raise ValueError("a reference needs its drawing's recorded sources (recording.drawing())")

    folder = Path(folder)
    partial = folder.with_name(folder.name + ".partial")
    partial.mkdir(parents=True, exist_ok=True)
    entries = []
    with (partial / "frames.bin").open("wb") as stream:
        for shape, data in python["frames"]:
            entries.append([list(shape), stream.tell(), len(data)])
            stream.write(data)
    mask_entries = {}
    with (partial / "masks.bin").open("wb") as stream:
        for index, mask in masks.items():
            mask = np.asarray(mask, bool)
            data = zlib.compress(np.packbits(mask.ravel()).tobytes(), 1)
            mask_entries[int(index)] = [list(mask.shape), stream.tell(), len(data)]
            stream.write(data)
    index = {"made_of": made_of, "drawing": {"files": list(drawing["files"]), "digest": drawing["digest"]},
             "frames": entries, "masks": mask_entries, "mappings": mappings,
             "backdrop_frames": int(backdrop_frames), "run": {k: python.get(k) for k in _KEPT if k in python}}
    (partial / "reference.json").write_text(json.dumps(index, default=str), encoding="utf-8")
    import shutil

    # Swap: the old reference aside, the new one into place, then the old one removed (a failure leaves one whole
    # reference at the key, never none).
    old = folder.with_name(folder.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if folder.exists():
        folder.rename(old)
    partial.rename(folder)
    if old.exists():
        shutil.rmtree(old)


def stale_sources(drawing: dict | None) -> str | None:
    """Why a stored ``drawing`` no longer matches the tree (None: it matches): its recorded files hashed again."""
    if not drawing or not drawing.get("files"):
        return "no recorded drawing sources"
    files = list(drawing["files"])
    if drawing_digest(files) == drawing.get("digest"):
        return None
    missing = [rel for rel in files if not (ROOT / rel).is_file()]
    return f"recorded files missing: {missing[:5]}" if missing else "a recorded file's bytes changed"


def load(folder: Path, made_of: dict) -> tuple[dict, Mapping, list, int] | None:
    """(the Python run, its masks, its window maps, the backdrop's frame count), or None when there is no whole
    reference made of exactly ``made_of`` whose recorded drawing sources are unchanged (``stale_sources``)."""
    folder = Path(folder)
    path = folder / "reference.json"
    if not path.is_file():
        return None
    index = json.loads(path.read_text(encoding="utf-8"))
    if json.dumps(index.get("made_of"), sort_keys=True, default=str) != json.dumps(made_of, sort_keys=True,
                                                                                   default=str):
        return None
    if stale_sources(index.get("drawing")) is not None:
        return None
    python = dict(index["run"])
    python["frames"] = StoredFrames(folder / "frames.bin", index["frames"])
    python["lit"] = []
    masks = StoredMasks(folder / "masks.bin", index["masks"])
    mappings = [tuple(tuple(row) if isinstance(row, list) else row for row in entry) for entry in index["mappings"]]
    return python, masks, mappings, int(index["backdrop_frames"])


__all__ = ["DEFAULT_ROOT", "StoredFrames", "StoredMasks", "drawing_digest", "load", "recording", "reference_key",
           "shared_source_hash", "stale_sources", "store"]

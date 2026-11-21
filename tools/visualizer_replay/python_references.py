"""Cached Python references for rule (a) (fast long-clip proof, part 2 step 3; ``Docs/Guides/Native_Parity_And_Timing_
Proof.md`` section 3: the Python renderers are frozen until N5.2h deletes them, so their frames are drawn once per take,
mode, variant and placement and kept).

A reference is what ``owner_render_parity.native_parity`` draws on the Python side of one run: the Python run (its frame
records, its frames, its logical digests, its Spectrum window maps) and the backdrop run's translucency masks. It is
stored under ``root/<key>/`` where the key is the run's inputs and the Python renderer's sources:

- the mode, the run's settings, the clip (its name and a digest of its frames), the placement and the device pixel
  ratio;
- ``renderer_source_hash``: every Python module of the Quick visualizer package, every shader source the modes compose
  and every QML file of the scene, so any change to the drawing code makes a new key (nothing is re-used across one);
- and, checked at use, the native run's own logical digests against the reference's (``native_parity``): a changed
  simulation never meets a stale reference, it is drawn again.

Frames are kept as the run kept them (zlib, one file) and read back by index; masks bit-packed. A 60 s take is about
2 GB, so the default root is the scratch drive's (``DEFAULT_ROOT``), never the repository's.
"""
from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: The references' default folder (the drive layout's scratch, never the repository or X:).
DEFAULT_ROOT = Path(r"D:\Temp\Scratch\SRPSS\fast_proof\references")
#: The layout of a stored reference (a change makes old ones unreadable, never misread).
FORMAT = 1
ROOT = Path(__file__).resolve().parents[2]


#: The shader stages the Python renderers compile (composed with their includes and the conventions spliced in).
_STAGES = (".frag", ".vert", ".comp")


def _source_files() -> list[Path]:
    """The Python drawing code's files, hashed by their bytes: the Quick visualizer package, the GL program helpers
    (``rendering/gl_programs``, the conventions' owner), the shader composer, the scene's QML and its QML shaders (their
    sources and packs)."""
    from rendering.quick.bootstrap import quick_qml_root

    files = sorted((ROOT / "rendering" / "quick" / "visualizer").rglob("*.py"))
    files += sorted((ROOT / "rendering" / "gl_programs").rglob("*.py"))
    files.append(ROOT / "widgets" / "spotify_visualizer" / "shaders" / "__init__.py")
    files += sorted(quick_qml_root().rglob("*.qml"))
    files += sorted(p for p in (quick_qml_root() / "shaders").rglob("*") if p.is_file())
    return files


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
              parity._python_reference, parity._python_masks, parity.content_backdrop,
              parity._read_bound_framebuffer, parity.rule_a_masks,
              parity.single_sample_scene_targets, parity.card_placement, parity.parity_script,
              pixel_tolerance.translucent_by_backgrounds, evidence.HiddenDisplayHost]
    return [(f"{piece.__module__}.{piece.__qualname__}", inspect.getsource(piece)) for piece in pieces]


def renderer_source_hash() -> str:
    """A digest of everything that makes a Python reference (audit 9 M1): the drawing code's files
    (``_source_files``), the composed text of every shader the renderers compile (``_composed_shaders``) and the
    harness's drawing, mask and capture code (``_harness_sources``)."""
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


def reference_key(mode: str, suffix: str, settings: dict, clip_name: str, clip_frames, placement: str,
                  dpr: float) -> tuple[str, dict]:
    """(the folder name, what it was made of)."""
    made_of = {"format": FORMAT, "mode": mode, "run": suffix, "settings": settings, "clip": clip_name,
               "clip_digest": clip_digest(clip_frames), "placement": placement, "dpr": float(dpr),
               "renderer_sources": renderer_source_hash()}
    text = json.dumps(made_of, sort_keys=True, default=str)
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
          backdrop_frames: int) -> None:
    """Write a reference (into a new folder, renamed into place once whole: a killed write leaves no reference)."""
    import numpy as np

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
    index = {"made_of": made_of, "frames": entries, "masks": mask_entries, "mappings": mappings,
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


def load(folder: Path, made_of: dict) -> tuple[dict, Mapping, list, int] | None:
    """(the Python run, its masks, its window maps, the backdrop's frame count), or None when there is no whole
    reference made of exactly ``made_of``."""
    folder = Path(folder)
    path = folder / "reference.json"
    if not path.is_file():
        return None
    index = json.loads(path.read_text(encoding="utf-8"))
    if json.dumps(index.get("made_of"), sort_keys=True, default=str) != json.dumps(made_of, sort_keys=True,
                                                                                   default=str):
        return None
    python = dict(index["run"])
    python["frames"] = StoredFrames(folder / "frames.bin", index["frames"])
    python["lit"] = []
    masks = StoredMasks(folder / "masks.bin", index["masks"])
    mappings = [tuple(tuple(row) if isinstance(row, list) else row for row in entry) for entry in index["mappings"]]
    return python, masks, mappings, int(index["backdrop_frames"])


__all__ = ["DEFAULT_ROOT", "StoredFrames", "StoredMasks", "load", "reference_key", "renderer_source_hash", "store"]

"""A native mode's program, from Python (N2.5's standing port rule, every N5 port reuses it).

Studio and Settings work on a Visualizer mode never needs a native build round:

- the fragment shader the core draws is the product's own pack, baked by ``tools/regen_qrc.py --shaders`` beside its
  source (``widgets/spotify_visualizer/shaders/<mode>.frag.qsb``) and handed to the core as bytes at run time
  (:func:`mode_fragment_pack`);
- every uniform that comes from Settings or the card is resolved here, in Python, from the spec, and handed over by
  name (:func:`settings_json`); the core packs it at the member's reflected offset, type and stride
  (``native/core/src/program_blocks.h``), refuses an unknown name, and reports a member nobody filled;
- the core's hand-written C++ holds only per-frame and simulation arithmetic (Spectrum: ``SPECTRUM_FRAME_MEMBERS``).

A new Settings-only uniform is then a shader line, a spec entry, its resolution in the mode's settings function and a
``regen_qrc --shaders`` bake: no C++, no module build.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping


def mode_fragment_pack_path(mode_id: str) -> Path:
    """Where ``mode_id``'s fragment pack lies (beside its source; the frozen build ships the folder)."""
    from widgets.spotify_visualizer import shaders

    filename = shaders._ALL_SHADER_FILES.get(str(mode_id))
    if filename is None:
        raise KeyError(f"no fragment shader for mode {mode_id!r}")
    return Path(shaders.__file__).resolve().parent / f"{filename}.qsb"


def mode_fragment_pack(mode_id: str) -> bytes:
    """``mode_id``'s fragment pack (a serialized QShader); raises when it was never baked."""
    path = mode_fragment_pack_path(mode_id)
    if not path.is_file():
        raise FileNotFoundError(f"{path.name} is missing: run tools/regen_qrc.py --shaders")
    return path.read_bytes()


def _plain(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"a setting is not finite: {value!r}")
        return value
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    raise TypeError(f"a setting is a number or a list of numbers, not {type(value).__name__}")


def settings_json(values: Mapping[str, Any]) -> str:
    """``values`` (name -> number or sequence of numbers) as the core's settings JSON."""
    return json.dumps({str(name): _plain(value) for name, value in values.items()}, separators=(",", ":"),
                      sort_keys=True)


__all__ = ["mode_fragment_pack", "mode_fragment_pack_path", "settings_json"]

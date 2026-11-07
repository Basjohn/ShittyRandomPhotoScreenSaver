"""Neon Lake's engine answers, per production tick, recorded through the production replay (out of process).

Neon Lake (mode id ``shockwave_grid``) runs Spectrum's own frame runtime and capture (``_capture_spectrum_family``)
under its own identity, plus the transient bus's onsets, the musical level / intensity and the pre-AGC analysis
spectrum Terrain Reaction reads, so its waves and land are the engine's processing on the process clock exactly like
Spectrum's bars. This module is its worker (``python -m ui.studio.shockwave_grid_recorded_inputs``, or the frozen
app's ``--studio-clip-worker`` path), run through the shared ``ClipLoadJob``; the recorder, synthetic audio and
replay are the Spectrum family's shared ``ui.studio.engine_answers``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from ui.studio import engine_answers
from ui.studio.engine_answers import frame_digest, to_inputs  # noqa: F401  (re-exported)

MODE = "shockwave_grid"
# Terrain Reaction (a mode-owned switch and amounts) reads these only while it is on; recorded every tick so turning
# it on in the Studio replays from the record (``_capture_shockwave_grid``).
NEON_LAKE = engine_answers.EngineAnswerMode(
    MODE, conditional_reads=("get_musical_level", "get_pre_agc_analysis_spectrum"), production_lanes=True)


def extract(source: str | Path, settings: Mapping[str, Any], **options) -> dict:
    """``engine_answers.extract`` for Neon Lake (``seconds``, ``features``, ``frames_out``)."""
    return engine_answers.extract(NEON_LAKE, source, settings, **options)


def main(argv: list[str]) -> int:
    return engine_answers.worker_main(NEON_LAKE, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

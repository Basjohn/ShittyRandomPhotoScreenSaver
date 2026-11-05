"""Spectrum's engine answers, per production tick, recorded through the production replay (out of process).

Spectrum's input is the engine's *own processing* (``consume_engine_bars`` ticks the beat engine on the process
clock), so this module runs as a *separate process* (``python -m ui.studio.spectrum_recorded_inputs``, or the frozen
app's ``--studio-clip-worker`` path) through the shared event-driven ``ClipLoadJob``. The recorder, the synthetic
audio and the replay are the Spectrum family's shared ``ui.studio.engine_answers``; this module only names the mode.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from ui.studio import engine_answers
from ui.studio.engine_answers import (  # noqa: F401  (re-exported: the Spectrum worker's public names)
    DURATION, HISTORY, PREROLL, RATE, SEED, START, STEP, SYNTHETIC, SYNTHETIC_PREFIX, frame_digest, load_source,
    synthetic_features, synthetic_score, to_inputs,
)

MODE = "spectrum"
ROOT = engine_answers.ROOT
SPECTRUM = engine_answers.EngineAnswerMode(MODE)


def extract(source: str | Path, settings: Mapping[str, Any], **options) -> dict:
    """``engine_answers.extract`` for Spectrum (``seconds``, ``features``, ``frames_out``)."""
    return engine_answers.extract(SPECTRUM, source, settings, **options)


def main(argv: list[str]) -> int:
    return engine_answers.worker_main(SPECTRUM, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

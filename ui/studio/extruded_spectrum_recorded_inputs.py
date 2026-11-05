"""Extruded Spectrum's engine answers, per production tick, recorded through the production replay (out of process).

Extruded Spectrum runs Spectrum's own frame runtime and capture (``_capture_spectrum_family``) under its own identity,
so its bars are the engine's processing on the process clock exactly like Spectrum's. This module is its worker
(``python -m ui.studio.extruded_spectrum_recorded_inputs``, or the frozen app's ``--studio-clip-worker`` path), run
through the shared ``ClipLoadJob``; the recorder, synthetic audio and replay are the Spectrum family's shared
``ui.studio.engine_answers``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from ui.studio import engine_answers
from ui.studio.engine_answers import frame_digest, to_inputs  # noqa: F401  (re-exported)

MODE = "extruded_spectrum"
EXTRUDED_SPECTRUM = engine_answers.EngineAnswerMode(MODE)


def extract(source: str | Path, settings: Mapping[str, Any], **options) -> dict:
    """``engine_answers.extract`` for Extruded Spectrum (``seconds``, ``features``, ``frames_out``, ``environment``)."""
    return engine_answers.extract(EXTRUDED_SPECTRUM, source, settings, **options)


def main(argv: list[str]) -> int:
    return engine_answers.worker_main(EXTRUDED_SPECTRUM, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

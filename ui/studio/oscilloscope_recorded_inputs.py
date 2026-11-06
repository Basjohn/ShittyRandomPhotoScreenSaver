"""Oscilloscope's engine answers, per production tick, recorded through the production replay (out of process).

Oscilloscope's capture (``logical_frame_capture._capture_oscilloscope``) reads the beat engine every tick: the capture
history (the raw audio the trace is drawn from, a NumPy array the engine keeps as the same object while its capture
serial holds), the 256-sample waveform, the transient bus's onsets after the runtime's serial, the musical level and
intensity, the pre-AGC analysis spectrum (Spectral Colour), the history's rate and the source identities; and
``consume_engine_bars`` ticks the engine on the process clock. So it uses the shared recorded engine answers
(``ui.studio.engine_answers``): this module is its worker (``python -m ui.studio.oscilloscope_recorded_inputs``, or
the frozen app's ``--studio-clip-worker`` path), run through the shared ``ClipLoadJob``. The history arrays are
recorded by identity and travel as raw bytes in a binary sidecar (``replay_engine.RecordedArrays``).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from ui.studio import engine_answers
from ui.studio.engine_answers import frame_digest, to_inputs  # noqa: F401  (re-exported)

MODE = "oscilloscope"
OSCILLOSCOPE = engine_answers.EngineAnswerMode(MODE)


def extract(source: str | Path, settings: Mapping[str, Any], **options) -> dict:
    """``engine_answers.extract`` for Oscilloscope (``seconds``, ``features``, ``frames_out``)."""
    return engine_answers.extract(OSCILLOSCOPE, source, settings, **options)


def main(argv: list[str]) -> int:
    return engine_answers.worker_main(OSCILLOSCOPE, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

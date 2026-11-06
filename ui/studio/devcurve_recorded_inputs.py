"""DevCurve's engine answers, per production tick, recorded through the production replay (out of process).

DevCurve's step (``tick_pipeline.dispatch_devcurve_field``, its logical tick hook) reads the beat engine's live
answers every tick: the pre-AGC control lanes, the transient lanes, the musical level and intensity and the
authoritative source frame, all produced by the engine's own analysis, which the technical (audio analysis) controls
configure and which runs on the process clock. Only an out-of-process replay may pin that clock, so this module runs
as a *separate process* (``python -m ui.studio.devcurve_recorded_inputs``, or the frozen app's
``--studio-clip-worker`` path) through the shared event-driven ``ClipLoadJob``. The recorder, the synthetic audio and
the replay are the shared ``ui.studio.engine_answers``; this module only names the mode.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from ui.studio import engine_answers
from ui.studio.engine_answers import frame_digest, to_inputs  # noqa: F401  (re-exported)

MODE = "devcurve"
DEVCURVE = engine_answers.EngineAnswerMode(MODE)


def extract(source: str | Path, settings: Mapping[str, Any], **options) -> dict:
    """``engine_answers.extract`` for DevCurve (``seconds``, ``features``, ``frames_out``)."""
    return engine_answers.extract(DEVCURVE, source, settings, **options)


def main(argv: list[str]) -> int:
    return engine_answers.worker_main(DEVCURVE, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

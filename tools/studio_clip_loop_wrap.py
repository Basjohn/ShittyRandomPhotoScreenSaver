"""The picture at a clip's wrap, for every Studio with recorded inputs (no window, no renderer).

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python tools/studio_clip_loop_wrap.py [--clip growing_pains] [--out FILE]

Each Studio's evaluator is driven the way the Studio drives it (``ui/studio/transport.py`` on a fake clock, the
controller's ``evaluation_time`` rule) through the wrap of a shipped loop clip, and the size of every frame-to-frame
step of the mode's published simulation state is measured. The step across the wrap is compared with the ordinary steps
around it and with the Studio's old behaviour (the transport's time restarting at zero) as the control. No pixels are
drawn: the frame the evaluator hands the renderer is the mode's whole state, so a jump in it is a jump on screen.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLIPS = ROOT / "assets" / "production" / "studio_clips"

# family -> (recorded-input worker module, evaluator module, evaluator class, engine-answer family)
FAMILIES = {
    "bubble": ("bubble_recorded_inputs", "bubble_adapter", "BubbleStudioEvaluator", False),
    "sphere": ("sphere_recorded_inputs", "sphere_adapter", "SphereStudioEvaluator", False),
    "extruded_bubble": ("extruded_bubble_recorded_inputs", "extruded_bubble_adapter",
                        "ExtrudedBubbleStudioEvaluator", False),
    "waveform": ("waveform_recorded_inputs", "waveform_adapter", "WaveformStudioEvaluator", False),
    "spectrum": ("spectrum_recorded_inputs", "spectrum_adapter", "SpectrumStudioEvaluator", True),
    "extruded_spectrum": ("extruded_spectrum_recorded_inputs", "extruded_spectrum_adapter",
                          "ExtrudedSpectrumStudioEvaluator", True),
    "oscilloscope": ("oscilloscope_recorded_inputs", "oscilloscope_adapter", "OscilloscopeStudioEvaluator", True),
    "devcurve": ("devcurve_recorded_inputs", "devcurve_adapter", "DevCurveStudioEvaluator", True),
    "shockwave_grid": ("shockwave_grid_recorded_inputs", "shockwave_grid_adapter", "NeonLakeStudioEvaluator", True),
}


# Paths of a mode's state that jump by design, left out of the step: DevCurve's travelling highlights leave at one edge
# and respawn at the other (position, variant and amplitude restart there), whenever their own travel says, not when
# the music or the wrap does.
HIDDEN_JUMPS = {"devcurve": r"\.specular_slots"}


def values() -> dict:
    from core.settings.default_contract import require_canonical_default
    return dict(require_canonical_default("widgets.spotify_visualizer"))


def state_map(frame) -> dict:
    """Every number of the frame's simulation state by its path (a mode that publishes ``mode_state`` is judged on
    that, not on the audio it draws), except bit-set words, which are identifiers, not positions. By path, so a step
    compares like with like when a bubble is born or a ghost retires."""
    frame = getattr(frame, "mode_state", frame)
    out: dict = {}

    def walk(x, path="", depth=0):
        if depth > 8:
            return
        if isinstance(x, (bool, int, float)):
            out[path] = float(x)
        elif isinstance(x, np.ndarray):
            if x.dtype.kind in "fiub":
                for i, v in enumerate(x.astype(float).ravel()[:4000]):
                    out[f"{path}[{i}]"] = float(v)
        elif isinstance(x, (tuple, list)):
            for i, item in enumerate(x):
                walk(item, f"{path}[{i}]", depth + 1)
        elif isinstance(x, dict):
            for key in sorted(x, key=str):
                walk(x[key], f"{path}.{key}", depth + 1)
        elif is_dataclass(x) and not isinstance(x, type):
            for field in fields(x):
                if not field.name.endswith("_bits"):
                    walk(getattr(x, field.name), f"{path}.{field.name}", depth + 1)
        elif hasattr(x, "__dict__") and not callable(x):
            for key, item in sorted(vars(x).items()):
                if not key.startswith("__") and not key.endswith("_bits"):
                    walk(item, f"{path}.{key}", depth + 1)
    walk(frame)
    return out


def step_size(a: dict, b: dict) -> float:
    """The distance between two state maps over every path either has (a path one lacks counts as 0)."""
    return float(np.sqrt(sum((a.get(k, 0.0) - b.get(k, 0.0)) ** 2 for k in a.keys() | b.keys())))


def beam_state(evaluator, _frame) -> dict:
    """Oscilloscope's carried state (afterglow, held ghosts, flare, drive, tone), not the trace it draws from the
    music: the evaluator's own reads of the frame on screen."""
    signals = evaluator.measurements()["signals"]
    return {k: float(signals[k]) for k in ("Afterglow", "Ghosts", "Flare", "Drive", "Tone")}


class NoLoader:
    """An engine-answer evaluator's loader that must not run: the answers on hand were recorded for these values."""

    def __call__(self, fixture, values, finished):
        raise AssertionError("the wrap must not start an analysis")


_extracts: dict = {}


def recorded_inputs(family: str, clip: str):
    """The family's recorded inputs for a shipped clip (analysed in this process, memoised)."""
    import importlib
    from ui.studio.adapter import RECORDED, StudioFixture
    key = (family, clip)
    if key not in _extracts:
        module = importlib.import_module("ui.studio." + FAMILIES[family][0])
        path = CLIPS / (clip + ".srclip")
        data = module.extract(str(path) if FAMILIES[family][3] else path, values(), seconds=None)
        fixture = StudioFixture("clip:" + clip, clip, RECORDED, float(data["duration"]), str(path))
        _extracts[key] = module.to_inputs(data, fixture)
    return _extracts[key]


def evaluator_for(family: str, clip: str):
    """(an evaluator of ``family`` with the clip's recorded inputs selected, the inputs)."""
    import importlib
    inputs = recorded_inputs(family, clip)
    cls = getattr(importlib.import_module("ui.studio." + FAMILIES[family][1]), FAMILIES[family][2])
    evaluator = cls(NoLoader()) if FAMILIES[family][3] else cls()
    evaluator.add_recorded(inputs)
    evaluator.select(inputs.fixture.id)
    return evaluator, inputs


def wrap_steps(evaluator, inputs, vals, *, loop: bool, window: float = 1.5, read=None):
    """Frame-to-frame step sizes through the wrap, driven the way the Studio drives them: the transport advances by
    wall time (a fake clock), the controller's rule picks the time, the evaluator answers. Returns the steps from
    ``window`` seconds before the wrap to ``window`` seconds after it, and the index of the one across it.
    ``loop=False`` is the Studio's old behaviour (the clip's own time, restarting at zero)."""
    from ui.studio.transport import StudioTransport
    period = inputs.fixture.duration
    now = [0.0]
    transport = StudioTransport(period, clock=lambda: now[0])
    transport.play()
    transport.on_frame()
    while transport.cycles == 0 and transport.time < period - window:          # the run up, at half rate
        now[0] += 1.0 / 30.0
        transport.on_frame()
        evaluator.evaluate(transport.evaluation_time(loop), vals, exact=True)
    vectors, passes = [], []
    while not (transport.cycles >= 1 and transport.time > window):
        now[0] += 1.0 / 60.0
        transport.on_frame()
        frame = evaluator.evaluate(transport.evaluation_time(loop), vals, exact=True)
        vectors.append(read(evaluator, frame) if read else state_map(frame))
        passes.append(transport.cycles)
    steps = np.array([step_size(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)])
    across = next(i for i in range(len(passes) - 1) if passes[i] == 0 and passes[i + 1] == 1)
    return steps, across


def probe(family: str, clip: str = "growing_pains") -> dict:
    """The wrap of ``family`` on ``clip``: the step across it, the ordinary steps (median, 95th percentile, maximum)
    and the same measurements for the old restart at zero."""
    import re
    vals = values()
    hidden = re.compile(HIDDEN_JUMPS[family]) if family in HIDDEN_JUMPS else None
    if family == "oscilloscope":
        read = beam_state
    elif hidden is not None:
        def read(_evaluator, frame):
            return {k: v for k, v in state_map(frame).items() if not hidden.search(k)}
    else:
        read = None
    out = {}
    for label, loop in (("carried", True), ("restart", False)):
        steps, across = wrap_steps(*evaluator_for(family, clip), vals, loop=loop, read=read)
        ordinary = np.delete(steps, [across])
        out[label] = {"wrap": float(steps[across]), "median": float(np.median(ordinary)),
                      "p95": float(np.percentile(ordinary, 95)), "max": float(ordinary.max()),
                      "after_wrap_moves": bool(steps[across + 1:].max() > 0.0)}
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", default="growing_pains")
    parser.add_argument("--family", action="append", choices=sorted(FAMILIES))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])
    result = {}
    for family in args.family or FAMILIES:
        result[family] = probe(family, args.clip)
        c, r = result[family]["carried"], result[family]["restart"]
        print(f"{family:18s} wrap step {c['wrap']:10.3f}  (ordinary median {c['median']:.3f} p95 {c['p95']:.3f})   "
              f"restart at zero {r['wrap']:10.3f}  ({r['wrap'] / max(c['wrap'], 1e-9):.0f}x)")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

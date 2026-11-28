"""The transition showcase loop through the production host on a real offscreen context.

Kept apart from test_release_media.py: its replay tests leave a non-GUI QCoreApplication, and an
OpenGL context needs a QGuiApplication."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from tools.release_media import MediaCase

@pytest.mark.qt
def test_a_transition_showcase_runs_there_and_back_with_exact_ends(qt_app, tmp_path: Path) -> None:
    from tools.release_media import TRANSITION_MID_HOLD_MS, capture_transition_loop, fit_scene

    colours = ((200, 40, 40), (40, 200, 40), (40, 40, 200), (200, 200, 40))
    scenes = tuple(Image.new("RGB", (400, 225), colour) for colour in colours)
    case = MediaCase("transition", "crossfade", "default", "Canonical")
    fps, duration_ms, size = 10, 500, (160, 90)
    pair = (2, 0)
    frames = capture_transition_loop(case, tmp_path / "frames", size=size, fps=fps, duration_ms=duration_ms,
                                     scenes=scenes, pair=pair, seed=713)
    run_frames = round(duration_ms * fps / 1000) + 1
    hold = round(TRANSITION_MID_HOLD_MS * fps / 1000)
    assert len(frames) == 2 * run_frames - 1 + hold
    first, second = (fit_scene(scenes[index], size).tobytes() for index in pair)

    def rgb(path):
        with Image.open(path) as image:
            return image.convert("RGB").tobytes()

    assert rgb(frames[0]) == first and rgb(frames[-1]) == first           # the loop's ends meet
    assert all(rgb(frames[run_frames - 1 + k]) == second for k in range(hold + 1))


@pytest.mark.qt
def test_the_showcase_frames_are_the_native_cores(qt_app, tmp_path: Path, monkeypatch) -> None:
    """Switch point 2: every showcase frame is drawn by the native background layer (the product's), none by the
    Python GL host."""
    from tools import native_transition_capture as native
    from tools.release_media import capture_transition_loop

    drawn: list[int] = []
    original = native.NativeTransitionCapture.render

    def counted(self, run, progress):
        result = original(self, run, progress)
        drawn.append(self.layer.runs)
        return result

    monkeypatch.setattr(native.NativeTransitionCapture, "render", counted)
    scenes = tuple(Image.new("RGB", (400, 225), colour) for colour in ((200, 40, 40), (40, 40, 200)))
    frames = capture_transition_loop(MediaCase("transition", "wipe", "default", "Canonical"), tmp_path / "frames",
                                     size=(160, 90), fps=10, duration_ms=500, scenes=scenes, pair=(0, 1), seed=713)
    run_frames = round(500 * 10 / 1000) + 1
    assert frames and len(drawn) == 2 * run_frames - 1                    # each leg's frames (the second's first skipped)
    assert all(runs >= 1 for runs in drawn)                               # the core drew the run each time

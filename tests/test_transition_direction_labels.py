"""Every direction label shows on screen what it says, through the production resolver and the
real renderers on an offscreen context (no window).

"Left to Right" starts on the left and travels right; a diagonal starts in its first named
corner. For reveals, the new picture shows first on the start side. Block Spins draws without
perspective, so its turn reads from the slab's edge: the start side's edge turns toward the
viewer and shows past the face.
"""
from __future__ import annotations

import copy
import random

import numpy as np
import pytest
from PIL import Image

from core.settings.default_contract import require_canonical_default
from rendering.quick.image_state import PresentationImage
from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec
from rendering.quick.transitions.state import TransitionRequest, TransitionRun
from rendering.transition_registry import get_transition_descriptor_for_runtime_identity
from rendering.transition_settings import BLOCK_SPIN_DIRECTIONS, transition_settings
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

W, H = 320, 180
_SIDES = {"L": np.s_[:, : W // 2], "R": np.s_[:, W // 2:], "T": np.s_[: H // 2], "B": np.s_[H // 2:],
          "TL": np.s_[: H // 2, : W // 2], "TR": np.s_[: H // 2, W // 2:],
          "BL": np.s_[H // 2:, : W // 2], "BR": np.s_[H // 2:, W // 2:]}
_OPPOSITE = {"L": "R", "R": "L", "T": "B", "B": "T", "TL": "BR", "BR": "TL", "TR": "BL", "BL": "TR"}
_START = {"Left to Right": "L", "Right to Left": "R", "Top to Bottom": "T", "Bottom to Top": "B",
          "Diagonal TL-BR": "TL", "Diagonal TR-BL": "TR", "Diagonal BL-TR": "BL", "Diagonal BR-TL": "BR",
          "Diagonal TL to BR": "TL", "Diagonal TR to BL": "TR",
          "Top-Left to Bottom-Right": "TL", "Top-Right to Bottom-Left": "TR",
          "Bottom-Left to Top-Right": "BL", "Bottom-Right to Top-Left": "BR"}
_CARDINAL = ("Left to Right", "Right to Left", "Top to Bottom", "Bottom to Top")
_DIAGONAL = ("Diagonal TL-BR", "Diagonal TR-BL")


def _sided(section):
    """The labels a transition's Settings page offers that start from a side or corner (its spec is
    what the page shows, so a label added there is checked here)."""
    return tuple(label for label in transition_settings(section).directions.codes if label in _START)


# (transition, its Settings section, labels the Settings page offers, extra section values, duration)
_REVEALS = (
    ("glass_shatter", "glass_shatter", _sided("glass_shatter"), {}, 6000),
    ("exploding_tiles", "exploding_tiles", _sided("exploding_tiles"), {}, 6000),
    ("pixel_accretion", "pixel_accretion", _sided("pixel_accretion"), {}, 3000),
    ("disintegrate", "disintegrate", _sided("disintegrate"), {}, 4000),
    ("volumetric_dissolve", "volumetric_dissolve", _sided("volumetric_dissolve"), {}, 4000),
    ("beam", "beam", _sided("beam"), {}, 3500),
    ("vhs", "vhs", _sided("vhs"), {}, 3000),
    ("burn", "burn", _CARDINAL + _DIAGONAL, {}, 3000),
    ("particle", "particle", _CARDINAL + ("Top-Left to Bottom-Right", "Top-Right to Bottom-Left",
                                          "Bottom-Left to Top-Right", "Bottom-Right to Top-Left"),
     {"mode": "Directional"}, 3000),
    ("slide", "slide", _sided("slide"), {"motion_style": "Linear"}, 3000),
    ("wipe", "wipe", _sided("wipe"), {}, 3000),
)


def _run(capture, transition_id, section, values, duration_ms):
    """Resolve one run exactly as production admits it, from the canonical defaults with
    ``values`` written into the transition's Settings section."""
    name = get_transition_descriptor_for_runtime_identity(transition_id).setting_name
    transitions = copy.deepcopy(require_canonical_default("transitions"))
    transitions.update(type=name, random_always=False)
    transitions.setdefault("activation", {})[name] = True
    transitions.setdefault("pool", {})[name] = True
    transitions[section] = {**transitions.get(section, {}), **values}

    class Settings:
        def get(self, key, default=None):
            return transitions if key == "transitions" else default

        def get_bool(self, _key):
            return True

    spec = resolve_quick_transition_spec(Settings(), random_source=random.Random(7))
    assert spec is not None and spec.transition_id == transition_id
    images = [PresentationImage(str(i), "diagnostic", (W, H), 1., (W, H), W * 4, image.tobytes())
              for i, image in enumerate(capture.images)]
    request = TransitionRequest(0, transition_id, spec.requested_name, False, duration_ms, spec.direction,
                                spec.parameters, *images)
    return TransitionRun.start(run_id=1, request=request, start_ns=0)


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


_CASES = [(t, s, label, v, d) for t, s, labels, v, d in _REVEALS for label in labels]


@pytest.mark.parametrize(("transition_id", "section", "label", "values", "duration_ms"), _CASES,
                         ids=[f"{c[0]}-{c[2]}" for c in _CASES])
def test_the_new_picture_shows_first_on_the_side_the_label_starts_from(
        capture, transition_id, section, label, values, duration_ms):
    run = _run(capture, transition_id, section, {**values, "direction": label}, duration_ms)
    source, destination = (np.asarray(image.convert("RGB"), dtype=np.int16) for image in capture.images)
    # Exploding Tiles throws its tiles up and lets them fall back: read it before they land.
    progress = 0.2 if transition_id == "exploding_tiles" else 0.3
    frame = np.asarray(capture.render(run, progress)[0].convert("RGB"), dtype=np.int16)
    new = (np.abs(frame - destination).sum(-1) < np.abs(frame - source).sum(-1)).astype(float)
    start = _START[label]
    assert new[_SIDES[start]].mean() > new[_SIDES[_OPPOSITE[start]]].mean() + 0.1


@pytest.fixture
def plain_capture(qt_app):
    capture = TransitionCapture(W, H, Image.new("RGB", (W, H), (200, 200, 200)),
                                Image.new("RGB", (W, H), (60, 200, 60)))
    yield capture
    capture.close()


@pytest.mark.parametrize("label", [label for label in BLOCK_SPIN_DIRECTIONS.codes if label in _START])
def test_block_spins_turns_its_start_side_toward_the_viewer(plain_capture, label):
    run = _run(plain_capture, "block_spins", "blockspin", {"direction": label}, 3000)
    frame = np.asarray(plain_capture.render(run, 0.4)[0].convert("RGB"), dtype=np.int16)
    ys, xs = np.nonzero(frame.sum(-1) > 150)
    x, y = xs - (W - 1) / 2, (ys - (H - 1) / 2) * W / H
    reach = {"L": (-x).max(), "R": x.max(), "T": (-y).max(), "B": y.max(), "TL": (-x - y).max(),
             "BR": (x + y).max(), "TR": (x - y).max(), "BL": (y - x).max()}
    start = _START[label]
    assert reach[start] > reach[_OPPOSITE[start]] + 3

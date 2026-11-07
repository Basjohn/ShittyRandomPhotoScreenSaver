"""A Spectrum drag no longer builds the production settings model per preview frame, and stays truthful.

Each new value of a dragged Spectrum-owned key used to build the whole production settings model
(``EngineAnswerMode.mode_kwargs``, about 10-14 ms) once per frame. A live gesture now takes the latest full build with
the one dragged entry replaced, but only for a numeric key the production build itself has shown to hand through
verbatim (a full build that differed from the previous one in that key alone produced exactly that key, with exactly
its value). Proven here: over a drag of every Spectrum-owned slider only the first preview frames build the model
(they prove the pass-through), none after them, the kwargs applied each preview frame equal a full production build of those values, and the release
replays exactly. Negative controls: without the learned pass-through every preview frame builds, and a key whose
build changes anything beyond itself is never patched. Timings are measured by ``tools/studio_drag_profile.py``
(evidence), not pinned here. Nothing shows a window.
"""
from __future__ import annotations

import pytest

from ui.studio.engine_answers import EngineAnswerEvaluator, EngineAnswerMode
from ui.studio.spectrum_adapter import SpectrumStudioEvaluator, spectrum_owned_keys
from ui.studio.spectrum_recorded_inputs import frame_digest

from tests.test_spectrum_studio import (  # noqa: F401  (fixtures and helpers)
    _clip_evaluator, _fresh_analysis_cache, canonical_section, recorded, shipped_clip, spec,
)

AT = 1.0
FRAMES = 8


def _drag_keys(values):
    """Every Spectrum-owned slider with a real interval (test-owned: derived from the registry)."""
    keys = []
    for control in spec().body_controls:
        value = values.get(control.key)
        if (control.key in spectrum_owned_keys() and isinstance(value, (int, float)) and not isinstance(value, bool)
                and getattr(control, "low", None) is not None and control.high > control.low):
            keys.append(control)
    return keys


def _drag(evaluator, values, control):
    """A drag of ``control`` across its range: one ``exact=False`` evaluation per frame. Returns the values seen
    and the model builds each frame made."""
    seen, builds = [], []
    for index in range(FRAMES):
        edited = dict(values)
        target = control.low + (control.high - control.low) * (0.2 + 0.6 * index / (FRAMES - 1))
        edited[control.key] = control.admit(target, values[control.key])
        before = evaluator.model_builds
        evaluator.evaluate(AT, edited, exact=False)
        builds.append(evaluator.model_builds - before)
        seen.append(edited)
    return seen, builds


@pytest.fixture
def applied(monkeypatch):
    """The kwargs each restyle hands the production state."""
    import widgets.spotify_visualizer.config_applier as applier
    calls = []
    original = applier.apply_logical_vis_mode_kwargs
    monkeypatch.setattr(applier, "apply_logical_vis_mode_kwargs",
                        lambda state, kwargs: (calls.append(dict(kwargs)), original(state, kwargs))[1])
    return calls


def test_a_drag_does_not_build_the_model_per_frame_and_applies_what_production_builds(qt_app, applied):
    clip = shipped_clip()
    values = canonical_section()
    data = recorded(clip.description, values, AT)
    evaluator = _clip_evaluator(clip, values=values, data=data)
    evaluator.evaluate(AT, values)
    mode = evaluator.mode
    controls = _drag_keys(values)
    assert controls
    for control in controls:                       # one drag after another, each released (committed)
        del applied[:]
        seen, builds = _drag(evaluator, values, control)
        # Only the first changed preview frames build (they prove the key passes through), never one per frame.
        assert sum(builds) <= 2, (control.key, builds)
        # One restyle per frame whose value changed (an integer key repeats values across frames).
        moved, previous = [], values[control.key]
        for edited in seen:
            if edited[control.key] != previous:
                moved.append(edited)
                previous = edited[control.key]
        assert len(moved) >= 2 and len(applied) == len(moved), control.key
        for kwargs, edited in zip(applied, moved):
            assert kwargs == mode.mode_kwargs(evaluator._effective(edited, evaluator._inputs)), control.key
        # The release replays exactly, from a full build (the same answers: a Spectrum-owned edit).
        values = seen[-1]
        exact = evaluator.evaluate(AT, values)
        expected = SpectrumStudioEvaluator(loader=evaluator._loader)       # the same answers, a fresh history
        expected.add_recorded(evaluator._inputs)
        expected.select(clip.id)
        assert frame_digest(exact) == frame_digest(expected.evaluate(AT, values)), control.key
        expected.release()
    evaluator.release()


def test_without_the_learned_pass_through_every_preview_frame_builds_negative_control(qt_app, monkeypatch):
    clip = shipped_clip()
    values = canonical_section()
    evaluator = _clip_evaluator(clip, values=values, data=recorded(clip.description, values, AT))
    evaluator.evaluate(AT, values)
    original = EngineAnswerEvaluator._learn

    def forgetful(self, effective, kwargs):
        original(self, effective, kwargs)
        self._pass_through.clear()
    monkeypatch.setattr(EngineAnswerEvaluator, "_learn", forgetful)
    control = _drag_keys(values)[0]
    _seen, builds = _drag(evaluator, values, control)
    assert builds == [1] * FRAMES
    evaluator.release()


def test_a_key_whose_build_changes_more_than_itself_is_never_patched(qt_app, monkeypatch, applied):
    """A production build that derives another entry from the dragged key: every preview frame builds."""
    clip = shipped_clip()
    values = canonical_section()
    evaluator = _clip_evaluator(clip, values=values, data=recorded(clip.description, values, AT))
    evaluator.evaluate(AT, values)
    control = _drag_keys(values)[0]
    original = EngineAnswerMode.mode_kwargs

    def deriving(self, vals):
        out = original(self, vals)
        out["_derived_from_drag"] = vals.get(control.key)
        return out
    monkeypatch.setattr(EngineAnswerMode, "mode_kwargs", deriving)
    del applied[:]
    seen, builds = _drag(evaluator, values, control)
    assert builds == [1] * FRAMES
    assert [kwargs["_derived_from_drag"] for kwargs in applied] == [edited[control.key] for edited in seen]
    evaluator.release()

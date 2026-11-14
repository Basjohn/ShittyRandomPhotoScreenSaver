"""The identity proof's run set (N1.6 coverage gap, 14 Nov): every mode is drawn at variants ``a`` and ``b`` and, with
offers, at every Choice offer, so no shader path a Toggle or a Choice selects goes unproved. Spec-derived only."""
from core.settings.visualizer_mode_settings import Choice, Toggle, require_mode_settings
from tools.conventions_identity import mode_runs
from tools.visualizer_replay import owner_worker_gate as gate


def _offer(control, value):
    return value if control.indexed else control.choices.index(value)


def test_every_mode_runs_both_variants_and_reaches_every_choice_offer():
    for mode in gate.modes():
        runs = mode_runs(mode, offers=True)
        suffixes = [suffix for suffix, _settings in runs]
        assert len(set(suffixes)) == len(suffixes), mode
        assert suffixes[:2] == ["", ":b"], mode
        base = runs[0][1]
        controls = require_mode_settings(mode).controls
        for control in controls:
            if isinstance(control, Toggle):
                # Both states of every Toggle are drawn (a: on, b: off).
                assert {runs[0][1][control.key], runs[1][1][control.key]} == {True, False}, (mode, control.key)
            if isinstance(control, Choice):
                reached = {_offer(control, settings[control.key]) for _suffix, settings in runs}
                assert reached == set(range(len(control.choices))), (mode, control.key)
        for suffix, settings in runs[2:]:
            moved = [key for key in settings if settings[key] != base[key]]
            assert len(moved) == 1 and suffix == f":{moved[0]}={suffix.rsplit('=', 1)[1]}", (mode, suffix, moved)


def test_without_offers_only_the_two_variants_run():
    for mode in gate.modes():
        assert [suffix for suffix, _settings in mode_runs(mode, offers=False)] == ["", ":b"]

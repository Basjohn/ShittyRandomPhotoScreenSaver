"""Layer L of the fast long-clip proof (``tools/visualizer_replay/native_record_identity.py``): per frame, the record,
settings and blocks the native route delivers against what the Python renderer uses, CPU only, on a short slice (the
shipped Studio clip's 5.5 s, the parity script's shortest). Needs the built native module for the block level (the
core's GPU-free packer); where it is not in this checkout the tests skip and say so.

Controls (run and seen failing): the record's field one ulp up at one input, and one frame that never reaches the core;
each is caught at that input and nowhere else.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
SECONDS = 5.5
AT = 100

needs_module = pytest.mark.skipif(
    not BUILT, reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")


def _run(mode: str, controls=()):
    from tools.visualizer_replay import native_record_identity as layer_l

    return layer_l.run(mode, seconds=SECONDS, module_dir=MODULE_DIR, controls=tuple(controls))


def test_every_native_mode_is_declared():
    # A port registered on the route without its layer L declaration is caught here.
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS
    from tools.visualizer_replay.native_record_identity import MODES

    assert set(NATIVE_MODE_IDS) <= set(MODES), sorted(set(NATIVE_MODE_IDS) - set(MODES))
    for mode, declaration in MODES.items():
        assert declaration.mode_id == mode and declaration.passes and declaration.ulp_field


def _pass_names(declaration) -> set:
    names = set()
    for value in declaration.passes.values():
        names.update((value,) if isinstance(value, str) else value)
    return names


@needs_module
@pytest.mark.parametrize("mode", ["spectrum", "devcurve", "bubble", "oscilloscope", "extruded_bubble"])
def test_the_native_path_receives_what_the_python_renderer_uses(qt_app, mode):
    report = _run(mode)
    halves = report["halves"]
    for name in ("first", "second"):
        assert halves[name]["expected"] > 0
        assert halves[name]["judged"] == halves[name]["expected"]
        assert halves[name]["compared"] == halves[name]["expected"]
    assert report["identical"], report["mismatches"][:3]
    # Not vacuous: every level compared every drawn frame, every declared pass and stream was compared.
    coverage = report["coverage"]
    compared = halves["first"]["compared"] + halves["second"]["compared"] + halves["switch"]["compared"]
    assert coverage["record_frames"] == coverage["settings_frames"] == compared
    assert coverage["settings_names"]
    assert coverage["settings_skipped"] == []           # every delivered setting compared (audit 9 L4)
    from tools.visualizer_replay.native_record_identity import MODES

    declared = MODES[mode]
    assert set(coverage["pass_frames"]) == _pass_names(declared)
    assert set(coverage["stream_frames"]) == set(declared.streams)
    assert all(count > 0 for count in coverage["stream_bytes"].values())


@needs_module
def test_a_run_of_the_widened_set_is_judged_under_its_own_settings(qt_app):
    # The Choice offers' runs (``--run``): every offer of the Oscilloscope's set, drawn under its own settings, and an
    # unknown key refused.
    from tools import conventions_identity
    from tools.visualizer_replay import native_record_identity as layer_l

    offers = [key for key, _settings in conventions_identity.mode_runs("oscilloscope", True) if key not in ("", ":b")]
    assert offers
    for key in offers:
        report = layer_l.run("oscilloscope", seconds=SECONDS, module_dir=MODULE_DIR, run_key=key)
        assert report["run"] == key and report["identical"], (key, report["mismatches"][:2])
    with pytest.raises(ValueError):
        layer_l.run("oscilloscope", seconds=SECONDS, module_dir=MODULE_DIR, run_key=":no_such_offer=1")


@needs_module
@pytest.mark.parametrize("mode", ["bubble", "oscilloscope", "extruded_bubble"])
@pytest.mark.parametrize("kind,level", [("setting", "settings"), ("block", "block")])
def test_a_perturbed_setting_and_a_perturbed_block_member_are_caught_at_their_input(qt_app, mode, kind, level):
    # Audit 9 L4: the settings and block levels are standing controls, as the record level's are.
    report = _run(mode, controls=[(kind, AT)])
    applied = report["controls_applied"][kind]
    assert applied >= AT and not report["identical"]
    assert [entry["input"] for entry in report["mismatches"]] == [applied]
    assert report["mismatches"][0]["first"]["level"] == level
    assert report["mismatches"][0]["first"]["native"] != report["mismatches"][0]["first"]["python"]


@needs_module
@pytest.mark.parametrize("kind", ["ulp", "drop"])
def test_a_one_ulp_record_change_and_a_dropped_frame_are_caught_at_their_input(qt_app, kind):
    report = _run("bubble", controls=[(kind, AT)])
    applied = report["controls_applied"][kind]
    assert applied >= AT
    assert not report["identical"]
    assert [entry["input"] for entry in report["mismatches"]] == [applied]
    first = report["mismatches"][0]["first"]
    assert first["level"] == "record" and first["field"] == "u_bubbles_pos" and first["element"] == 0
    assert first["native"] != first["python"]


@needs_module
@pytest.mark.parametrize("kind", ["ulp", "drop"])
def test_the_oscilloscope_catches_a_one_ulp_record_change_and_a_dropped_frame_at_their_input(qt_app, kind):
    # The Oscilloscope's ulp field is a scalar (no element); a dropped frame leaves the core the previous record, whose
    # first differing field is the record's own business, so only its level is pinned.
    from tools.visualizer_replay.native_record_identity import MODES

    report = _run("oscilloscope", controls=[(kind, AT)])
    applied = report["controls_applied"][kind]
    assert applied >= AT
    assert not report["identical"]
    assert [entry["input"] for entry in report["mismatches"]] == [applied]
    first = report["mismatches"][0]["first"]
    assert first["level"] == "record" and first["native"] != first["python"]
    if kind == "ulp":
        assert first["field"] == MODES["oscilloscope"].ulp_field and first["element"] is None


@needs_module
@pytest.mark.parametrize("kind", ["ulp", "drop"])
def test_extruded_bubble_catches_a_one_ulp_record_change_and_a_dropped_frame_at_their_input(qt_app, kind):
    # Extruded Bubble's record changes every frame (its clock), so a dropped frame shows at the record level too.
    from tools.visualizer_replay.native_record_identity import MODES

    report = _run("extruded_bubble", controls=[(kind, AT)])
    applied = report["controls_applied"][kind]
    assert applied >= AT
    assert not report["identical"]
    assert [entry["input"] for entry in report["mismatches"]] == [applied]
    first = report["mismatches"][0]["first"]
    assert first["level"] == "record" and first["native"] != first["python"]
    if kind == "ulp":
        assert first["field"] == MODES["extruded_bubble"].ulp_field

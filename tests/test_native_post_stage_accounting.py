"""Post-stage allocation proof: reject missing/negative/partial ownership and preserve native control semantics."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native" / "core" / "python"))
import post_stage_check as check
from rendering.native import loader


def test_exact_stage_accounting_includes_every_sampler_binding_and_pipeline():
    baseline = dict.fromkeys(check.ACCOUNTING_KEYS, 0)
    expected = {**baseline, "stage_bloom_chains": 1, "stage_textures": 4,
                "stage_bytes": 4096, "stage_pipelines": 11}
    assert check.stage_accounting_verdict(expected, baseline, expected)["pass"]
    # The old successful path counted one sampler and three pipelines, omitting seven actual bindings.
    assert not check.stage_accounting_verdict({**expected, "stage_pipelines": 4}, baseline, expected)["pass"]


@pytest.mark.parametrize("key", check.ACCOUNTING_KEYS)
@pytest.mark.parametrize("broken", [-1, 1, None, float("nan"), float("inf")])
def test_release_baseline_rejects_every_wrong_or_missing_count(key, broken):
    zero = dict.fromkeys(check.ACCOUNTING_KEYS, 0)
    actual = {**zero, key: broken}
    assert not check.stage_accounting_verdict(actual, zero, zero)["pass"]
    if broken is None:
        actual.pop(key)
        assert not check.stage_accounting_verdict(actual, zero, zero)["pass"]


def test_a_negative_baseline_cannot_hide_another_negative_release():
    zero = dict.fromkeys(check.ACCOUNTING_KEYS, 0)
    broken = {**zero, "stage_textures": -1}
    assert not check.stage_accounting_verdict(broken, broken, zero)["pass"]


def test_partial_skipped_release_must_report_actual_held_objects():
    zero = dict.fromkeys(check.ACCOUNTING_KEYS, 0)
    partial = {**zero, "stage_left_behind": 1}
    assert not check.stage_accounting_verdict(partial, zero, zero)["pass"]
    assert check.stage_accounting_verdict(partial, zero, partial)["pass"]
    assert not check.stage_accounting_verdict({**partial, "stage_left_behind": 12}, zero, partial)["pass"]


def test_fault_controls_reset_when_scene_creation_raises(monkeypatch):
    state = {"fail_allocation": 0, "fail_build": 0, "skip_stage_release": False}
    def control(name, value):
        state[name] = value
        return True
    core = SimpleNamespace(module=SimpleNamespace(stage_control=control),
                           composite_live=lambda: dict.fromkeys(check.ACCOUNTING_KEYS, 0))
    monkeypatch.setattr(check, "build", lambda *_: ((), (), {}))
    def fail(*_args, **_kwargs):
        raise RuntimeError("scene failed")
    monkeypatch.setattr(check.stc, "Scene", fail)
    with pytest.raises(RuntimeError, match="scene failed"):
        check._allocation_fault_case(core, None, None, None, {}, "bloom", "fail_allocation", 5)
    assert state == {"fail_allocation": 0, "fail_build": 0, "skip_stage_release": False}


MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()


@pytest.mark.skipif(not BUILT, reason="the GitHub-built native module is not installed")
def test_native_stage_fault_controls_are_bounded_integers_and_boolean_controls_keep_truth_errors():
    core = loader.load(MODULE_DIR)
    class BadTruth:
        def __bool__(self):
            raise LookupError("truth failed")
    try:
        for name in ("fail_allocation", "fail_build"):
            assert core.module.stage_control(name, 1)
            assert core.module.stage_control(name, 0)
            for invalid in (-1, 1000000):
                with pytest.raises(ValueError):
                    core.module.stage_control(name, invalid)
            for invalid in (True, 1.5, "1", None):
                with pytest.raises(TypeError):
                    core.module.stage_control(name, invalid)
        with pytest.raises(LookupError, match="truth failed"):
            core.module.stage_control("skip_stage_release", BadTruth())
        assert core.module.stage_control("skip_stage_release", [])
        assert not core.module.stage_control("unknown_control", False)
    finally:
        core.module.stage_control("fail_allocation", 0)
        core.module.stage_control("fail_build", 0)
        core.module.stage_control("skip_stage_release", False)


def test_an_environment_holds_its_mipped_texture_and_four_build_objects():
    expected = check._environment_expected((512, 288))
    levels = [(512, 288), (256, 144), (128, 72), (64, 36), (32, 18), (16, 9), (8, 4), (4, 2), (2, 1), (1, 1)]
    assert expected["stage_bytes"] == sum(w * h * 4 for w, h in levels) and expected["stage_textures"] == 1
    assert expected["stage_environments"] == 1 and expected["stage_pipelines"] == check.ENVIRONMENT_PIPELINES
    zero = dict.fromkeys(check.ACCOUNTING_KEYS, 0)
    assert check.stage_accounting_verdict(expected, zero, expected)["pass"]
    # Control: an environment left behind after its release is caught (its count is an accounting key).
    assert not check.stage_accounting_verdict({**zero, "stage_environments": 1}, zero, zero)["pass"]


def test_the_environments_creates_and_bind_take_the_stages_fault_count():
    """N5.2c audit: the environment's texture, chain bindings and target go through the sync's counted create (one count
    continued from the record's sync), and a held texture is never resized in place (a size is part of its spec)."""
    source = (ROOT / "native" / "core" / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    environments = source[source.index("bool PostStages::syncEnvironments("):
                          source.index("bool PostStages::environmentBindings(")]
    assert environments.count("createAllocation(e.texture.get())") == 1
    assert environments.count("createAllocation(e.target.get())") == 1
    assert "!allocationAllowed() || !m_environmentChains.bind(" in environments
    assert "->create()" not in environments and "setPixelSize" not in environments
    sync = source[source.index("bool PostStages::sync("):]
    assert "m_allocationAttempt = 0;" in sync[:sync.index("\n}\n")]
    assert len(check.ENVIRONMENT_ATTEMPTS) == 3

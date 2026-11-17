"""CPU guards for evidence refusal, receipt identity and temporary diagnostic ownership."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import artifact_paths
from tools.visualizer_replay import _bubble_native_common as common
from tools.visualizer_replay import bubble_native_diagnostics as cli


def test_existing_output_is_refused_before_recipe_import(tmp_path, monkeypatch):
    with artifact_paths.use_root(tmp_path):
        common.fresh_output("occupied").mkdir(parents=True)

        def forbidden_import(_name):
            pytest.fail("renderer recipe imported before fresh-output refusal")

        monkeypatch.setattr(cli.importlib, "import_module", forbidden_import)
        with pytest.raises(FileExistsError):
            cli.main(["replay", "--repo", str(artifact_paths.REPO_ROOT),
                      "--module-dir", "unused", "--label", "occupied"])


def test_promoted_passive_receipt_requires_exact_bundle_and_no_control():
    tool = common.provenance("fade")
    receipt = {"helper_sha256": tool["source_sha256"]["_bubble_native_fade.py"],
               "diagnostic_tool": tool, "quad_control_requested": False}
    assert common.passive_helper_matches(receipt)
    assert not common.passive_helper_matches({**receipt, "quad_control_requested": True})
    assert not common.passive_helper_matches({**receipt, "helper_sha256": "stale-helper"})
    assert not common.passive_helper_matches({**receipt, "diagnostic_tool": {**tool, "source_sha256": {}}})
    frozen = {"helper_sha256": common.FROZEN_FADE_SHA256, "quad_control_requested": False}
    assert common.passive_helper_matches(frozen)
    assert not common.passive_helper_matches({**frozen, "quad_control_requested": True})
    assert not common.passive_helper_matches({"helper_sha256": common.FROZEN_FADE_SHA256})


def test_canonical_wire_bytes_are_stable_and_reject_nonfinite():
    assert common.json_bytes({"b": (b"\x01",), "a": 1}) == common.json_bytes({"a": 1, "b": ["01"]})
    with pytest.raises(ValueError):
        common.json_bytes({"unsafe": float("nan")})


def test_baseline_replay_identity_requires_integrity_but_preserves_pixel_failure():
    assert common.replay_helper_matches({"helper_sha256": common.ORIGIN_SHA256["replay"]})
    tool = common.provenance("replay")
    receipt = {"helper_sha256": tool["source_sha256"]["_bubble_native_replay.py"],
               "diagnostic_tool": tool, "owner_exit_code": 1,
               "passive_guards_pass": True, "checks": {"retired": True}}
    assert common.replay_helper_matches(receipt)
    assert not common.replay_helper_matches({**receipt, "helper_sha256": "untrusted"})
    assert not common.replay_helper_matches({**receipt, "checks": {"retired": False}})
    assert not common.replay_helper_matches({**receipt, "checks": {}})
    assert not common.replay_helper_matches({**receipt, "passive_guards_pass": False})
    assert not common.replay_helper_matches({**receipt, "diagnostic_tool": {}})


def _fake_owner(*_args, **_kwargs):
    return 1  # The diagnostic must preserve an independently failing owner pixel verdict.


@pytest.mark.parametrize("failure", [None, "exception", "retirement", "module"])
def test_replay_restores_owners_and_keeps_independent_verdict(tmp_path, monkeypatch, failure):
    from rendering.quick.visualizer import native_route as route
    from tools.visualizer_replay import owner_render_parity as parity
    from tools.visualizer_replay import _bubble_native_replay as recipe

    module_dir = tmp_path / "module"
    module_dir.mkdir()
    module = module_dir / "fake_native.pyd"
    module.write_bytes(b"CPU-only module identity")
    manifest = {"files": {module.name: {"sha256": common.sha(module.read_bytes()), "bytes": module.stat().st_size}}}
    if failure == "module":
        manifest["files"][module.name]["sha256"] = "different"
    (module_dir / "remote_build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(parity, "native_parity", _fake_owner)
    saved = route.GENERIC_MODE_SETTINGS, route.NATIVE_MODE_IDS, parity.NativeSceneMirror.frame, parity.native_parity
    live = {key: 0 for key in common.LIVE_KEYS}
    core = SimpleNamespace(info={"module_path": str(module)},
                           composite_live=lambda: dict(live), live_hosts=lambda: int(failure == "retirement"))

    def fake_main(argv):
        assert route.GENERIC_MODE_SETTINGS is not saved[0]
        assert "bubble" in route.NATIVE_MODE_IDS
        if failure == "exception":
            raise RuntimeError("injected owner failure")
        assert parity.native_parity(core) == 1
        out = Path(argv[argv.index("--out") + 1])
        out.mkdir(parents=True)
        case = {"frames_drawn": [549, 549], "python_hashes": ["reference"] * 549,
                "native_hashes": ["native"] * 549, "digests_identical": True}
        (out / "native_render_parity.json").write_text(json.dumps({"results": {"bubble": case}}), encoding="utf-8")
        return 1

    monkeypatch.setattr(parity, "main", fake_main)
    with artifact_paths.use_root(tmp_path / "artifacts"):
        args = SimpleNamespace(repo=artifact_paths.REPO_ROOT, module_dir=module_dir, label="cpu_replay")
        if failure in ("exception", "module"):
            with pytest.raises(RuntimeError):
                recipe.run(args)
        else:
            assert recipe.run(args) == (2 if failure == "retirement" else 1)
        out = artifact_paths.evidence_dir("native_core", "n5_1_bubble", args.label)
        receipt = json.loads((out / "reproduction_metadata.json").read_text(encoding="utf-8"))
    assert route.GENERIC_MODE_SETTINGS is saved[0]
    assert route.NATIVE_MODE_IDS is saved[1]
    assert parity.NativeSceneMirror.frame is saved[2]
    assert parity.native_parity is saved[3]
    assert receipt["wrappers_restored"] is True
    assert receipt["passive_guards_pass"] is (failure is None)
    if failure is None:
        assert receipt["owner_exit_code"] == 1


@pytest.mark.parametrize("recipe_name", ["fade", "components"])
def test_capture_exception_restores_exact_hooks(tmp_path, monkeypatch, recipe_name):
    from tools import conventions_identity
    from rendering.quick.visualizer import native_route as route
    from rendering.quick.visualizer.node import VisualizerRenderNode
    from rendering.quick.visualizer.implementations import bubble
    from rendering.quick.visualizer.implementations.bubble_ambient_gl import QuickBubbleAmbientPoints
    from tools.visualizer_replay import owner_render_parity as parity

    recipe = __import__(f"tools.visualizer_replay._bubble_native_{recipe_name}", fromlist=["run"])
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    manifest_bytes = b'{"files": {}}'
    (module_dir / "remote_build_manifest.json").write_bytes(manifest_bytes)
    sources = {"native_parity": common.sha(inspect.getsource(parity.native_parity).encode()),
               "bubble_program": common.sha(inspect.getsource(route.bubble_program).encode())}
    for name in ("bubble.frag", "bubble_ambient_points.vert", "bubble_ambient_points.frag",
                 "bubble_ambient_mask.vert", "bubble_ambient_mask.frag"):
        sources[name] = common.sha((artifact_paths.REPO_ROOT / "widgets/spotify_visualizer/shaders" / name).read_bytes())
    settings = dict(conventions_identity.mode_runs("bubble", False))[""]
    baseline = {"settings": settings, "manifest_sha256": common.sha(manifest_bytes),
                "source_sha256": sources, "helper_sha256": common.ORIGIN_SHA256["replay"],
                "module_sha256": "baseline-module"}
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    metadata_bytes = json.dumps(baseline).encode()
    report_bytes = json.dumps({"results": {"bubble": {"frames_drawn": [549, 549],
        "python_hashes": ["reference"] * 549, "native_hashes": ["native"] * 549}}}).encode()
    (baseline_dir / "reproduction_metadata.json").write_bytes(metadata_bytes)
    (baseline_dir / "native_render_parity.json").write_bytes(report_bytes)
    passive = {**baseline, "helper_sha256": common.FROZEN_FADE_SHA256, "passive_guards_pass": True,
               "quad_control_requested": False,
               "checks": {"cpu_fake_receipt": True}, "baseline_helper_sha256": baseline["helper_sha256"],
               "baseline_metadata_sha256": common.sha(metadata_bytes), "baseline_report_sha256": common.sha(report_bytes)}
    (baseline_dir / "fade_capture_metadata.json").write_text(json.dumps(passive), encoding="utf-8")
    owners = ((route, "GENERIC_MODE_SETTINGS"), (route, "NATIVE_MODE_IDS"), (parity.SceneMirror, "frame"),
              (parity, "native_parity"), (VisualizerRenderNode, "_inherited_scene_opacity"),
              (bubble.QuickBubbleRenderer, "render"), (route.NativeVisualizerRoute, "card"),
              (QuickBubbleAmbientPoints, "_draw_occluders"), (QuickBubbleAmbientPoints, "render_texture"))
    saved = [getattr(owner, name) for owner, name in owners]

    def interrupted(_argv):
        assert parity.SceneMirror.frame is not saved[2]
        raise RuntimeError("injected replay interruption")

    monkeypatch.setattr(parity, "main", interrupted)
    with artifact_paths.use_root(tmp_path / "artifacts"):
        args = SimpleNamespace(repo=artifact_paths.REPO_ROOT, module_dir=module_dir, label="capture_interrupted",
                               baseline_dir=baseline_dir, passive_dir=baseline_dir, quad_adapter=None)
        with pytest.raises(RuntimeError, match="injected replay interruption"):
            recipe.run(args)
        out = artifact_paths.evidence_dir("native_core", "n5_1_bubble", args.label)
        filename = "fade_capture_metadata.json" if recipe_name == "fade" else "component_capture_metadata.json"
        receipt = json.loads((out / filename).read_text(encoding="utf-8"))
    assert all(getattr(owner, name) is original for (owner, name), original in zip(owners, saved))
    assert receipt["wrappers_restored"] is True
    assert receipt["capture_failed"] is True
    assert receipt["passive_guards_pass"] is False

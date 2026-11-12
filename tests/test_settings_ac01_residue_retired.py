"""AC-23: the AC-01 residue is gone and the three disclosure schemas no live builder constructs are retired.

* Reachability at symbol level: every function, method and module constant of the Visualizer Settings mixin is
  referenced by production code (the dead Technical widget machinery went with its module in AC-18).
* The mixin keeps no copy of the live preset key rules (``core.settings.visualizer_presets``).
* Canonical ``ui`` defaults declare no Visualizer disclosure schema whose members are not buckets a mode's spec
  builds (derived from the spec, never a pinned list).
* Retiring a schema follows ``Persisted_Input_Compatibility.md``: an old profile's members are accepted at input and
  dropped by the projection, and a second projection is a no-op.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "settings_bucket_state_full_map_profile.json"
_PRODUCTION = ("core", "ui", "rendering", "widgets", "engine", "sources", "utils", "tools")


def _production_sources() -> list[str]:
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in ROOT.glob("*.py")]
    for folder in _PRODUCTION:
        texts += [p.read_text(encoding="utf-8", errors="replace") for p in (ROOT / folder).rglob("*.py")]
    return texts


def test_every_symbol_of_the_visualizer_settings_mixin_module_is_reachable():
    module = ROOT / "ui" / "tabs" / "visualizer_settings_context.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    names |= {target.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
              for target in node.targets if isinstance(target, ast.Name)}
    sources = _production_sources()
    unreachable = sorted(name for name in names if not name.startswith("__")
                         and sum(len(re.findall(rf"\b{re.escape(name)}\b", text)) for text in sources) <= 1)
    assert not unreachable, f"defined but never referenced by production code: {unreachable}"


def test_the_dead_technical_widget_module_is_gone():
    assert importlib.util.find_spec("ui.tabs.media.technical_controls") is None


def test_the_tab_keeps_no_copy_of_the_live_preset_key_rules():
    from core.settings import visualizer_presets
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin
    live_rules = {name for name, value in vars(visualizer_presets).items()
                  if inspect.isfunction(value) and value.__module__ == visualizer_presets.__name__}
    copies = sorted(name for name in vars(VisualizerSettingsContextMixin) if name in live_rules)
    assert not copies, f"the Settings tab restates visualizer_presets rules: {copies}"


def test_canonical_visualizer_disclosure_schemas_name_only_buckets_a_mode_builds():
    from core.settings.default_settings import DEFAULT_SETTINGS
    from core.settings.visualizer_mode_settings import mode_settings
    from ui.tabs.visualizers_fullscreen_page import FULLSCREEN_BUCKET_SCOPE, FULLSCREEN_BUCKETS
    schemas = {key: value for key, value in DEFAULT_SETTINGS["ui"].items()
               if key.startswith("visualizer_") and key.endswith("_states")}
    assert schemas, "the Custom leaf schema must remain"
    for name, members in schemas.items():
        for member in members:
            mode, _, bucket = str(member).partition(":")
            if mode == FULLSCREEN_BUCKET_SCOPE:
                # The Fullscreen Mode page's buckets (not a mode's spec): only the ones that page builds.
                assert bucket in FULLSCREEN_BUCKETS, f"ui.{name} declares {member!r}, which the page never builds"
                continue
            spec = mode_settings(mode)
            assert spec is not None and bucket in {b.key for b in spec.buckets}, \
                f"ui.{name} declares {member!r}, which no mode's spec builds"


class _Recorder:
    """Counts the projection's store writes on a real SettingsManager."""

    def __init__(self, manager):
        self.manager, self.writes = manager, []

    def __getattr__(self, name):
        return getattr(self.manager, name)

    def set(self, key, value, **kwargs):
        self.writes.append(("set", key))
        return self.manager.set(key, value, **kwargs)

    def remove(self, key):
        self.writes.append(("remove", key))
        return self.manager.remove(key)


def test_an_old_profiles_retired_disclosure_members_are_accepted_dropped_once_and_idempotent(tmp_path):
    from core.settings.settings_manager import SettingsManager
    from core.settings.ui_bucket_state import project_settings_bucket_context
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
    old = dict(json.loads(FIXTURE.read_text(encoding="utf-8"))["ui"])   # holds the old Technical leaf map
    assert "visualizer_tech_bucket_states" in old, "the old-input fixture must hold a retired schema"
    # The two outer disclosure maps had one member per mode (an open Advanced and Technical for each).
    old["visualizer_adv_states"] = {mode: True for mode in VISUALIZER_MODE_IDS}
    old["visualizer_tech_states"] = {mode: True for mode in VISUALIZER_MODE_IDS}
    retired = ("visualizer_adv_states", "visualizer_tech_states", "visualizer_tech_bucket_states")
    manager = SettingsManager(application="ac01_residue", storage_base_dir=tmp_path)
    for name in retired:
        manager.set(f"ui.{name}", dict(old[name]))
    custom_before = manager.get("ui.visualizer_bucket_states")
    recorder = _Recorder(manager)
    project_settings_bucket_context(recorder, "visualizers", "spectrum")
    for name in retired:
        assert manager.get(f"ui.{name}") is None, f"ui.{name} survived the projection"
    assert manager.get("ui.visualizer_bucket_states") == custom_before
    recorder.writes.clear()
    project_settings_bucket_context(recorder, "visualizers", "spectrum")
    assert recorder.writes == [], "a second projection must be a no-op"
    assert manager.flush(timeout=5.0)

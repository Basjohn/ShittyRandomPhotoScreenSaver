"""Expanded Visualizer M1: the mode capability and import dormancy (plan 01 §0.3, §0.4, §B2, Gate 1).

The capability is descriptor metadata in ``core/settings/visualizer_mode_registry.py`` (default False). The
operator's set (7 Nov): every mode except Voxel Sphere and Extruded Spectrum opts in (one flag each). Every predicate resolves through ``resolve_expanded_display_capable``, which a disabled, gated,
unknown or retired mode can never pass. The takeover reducer is a pure standard-library module that nothing on the
common Quick path or any mode's runtime/renderer/Settings wiring imports (an AST scan over the project's import
graph, plus a fresh-interpreter check).
"""
from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from dataclasses import fields
from pathlib import Path

import pytest

from core.settings import visualizer_mode_registry as registry
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    VisualizerModeDescriptor,
    build_visualizer_mode_activation,
    get_visualizer_mode_descriptor,
    iter_all_visualizer_mode_descriptors,
)

REPO = Path(__file__).resolve().parents[1]
REDUCER = "core.expanded_visualizer_takeover"
COORDINATOR = "widgets.spotify_visualizer.expanded_display_coordinator"
FIRST_CAPABLE_MODE = "extruded_bubble"   # plan 01: the initial supported Visualizer
#: The operator's decision (7 Nov). Product capability, not authored content.
CAPABLE_MODES = {"extruded_bubble", "spectrum", "oscilloscope", "devcurve", "bubble", "shockwave_grid",
                 "waveform_ribbon"}
NEVER_CAPABLE = {"sphere", "extruded_spectrum"}


def test_capability_defaults_off_and_only_the_operators_modes_opt_in():
    field = next(f for f in fields(VisualizerModeDescriptor) if f.name == "supports_expanded_display")
    assert field.default is False
    capable = {d.mode_id for d in iter_all_visualizer_mode_descriptors() if d.supports_expanded_display}
    assert capable == CAPABLE_MODES
    assert not capable & NEVER_CAPABLE


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_capable_requires_registered_active_enabled_and_opted_in(mode):
    descriptor = get_visualizer_mode_descriptor(mode)
    enabled = build_visualizer_mode_activation(VISUALIZER_MODE_IDS)
    assert registry.resolve_expanded_display_capable(mode, enabled) is (
        descriptor.supports_expanded_display and registry.is_mode_active(mode)
    )


def test_a_disabled_capable_mode_cannot_force_expansion():
    others = tuple(m for m in VISUALIZER_MODE_IDS if m != FIRST_CAPABLE_MODE)
    activation = build_visualizer_mode_activation(others)
    assert activation[FIRST_CAPABLE_MODE] is False
    assert registry.resolve_expanded_display_capable(FIRST_CAPABLE_MODE, activation) is False


def test_a_gated_capable_mode_cannot_force_expansion(monkeypatch):
    monkeypatch.setitem(registry._GATED_MODES, FIRST_CAPABLE_MODE, lambda: False)
    activation = build_visualizer_mode_activation(VISUALIZER_MODE_IDS)
    assert registry.resolve_expanded_display_capable(FIRST_CAPABLE_MODE, activation) is False


@pytest.mark.parametrize("mode_id", ["", None, "nope", "EXTRUDED_BUBBLE_", "extruded bubble", 3, ["extruded_bubble"]])
def test_unregistered_or_malformed_mode_ids_are_inert(mode_id):
    activation = build_visualizer_mode_activation(VISUALIZER_MODE_IDS)
    assert registry.resolve_expanded_display_capable(mode_id, activation) is False


def test_mode_id_spelling_is_canonicalised_like_the_registry():
    activation = build_visualizer_mode_activation(VISUALIZER_MODE_IDS)
    assert registry.resolve_expanded_display_capable(" Extruded_Bubble ", activation) is True


def test_capability_is_descriptor_metadata_not_a_settings_flag_or_preset_field():
    from core.settings.defaults import get_default_settings
    from core.settings.visualizer_presets import MODE_KEY_PREFIXES

    # The one owner is the descriptor (plan 01 §0.3) ...
    assert "supports_expanded_display" in {f.name for f in fields(VisualizerModeDescriptor)}
    # ... and no persisted key or preset prefix shadows it.
    section = get_default_settings("Screensaver")["widgets"]["spotify_visualizer"]
    assert not [key for key in section if "supports_expanded" in key]
    assert not [p for prefixes in MODE_KEY_PREFIXES.values() for p in prefixes if "expanded_display".startswith(p)]


# ---------------------------------------------------------------------------------------------- import dormancy


def _reducer_path() -> Path:
    return REPO / (REDUCER.replace(".", "/") + ".py")


def test_reducer_imports_only_the_standard_library():
    tree = ast.parse(_reducer_path().read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "enum"}, imported
    # No clock, timer, thread, Qt object, settings access or dynamic import hides behind a builtin either.
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"QTimer", "QObject", "singleShot", "threading", "time", "monotonic", "perf_counter", "sleep",
                 "import_module", "__import__", "SettingsManager", "OpenGL", "open", "eval", "exec", "globals"}
    assert not names & forbidden, sorted(names & forbidden)


def _common_and_mode_roots() -> set[str]:
    roots = {
        "main", "engine.display_manager", "engine.screensaver_engine", "engine.engine_handlers",
        "rendering.quick.scene_controller", "rendering.quick.runtime", "rendering.quick.display_presenter",
        "rendering.quick.visualizer.implementation_registry",
        "widgets.spotify_visualizer.quick_display_visualizer_owner",
        "widgets.spotify_visualizer.visualizer_host_binding",
        "core.settings.visualizer_mode_registry", "core.settings.settings_manager",
    }
    for descriptor in iter_all_visualizer_mode_descriptors():
        roots.update(m for m in (descriptor.frame_runtime_module, descriptor.renderer_module,
                                 descriptor.settings_builder_module, descriptor.capture_module,
                                 descriptor.logical_tick_hook_module) if m)
    return roots


def test_import_scan_no_common_quick_or_mode_path_reaches_the_reducer():
    """AST import graph (``tools/impacted_tests.ImportGraph``): which project modules import the reducer through any
    chain of module-level (eager) imports, and through one lazy hop. No eager chain may include the common Quick path
    or any mode's (capable or not) runtime, renderer, capture, logical hook or Settings builder. Since M2 the one
    production entry is the display manager's lazy construction of the takeover coordinator (beside the host
    binding), so the lazy hop reaches only that manager and the modules that import it; never a scene, owner,
    binding or mode module."""
    sys.path.insert(0, str(REPO))
    from tools.impacted_tests import ImportGraph

    graph = ImportGraph()
    assert REDUCER in graph.files
    eager = set(graph.affected({REDUCER}, lazy_hops=0))
    one_lazy = set(graph.affected({REDUCER}, lazy_hops=1))
    roots = {root for root in _common_and_mode_roots() if root in graph.files}
    assert len(roots) >= 12
    assert not eager & roots, sorted(eager & roots)
    manager_chain = {"engine.display_manager", "engine.engine_handlers", "engine.screensaver_engine", "main"}
    assert one_lazy & roots <= manager_chain, sorted(one_lazy & roots)
    # Eagerly, only the coordinator (and tests) import the reducer; nothing in production imports the coordinator
    # at module level.
    assert {m for m in eager if not m.startswith("tests")} == {REDUCER, COORDINATOR}, sorted(eager)
    coordinator_eager = set(graph.affected({COORDINATOR}, lazy_hops=0))
    assert {m for m in coordinator_eager if not m.startswith("tests")} == {COORDINATOR}, sorted(coordinator_eager)


def test_fresh_interpreter_common_quick_and_every_mode_leave_the_reducer_unloaded():
    modules = sorted(m for m in _common_and_mode_roots() if m != "main")
    script = textwrap.dedent(
        f"""
        import importlib, sys
        sys.path.insert(0, {str(REPO)!r})
        from rendering.gl_error_policy import disable_per_call_gl_error_checking
        disable_per_call_gl_error_checking()  # the production order, before OpenGL.GL is first imported
        for name in {modules!r}:
            importlib.import_module(name)
        print({REDUCER!r} in sys.modules or {COORDINATOR!r} in sys.modules)
        # The check is meaningful only for a module that exists and loads on demand without Qt or GL.
        before = {{m for m in sys.modules if m.startswith(("PySide6", "OpenGL"))}}
        importlib.import_module({REDUCER!r})
        print(sorted({{m for m in sys.modules if m.startswith(("PySide6", "OpenGL"))}} - before))
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=240,
                            cwd=str(REPO))
    assert result.returncode == 0, result.stderr[-4000:]
    loaded_by_roots, added_by_reducer = result.stdout.strip().splitlines()[-2:]
    assert loaded_by_roots == "False"
    assert added_by_reducer == "[]"

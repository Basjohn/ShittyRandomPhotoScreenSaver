"""The "available on this backend" answer of the capability registries (D10 point 2, Current_Plan.md item 8b N2.7).

A mode without a renderer on the process's backend is not offered there (never started, activated or cycled to);
a transition without one runs as Crossfade; the background family (presenter, backdrop, transitions) creates no
surface on a backend without its renderers. The process's backend is the one owner's (``rendering.quick.bootstrap``);
these tests answer "vulkan" from it without changing Qt. Which modes and transitions are ported is read from each
descriptor, never listed here: a port is simulated by giving one descriptor the backend.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from core.settings import visualizer_mode_registry as modes
from rendering import transition_registry as transitions


@pytest.fixture
def on_vulkan(monkeypatch):
    from rendering.quick import bootstrap

    monkeypatch.setattr(bootstrap, "quick_backend_api", lambda: "vulkan")


def _ported_modes(monkeypatch, ported: set[str]) -> None:
    """Exactly ``ported`` have a Vulkan renderer (whatever the registry says today)."""
    patched = tuple(dataclasses.replace(d, renderer_backends=("opengl", "vulkan") if d.mode_id in ported
                                        else ("opengl",)) for d in modes._ALL_DESCRIPTORS)
    monkeypatch.setattr(modes, "_ALL_DESCRIPTORS", patched)


def _ported_transitions(monkeypatch, ported: set[str]) -> None:
    patched = {d.setting_name: dataclasses.replace(d, renderer_backends=("opengl", "vulkan")
                                                   if d.setting_name in ported else ("opengl",))
               for d in transitions.iter_transition_descriptors()}
    monkeypatch.setattr(transitions, "_BY_SETTING_NAME", patched)
    monkeypatch.setattr(transitions, "_BY_STABLE_ID", {d.stable_id: d for d in patched.values()})


def _enabled() -> tuple[str, ...]:
    enabled = modes.resolve_admissible_enabled_modes(None)
    assert len(enabled) >= 2, "the canonical activation enables at least two modes"
    return enabled


# ---------------------------------------------------------------------------------------------------------- OpenGL


def test_on_opengl_every_mode_and_transition_has_its_renderer_and_nothing_changes():
    # The pytest process runs the product path: the owner chose OpenGL.
    for descriptor in modes.iter_all_visualizer_mode_descriptors():
        assert "opengl" in descriptor.renderer_backends
        assert modes.is_mode_available_on_backend(descriptor.mode_id)
        assert modes.resolve_backend_mode(descriptor.mode_id, None) == modes.resolve_effective_mode(
            descriptor.mode_id, None)[0]
    for descriptor in transitions.iter_transition_descriptors():
        assert transitions.resolve_backend_transition_name(descriptor.setting_name) == descriptor.setting_name
    assert transitions.background_family_available_on_backend()
    assert not modes.is_mode_available_on_backend("no_such_mode", "opengl")


def test_each_descriptor_answers_for_itself_on_vulkan(on_vulkan):
    for descriptor in modes.iter_all_visualizer_mode_descriptors():
        assert modes.is_mode_available_on_backend(descriptor.mode_id) == ("vulkan" in descriptor.renderer_backends)
    for descriptor in transitions.iter_transition_descriptors():
        assert transitions.is_transition_available_on_backend(descriptor.setting_name) == (
            "vulkan" in descriptor.renderer_backends)
    assert transitions.background_family_available_on_backend() == (
        "vulkan" in transitions.BACKGROUND_FAMILY_BACKENDS)


# ----------------------------------------------------------------------------------------------------------- modes


def test_without_a_ported_mode_no_visualizer_starts_on_vulkan(on_vulkan, monkeypatch):
    _ported_modes(monkeypatch, set())
    for mode_id in modes.VISUALIZER_MODE_IDS:
        assert modes.resolve_backend_mode(mode_id, None) is None
    assert modes.resolve_backend_mode(modes.VISUALIZER_MODE_IDS[0], None, "opengl") is not None   # control


def test_an_unported_mode_starts_the_next_enabled_ported_one_and_never_a_disabled_one(on_vulkan, monkeypatch):
    enabled = _enabled()
    requested, ported = enabled[0], enabled[-1]
    _ported_modes(monkeypatch, {ported})
    assert modes.resolve_backend_mode(requested, None) == ported
    assert modes.resolve_backend_mode(ported, None) == ported
    disabled = {mode_id: mode_id != ported for mode_id in modes.VISUALIZER_MODE_IDS}
    assert modes.resolve_backend_mode(requested, disabled) is None


def test_the_cycle_never_reaches_a_mode_without_a_renderer(monkeypatch):
    from rendering.quick import bootstrap
    from rendering.quick.visualizer.double_click_admission import (
        next_visualizer_mode_id,
        visualizer_mode_cycle_order,
    )

    enabled = _enabled()
    first, last = enabled[0], enabled[-1]
    _ported_modes(monkeypatch, {first, last})
    on_opengl = visualizer_mode_cycle_order(first, None)
    assert len(on_opengl) == len(modes.iter_visualizer_mode_descriptors()) - 1               # control: every mode
    monkeypatch.setattr(bootstrap, "quick_backend_api", lambda: "vulkan")
    assert next_visualizer_mode_id(first, None) == last
    assert visualizer_mode_cycle_order(first, None) == (last,)


def test_an_activation_request_for_a_mode_without_a_renderer_is_refused(on_vulkan, monkeypatch):
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    current, target = _enabled()[0], _enabled()[-1]
    owner = SimpleNamespace(
        _retired=False, _started=True, _controller=SimpleNamespace(mode_id=current), _mode_transition_phase="idle",
        _pending_mode_activation=None, _mode_transition_fade=1.0, _transition_clock=lambda: 0.0,
        _transition_request_serial=0, _transition_recovery_issued=False, _arm_transition_deadline=lambda: None,
    )

    def request() -> bool:
        return QuickDisplayVisualizerOwner._request_visualizer_activation(
            owner, kind="mode", target_mode=target, settings_model=None, resolved_activation=None,
            technical_cache={}, logical_kwargs={}, presentation_kwargs={}, on_complete=None)

    _ported_modes(monkeypatch, {current})
    assert request() is False and owner._pending_mode_activation is None
    _ported_modes(monkeypatch, {current, target})                                            # control: once ported
    assert request() is True and owner._pending_mode_activation["mode"] == target


# ----------------------------------------------------------------------------------------------------- transitions


def test_on_vulkan_an_unported_transition_is_crossfade(on_vulkan, monkeypatch):
    names = [d.setting_name for d in transitions.iter_transition_descriptors()
             if d.setting_name != transitions.BACKEND_FALLBACK_TRANSITION]
    _ported_transitions(monkeypatch, set())
    for name in names:
        assert transitions.resolve_backend_transition_name(name) == transitions.BACKEND_FALLBACK_TRANSITION
    _ported_transitions(monkeypatch, {names[0]})
    assert transitions.resolve_backend_transition_name(names[0]) == names[0]
    assert transitions.resolve_backend_transition_name(names[1]) == transitions.BACKEND_FALLBACK_TRANSITION


def test_the_resolved_transition_on_vulkan_is_crossfade_with_its_own_duration(monkeypatch):
    from rendering.quick import bootstrap
    from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec
    from tests.test_qtquick_transition_request_resolution import _Settings

    settings = _Settings({"type": "Slide", "random_always": False, "durations": {"Slide": 321, "Crossfade": 654},
                          "slide": {"direction": "Right to Left"}})
    on_opengl = resolve_quick_transition_spec(settings)
    assert (on_opengl.transition_id, on_opengl.duration_ms) == ("slide", 321)                 # control
    monkeypatch.setattr(bootstrap, "quick_backend_api", lambda: "vulkan")
    _ported_transitions(monkeypatch, set())
    spec = resolve_quick_transition_spec(settings)
    assert (spec.transition_id, spec.duration_ms, spec.requested_name) == ("crossfade", 654, "Slide")


# ------------------------------------------------------------------------------------------ the background family


def test_on_vulkan_no_background_or_backdrop_node_is_created(on_vulkan, qt_app):
    from rendering.quick.render.background_item import BackgroundRenderItem
    from rendering.quick.render.surface_backdrop import SurfaceBackdropSource

    background = BackgroundRenderItem()
    background.setProofProgress(0.25)                 # a render that creates the node wherever the family runs
    assert background.updatePaintNode(None, None) is None
    assert background.schedule_warm_step("crossfade", {}, object(), 1) is False
    backdrop = SurfaceBackdropSource()
    backdrop.request_refresh()
    assert backdrop.armed and backdrop.updatePaintNode(None, None) is None


def test_on_opengl_the_background_family_keeps_its_renderers(qt_app):
    from rendering.quick.render.background_item import BackgroundRenderItem
    from rendering.quick.render.surface_backdrop import SurfaceBackdropSource

    assert BackgroundRenderItem()._renderers_on_backend is True
    assert SurfaceBackdropSource()._renderers_on_backend is True

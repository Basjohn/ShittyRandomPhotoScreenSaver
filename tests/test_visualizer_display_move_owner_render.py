"""A display move rendered end to end through the real owner (Current_Plan 1C.2): the target's first visible frame
draws with the renderer it prepared before the hop.

Until now this was proved in two halves: the owner's hop adopts the prepared item (``test_visualizer_display_move_
retarget``, unrendered scenes) and the renderer survives a scene's take-over (``test_visualizer_display_move_gpu``,
scene calls without the owner). Here the real ``QuickDisplayVisualizerOwner`` (Spectrum, the in-process replay
engine, a test clock) runs ``move_display`` itself, its warm, fade-out, hop and fade-in at its own publication edges,
between two hidden production hosts (``tools/expanded_visualizer_evidence.HiddenDisplayHost``: the production scene
through ``QQuickRenderControl`` into a hidden texture; no window is shown) whose GL contexts share, as every product
display window's do. Each runtime is the host's scene seen through the few runtime seams the owner calls.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from tests.test_qtquick_custom_layout_owner import _LiveCommitEngine, _configure_visualizer
from widgets.spotify_visualizer import tick_pipeline

MODE = "spectrum"
W, H = 1280, 720
SHADOW = {"background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255), "border_width": 4.,
          "corner_radius": 6., "content_inset": 14., "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
          "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0., "shadow_extensions": (0., 0., 0., 0.)}


class _HostRuntime:
    """A hidden host's scene behind the runtime seams the owner uses (``QuickDisplayRuntime``'s, delegated)."""

    def __init__(self, host, index: int) -> None:
        self.host = host
        self.scene_controller = host.scene
        self.window = host.window
        self.screen_index = index
        self.runtime_generation = host.window.runtime_generation
        self.display_identity = SimpleNamespace(screen_key=f"hidden-{index}", screen_index=index,
                                                runtime_generation=self.runtime_generation,
                                                geometry=(index * W, 0, W, H), device_pixel_ratio=1.0)

    def bind_visualizer_render_source(self, controller, *, engine_generation: int, activation_id: int):
        identity = controller.begin_render_activation(engine_generation=int(engine_generation),
                                                      activation_id=int(activation_id))
        self.scene_controller.set_visualizer_render_source(controller.render_bridge, identity)
        return identity

    def bind_visualizer_viewport_config(self, override_sink, *, framed_view_sink=None) -> None:
        self.scene_controller.set_visualizer_viewport_config_sink(override_sink, framed_view_sink=framed_view_sink)


def _renderer(scene):
    """The mode's renderer on ``scene``'s render host (None before one is built)."""
    item = scene._visualizer_item
    node = item._retirement._node if item is not None else None
    host = None if node is None else node.render_host
    return None if host is None else (host._implementations.get(MODE), host.prepared_activation)


@pytest.fixture
def hidden_pair(qt_app, monkeypatch):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production host needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    hosts = (HiddenDisplayHost(W, H, dpr=1.0, share=True), HiddenDisplayHost(W, H, dpr=1.0, share=True))
    try:
        yield hosts
    finally:
        for host in hosts:
            host.close()


def _move(hosts, *, prepare: bool) -> dict:
    """Run the owner on ``hosts[0]``, move it to ``hosts[1]`` and render both at every publication. Returns what
    the target had at the hop and at its first visible frame."""
    from tests._visualizer_presentation import make_visualizer_owner

    source, target = _HostRuntime(hosts[0], 0), _HostRuntime(hosts[1], 1)
    if not prepare:
        target.scene_controller.begin_visualizer_prewarm = lambda _identity, _record: False
    clock = [0.0]
    owner = make_visualizer_owner(source, initial_mode=MODE, bar_count=24,
                                  engine_factory=lambda _count: _LiveCommitEngine(),
                                  card_shadow_kwargs=SHADOW, transition_clock=lambda: clock[0])
    seen: dict = {"first_visible": None}
    try:
        _configure_visualizer(owner, playing=True)
        owner.set_authored_outer_origin(100., 100.)
        owner.bind(engine_generation=3, activation_id=5)
        owner._apply_resolved_presentation(owner._resolve_current_presentation())
        owner.start(interval_s=10.)
        state = owner.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 3
        state._display_bars_source_activation = 5

        def publish(seconds: float) -> None:
            clock[0] += seconds
            assert tick_pipeline.logical_tick(owner.controller.logical_tick_state) is not None
            owner.sync_present()
            hosts[0].render()
            hosts[1].render()

        publish(2.0)                                  # past the first-appearance fade: the card is fully shown
        for _ in range(200):                          # the source draws with its own renderer before the move
            if (_renderer(source.scene_controller) or (None,))[0] is not None:
                break
            time.sleep(0.02)
            publish(1.0 / 60.0)
        assert _renderer(source.scene_controller)[0] is not None
        identity = owner.render_identity

        def hop() -> bool:
            seen["at_hop"] = _renderer(target.scene_controller)
            source.scene_controller.transfer_visualizer_to(target.scene_controller)
            return owner.set_presentation_runtime(target)

        done: list = []
        assert owner.move_display(target, end_expanded=False, hop=hop, on_complete=done.append)
        for _ in range(600):
            publish(1.0 / 60.0)
            item = target.scene_controller._visualizer_item
            if seen["first_visible"] is None and "at_hop" in seen and item is not None and not item.prewarming \
                    and item.presentation is not None and float(item.presentation.scene_fade) > 0.0:
                seen["first_visible"] = _renderer(target.scene_controller)
            if done:
                break
            time.sleep(0.02)                          # the render host spaces its preparation units (real time)
        seen["done"] = list(done)
        seen["identity"] = identity
        seen["on_target"] = owner.presentation_runtime is target
    finally:
        owner.retire()
        for host in hosts:
            host.app.processEvents()
    return seen


@pytest.mark.qt
def test_the_targets_first_visible_frame_draws_with_the_renderer_it_prepared(hidden_pair):
    """The owner's move warms the target from the latest snapshot while the source draws; at the hop the target's
    renderer is built and prepared for the live identity, and the first frame in which the target's card is visible
    is drawn by that same renderer object, still prepared (nothing is built on the first visible frame). Negative
    control (the target refusing the warm, as before 1C.2's preparation): the hop finds no renderer there."""
    seen = _move(hidden_pair, prepare=True)
    identity = seen["identity"]
    assert seen["done"] == [True] and seen["on_target"]
    renderer, prepared = seen["at_hop"]
    assert renderer is not None and prepared == (identity.mode_id, identity.activation_id)
    assert seen["first_visible"] is not None
    first_renderer, first_prepared = seen["first_visible"]
    assert first_renderer is renderer
    assert first_prepared == (identity.mode_id, identity.activation_id)


@pytest.mark.qt
def test_without_the_warm_the_hop_finds_no_prepared_renderer(qt_app, monkeypatch):
    """The control's own run (fresh hosts): the target refuses the warm, so at the hop nothing is prepared there and
    the renderer the first visible frame draws with is built after the hop."""
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production host needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    hosts = (HiddenDisplayHost(W, H, dpr=1.0, share=True), HiddenDisplayHost(W, H, dpr=1.0, share=True))
    try:
        seen = _move(hosts, prepare=False)
    finally:
        for host in hosts:
            host.close()
    assert seen["done"] == [True] and seen["on_target"]
    assert seen["at_hop"] is None or seen["at_hop"][0] is None

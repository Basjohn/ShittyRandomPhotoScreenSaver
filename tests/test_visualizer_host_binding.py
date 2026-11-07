"""AC-02: the Visualizer host binding is host-neutral and keeps exactly one owner.

The binding owns construct, bind, transfer, retire, input admissions and
authored layout for one host unit. Its caller keeps only the "which unit"
record. These bars drive it from a caller that is not ``DisplayManager`` and
move the owner onto a stub second host (the shape of an SMP dock / Pop Out or
the Expanded Visualizer host), then prove the manager itself no longer builds
the owner.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


class _Engine:
    @staticmethod
    def get_generation_id() -> int:
        return 41

    @staticmethod
    def get_activation_id() -> int:
        return 42


def _owner_class(constructed: list):
    class _Owner:
        """Stands in for QuickDisplayVisualizerOwner (never a real GL owner)."""

        def __init__(self, runtime, *, bar_count, initial_mode, **kwargs) -> None:
            del bar_count
            self.presentation_runtime = runtime
            self.card_shadow_kwargs = kwargs.get("card_shadow_kwargs")
            self.controller = SimpleNamespace(
                mode_id=initial_mode,
                presentation_state=SimpleNamespace(),
                engine=_Engine(),
                settings_model=None,
                technical_config_cache=None,
                record_resolved_activation=lambda _activation: None,
            )
            self.is_started = False
            self.is_retired = False
            self.retire_calls = 0
            self.origins: list[tuple[float, float]] = []
            constructed.append(self)

        def configure(self, **_kwargs) -> None:
            return None

        def resolved_outer_size(self):
            return (420.0, 280.0)

        def set_authored_outer_origin(self, x, y) -> bool:
            self.origins.append((float(x), float(y)))
            return True

        def bind(self, **_kwargs) -> None:
            return None

        def set_playing(self, _playing, **_kwargs) -> None:
            return None

        def set_display_power(self, _on) -> None:
            return None

        def start(self) -> None:
            self.is_started = True

        def set_presentation_runtime(self, runtime) -> bool:
            self.presentation_runtime = runtime
            return True

        def retire(self) -> bool:
            self.retire_calls += 1
            self.is_retired = True
            return True

    return _Owner


class _Scene:
    def __init__(self) -> None:
        self.double_click = None
        self.middle_click = None
        self.volume_wheel = None
        self.discarded = 0

    def set_visualizer_double_click_admission(self, admission) -> None:
        self.double_click = admission

    def set_visualizer_middle_click_admission(self, admission) -> None:
        self.middle_click = admission

    def set_visualizer_volume_wheel_handler(self, handler) -> None:
        self.volume_wheel = handler

    def visualizer_contains_scene_position(self, _position) -> bool:
        return True

    def discard_unowned_visualizer_admission(self) -> None:
        self.discarded += 1


class _Presenter:
    def __init__(self, media_rect=None) -> None:
        self.authored_layout_enabled = True
        self.media_rect = media_rect
        self.observer = None
        self.obstacles = None

    def authored_geometry_for(self, widget_id):
        return self.media_rect if widget_id == "media" else None

    def presentation_for_widget_id(self, _widget_id):
        return None

    def set_layout_observer(self, observer) -> None:
        self.observer = observer

    def set_external_stack_obstacles(self, obstacles, **_kwargs) -> None:
        self.obstacles = obstacles


class _StubHost:
    """A second host that is not a display unit: only the binding's host surface."""

    def __init__(self, screen_index: int, *, media_rect=None) -> None:
        from rendering.quick.widgets.host import OverlayWidgetGeometry

        self.screen_index = screen_index
        self.is_retired = False
        self.runtime = SimpleNamespace(
            scene_controller=_Scene(),
            window=SimpleNamespace(screen=lambda: None),
        )
        self.presenter = _Presenter(media_rect)
        self.visualizer_owner = None
        self._bounds = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)

    def display_bounds(self):
        return self._bounds

    def attach_visualizer_owner(self, owner) -> None:
        if self.visualizer_owner is not None:
            raise RuntimeError("stub host already owns a visualizer")
        self.visualizer_owner = owner

    def detach_visualizer_owner(self, owner) -> bool:
        if self.visualizer_owner is None:
            return False
        if self.visualizer_owner is not owner:
            raise RuntimeError("wrong owner")
        self.visualizer_owner = None
        return True


class _Caller:
    """The "which unit" side: a routing record and nothing else."""

    def __init__(self, units) -> None:
        self.units = list(units)
        self.owner = None
        self.unit = None
        self.retired = False
        self.outcomes: list[tuple] = []
        self.admission_installs: list[tuple] = []
        self.widgets = {
            "family_activation": {"media": True, "visualizers": True},
            "media": {"enabled": True, "position": "Top Left", "monitor": "1"},
            "spotify_visualizer": {"enabled": True, "visualizers_enabled": True, "position": "Top Left",
                                   "monitor": "1"},
        }

    def services(self):
        from core.settings.default_contract import require_canonical_default
        from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostServices

        def _record(owner, unit) -> None:
            self.owner, self.unit = owner, unit

        def _install(unit, owner) -> None:
            self.admission_installs.append((unit, owner))
            unit.runtime.scene_controller.set_visualizer_double_click_admission(("double", owner))

        return VisualizerHostServices(
            admitted_owner=lambda: self.owner,
            admitted_unit=lambda: self.unit,
            record_admission=_record,
            record_unit=lambda unit: setattr(self, "unit", unit),
            live_units=lambda: self.units,
            caller_retired=lambda: self.retired,
            widgets_config=lambda: self.widgets,
            shadow_values=lambda: require_canonical_default("widgets.shadows"),
            thread_manager=lambda: None,
            process_supervisor=lambda: None,
            display_power_on=lambda: True,
            set_construct_outcome=lambda *args: self.outcomes.append(args),
            committed_layout_profile_resolver=lambda _mode: None,
            edit_layout_profile_activator=lambda _mode: True,
            transition_failure=lambda _reason: None,
            presentation_kwargs=lambda _model, _mode: {},
            media_model_for=lambda _unit: None,
            bind_media=lambda _model: None,
            disconnect_media=lambda: None,
            publish_view_orbit_admission=lambda: None,
            release_view_state=lambda: None,
            install_input_admissions=_install,
            refresh_context_menus=lambda: None,
            refresh_transfer_glyphs=lambda: None,
        )


def _today_unit():
    """Today's host: a real QuickDisplayUnit shell (never shown) with no Media card."""

    from tests.test_visualizer_custom_route_contract import _live_unit

    unit = _live_unit(0)
    unit.presenter.authored_geometry_for = lambda _widget_id: None
    return unit


@pytest.fixture
def constructed(monkeypatch):
    import widgets.spotify_visualizer.quick_display_visualizer_owner as owner_module

    owners: list = []
    monkeypatch.setattr(owner_module, "QuickDisplayVisualizerOwner", _owner_class(owners))
    return owners


def test_one_owner_across_construct_transfer_retire_onto_a_stub_second_host(constructed) -> None:
    from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding

    display = _today_unit()
    second_host = _StubHost(7)
    caller = _Caller([display, second_host])
    binding = VisualizerHostBinding(caller.services())

    assert binding.construct(display) is True
    (owner,) = constructed
    assert (caller.owner, caller.unit) == (owner, display)
    assert display.visualizer_owner is owner
    assert caller.admission_installs == [(display, owner)]

    # A second construction anywhere is rejected at the binding and builds nothing.
    assert binding.construct(second_host) is False
    assert caller.outcomes[-1] == ("rejected", "owner_already_admitted")
    assert len(constructed) == 1

    # The transactional transfer moves retirement authority to the second host.
    assert binding.transfer(second_host) is True
    assert caller.unit is second_host
    assert owner.presentation_runtime is second_host.runtime
    assert display.visualizer_owner is None
    assert second_host.visualizer_owner is owner
    assert len(constructed) == 1 and not owner.is_retired

    # Retire releases the second host: owner retired once, record and admissions cleared.
    second_host.runtime.scene_controller.set_visualizer_double_click_admission(("double", owner))
    assert binding.retire() is True
    assert owner.is_retired and owner.retire_calls == 1
    assert second_host.visualizer_owner is None
    assert (caller.owner, caller.unit) == (None, None)
    assert second_host.runtime.scene_controller.double_click is None
    assert second_host.runtime.scene_controller.discarded == 1
    assert len(constructed) == 1

    # Only after retirement may the one owner be built again.
    assert binding.construct(second_host) is True
    assert len(constructed) == 2
    assert sum(not candidate.is_retired for candidate in constructed) == 1


def test_a_failed_transfer_leaves_the_owner_on_its_host(constructed) -> None:
    from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding

    display = _today_unit()
    second_host = _StubHost(7)
    caller = _Caller([display, second_host])
    services = caller.services()
    binding = VisualizerHostBinding(services)
    assert binding.construct(display) is True
    (owner,) = constructed

    def _attach_fails(_owner) -> None:
        raise RuntimeError("host refused")

    second_host.attach_visualizer_owner = _attach_fails
    with pytest.raises(RuntimeError, match="host refused"):
        binding.transfer(second_host)
    assert caller.unit is display
    assert display.visualizer_owner is owner
    assert owner.presentation_runtime is display.runtime
    assert len(constructed) == 1


def test_display_manager_routes_through_the_binding_with_one_owner(constructed) -> None:
    from tests.test_visualizer_custom_route_contract import _manager

    manager = _manager("Center")
    display = _today_unit()
    second_host = _StubHost(7)
    manager.displays = [display, second_host]
    manager._retired = False
    manager._display_power_on = True
    manager._refresh_all_quick_context_menus = lambda: None
    manager._refresh_quick_visualizer_transfer_glyphs = lambda: None
    manager._quick_scene_view_gesture = None
    manager._quick_view_pose_owner = None
    manager._quick_view_orbit_admitted = lambda: False
    manager._configure_quick_visualizer_input_admission = lambda *_args, **_kwargs: None

    assert manager._admit_quick_visualizer([display]) is True
    assert manager._construct_quick_visualizer_owner_on(second_host) is False
    (owner,) = constructed
    assert manager._transfer_quick_visualizer_unit(second_host) is True
    assert manager._quick_visualizer_unit is second_host
    assert manager._commit_quick_visualizer_presence(False) is True
    assert owner.is_retired and owner.retire_calls == 1
    assert manager._quick_visualizer_owner is None and manager._quick_visualizer_unit is None
    assert len(constructed) == 1


def test_display_manager_no_longer_builds_or_imports_the_owner() -> None:
    tree = ast.parse((ROOT / "engine" / "display_manager.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
            if node.module and node.module.endswith("quick_display_visualizer_owner"):
                names.add(node.module)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    assert "QuickDisplayVisualizerOwner" not in names
    assert not any(name.endswith("quick_display_visualizer_owner") for name in names)


# --------------------------------------------------------------------------
# Media docking is one declared placement policy (docked_to: media | none).


class _PlacedOwner:
    def __init__(self) -> None:
        self.origin = None

    def resolved_outer_size(self):
        return (420.0, 280.0)

    def set_authored_outer_origin(self, x, y) -> bool:
        self.origin = (float(x), float(y))
        return True


def _docking_binding(position: str = "Top Left"):
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding

    host = _StubHost(0, media_rect=OverlayWidgetGeometry(40.0, 40.0, 500.0, 220.0))
    caller = _Caller([host])
    caller.widgets["media"]["position"] = position
    caller.widgets["spotify_visualizer"]["position"] = position
    owner = _PlacedOwner()
    caller.owner, caller.unit = owner, host
    return VisualizerHostBinding(caller.services()), host, owner


def _move_media(host, x: float, y: float) -> None:
    from rendering.quick.widgets.host import OverlayWidgetGeometry

    moved = OverlayWidgetGeometry(x, y, 500.0, 220.0)
    host.presenter.media_rect = moved
    if host.presenter.observer is not None:
        host.presenter.observer("media", moved)


def _undock(monkeypatch) -> None:
    """Declare the Visualizer undocked (the policy is a removable descriptor value)."""

    from dataclasses import replace

    import rendering.visualizer_placement as placement
    from rendering.widget_descriptors import get_widget_runtime_descriptor

    undocked = replace(get_widget_runtime_descriptor("spotify_visualizer"), docked_to="none")
    monkeypatch.setattr(
        placement, "get_widget_runtime_descriptor",
        lambda widget_id: undocked if widget_id == "spotify_visualizer" else get_widget_runtime_descriptor(widget_id),
    )


def test_the_docking_policy_is_declared_on_the_layout_descriptor() -> None:
    from rendering.visualizer_placement import DOCKING_TARGETS, declared_visualizer_docked_to
    from rendering.widget_descriptors import get_widget_runtime_descriptors

    declared = {d.widget_id: d.docked_to for d in get_widget_runtime_descriptors()}
    assert declared["spotify_visualizer"] == "media" == declared_visualizer_docked_to()
    assert set(declared.values()) <= DOCKING_TARGETS
    assert {widget_id for widget_id, target in declared.items() if target != "none"} == {"spotify_visualizer"}


def test_moving_media_moves_a_docked_visualizer() -> None:
    binding, host, owner = _docking_binding()
    assert binding.install_authored_layout(host, owner, install_observer=True) is True
    assert host.presenter.observer is not None
    docked_at = owner.origin
    assert docked_at[1] > 40.0 + 220.0  # beside (below) Media
    assert [obstacle.key for obstacle in host.presenter.obstacles] == ["media", "spotify_visualizer"]

    _move_media(host, 900.0, 300.0)
    assert owner.origin != docked_at
    assert owner.origin[0] == 900.0  # follows Media


def test_moving_media_leaves_an_undocked_visualizer_in_place(monkeypatch) -> None:
    _undock(monkeypatch)
    binding, host, owner = _docking_binding()
    assert binding.install_authored_layout(host, owner, install_observer=True) is True
    assert host.presenter.observer is None  # nothing follows Media
    resting = owner.origin
    # Undocked: Media's plain authored slot (Top Left), not beside Media's card.
    plain = binding.resolve_placement(host, owner, authored_layout_enabled=False)
    assert resting == (plain.x, plain.y)
    # Still an ordinary card: it reserves its own box, with no fixed Media.
    assert [obstacle.key for obstacle in host.presenter.obstacles] == ["spotify_visualizer"]

    _move_media(host, 900.0, 300.0)
    assert binding.install_authored_layout(host, owner, install_observer=False) is True
    assert owner.origin == resting


def test_global_custom_resolves_undocked_and_never_follows_media() -> None:
    binding, host, owner = _docking_binding("Custom")
    placement = binding.resolve_placement(host, owner)
    assert (placement.authored, placement.docked_to) == (False, "none")
    assert binding.install_authored_layout(host, owner, install_observer=True) is False
    assert host.presenter.observer is None and owner.origin is None
    assert binding.project_base_authored_origin() is True
    resting = owner.origin
    _move_media(host, 900.0, 300.0)
    assert binding.install_authored_layout(host, owner, install_observer=False) is False
    assert owner.origin == resting


@pytest.mark.parametrize("docked", (True, False), ids=("docked", "undocked"))
def test_arrange_and_the_saver_place_the_visualizer_through_one_policy(monkeypatch, docked) -> None:
    from copy import deepcopy

    from core.settings.default_settings import DEFAULT_SETTINGS
    from rendering.quick.widgets.authored_layout_projection import project_authored_display_layout
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from widgets.spotify_visualizer.visualizer_host_binding import VisualizerHostBinding

    if not docked:
        _undock(monkeypatch)
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])  # TEST INPUT: Media and the Visualizer on one display
    widgets["family_activation"] = {family: family in {"media", "visualizers"}
                                    for family in widgets["family_activation"]}
    widgets["media"].update(enabled=True, position="Bottom Left", monitor="ALL")
    widgets["spotify_visualizer"].update(enabled=True)
    arranged = project_authored_display_layout(
        widgets, display_size=(1920, 1080), ordinary=[("media", (500.0, 220.0))], visualizer_size=(420.0, 280.0),
    )
    media = arranged["media"]

    host = _StubHost(0, media_rect=OverlayWidgetGeometry(media.x, media.y, media.width, media.height))
    caller = _Caller([host])
    caller.widgets = widgets
    owner = _PlacedOwner()
    caller.owner, caller.unit = owner, host
    assert VisualizerHostBinding(caller.services()).install_authored_layout(host, owner, install_observer=True)

    shown = arranged["spotify_visualizer"]
    assert owner.origin == (shown.x, shown.y)
    beside_media = shown.y + shown.height <= media.y  # Bottom Left Media: docked above it
    assert beside_media is docked
    assert (host.presenter.observer is not None) is docked

"""Held-key Edit framing follows only admitted authored-view publications."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from core.settings.default_contract import get_raw_default_settings
from core.settings.scene3d_quality import resolve_visualizer_tier
from engine.display_manager import DisplayManager
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_overlay import CustomLayoutOverlayModel
from tests._visualizer_presentation import resolve_presentation
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
from widgets.spotify_visualizer.config_applier import presentation_setting_range
from widgets.spotify_visualizer.config_applier import extruded_spectrum_parameters
from widgets.spotify_visualizer.render_state import freeze_render_fields
from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from widgets.spotify_visualizer.quick_presentation_sync import QuickVisualizerPresentationSync, QuickVisualizerPublicationWake
from widgets.spotify_visualizer.view_orbit import stop_view_orbit_motion


def _item(widget: str, variant: str) -> CustomLayoutSessionItem:
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey(widget, "display:a", variant), model_identity=widget,
        baseline_global_rect=QRect(100, 80, 420, 280), current_global_rect=QRect(100, 80, 420, 280),
        baseline_size_payload={}, current_size_payload={}, baseline_enabled=True, current_enabled=True,
    )


@pytest.mark.qt
def test_held_orbit_updates_from_gui_publication_and_audio_only_has_no_observer(qt_app, monkeypatch):
    import rendering.quick.visualizer.edit_content_envelope as framing
    from engine import display_manager

    gui_thread = threading.get_ident()
    now = [100.0]
    monkeypatch.setattr(display_manager.time, "time", lambda: now[0])
    presentation = resolve_presentation(
        policy=get_visualizer_presentation_policy("extruded_spectrum"),
        display_size=(1920.0, 1080.0), outer_origin=(100.0, 80.0), viewport_extent=(420.0, 280.0),
    )
    host = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host, {
        **dict(get_raw_default_settings()["widgets"]["spotify_visualizer"]),
        "scene3d_detail": resolve_visualizer_tier(None, "extruded_spectrum"),
    })
    mailbox = LatestStateMailbox()
    identity = SimpleNamespace(runtime_generation=1, engine_generation=2, activation_id=3, mode_id="extruded_spectrum")
    retained = [None]
    accepted_slot = [None]
    def accept(logical, _presentation, **kwargs):
        accepted_slot[0] = SimpleNamespace(logical=logical)
        return True
    controller = SimpleNamespace(
        mode_id="extruded_spectrum", bar_count=32, presentation_state=host,
        logical_mailbox=mailbox, render_identity=identity, publish_render_snapshot=accept,
        render_bridge=SimpleNamespace(peek=lambda: accepted_slot[0]),
    )
    published = []
    scene = SimpleNamespace(
        visualizer_item=SimpleNamespace(presentation=presentation, retained_snapshot=lambda identity: retained[0]),
        set_visualizer_edit_content_envelope=lambda record: published.append((threading.get_ident(), record)),
    )
    owner = object.__new__(QuickDisplayVisualizerOwner)
    owner._controller = controller
    owner._retired = False
    owner._mode_transition_phase = "idle"
    owner._sync = QuickVisualizerPresentationSync(controller, resolve_presentation=lambda: presentation)
    session = CustomLayoutSession()
    visualizer, clock = _item("spotify_visualizer", "freeform_3d"), _item("clock", "default")
    session.add_item(visualizer)
    session.add_item(clock)
    custom_owner = SimpleNamespace(is_editing=True, session=session)
    manager = DisplayManager.__new__(DisplayManager)
    manager._quick_visualizer_owner = owner
    manager._quick_visualizer_unit = SimpleNamespace(is_retired=False, runtime=SimpleNamespace(scene_controller=scene))
    manager._quick_custom_layout_owner = custom_owner
    manager._quick_view_orbit_pending = None
    model = CustomLayoutOverlayModel(session=session, display_identity="display:a")
    model.selection_changed.connect(manager._refresh_quick_visualizer_edit_content_envelope)
    resolutions = []
    resolve = framing.resolve_edit_content_envelope

    def counted(*args, **kwargs):
        resolutions.append(args[2]["extruded_spectrum_turn"])
        return resolve(*args, **kwargs)

    monkeypatch.setattr(framing, "resolve_edit_content_envelope", counted)
    wake = QuickVisualizerPublicationWake(owner.sync_present)
    mailbox.set_wake_callback(wake.request)

    def publish(timestamp=100.0, *, deliver=True, parameter_changes=None, **changes):
        parameters = extruded_spectrum_parameters(host, timestamp)
        parameters.update(spectrum_ghosting_enabled=False, spectrum_ghost_alpha=0.0)
        parameters.update(parameter_changes or {})
        frame = SimpleNamespace(
            **vars(identity), logical_timestamp=timestamp,
            present_frame=True, playing=False,
            mode_state=SimpleNamespace(parameters=freeze_render_fields(parameters), peaks=(0.4,) * controller.bar_count),
            common=SimpleNamespace(bar_count=controller.bar_count, bars=(0.35,) * controller.bar_count,
                style={"fill_color": (255, 255, 255, 255), "border_color": (255, 255, 255, 255)}),
        )
        for key, value in changes.items():
            setattr(frame, key, value)
        producer = threading.Thread(target=lambda: mailbox.publish(frame, generation=1, activation_id=3))
        producer.start()
        producer.join()
        if deliver:
            qt_app.processEvents()
            retained[0] = SimpleNamespace(logical=frame)
        return frame

    try:
        model.selectItem(0)
        before_stage = QRect(visualizer.current_global_rect)
        resolutions.clear()
        publish()
        assert len(resolutions) == 1             # pending Enter source admits exactly one frame
        assert published[-1][1]["admitted"]
        assert published[-1][1]["orbit_admitted"]
        resolutions.clear()
        publish(100.2)
        assert resolutions == []                 # selected Edit alone observes no audio frames

        # Same-family activation/preset replacement: both slots unavailable at
        # the edge. Re-arm exactly until a current visible draw is admitted.
        identity.activation_id += 1
        retained[0] = accepted_slot[0] = None
        manager._refresh_quick_visualizer_edit_content_envelope()
        assert published[-1][1] == {"admitted": False, "mode": "extruded_spectrum", "orbit_admitted": True}
        publish(100.3, present_frame=False)
        assert resolutions == []
        assert owner._sync._authored_view_publication_callback is not None
        publish(100.4)
        assert len(resolutions) == 1
        assert owner._sync._authored_view_publication_callback is None
        resolutions.clear()
        publish(100.45)
        assert resolutions == []

        identity.activation_id += 1
        retained[0] = accepted_slot[0] = None
        manager._refresh_quick_visualizer_edit_content_envelope()
        publish(100.46, parameter_changes={
            "extruded_spectrum_body_alpha": 0.0, "extruded_spectrum_reflection": 0.0,
            "extruded_spectrum_shadow_enabled": False,
        })
        assert published[-1][1] == {"admitted": False, "mode": "extruded_spectrum", "orbit_admitted": True}
        assert owner._sync._authored_view_publication_callback is None
        resolutions.clear()
        publish(100.47)
        assert resolutions == []                 # empty is valid, never an endless audio observer

        manager._set_quick_view_orbit_rates(1.0, 0.0)
        resolutions.clear()
        publish(100.5)
        first = published[-1][1]
        publish(101.0)
        second = published[-1][1]
        assert len(resolutions) == 2
        assert first != second
        assert all(thread == gui_thread for thread, _record in published)
        assert visualizer.current_global_rect == before_stage
        assert visualizer.current_size_payload == {}
        publish(101.2, activation_id=99)          # rejected publication cannot refresh framing
        assert len(resolutions) == 2

        model.selectItem(1)
        resolutions.clear()
        publish(101.5)
        assert resolutions == []                 # held orbit with another selected item is dormant
        model.selectItem(0)
        resolutions.clear()
        publish(102.0)
        assert len(resolutions) == 1             # selection re-admits held orbit without a new clock

        queued = publish(102.5, deliver=False)
        now[0] = 102.75
        manager._set_quick_view_orbit_rates(-1.0, 0.0)
        apply_presentation_vis_mode_kwargs(host, {"extruded_spectrum_depth": 4.0})
        manager._refresh_quick_visualizer_edit_content_envelope()
        current_authored = published[-1][1]
        qt_app.processEvents()
        accepted = dict(queued.mode_state.parameters)
        accepted["bar_count"] = queued.common.bar_count
        assert published[-1][1] == resolve("extruded_spectrum", presentation, accepted, logical=queued)
        assert published[-1][1] != current_authored   # queued snapshot keeps its captured view/shape

        stop_view_orbit_motion(host, 102.0)
        manager._refresh_quick_visualizer_edit_content_envelope()
        resolutions.clear()
        publish(102.5)
        assert resolutions == []
        host._extruded_spectrum_tilt = presentation_setting_range("extruded_spectrum_tilt")[1]
        now[0] = 103.0
        manager._set_quick_view_orbit_rates(0.0, 1.0)
        resolutions.clear()
        publish(103.5, parameter_changes={"floor_snapshot": 0.4, "audio_revision": 93})
        publish(104.0, parameter_changes={"floor_snapshot": 0.8, "audio_revision": 94})
        assert len(resolutions) == 1             # first accepted pose only; clamped tilt then stays dormant
        now[0] = 103.0
        manager._set_quick_view_orbit_rates(1.0, 0.0)
        custom_owner.is_editing = False
        def closed_item_must_not_be_sampled(_identity):
            raise AssertionError("closed Edit sampled retained renderer input")
        scene.visualizer_item.retained_snapshot = closed_item_must_not_be_sampled
        manager._refresh_quick_visualizer_edit_content_envelope()
        resolutions.clear()
        publish(103.5)
        assert resolutions == []                 # closed Edit remains dormant even if keys are held
    finally:
        mailbox.set_wake_callback(None)
        wake.close()
        model.retire()


def test_disarmed_publication_callback_cannot_survive_queued_wake(qt_app):
    deliveries = []
    mailbox = LatestStateMailbox()
    identity = SimpleNamespace(runtime_generation=1, engine_generation=2, activation_id=3, mode_id="spectrum")
    controller = SimpleNamespace(logical_mailbox=mailbox, render_identity=identity, publish_render_snapshot=lambda *a, **k: True)
    sync = QuickVisualizerPresentationSync(controller, resolve_presentation=lambda: object())
    sync.set_authored_view_publication_callback(lambda logical, _presentation: deliveries.append(logical.logical_timestamp))
    wake = QuickVisualizerPublicationWake(sync.sync_latest)
    mailbox.set_wake_callback(wake.request)
    try:
        mailbox.publish(SimpleNamespace(**vars(identity), logical_timestamp=100.0), generation=1, activation_id=3)
        sync.set_authored_view_publication_callback(None)
        qt_app.processEvents()
        assert deliveries == []
        wake.close()
        wake.request()
        qt_app.processEvents()
        assert deliveries == []
    finally:
        mailbox.set_wake_callback(None)
        wake.close()

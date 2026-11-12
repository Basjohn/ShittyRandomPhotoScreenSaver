"""1C.2 root-cause probe (the reproducer of move_trace.txt). Not a test of record: copy it to
tests/probe_1c2_move_trace.py to run it (it needs tests/conftest.py), and delete the copy afterwards.

The real chrome-less display move (``QuickCustomLayoutOwner.move_visualizer_to_display``, the takeover's
``move_to_display`` service) on a real ``QuickDisplayVisualizerOwner`` across two real (never shown) Quick display
units. Each unit's screen is a stand-in so the two have distinct identities side by side. Prints what is kept, what
is requested (a runtime reload), and the log lines; a second case runs the same hop through real Edit (session bound
to the scenes) as the control.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from PySide6.QtCore import QRect

from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from tests.test_qtquick_custom_layout_owner import (
    _LiveCommitEngine, _Settings, _clock_unit, _clock_widgets, _configure_visualizer,
)
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

SHADOW = {"background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255), "border_width": 4.,
          "corner_radius": 6., "content_inset": 14., "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
          "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0., "shadow_extensions": (0., 0., 0., 0.)}


def _screen(name, rect):
    return SimpleNamespace(geometry=lambda r=QRect(rect): QRect(r), name=lambda: name, serialNumber=lambda: name,
                           manufacturer=lambda: "", model=lambda: "", devicePixelRatio=lambda: 1.0)


class _Window:
    def __init__(self, real, screen):
        self._real, self._screen = real, screen

    def screen(self):
        return self._screen

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Runtime:
    def __init__(self, real, screen, rect):
        self._real = real
        self.window = _Window(real.window, screen)
        from dataclasses import replace
        self.display_identity = replace(real.display_identity, screen_key=screen.name(),
                                        geometry=(rect.x(), rect.y(), rect.width(), rect.height()))

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Unit:
    def __init__(self, real, screen, rect):
        self._real = real
        self.runtime = _Runtime(real.runtime, screen, rect)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.lines = []

    def emit(self, record):
        message = record.getMessage()
        if any(tag in message for tag in ("[CUSTOM_LAYOUT]", "[SPOTIFY_VIS]", "[EXPANDED_VIS]")):
            self.lines.append(f"{record.levelname} {record.name}: {message}")


def _rig(qt_app, target_rect):
    widgets = _clock_widgets()
    widgets["clock"]["enabled"] = False
    widgets["spotify_visualizer"] = {"enabled": True, "mode": "spectrum", "monitor": "1"}
    real0, factory = _clock_unit(qt_app, widgets, generation=1201, screen_index=0)
    real1, _ = _clock_unit(qt_app, widgets, generation=1201, screen_index=1, factory=factory)
    rects = (QRect(0, 0, 1280, 720), QRect(target_rect))
    units = tuple(_Unit(real, _screen(f"probe-{index}", rect), rect)
                  for index, (real, rect) in enumerate(zip((real0, real1), rects)))
    owner = QuickDisplayVisualizerOwner(units[0].runtime, initial_mode="spectrum", bar_count=24,
                                        engine_factory=lambda _count: _LiveCommitEngine(), card_shadow_kwargs=SHADOW)
    units[0].attach_visualizer_owner(owner)
    current = {"unit": units[0]}
    reloads: list[str] = []

    def transfer(target):            # VisualizerHostBinding.transfer's owner edge
        source = current["unit"]
        owner.set_presentation_runtime(target.runtime)
        source.detach_visualizer_owner(owner)
        target.attach_visualizer_owner(owner)
        current["unit"] = target
        return True

    settings = _Settings(widgets)
    layout = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: units,
        visualizer_provider=lambda: (owner, current["unit"]), reload_request=reloads.append,
        visualizer_unit_transfer=transfer, live_config_commit=lambda _widgets: None)
    _configure_visualizer(owner, playing=True)
    owner.set_authored_outer_origin(100., 100.)
    owner.bind(engine_generation=3, activation_id=5)
    owner._apply_resolved_presentation(owner._resolve_current_presentation())
    owner.start(interval_s=10.)
    return layout, units, owner, current, reloads, settings, (real0, real1, factory)


def _facts(owner):
    controller = owner.controller
    return {"owner": id(owner), "controller": id(controller), "logical_runtime": id(controller.logical_runtime),
            "engine": id(controller.engine), "activation": controller.engine.get_activation_id(),
            "running": controller.logical_runtime.is_running()}


def _close(layout, owner, reals, qt_app):
    layout.retire()
    real0, real1, factory = reals
    real0.retire()
    real1.retire()
    factory.deleteLater()
    qt_app.processEvents()


def _run(qt_app, monkeypatch, target_rect, *, through_edit):
    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    capture = _Capture()
    logging.getLogger().addHandler(capture)
    levels = {name: logging.getLogger(name).level for name in ("", "rendering", "widgets", "engine")}
    for name in levels:
        logging.getLogger(name).setLevel(logging.INFO)
    layout, units, owner, current, reloads, settings, reals = _rig(qt_app, target_rect)
    try:
        before = _facts(owner)
        print(f"\n=== case: target={QRect(target_rect).getRect()} through_edit={through_edit}")
        print("before:", before, "source rect:", units[0].runtime.scene_controller.visualizer_item.presentation.outer_rect)
        if through_edit:
            assert layout.start() is True
            item = next(i for i in layout.session.items() if i.model_identity == "spotify_visualizer")
            print("override during Edit:", owner.controller.has_custom_viewport_override)
            moved = layout.transfer_display(item, "right")
            layout.session.notify_item_changed(item)     # what Edit's hop delivers to the scene coordinator
            print("hop:", moved, "override after hop:", owner.controller.has_custom_viewport_override)
            saved = layout.save()
        else:
            saved = layout.move_visualizer_to_display(units[1])
        after = _facts(owner)
        target_item = units[1].runtime.scene_controller.visualizer_item
        print("move/save returned:", saved)
        print("after:", after)
        print("same owner/controller/logical runtime/engine:",
              {key: before[key] == after[key] for key in ("owner", "controller", "logical_runtime", "engine")})
        print("owner on target:", current["unit"] is units[1], "override now:", owner.controller.has_custom_viewport_override)
        print("target rect:", None if target_item is None else target_item.presentation.outer_rect)
        print("monitor persisted:", settings.widgets["spotify_visualizer"].get("monitor"))
        print("RUNTIME RELOADS REQUESTED:", reloads)
        print("log lines:")
        for line in capture.lines:
            print("   ", line)
    finally:
        logging.getLogger().removeHandler(capture)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)
        _close(layout, owner, reals, qt_app)


def test_probe_glyph_move_same_size(qt_app, monkeypatch):
    _run(qt_app, monkeypatch, QRect(1280, 0, 1280, 720), through_edit=False)


def test_probe_glyph_move_other_size(qt_app, monkeypatch):
    _run(qt_app, monkeypatch, QRect(1280, 0, 1920, 1080), through_edit=False)


def test_probe_edit_hop_and_save_control(qt_app, monkeypatch):
    _run(qt_app, monkeypatch, QRect(1280, 0, 1280, 720), through_edit=True)


def test_probe_edit_hop_and_save_control_other_size(qt_app, monkeypatch):
    _run(qt_app, monkeypatch, QRect(1280, 0, 1920, 1080), through_edit=True)

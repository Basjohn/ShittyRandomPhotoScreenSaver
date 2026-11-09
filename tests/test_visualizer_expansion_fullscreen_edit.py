"""Expanded Visualizer M3c: Fullscreen Edit (plan 01 §H Milestone 3c).

Operator, 8 Nov: "when we choose edit mode during a fullscreen visualizer we should be able to adjust the
size/position/placement of the toast and preset text elements and artwork instead of it going back to the full quick
scene. Like we can most geometry normally."

The bars run the production ``DisplayScene.qml`` / ``VisualizerPresentation.qml`` / ``CustomLayoutOverlay.qml`` and
``QuickSceneController`` in the hidden ``QQuickRenderControl`` host (no window is shown), the real
``QuickCustomLayoutOwner`` (its one session, its overlay model and gestures) and a real ``SettingsManager`` in
``tmp_path``:

* a parity map in the spirit of the Edit/Arrange parity harness: one gesture script through the Edit owner on a draft,
  Cancel (everything exactly as before), the same script again and Save (the committed value draws exactly what the
  draft showed);
* a Fullscreen-only Save or Cancel leaves the ordinary layout, CUSTOM and the layout slots byte-identical;
* entering Edit on the expanded view emits no collapse transaction (the display manager's real Edit entry, the real
  takeover coordinator) and the context menu's Save ends it like Enter;
* while Fullscreen Edit is open the overlays show (as if Always Show) and follow content changes; on exit they fade
  back to their authored visibility (never vanish);
* overlays moved into the card's right-hand control column keep clear of the collapse glyph, the 3D hint, Reset Camera
  and the preset steps;
* an unsaved draft holds Settings (Save or Cancel first).

Every value a test writes is test-owned; nothing pins a default, a preset or UI wording.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtQuick import QQuickItem

from tests.test_visualizer_expansion_overlays import (
    SLOTS,
    _Media,
    _controls,
    _draw,
    _expanded_card,
    _open,
    _rect,
    _root,
    _run,
    _settle,
    _slot,
)

WIDTH, HEIGHT = 1280, 720
PARTS = ("preset", "now_playing")
BLOCK = "fullscreen_overlay.now_playing"


@pytest.fixture
def display(qt_app):
    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    from tools.expanded_visualizer_evidence import HiddenDisplayHost

    host = HiddenDisplayHost(WIDTH, HEIGHT, dpr=1.0)
    try:
        yield host
    finally:
        host.close()


def _manager(root: Path):
    from core.settings.settings_manager import SettingsManager

    return SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}", storage_base_dir=root)


def _value(settings) -> dict:
    from core.settings.fullscreen_overlays import FULLSCREEN_OVERLAYS_KEY, normalize_fullscreen_overlays

    return normalize_fullscreen_overlays(settings.get(FULLSCREEN_OVERLAYS_KEY))


def _seed(settings, **overlays) -> dict:
    """A test-owned overlays value (the canonical one with ``overlays``' members) written to Settings."""
    from core.settings.fullscreen_overlays import FULLSCREEN_OVERLAYS_KEY, canonical_fullscreen_overlays

    value = canonical_fullscreen_overlays()
    for overlay, options in overlays.items():
        value[overlay].update(options)
    settings.set(FULLSCREEN_OVERLAYS_KEY, value)
    settings.save()
    return _value(settings)


def _projection(value: dict) -> dict:
    from widgets.spotify_visualizer.expanded_overlays import resolve_expanded_overlay_config

    return resolve_expanded_overlay_config({"fullscreen_overlays": value})


class _Fullscreen:
    """Fullscreen Edit through the real owner on the hidden scene (the display manager's start, minus its menus)."""

    def __init__(self, display, settings, visualizer=None) -> None:
        from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

        self.display = display
        self.settings = settings
        self.visualizer = visualizer
        self.reloads: list[str] = []
        self.flips: list[bool] = []
        self.unit = SimpleNamespace(
            is_retired=False, screen_index=0, presenter=SimpleNamespace(bound_widget_ids=()),
            runtime=SimpleNamespace(scene_controller=display.scene, window=display.window,
                                    display_identity=SimpleNamespace(screen_key="hidden",
                                                                     geometry=(0, 0, WIDTH, HEIGHT))))
        self.owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (self.unit,),
            visualizer_provider=lambda: (self.visualizer, self.unit) if self.visualizer is not None else (None, None),
            reload_request=self.reloads.append,
            fullscreen_draft_listener=self.flips.append)

    def start(self) -> bool:
        started = self.owner.start_fullscreen(self.unit, _value(self.settings))
        _run(self.display, 120)
        return started

    @property
    def model(self):
        return self.display.scene.custom_layout_overlay.model

    def row(self, part: str) -> int:
        return next(index for index, item in enumerate(self.model._items)
                    if item.model_identity == f"fullscreen_overlay.{part}")

    def item(self, part: str):
        return self.model._items[self.row(part)]

    def _local(self, rect: QRect) -> QRect:
        return rect.translated(-self.model._display_origin)

    def drag(self, part: str, dx: int, dy: int, *, steps: int = 6, release: bool = True) -> None:
        row = self.row(part)
        start = self._local(self.item(part).current_global_rect)
        grab = QPoint(start.x() + 6, start.y() + 6)
        self.model.selectItem(row)
        self.model.finishMove()
        for step in range(1, steps + 1):
            fx, fy = round(dx * step / steps), round(dy * step / steps)
            self.model.moveItem(self.row(part), start.x() + fx, start.y() + fy, grab.x() + fx, grab.y() + fy)
        if release:
            self.model.finishMove()

    def wheel(self, part: str, notches: int) -> None:
        self.model.resizeWheel(self.row(part), 120 * notches)

    def corner(self, part: str, handle: str, dx: int, dy: int) -> None:
        row = self.row(part)
        rect = self._local(self.item(part).current_global_rect)
        x = rect.x() if handle.endswith("left") else rect.x() + rect.width()
        y = rect.y() if handle.startswith("top") else rect.y() + rect.height()
        assert self.model.beginResize(row, handle, x, y)
        self.model.resizeItem(row, handle, x + dx / 2, y + dy / 2, False)
        self.model.resizeItem(row, handle, x + dx, y + dy, True)

    def side(self, part: str, handle: str, delta: int, *, release: bool = True) -> None:
        """Drag one side handle (``left``/``right``/``top``/``bottom``) or a two-axis diagonal (``content_*``) by
        ``delta`` along its axis (both axes for a diagonal), pressing on the frame's edge as the Edit layer does."""
        row = self.row(part)
        rect = self._local(self.item(part).current_global_rect)
        corner = handle.removeprefix("content_")
        x = rect.x() if corner.endswith("left") else (rect.x() + rect.width() if corner.endswith("right")
                                                       else rect.center().x())
        y = rect.y() if corner.startswith("top") else (rect.y() + rect.height() if corner.startswith("bottom")
                                                        else rect.center().y())
        dx = delta if handle in ("left", "right") or handle.startswith("content_") else 0
        dy = delta if handle in ("top", "bottom") or handle.startswith("content_") else 0
        assert self.model.beginResize(row, handle, x, y)
        self.model.resizeItem(row, handle, x + dx / 2, y + dy / 2, False)
        self.model.resizeItem(row, handle, x + dx, y + dy, release)

    def frames(self) -> dict[str, tuple[int, int, int, int]]:
        return {part: self.item(part).current_global_rect.getRect() for part in PARTS}

    # ---- Now Playing's parts: ordinary Edit's child editor on the block (select it, open its child lock)

    def layer_item(self, name: str):
        layer = self.display.scene.custom_layout_overlay.item
        return next((item for item in _visual_items(layer) if item.objectName() == name), None)

    def open_children(self) -> None:
        """Select the block and open its child lock (the Edit layer's L route), as ordinary Edit does."""
        self.model.selectItem(self.row("now_playing"))
        _run(self.display, 30)
        self.display.scene.toggle_selected_child_edit_lock()
        _run(self.display, 200)

    def child_frame(self, role: str):
        frame = self.layer_item(f"customLayoutChildRole-{BLOCK}-{role}")
        assert frame is not None and frame.isVisible(), role
        return frame

    def _child_point(self, frame, fx: float, fy: float) -> QPointF:
        layer = self.display.scene.custom_layout_overlay.item
        return frame.mapToItem(layer, QPointF(frame.width() * fx, frame.height() * fy))

    def child_move(self, role: str, dx: int, dy: int) -> None:
        """One child move through the overlay model (the child layer's press, samples and release)."""
        frame, row = self.child_frame(role), self.row("now_playing")
        point = self._child_point(frame, 0.5, 0.5)
        assert self.model.beginChildMove(row, role, point.x(), point.y(), float(frame.property("normalizationWidth")),
                                         float(frame.property("normalizationHeight")), 0.0, 0.0)
        self.model.moveChild(row, role, point.x() + dx / 2, point.y() + dy / 2, False)
        self.model.moveChild(row, role, point.x() + dx, point.y() + dy, True)
        _run(self.display, 30)

    def child_resize(self, role: str, handle: str, delta: int) -> None:
        """One child resize through the overlay model from ``handle`` (a side along its axis, a corner on both)."""
        dx = 0 if handle in ("top", "bottom") else delta
        dy = 0 if handle in ("left", "right") else delta
        frame, row = self.child_frame(role), self.row("now_playing")
        fx = 0.0 if handle.endswith("left") else (1.0 if handle.endswith("right") else 0.5)
        fy = 0.0 if handle.startswith("top") else (1.0 if handle.startswith("bottom") else 0.5)
        point = self._child_point(frame, fx, fy)
        assert self.model.beginChildResize(row, role, handle, point.x(), point.y(), frame.width(), frame.height(),
                                           float(frame.property("normalizationWidth")),
                                           float(frame.property("normalizationHeight")))
        self.model.resizeChild(row, role, handle, point.x() + dx / 2, point.y() + dy / 2, False)
        self.model.resizeChild(row, role, handle, point.x() + dx, point.y() + dy, True)
        _run(self.display, 30)

    def drawn(self) -> dict[str, tuple[int, int, int, int]]:
        """The parts as the overlays draw them now (read from the QML, independent of the session)."""
        geometry = self.display.scene.expanded_overlay_edit_geometry()
        origin = QPoint(0, 0) if not self.model_bound() else self.model._display_origin
        return {part: QRectF(*geometry["parts"][part]).toRect().translated(origin).getRect() for part in PARTS}

    def model_bound(self) -> bool:
        try:
            self.display.scene.custom_layout_overlay.model
        except RuntimeError:
            return False
        return True


def _gesture(edit: _Fullscreen) -> None:
    """One script exercising every Fullscreen Edit gesture: move, wheel, corner drags, side handles (width only,
    height only) on both overlays, Restore Size, and Now Playing's parts through the child editor (a move and an
    artwork resize)."""
    edit.drag("preset", 180, 96)
    edit.wheel("now_playing", 2)
    edit.corner("now_playing", "top_right", 36, -36)
    edit.drag("now_playing", 60, -48)
    edit.corner("preset", "bottom_right", 40, 18)
    edit.wheel("preset", -1)
    edit.model.restoreSize(edit.row("preset"))
    edit.drag("preset", -24, 30)
    edit.side("preset", "right", -70)
    edit.side("preset", "bottom", 64)
    edit.side("now_playing", "right", 140)
    edit.side("now_playing", "top", -50)
    edit.open_children()
    edit.child_move("title", 36, 24)
    edit.child_resize("artwork", "right", -30)
    edit.child_move("artist", -12, 18)


def _visual_items(item) -> list:
    found, queue = [], list(item.childItems())
    while queue:
        child = queue.pop()
        found.append(child)
        queue.extend(child.childItems())
    return found


def _shown_and_settled(display) -> None:
    _settle(display, lambda: all(float(_slot(display, name).property("presence")) >= 1.0 for name in SLOTS))


# ---------------------------------------------------------------------------------------------- parity map


@pytest.mark.qt
def test_parity_map_the_draft_cancels_exactly_and_save_commits_what_the_draft_showed(display, tmp_path):
    settings = _manager(tmp_path)
    seeded = _seed(settings, preset={"offset_x": 0.05, "offset_y": 0.1}, now_playing={"scale": 1.2})
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings)

    assert edit.start()
    _shown_and_settled(display)
    assert {item.model_identity for item in edit.model._items} == {f"fullscreen_overlay.{p}" for p in PARTS}
    # The same Edit frames as every widget's, without a close control (the overlays have no enabled state).
    layer = display.scene.custom_layout_overlay.item
    frames = {item.objectName(): item for item in _visual_items(layer)}
    for part in PARTS:
        assert f"customLayoutEditFrame-fullscreen_overlay.{part}" in frames
        assert not frames[f"customLayoutClose-fullscreen_overlay.{part}"].isVisible()
        assert frames[f"customLayoutResize-fullscreen_overlay.{part}-bottom_right"].isVisible()
        # ... and the same single-axis side strips as ordinary content-extent widgets, each one grabbable (a one-line
        # toast is shorter than the strips' usual corner insets).
        for edge in ("left", "right", "top", "bottom"):
            strip = frames[f"customLayoutViewportEdge-fullscreen_overlay.{part}-{edge}"]
            assert strip.isVisible() and min(strip.width(), strip.height()) >= 8, (part, edge)
    before_config = dict(display.scene._visualizer_overlay_config)
    before = edit.frames()
    assert before == edit.drawn()

    _gesture(edit)
    _run(display, 120)
    draft_value = edit.owner._fullscreen.draft_value()
    draft_frames, draft_config = edit.frames(), dict(display.scene._visualizer_overlay_config)
    assert draft_frames == edit.drawn()                      # every frame is what the overlays draw
    assert draft_value != seeded and draft_frames != before   # the script really edited the draft
    from core.settings.fullscreen_overlays import PLACEMENT_KEYS

    for overlay, keys in PLACEMENT_KEYS.items():
        assert {k: v for k, v in draft_value[overlay].items() if k not in keys} == {
            k: v for k, v in seeded[overlay].items() if k not in keys}
        # The side handles really set every extent the script touched (each axis on its own; the Volume OSD has none
        # and this display has no OSD).
        if "text_width" in keys:
            assert all(draft_value[overlay][key] != seeded[overlay][key] for key in ("text_width", "text_height"))
    # Now Playing's parts moved and sized through the child editor are records of its child_geometry.
    assert set(draft_value["now_playing"]["child_geometry"]) == {"title", "artwork", "artist"}
    assert edit.owner.fullscreen_draft_pending and edit.flips == [True]

    assert edit.owner.cancel()
    _run(display, 120)
    assert _value(settings) == seeded                         # nothing written
    assert display.scene._visualizer_overlay_config == before_config
    assert edit.drawn() == before                             # the pre-Edit geometry, exactly
    assert edit.flips == [True, False]

    assert edit.start()
    _gesture(edit)
    _run(display, 120)
    assert edit.frames() == draft_frames and edit.owner._fullscreen.draft_value() == draft_value
    assert edit.owner.save()
    _run(display, 120)
    assert _value(settings) == draft_value                    # exactly the draft's placement
    # The committed value, projected the way the display manager publishes it, draws what the draft showed.
    display.scene.set_visualizer_expanded_overlay_config(_projection(_value(settings)))
    assert display.scene._visualizer_overlay_config == draft_config
    assert edit.drawn() == draft_frames
    assert edit.reloads == []


# ------------------------------------------------------------------------------ the ordinary layout is untouched


def _store(settings) -> str:
    """Every stored value but the overlays' one, canonically serialised."""
    from core.settings.fullscreen_overlays import FULLSCREEN_OVERLAYS_KEY

    snapshot = {}
    for key in sorted(settings.get_all_keys()):
        value = deepcopy(settings.get(key))
        if key == "widgets" and isinstance(value, dict):
            value.get("spotify_visualizer", {}).pop("fullscreen_overlays", None)
        elif key == "widgets.spotify_visualizer" and isinstance(value, dict):
            value.pop("fullscreen_overlays", None)
        elif key == FULLSCREEN_OVERLAYS_KEY or key.startswith(FULLSCREEN_OVERLAYS_KEY + "."):
            continue
        snapshot[key] = value
    return json.dumps(snapshot, sort_keys=True, default=repr)


def _seed_ordinary_layout(settings) -> None:
    from core.settings.layout_slots import save_layout_slot
    from rendering.custom_layout_contract import (
        CustomLayoutEntry, NormalizedRect, load_custom_layout_map, set_screen_layout_entry, write_custom_layout_map,
    )

    widgets = settings.get_widgets_map()
    custom = load_custom_layout_map(widgets)
    set_screen_layout_entry(custom, "TEST-DISPLAY", "clock", CustomLayoutEntry(
        widget_id="clock", geometry_variant="digital", rect=NormalizedRect(0.1, 0.2, 0.3, 0.15),
        size_payload={"resize_scale": 1.25}, resize_mode="uniform"))
    write_custom_layout_map(widgets, custom)
    assert save_layout_slot(widgets, "1")
    settings.set_widgets_map(widgets)
    settings.save()


@pytest.mark.qt
@pytest.mark.parametrize("ending", ["save", "cancel"])
def test_a_fullscreen_only_save_or_cancel_leaves_the_ordinary_layout_custom_and_slots_byte_identical(
        display, tmp_path, ending):
    settings = _manager(tmp_path)
    _seed_ordinary_layout(settings)
    seeded = _seed(settings)
    store = _store(settings)
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _gesture(edit)
    assert (edit.owner.save() if ending == "save" else edit.owner.cancel())
    assert _store(settings) == store
    assert (_value(settings) != seeded) is (ending == "save")


# ----------------------------------------------------------------------- the display manager's Edit entry


class _VisualizerOwner:
    """The Visualizer owner's route as the takeover coordinator drives it (records every viewport change)."""

    def __init__(self) -> None:
        self.controller = SimpleNamespace(mode_id="extruded_bubble", engine=SimpleNamespace(get_activation_id=lambda: 1))
        self.is_retired = False
        self.expanded_display = False
        self.expanded_display_transition_active = False
        self.expanded_display_fade_half_s = 0.25
        self.calls: list[tuple[bool, bool]] = []

    def set_expanded_display(self, expanded, *, animate=False, on_complete=None):
        self.calls.append((bool(expanded), bool(animate)))
        self.expanded_display = bool(expanded)
        if on_complete is not None:
            on_complete()
        return True


def _manager_host(display, settings):
    """A display manager stand-in carrying the real Edit entry, Save/Cancel and context-menu routes."""
    from engine.display_manager import DisplayManager
    from widgets.spotify_visualizer.expanded_display_coordinator import (
        ExpandedDisplayCoordinator,
        ExpandedDisplayServices,
    )

    edit = _Fullscreen(display, settings)
    visualizer = _VisualizerOwner()
    host = SimpleNamespace(
        _quick_custom_layout_owner=edit.owner, _quick_visualizer_unit=edit.unit, settings_manager=settings,
        authored_calls=[], menu_refreshes=[], published=[], settings_emits=[])
    host._visualizer_section = lambda: settings.get("widgets.spotify_visualizer")
    host._set_quick_authored_layout_enabled = lambda *a, **k: host.authored_calls.append((a, k))
    host._authored_layout_allowed_by_settings = lambda: True
    host._refresh_all_quick_context_menus = lambda: host.menu_refreshes.append(1)
    host._refresh_quick_visualizer_edit_content_envelope = lambda *a, **k: None
    host._publish_expanded_overlays = lambda: host.published.append(1)
    host.settings_requested = SimpleNamespace(emit=lambda: host.settings_emits.append(1))
    for name in ("_start_quick_custom_layout_session", "_start_fullscreen_overlay_edit", "_save_quick_custom_layout",
                 "cancel_custom_layout_session", "_fullscreen_edit_holds_draft", "_handle_quick_context_action"):
        setattr(host, name, getattr(DisplayManager, name).__get__(host))
    host._expanded_display_coordinator = ExpandedDisplayCoordinator(ExpandedDisplayServices(
        admitted_owner=lambda: visualizer,
        admitted_unit=lambda: edit.unit,
        requested=lambda: False,
        persist_requested=lambda _value: None,
        mode_capable=lambda _mode: True,
        edit_active=lambda: edit.owner.is_active,
        publish_glyph=lambda *_args: None,
    ))
    return host, edit, visualizer


def _expanded(host, visualizer):
    from core.expanded_visualizer_takeover import Phase

    coordinator = host._expanded_display_coordinator
    coordinator.generation_ready()
    assert coordinator.glyph_pressed(host._quick_visualizer_unit, True)
    assert coordinator.phase is Phase.EXPANDED and visualizer.calls == [(True, True)]
    return coordinator


@pytest.mark.qt
def test_entering_edit_on_the_expanded_view_opens_fullscreen_edit_without_a_collapse_transaction(display, tmp_path):
    from core.expanded_visualizer_takeover import Phase

    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    host, edit, visualizer = _manager_host(display, settings)
    coordinator = _expanded(host, visualizer)

    assert host._start_quick_custom_layout_session()
    assert visualizer.calls == [(True, True)]                 # no collapse reached the Visualizer owner
    assert coordinator.phase is Phase.EXPANDED and coordinator.fullscreen_edit
    assert edit.owner.is_fullscreen and host.authored_calls == []   # the ordinary layout was never quiesced
    assert display.scene.custom_layout_fullscreen and display.scene.visualizer_overlay_editing
    # The owner keeps publishing the display-wide presentation every frame: under Fullscreen Edit it stays drawn
    # (the Visualizer is not a session item, so CUSTOM never hides or re-places it).
    _expanded_card(display)
    _run(display, 60)
    root = display.scene._visualizer_root
    assert root.property("customLayoutWorkingVisible") is True and root.isVisible()

    # The context menu's Save is the one Save route: the takeover hears that Edit ended.
    assert host._handle_quick_context_action(edit.unit, "save_layout", "")
    assert not edit.owner.is_active and not coordinator.fullscreen_edit
    assert coordinator.phase is Phase.EXPANDED and visualizer.calls == [(True, True)]
    assert not display.scene.visualizer_overlay_editing

    # Edit again, then Cancel: still expanded, nothing collapsed.
    assert host._start_quick_custom_layout_session() and coordinator.fullscreen_edit
    assert host.cancel_custom_layout_session()
    assert not coordinator.fullscreen_edit and coordinator.phase is Phase.EXPANDED
    assert visualizer.calls == [(True, True)] and host.authored_calls == []


@pytest.mark.qt
def test_an_unsaved_draft_holds_settings_until_save_or_cancel(display, tmp_path):
    settings = _manager(tmp_path)
    seeded = _seed(settings)
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    host, edit, visualizer = _manager_host(display, settings)
    _expanded(host, visualizer)
    assert host._start_quick_custom_layout_session()

    # A clean draft: nothing to lose, Settings opens (the session ends without a write).
    assert host._handle_quick_context_action(edit.unit, "settings", "")
    assert host.settings_emits == [1] and not edit.owner.is_active and _value(settings) == seeded

    assert host._start_quick_custom_layout_session()
    edit.drag("preset", 90, 60)
    assert edit.owner.fullscreen_draft_pending and edit.flips[-1] is True
    assert host._handle_quick_context_action(edit.unit, "settings", "") is False
    assert host.settings_emits == [1] and edit.owner.is_fullscreen        # the draft and Edit stay
    assert _value(settings) == seeded                                      # nothing saved implicitly
    assert host.cancel_custom_layout_session()
    assert edit.flips[-1] is False


def test_the_menu_offers_settings_disabled_and_no_reset_under_a_fullscreen_draft():
    from rendering.quick.context_menu import build_quick_context_menu_entries

    def entries(**kwargs):
        rows = build_quick_context_menu_entries(
            transition_names=("Crossfade",), current_transition="Crossfade", random_enabled=False,
            random_selectable=True, visualizer_modes=(), current_visualizer="", visualizer_available=False,
            dimming_enabled=False, interaction_mode_enabled=False, interaction_mode_locked=False,
            edit_mode_active=True, **kwargs)
        return {row.action_id: row for row in rows if row.action_id}

    plain = entries()
    assert plain["settings"].enabled and "reset_layout" in plain
    held = entries(settings_available=False, layout_reset_available=False)
    assert held["settings"].enabled is False and "reset_layout" not in held
    assert {"save_layout", "cancel_layout"} <= set(held)


# ------------------------------------------------------------------------------------------- visibility


@pytest.mark.qt
def test_fullscreen_edit_shows_both_overlays_and_returns_them_to_their_authored_visibility_with_a_fade(
        display, tmp_path):
    settings = _manager(tmp_path)
    seeded = _seed(settings, preset={"always_show": True})
    _draw(display, media=None, config=_projection(seeded))      # no track: Now Playing has nothing yet
    _open(display)
    # Items are re-found at every read: a held wrapper can go stale across hidden hosts (address reuse).
    def presence(name: str) -> float:
        return float(_slot(display, name).property("presence"))

    preset, now_playing = SLOTS
    _settle(display, lambda: presence(preset) >= 1.0)
    assert presence(now_playing) == 0.0
    edit = _Fullscreen(display, settings)
    assert edit.start()
    # Both show to be grabbed, past every hold, Now Playing with its placeholder content.
    _shown_and_settled(display)
    _run(display, 700)
    assert presence(preset) >= 1.0 and presence(now_playing) >= 1.0
    assert _slot(display, now_playing).property("contentTitle")
    assert edit.frames() == edit.drawn()

    assert edit.owner.cancel()
    # Now Playing (event-only, nothing to show) fades out: gradually, never at once.
    samples = []
    _run(display, 80, lambda: samples.append(presence(now_playing)))
    assert samples and samples[0] > 0.0 and any(0.0 < sample < 1.0 for sample in samples)
    _settle(display, lambda: presence(now_playing) == 0.0)
    assert presence(preset) >= 1.0                            # Always Show stays up


@pytest.mark.qt
def test_the_frames_follow_a_content_change_during_fullscreen_edit(display, tmp_path):
    settings = _manager(tmp_path)
    media = _Media(title="Short")
    _draw(display, media=media, config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _run(display, 300)
    narrow = edit.item("now_playing").current_global_rect.width()
    media.update(title="A Considerably Longer Track Title Than Before")
    _settle(display, lambda: edit.item("now_playing").current_global_rect.width() > narrow + 40)
    _run(display, 200)
    assert edit.frames() == edit.drawn()
    edit.owner.cancel()


# ----------------------------------------------------------------------------- clear of the card's controls


@pytest.mark.qt
@pytest.mark.parametrize("target", ["top_right", "bottom_right"])
def test_overlays_moved_into_the_control_column_keep_clear_of_the_cards_controls(display, tmp_path, target):
    settings = _manager(tmp_path)
    seeded = _seed(settings, now_playing={"media_controls": True})
    _draw(display, media=_Media(), config=_projection(seeded))
    root = _root(display)
    root.setProperty("controlHintsAvailable", True)          # reserve the 3D hint's place too
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    dy = -HEIGHT if target.startswith("top") else HEIGHT
    for part in ("preset", "now_playing"):
        edit.drag(part, WIDTH, dy, steps=10)
    _run(display, 200)
    controls = _controls(root)
    for name in SLOTS:
        rect = _rect(_slot(display, name), root)
        assert rect.right() > root.width() * 0.75              # it really went into the right-hand column
        for control_name, control in controls.items():
            assert not rect.intersects(control), (target, name, control_name)
    # The draft stores the offset the overlay really took (the clamps included), never an intent beyond them.
    from rendering.quick.fullscreen_overlay_edit import offsets_for_position

    draft = edit.owner._fullscreen.draft_value()
    geometry = display.scene.expanded_overlay_edit_geometry()
    for overlay in ("preset", "now_playing"):
        slot = geometry["slots"][overlay]
        assert offsets_for_position(slot["pos"], slot["anchored"], (geometry["safe_width"], geometry["safe_height"]))             == (draft[overlay]["offset_x"], draft[overlay]["offset_y"]), overlay
    edit.owner.cancel()


# ------------------------------------------------------------------- single-axis sizing (ordinary side handles)


def _centred(edit: _Fullscreen) -> None:
    """Both overlays away from the safe area's edges, so every edge has room to move."""
    edit.drag("preset", 300, 200)
    edit.drag("now_playing", 320, -220)


SIDES = {"right": 90, "left": -90, "top": -60, "bottom": 60}


@pytest.mark.qt
@pytest.mark.parametrize("part", PARTS)
@pytest.mark.parametrize("handle", tuple(SIDES))
def test_a_side_handle_changes_only_its_own_axis(display, tmp_path, part, handle):
    """Ordinary Edit's single-axis content-extent semantics: a side strip changes one dimension and one extent member;
    the other dimension and member stay exactly; the opposite edge stays where it was. Now Playing's block is its
    artwork beside its text box: its side strips set the text box that makes the block that size."""
    from rendering.quick.fullscreen_overlay_edit import EXTENT_KEYS, SCALE_KEY

    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    before = QRect(edit.item(part).current_global_rect)
    payload = dict(edit.item(part).current_size_payload)

    edit.side(part, handle, SIDES[handle])
    _run(display, 60)
    after = edit.item(part).current_global_rect
    horizontal = handle in ("left", "right")
    grown, kept = ((after.width(), before.width()), (after.height(), before.height())) if horizontal else (
        (after.height(), before.height()), (after.width(), before.width()))
    assert grown[0] >= grown[1] + abs(SIDES[handle]) // 2, (before, after)     # its axis followed the drag
    assert kept[0] == kept[1], (before, after)                                   # the other axis did not move
    fixed = {"right": before.left() == after.left() and before.top() == after.top(),
             "left": before.right() == after.right() and before.top() == after.top(),
             "top": before.bottom() == after.bottom() and before.left() == after.left(),
             "bottom": before.top() == after.top() and before.left() == after.left()}
    assert fixed[handle], (before, after)
    changed, untouched = EXTENT_KEYS[part] if horizontal else EXTENT_KEYS[part][::-1]
    now = edit.item(part).current_size_payload
    assert now[changed] != payload[changed]
    assert now[untouched] == payload[untouched] and now[SCALE_KEY[part]] == payload[SCALE_KEY[part]]
    assert edit.frames() == edit.drawn()
    edit.owner.cancel()


@pytest.mark.qt
def test_a_set_extent_reflows_the_text_and_crops_the_artwork(display, tmp_path):
    """A narrower text box elides; a taller one gives the text more lines (it wraps); a non-square artwork frame (the
    artwork sized on one axis as Now Playing's child) crops the image into it (the ordinary freeform artwork frame)."""
    settings = _manager(tmp_path)
    _draw(display, media=_Media(title="A Longer Track Title"),
          preset="A Longer Preset Name", config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    layer = _root(display)

    def main(name: str):
        holder = layer.findChild(QQuickItem, name)
        return next(child for child in _visual_items(holder) if child.objectName() == "shadowedTextMain")

    preset, title = main("expandedOverlayPresetText"), main("expandedOverlayTitle")
    assert not preset.property("truncated") and int(preset.property("lineCount")) == 1
    edit.side("preset", "right", -WIDTH)                       # as narrow as it draws: it elides
    _run(display, 60)
    assert preset.property("truncated") and int(preset.property("lineCount")) == 1
    edit.side("preset", "bottom", 120)                         # taller: the name wraps onto more lines
    _run(display, 60)
    assert int(preset.property("lineCount")) >= 2

    assert int(title.property("lineCount")) == 1
    edit.side("now_playing", "right", -WIDTH)
    _run(display, 60)
    assert title.property("truncated")
    art_item = layer.findChild(QQuickItem, "expandedOverlayArtwork")
    artwork_before = (art_item.width(), art_item.height())
    edit.side("now_playing", "top", -140)                       # the title gets the extra lines, the artwork stays
    _run(display, 60)
    assert int(title.property("lineCount")) >= 2
    assert (art_item.width(), art_item.height()) == artwork_before

    edit.open_children()
    edit.child_resize("artwork", "right", 80)
    _run(display, 60)
    assert art_item.width() > art_item.height()
    image = layer.findChild(QQuickItem, "expandedOverlayArtworkImage")
    assert int(image.property("fillMode")) == 2                 # Image.PreserveAspectCrop: never distorted
    assert edit.frames() == edit.drawn()
    edit.owner.cancel()


@pytest.mark.qt
@pytest.mark.parametrize("controls", [False, True])
def test_the_artist_line_follows_the_text_box_in_the_draft_and_after_save(display, tmp_path, controls):
    """Operator, 8 Nov (live): the X/Y side handles on Now Playing did not move the artist line with the box (the
    rows stayed bunched in its middle: a stale gap above and below). Every box the side handles make draws the title
    at the box's top and the last row (the artist, or the Media Controls) at its bottom, the artist always below the
    title and never overlapping it; Save keeps exactly what the draft showed."""
    settings = _manager(tmp_path)
    _draw(display, media=_Media(title="A Considerably Longer Track Title", artist="Some Artist With A Long Name"),
          config=_projection(_seed(settings, now_playing={"media_controls": controls, "always_show": True})))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    root = _root(display)
    names = ("expandedOverlayNowPlayingText", "expandedOverlayTitle", "expandedOverlayArtist",
             "expandedOverlayMediaControls")

    def rows() -> dict[str, QRectF]:
        _run(display, 60)
        return {name: _rect(root.findChild(QQuickItem, name), root) for name in names}

    def check(label: str) -> dict[str, QRectF]:
        drawn = rows()
        box, title, artist = (drawn[name] for name in names[:3])
        last = drawn["expandedOverlayMediaControls"] if controls else artist
        assert abs(title.top() - box.top()) <= 1.0, label
        assert abs(last.bottom() - box.bottom()) <= 1.0, (label, last.bottom(), box.bottom())
        assert artist.top() >= title.bottom() - 0.5, label                 # below the title, never over it
        if controls:
            assert drawn["expandedOverlayMediaControls"].top() >= artist.bottom() - 0.5, label
        return drawn

    for handle, delta in (("bottom", 90), ("right", -120), ("top", -60), ("right", 260), ("bottom", -50)):
        edit.side("now_playing", handle, delta)
        check(f"{handle} {delta}")
    draft = check("draft")
    assert edit.owner.save()
    _run(display, 300)
    saved = rows()
    assert {name: saved[name].getRect() for name in names} == {name: draft[name].getRect() for name in names}


@pytest.mark.qt
def test_a_side_change_undoes_exactly_and_restore_size_returns_the_natural_box(display, tmp_path):
    from core.settings.fullscreen_overlays import canonical_fullscreen_overlays
    from rendering.quick.fullscreen_overlay_edit import EXTENT_KEYS

    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    before = (edit.frames(), {part: dict(edit.item(part).current_size_payload) for part in PARTS})
    edit.side("now_playing", "left", -80)
    _run(display, 60)
    assert edit.frames() != before[0]
    assert edit.owner.undo_last_change()                        # Ctrl+Z: one step, exactly back
    _run(display, 60)
    assert (edit.frames(), {part: dict(edit.item(part).current_size_payload) for part in PARTS}) == before

    canonical = canonical_fullscreen_overlays()
    art_item = _root(display).findChild(QQuickItem, "expandedOverlayArtwork")
    art_before = (art_item.width(), art_item.height())
    for part, handle in (("preset", "right"), ("preset", "bottom"), ("now_playing", "bottom")):
        edit.side(part, handle, 60)
    edit.open_children()
    edit.child_resize("artwork", "bottom", 30)
    assert (art_item.width(), art_item.height()) != art_before
    for part in PARTS:
        assert edit.model.restoreSize(edit.row(part))
        for key in EXTENT_KEYS[part]:
            assert edit.item(part).current_size_payload[key] == canonical[part][key], (part, key)
    # Ordinary Restore Size also restores the authored child geometry: the records and the carrier together.
    assert edit.item("now_playing").current_child_sizes == {}
    assert not edit.item("now_playing").current_size_payload.get("child_geometry")
    _run(display, 60)
    assert edit.frames()["preset"][2:] == before[0]["preset"][2:]
    assert edit.frames()["now_playing"][2:] == before[0]["now_playing"][2:]
    assert (art_item.width(), art_item.height()) == art_before
    edit.owner.cancel()


@pytest.mark.qt
def test_a_uniform_scale_keeps_the_box_its_extents_are_font_relative(display, tmp_path):
    """Ordinary Edit's uniform scale keeps the content box; here the box is in ems, so the wheel grows it whole."""
    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    edit.side("preset", "right", 120)
    edit.side("preset", "bottom", 70)
    payload = dict(edit.item("preset").current_size_payload)
    _, _, width, height = edit.frames()["preset"]
    edit.wheel("preset", 4)
    _run(display, 60)
    grown = edit.item("preset").current_size_payload
    assert (grown["text_width"], grown["text_height"]) == (payload["text_width"], payload["text_height"])
    assert grown["scale"] > payload["scale"]
    _, _, new_width, new_height = edit.frames()["preset"]
    assert new_width > width and new_height > height
    assert new_width / new_height == pytest.approx(width / height, rel=0.03)
    edit.owner.cancel()


# --------------------------------------------------------- Rotate Widget Content on the expanded card (operator)


class _Visualizer:
    """The Visualizer owner surface Fullscreen Edit reads and calls: the controller's mode, policy, committed world and
    orientation map, the ordinary card's record and the live promotion (recorded). The production owner's side of
    the same calls is proven by ``test_the_production_owner_draws_promotes_and_restores_a_turn_while_expanded``."""

    def __init__(self, mode: str, ordinary, rotations: dict | None = None) -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy

        self.controller = SimpleNamespace(
            mode_id=mode, presentation_policy=get_visualizer_presentation_policy(mode),
            committed_viewport_extent=tuple(ordinary.viewport_extent),
            committed_content_rotations=dict(rotations or {}))
        self.ordinary_presentation = ordinary
        self.promoted: list[dict] = []

    def commit_live_custom_layout(self, **kwargs) -> None:
        self.promoted.append(kwargs)


def _ordinary_card(mode: str = "spectrum"):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests.test_visualizer_expansion_overlays import CHROME
    from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

    return resolve_visualizer_presentation(policy=get_visualizer_presentation_policy(mode), display_size=(WIDTH, HEIGHT),
                                           outer_origin=(30.0, 400.0), **CHROME)


def _visualizer_entry(settings, screen, mode: str = "spectrum"):
    from rendering.quick.custom_layout_hydration import resolve_visualizer_custom_entry

    return resolve_visualizer_custom_entry(settings.get_widgets_map(), screen, mode)


@pytest.mark.qt
@pytest.mark.parametrize("mode", ["spectrum", "waveform_ribbon"])
def test_the_expanded_card_offers_rotate_widget_content_through_the_one_edit_session(display, tmp_path, mode):
    """Ordinary Edit's Visualizer frame offers Rotate Widget Content for a mode that turns its content; Fullscreen
    Edit's expanded card does too: the same glyph and ``rotateContent`` route, one undo step per turn, the draft
    orientation previewed through the Visualizer's viewport/orientation seam, Cancel restoring exactly (nothing
    written) and Save writing the turn where every Edit writes it (the Visualizer's CUSTOM entry, at its unchanged
    ordinary rect) and promoting it live."""
    from widgets.spotify_visualizer.presentation_orientation import normalize_content_rotation_by_mode

    settings = _manager(tmp_path)
    seeded = _seed(settings)
    store = _store(settings)
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    ordinary = _ordinary_card()
    visualizer = _Visualizer(mode, ordinary)
    edit = _Fullscreen(display, settings, visualizer)
    published: list[tuple] = []
    display.scene.set_visualizer_viewport_config_sink(
        lambda extent, state: published.append((extent, normalize_content_rotation_by_mode(state))))
    try:
        assert edit.start()
        _shown_and_settled(display)
        extent = tuple(ordinary.viewport_extent)
        # The card is the session's first item (its frame lies under the overlays' frames), offering only the turn.
        assert edit.row("visualizer") == 0
        layer = display.scene.custom_layout_overlay.item
        chrome = {item.objectName(): item for item in _visual_items(layer)}
        rotate = chrome["customLayoutRotateContent-fullscreen_overlay.visualizer"]
        assert rotate.isVisible()
        # The card's frame takes no press: the background stays Edit's (its double-click Saves).
        assert chrome["customLayoutParentMoveArea-fullscreen_overlay.visualizer"].property("enabled") is False
        assert not chrome["customLayoutRestoreSize-fullscreen_overlay.visualizer"].isVisible()
        corner = chrome.get("customLayoutResize-fullscreen_overlay.visualizer-bottom_right")
        assert corner is None or not corner.isVisible()                # never sized
        # It sits in the card's own bottom-right glyph row: the card's baseline and glyph size, at the row's far
        # corner here (the card offers no other member under Edit); test_visualizer_glyph_row.py has the full row.
        root = _root(display)
        glyph = rotate.mapRectToItem(layer, QRectF(0.0, 0.0, rotate.width(), rotate.height()))
        corner = root.mapToItem(layer, QPointF(float(root.property("glyphRowRight")),
                                               float(root.property("glyphRowBottom"))))
        assert abs(glyph.bottom() - corner.y()) < 0.5 and abs(glyph.right() - corner.x()) < 0.5
        assert abs(glyph.width() - float(root.property("glyphSize")) * float(root.property("glyphRowScale"))) < 0.5
        # A clean draft publishes nothing to the Visualizer (its committed orientation stays the authority).
        assert all(extent_ is None for extent_, _state in published)

        card = edit.row("visualizer")
        assert edit.model.rotateContent(card)
        assert published[-1] == (extent, {mode: 1})          # the expanded card previews the turn
        assert edit.owner.fullscreen_draft_pending and edit.flips == [True]
        assert edit.owner.undo_last_change()                         # one step, exactly back
        assert published[-1] == (None, {}) and not edit.owner.fullscreen_draft_pending   # committed truth again
        assert edit.model.rotateContent(card) and edit.model.rotateContent(card)
        assert published[-1] == (extent, {mode: 2})
        assert edit.owner.cancel()
        assert published[-1] == (None, {})                           # the preview retired: committed truth again
        assert _store(settings) == store and visualizer.promoted == []

        # A Save without a turn writes nothing but the overlays' value (the ordinary layout stays byte-identical).
        assert edit.start()
        edit.drag("preset", 40, 30)
        assert edit.owner.save()
        assert _store(settings) == store and visualizer.promoted == []

        assert edit.start()
        binding = next(iter(edit.owner._bindings.values()))
        assert edit.model.rotateContent(edit.row("visualizer"))
        assert edit.owner.save()
        entry = _visualizer_entry(settings, binding.screen)
        assert entry is not None
        assert normalize_content_rotation_by_mode(entry.size_payload.get("content_rotation_quarters_by_mode")) == {
            mode: 1}
        from rendering.quick.custom_layout_hydration import resolve_committed_visualizer_rect

        saved = resolve_committed_visualizer_rect(entry, binding.geometry.size())
        x, y, width, height = ordinary.outer_rect
        assert saved.getRect() == (round(x), round(y), round(width), round(height))   # the card's rect, unchanged
        assert visualizer.promoted == [{"local_rect": (float(round(x)), float(round(y)), float(round(width)),
                                                       float(round(height))),
                                        "viewport_extent": extent, "content_rotation_by_mode": {mode: 1}}]
        assert published[-1] == (None, {}) and edit.reloads == []
    finally:
        if edit.owner.is_active:
            edit.owner.cancel()
        display.scene.set_visualizer_viewport_config_sink(None)


@pytest.mark.qt
def test_a_mode_that_cannot_turn_its_content_gets_no_rotate_glyph(display, tmp_path):
    """As on the ordinary Visualizer frame: no turn for a mode whose content does not turn (a framed 3D mode)."""
    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings, _Visualizer("sphere", _ordinary_card("sphere")))
    assert edit.start()
    assert {item.model_identity for item in edit.model._items} == {f"fullscreen_overlay.{p}" for p in PARTS}
    edit.owner.cancel()


@pytest.mark.qt
@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_the_production_owner_previews_saves_and_cancels_a_turn_while_expanded(qt_app, tmp_path, mode):
    """End to end on the production Visualizer owner (an unshown runtime, never shown): Fullscreen Edit's card turn
    reaches the owner through the scene's viewport/orientation seam, so the drawn display-wide card turns (same card
    rect) while nothing is committed; Cancel returns the committed orientation exactly; Save writes the turn into the
    Visualizer's CUSTOM entry and the live promotion (validated against the ordinary record, since the scene draws
    the display-wide one) commits it, so it stays after Edit ends and the collapsed card shows it at its own rect."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.custom_layout_hydration import resolve_committed_visualizer_rect
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import make_visualizer_owner
    from widgets.spotify_visualizer.presentation_orientation import normalize_content_rotation_by_mode

    descriptor = get_visualizer_mode_descriptor(mode)
    fullscreen = descriptor.supports_expanded_display
    settings = _manager(tmp_path)
    _seed(settings)
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=778, screen=qt_app.primaryScreen(),
                                  scene_factory=factory,
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    owner = make_visualizer_owner(runtime, bar_count=32, initial_mode=mode)
    controller = owner.controller
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    apply_presentation_vis_mode_kwargs(controller.presentation_state, frozen_visualizer_settings(mode))
    unit = SimpleNamespace(is_retired=False, screen_index=0, presenter=SimpleNamespace(bound_widget_ids=()),
                           runtime=runtime)
    edit = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
                                  visualizer_provider=lambda: (owner, unit), reload_request=lambda _reason: None)
    scene = runtime.scene_controller

    def drawn():
        owner._reapply_route()           # one publication edge (no logical runtime runs here)
        qt_app.processEvents()
        return scene.visualizer_item.presentation

    def turn() -> None:
        model = scene.custom_layout_overlay.model
        identity = "fullscreen_overlay.visualizer" if fullscreen else "spotify_visualizer"
        row = next(index for index, item in enumerate(model._items)
                   if item.model_identity == identity)
        qt_app.processEvents()
        glyph = next(item for item in _visual_items(scene.custom_layout_overlay.item)
                     if item.objectName() == f"customLayoutRotateContent-{identity}")
        assert glyph.isVisible()
        assert model.rotateContent(row)

    try:
        owner.bind(engine_generation=1, activation_id=1)
        ordinary = drawn()
        extent = controller.committed_viewport_extent
        if fullscreen:
            assert owner.set_expanded_display(True)
        expanded = drawn()
        assert (expanded.outer_rect != ordinary.outer_rect) is fullscreen
        assert expanded.content_rotation_quarters == 0
        scene.set_visualizer_startup_reveal_opacity(1.0)

        if mode == "sphere":
            assert edit.start()
            model = scene.custom_layout_overlay.model
            row = next(index for index, item in enumerate(model._items) if item.model_identity == "spotify_visualizer")
            assert not model._items[row].content_rotation_capable
            qt_app.processEvents()
            glyph = next(item for item in _visual_items(scene.custom_layout_overlay.item)
                         if item.objectName() == "customLayoutRotateContent-spotify_visualizer")
            assert not glyph.isVisible()
            assert model.rotateContent(row) is False
            assert drawn().content_rotation_quarters == 0
            assert edit.cancel()
            return

        def start_edit():
            return edit.start_fullscreen(unit, _value(settings)) if fullscreen else edit.start()

        # Turn, then Cancel: the display-wide card turns in place, nothing is committed; Cancel restores it exactly.
        assert start_edit()
        turn()
        turned = drawn()
        assert turned.content_rotation_quarters == 1 and turned.outer_rect == expanded.outer_rect
        assert owner.ordinary_presentation.outer_rect == ordinary.outer_rect
        assert controller.committed_content_rotation_quarters == 0
        assert edit.cancel()
        assert drawn() == expanded and controller.committed_content_rotation_quarters == 0

        # Turn, then Save: written into the Visualizer's CUSTOM entry at the card's own rect, promoted live.
        assert start_edit()
        binding = next(iter(edit._bindings.values()))
        turn()
        drawn()
        owner._started = True            # the live promotion's liveness gate (no logical runtime is started here)
        assert edit.save()
        assert controller.committed_content_rotation_quarters == 1
        assert drawn().content_rotation_quarters == 1
        entry = _visualizer_entry(settings, binding.screen, mode)
        assert normalize_content_rotation_by_mode(entry.size_payload.get("content_rotation_quarters_by_mode")) == {
            mode: 1}
        saved = resolve_committed_visualizer_rect(entry, binding.geometry.size())
        assert all(abs(a - b) <= 0.5 for a, b in zip(saved.getRect(), ordinary.outer_rect))
        # Collapsing shows the ordinary card turned, at its own rect.
        if fullscreen:
            assert owner.set_expanded_display(False)
        collapsed = drawn()
        assert collapsed.content_rotation_quarters == 1 and collapsed.outer_rect == ordinary.outer_rect
    finally:
        if edit.is_active:
            edit.cancel()
        owner._started = False
        owner.retire()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


# ----------------------------------------------------------------------- the Volume OSD (operator, 8 Nov, live)


def _volume_osd(display, rect=(560.0, 600.0, 320.0, 60.0)):
    """A Volume OSD on the hidden display, as the family binder creates it (its ordinary rectangle ``rect``)."""
    from rendering.quick.widgets.host import OverlayWidgetGeometry
    from rendering.quick.widgets.system_audio_osd import (
        RetainedSystemAudioOSDPresentation,
        SystemAudioOSDConfig,
        SystemAudioOSDPresentationModel,
    )

    model = SystemAudioOSDPresentationModel(SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": {}}),
                                            runtime_generation=1)
    return RetainedSystemAudioOSDPresentation(host=display.scene.ordinary_widget_host, model=model,
                                              geometry=OverlayWidgetGeometry(*rect))


def _osd_rect(osd) -> tuple[float, float, float, float]:
    item = osd.item
    return (item.x(), item.y(), item.width(), item.height())


@pytest.mark.qt
def test_the_volume_osd_is_moved_and_sized_in_fullscreen_edit_and_keeps_its_ordinary_place(display, tmp_path):
    """Operator, 8 Nov (live): the Volume OSD shows during Fullscreen Edit but could not be moved or sized there. It is
    a part of the same session (its frame, a move with snapping and one undo step, corner scaling, no side strips);
    Save writes its placement over the expanded card (``volume_osd``, mirroring the overlays' model), the expanded
    card draws it there, and its ordinary placement is never touched: collapsing returns it exactly."""
    settings = _manager(tmp_path)
    seeded = _seed(settings)
    store = _store(settings)
    osd = _volume_osd(display)
    ordinary = _osd_rect(osd)
    try:
        _draw(display, media=_Media(), config=_projection(seeded))
        _open(display)
        _run(display, 60)
        assert _osd_rect(osd) == ordinary                       # a zero offset and unit scale: exactly its place
        edit = _Fullscreen(display, settings)
        assert edit.start()
        _shown_and_settled(display)
        assert edit.row("volume_osd") >= 0
        layer = display.scene.custom_layout_overlay.item
        frames = {item.objectName(): item for item in _visual_items(layer)}
        assert frames["customLayoutEditFrame-fullscreen_overlay.volume_osd"].isVisible()
        assert frames["customLayoutResize-fullscreen_overlay.volume_osd-bottom_right"].isVisible()
        strip = frames.get("customLayoutViewportEdge-fullscreen_overlay.volume_osd-right")
        assert strip is None or not strip.isVisible()            # no single-axis extents
        assert float(osd.item.property("fadeOpacity")) > 0.0 or osd.item.property("customLayoutInputBlocked")

        before = QRect(edit.item("volume_osd").current_global_rect)
        edit.drag("volume_osd", -260, -300)
        _run(display, 60)
        moved = QRect(edit.item("volume_osd").current_global_rect)
        assert moved.topLeft() != before.topLeft() and moved.size() == before.size()
        assert edit.owner.undo_last_change()                     # one step, exactly back
        _run(display, 60)
        assert edit.item("volume_osd").current_global_rect == before
        edit.drag("volume_osd", -260, -300)
        edit.corner("volume_osd", "bottom_right", 80, 30)       # grows; the opposite corner stays
        _run(display, 60)
        grown = QRect(edit.item("volume_osd").current_global_rect)
        assert grown.width() > moved.width() and abs(grown.x() - moved.x()) <= 1 and abs(grown.y() - moved.y()) <= 1
        drawn = _osd_rect(osd)
        draft = edit.owner._fullscreen.draft_value()["volume_osd"]
        assert draft["offset_x"] != 0.0 and draft["offset_y"] != 0.0 and draft["scale"] > 1.0

        assert edit.owner.save()
        _run(display, 120)
        assert _value(settings)["volume_osd"] == draft
        assert _store(settings) == store                         # the ordinary layout (CUSTOM) is untouched
        display.scene.set_visualizer_expanded_overlay_config(_projection(_value(settings)))
        assert _osd_rect(osd) == drawn                           # the committed value draws what the draft showed
        authored = display.scene.ordinary_widget_host.presentation_for_model_identity(
            "system_audio_osd").authored_geometry
        assert (authored.x, authored.y, authored.width, authored.height) == ordinary   # its layout's own rectangle

        display.scene.set_visualizer_expanded_overlays_drawn(False)   # collapsing: back to its ordinary place
        _run(display, 60)
        assert _osd_rect(osd) == ordinary
        display.scene.set_visualizer_expanded_overlays_drawn(True)
        _run(display, 60)
        assert _osd_rect(osd) == drawn
    finally:
        if edit.owner.is_active:
            edit.owner.cancel()
        display.scene.set_visualizer_overlay_media_model(None)
        osd.retire()


# ------------------------------------------------------------- the text block drags (operator, 8 Nov, live)


def _pointer_drag(display, edit: _Fullscreen, part: str, dx: int, dy: int, *, steps: int = 8) -> str:
    """Drag ``part`` by its middle through the window as the operator does (press, moves, release on the Edit layer);
    returns the name of the item that took the press."""
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    rect = edit._local(edit.item(part).current_global_rect)
    start = QPointF(rect.x() + rect.width() * 0.4, rect.center().y())

    def send(kind, point: QPointF, button, buttons) -> None:
        QCoreApplication.sendEvent(display.window, QMouseEvent(kind, point, point, point, button, buttons,
                                                               Qt.KeyboardModifier.NoModifier))
        _run(display, 1)

    send(QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    grabber = display.window.mouseGrabberItem()
    for step in range(1, steps + 1):
        send(QEvent.Type.MouseMove, start + QPointF(dx * step / steps, dy * step / steps), Qt.MouseButton.NoButton,
             Qt.MouseButton.LeftButton)
    send(QEvent.Type.MouseButtonRelease, start + QPointF(dx, dy), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
    return grabber.objectName() if grabber is not None else ""


@pytest.mark.qt
@pytest.mark.parametrize("controls", [False, True])
def test_dragging_now_playings_text_moves_it_through_the_edit_layer(display, tmp_path, controls):
    """Operator, 8 Nov (live): "the metadata text cannot be moved". A drag on Now Playing's text block, delivered to
    the window as real pointer events, is taken by its Edit frame (the block's, while its child lock is closed) and
    moves Now Playing as one (artwork and text), publishes snapping guides while it runs, is one undo step, and Save
    keeps where it was dropped."""
    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings, now_playing={"media_controls": controls})))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    root = _root(display)

    def parts() -> tuple[QRect, QRect]:
        return tuple(_rect(root.findChild(QQuickItem, name), root).toRect()
                     for name in ("expandedOverlayNowPlayingText", "expandedOverlayArtwork"))

    block = QRect(edit.item("now_playing").current_global_rect)
    text, artwork = parts()
    guides: list[tuple] = []
    original = display.scene.set_custom_layout_guides
    display.scene.set_custom_layout_guides = lambda **kw: guides.append(kw) or original(**kw)
    try:
        taker = _pointer_drag(display, edit, "now_playing", 240, -200)
    finally:
        display.scene.set_custom_layout_guides = original
    assert taker == "customLayoutParentMoveArea-fullscreen_overlay.now_playing"
    _run(display, 30)
    moved_text, moved_art = parts()
    delta = moved_text.topLeft() - text.topLeft()
    assert abs(delta.x() - 240) <= 12 and abs(delta.y() + 200) <= 12     # it followed the pointer (snaps allowed)
    art_delta = moved_art.topLeft() - artwork.topLeft()                   # the artwork moved with it, as one
    assert abs(art_delta.x() - delta.x()) <= 1 and abs(art_delta.y() - delta.y()) <= 1
    assert guides                                                         # the move published its guides
    assert edit.frames() == edit.drawn()
    assert edit.owner.undo_last_change()
    _run(display, 60)
    assert edit.item("now_playing").current_global_rect == block
    _pointer_drag(display, edit, "now_playing", 240, -200)
    dropped = edit.frames()
    assert edit.owner.save()
    _run(display, 120)
    display.scene.set_visualizer_expanded_overlay_config(_projection(_value(settings)))
    assert edit.drawn() == dropped


# ------------------------------------------------- Now Playing's parts as the block's children (operator, 8 Nov)


def _send(display, kind, point: QPointF, button, buttons) -> None:
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QMouseEvent

    QCoreApplication.sendEvent(display.window, QMouseEvent(kind, point, point, point, button, buttons,
                                                           Qt.KeyboardModifier.NoModifier))
    _run(display, 1)


def _scene_point(item, fx: float = 0.5, fy: float = 0.5) -> QPointF:
    return item.mapToScene(QPointF(item.width() * fx, item.height() * fy))


def _real_drag(display, start: QPointF, dx: float, dy: float, *, steps: int = 8) -> str:
    """Press at ``start``, move by (dx, dy) in steps, release: real pointer events through the window. Returns the
    name of the item that took the press."""
    from PySide6.QtCore import QEvent, Qt

    _send(display, QEvent.Type.MouseMove, start, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton)
    _send(display, QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    grabber = display.window.mouseGrabberItem()
    for step in range(1, steps + 1):
        _send(display, QEvent.Type.MouseMove, start + QPointF(dx * step / steps, dy * step / steps),
              Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
    _send(display, QEvent.Type.MouseButtonRelease, start + QPointF(dx, dy), Qt.MouseButton.LeftButton,
          Qt.MouseButton.NoButton)
    _run(display, 40)
    return grabber.objectName() if grabber is not None else ""


def _real_click(display, point: QPointF) -> str:
    return _real_drag(display, point, 0.0, 0.0, steps=1)


NP_PARTS = {"artwork": "expandedOverlayArtwork", "title": "expandedOverlayTitle", "artist": "expandedOverlayArtist",
            "controls": "expandedOverlayMediaControls"}


def _np_parts(display) -> dict[str, QRect]:
    """Now Playing's parts as drawn (scene rectangles, transforms included)."""
    root = _root(display)
    return {role: _rect(root.findChild(QQuickItem, name), root).toRect() for role, name in NP_PARTS.items()}


def _room(edit: _Fullscreen) -> None:
    """Make room in Now Playing's block with its own side handles (wider and taller than its content)."""
    edit.side("now_playing", "right", 160)
    edit.side("now_playing", "bottom", 70)
    _run(edit.display, 60)


def _open_children_by_pointer(display, edit: _Fullscreen) -> None:
    """As the operator does it: click the block (it is selected), rest the pointer on it until its Edit glyphs show,
    click its child lock."""
    from PySide6.QtCore import QEvent, Qt

    frame = edit.layer_item(f"customLayoutEditFrame-{BLOCK}")
    _real_click(display, _scene_point(frame, 0.5, 0.15))
    assert edit.model.data(edit.model.index(edit.row("now_playing"), 0), edit.model._SELECTED_FOR_CHILD_EDIT_ROLE)
    lock = edit.layer_item(f"customLayoutChildEditLock-{BLOCK}")
    assert lock is not None and lock.isVisible()
    _send(display, QEvent.Type.MouseMove, _scene_point(frame, 0.5, 0.5), Qt.MouseButton.NoButton,
          Qt.MouseButton.NoButton)
    _settle(display, lambda: float(lock.opacity()) > 0.5)
    assert frame.property("childEditingLocked") is True
    _real_click(display, _scene_point(lock))
    assert frame.property("childEditingLocked") is False
    _run(display, 200)                                     # the child layer's own short fade-in


@pytest.mark.qt
@pytest.mark.parametrize("card", [False, True])
def test_now_playings_parts_move_and_size_inside_the_block_through_the_child_editor(display, tmp_path, card):
    """Operator, 8 Nov: "allow movement within the block that is not drawn like we already do for child elements in
    normal geometry. I should be able to move every element around in that block and change it." With real pointer
    events through the window: the block is selected and its child lock opened as on any widget; the title, the
    artist line and the Media Controls bar move on their own and the artwork sizes on one axis, each through ordinary
    Edit's child editor (its move areas and side strips); the block's frame and the other parts stay put; a part
    cannot leave the block; each gesture is one undo step; Save commits what the draft showed and Cancel restores
    exactly. Decided: with a block surface (Card) the parts stay editable inside it, as a widget card's children."""
    settings = _manager(tmp_path)
    seeded = _seed(settings, now_playing={"media_controls": True, "card": card})
    _draw(display, media=_Media(title="A Track Title", artist="An Artist"), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    authored = _np_parts(display)
    _centred(edit)
    _run(display, 60)
    # The block is as large as its content until its own side handles make room; the parts then move inside it.
    _room(edit)
    block = QRect(edit.item("now_playing").current_global_rect)
    _open_children_by_pointer(display, edit)
    for role in NP_PARTS:
        assert edit.child_frame(role).isVisible(), role

    def moved(role: str, dx: int, dy: int) -> None:
        area = edit.layer_item(f"customLayoutChildMoveArea-{BLOCK}-{role}")
        before = _np_parts(display)
        taker = _real_drag(display, _scene_point(area), dx, dy)
        assert taker == f"customLayoutChildMoveArea-{BLOCK}-{role}", taker
        after = _np_parts(display)
        shift = after[role].topLeft() - before[role].topLeft()
        assert abs(shift.x() - dx) <= 12 and abs(shift.y() - dy) <= 12, (role, shift)  # followed (gentle snaps)
        assert after[role].size() == before[role].size()
        assert all(after[other] == before[other] for other in NP_PARTS if other != role), role
        assert edit.item("now_playing").current_global_rect == block                 # the block stays put

    moved("title", 34, 18)
    moved("artist", 26, -10)
    moved("controls", 30, -8)
    # The artwork's right side strip: one axis, from its own place (the image crops into the frame).
    strip = edit.layer_item(f"customLayoutChildResizeEdge-{BLOCK}-artwork-right")
    before = _np_parts(display)
    taker = _real_drag(display, _scene_point(strip), -24, 0)
    assert taker == f"customLayoutChildResizeEdge-{BLOCK}-artwork-right"
    art = _np_parts(display)["artwork"]
    assert abs(art.width() - (before["artwork"].width() - 24)) <= 3 and art.height() == before["artwork"].height()
    assert art.topLeft() == before["artwork"].topLeft()
    assert edit.item("now_playing").current_global_rect == block

    records = edit.item("now_playing").current_size_payload["child_geometry"]
    assert set(records) == set(NP_PARTS)
    assert edit.owner.fullscreen_draft_pending and edit.flips[-1] is True
    # A part never leaves the block (ordinary Edit's containment), card padding included.
    area = edit.layer_item(f"customLayoutChildMoveArea-{BLOCK}-title")
    _real_drag(display, _scene_point(area), 3 * WIDTH, 3 * HEIGHT)
    title = _np_parts(display)["title"]
    slot = _rect(_slot(display, "expandedOverlayNowPlaying"), _root(display)).toRect()
    assert slot.adjusted(-1, -1, 1, 1).contains(title), (slot, title)
    # One undo step per gesture: the containment drag comes back exactly.
    contained = _np_parts(display)
    assert edit.owner.undo_last_change()
    _run(display, 60)
    undone = _np_parts(display)
    assert undone != contained and undone["title"] != contained["title"]
    draft_parts, draft_value = _np_parts(display), edit.owner._fullscreen.draft_value()

    # Cancel: exactly the layout before Edit, nothing written.
    assert edit.owner.cancel()
    _run(display, 120)
    assert _value(settings) == seeded and _np_parts(display) == authored

    # Save (the same gestures again): the committed value draws exactly what the draft showed.
    assert edit.start()
    _shown_and_settled(display)
    _centred(edit)
    _run(display, 60)
    _room(edit)
    _open_children_by_pointer(display, edit)
    moved("title", 34, 18)
    moved("artist", 26, -10)
    moved("controls", 30, -8)
    _real_drag(display, _scene_point(edit.layer_item(f"customLayoutChildResizeEdge-{BLOCK}-artwork-right")), -24, 0)
    assert _np_parts(display) == draft_parts
    assert edit.owner.save()
    _run(display, 120)
    saved = _value(settings)
    assert saved["now_playing"]["child_geometry"] == draft_value["now_playing"]["child_geometry"]
    display.scene.set_visualizer_expanded_overlay_config(_projection(saved))
    _run(display, 300)
    assert _np_parts(display) == draft_parts


@pytest.mark.qt
def test_the_block_offers_no_child_editing_to_the_preset_toast_and_the_parts_follow_the_blocks_scale(
        display, tmp_path):
    """The toast has no parts (no child lock). A part's edit alone makes the draft pending (Settings is held, Save or
    Cancel resolves it). Now Playing's parts keep their places relative to the block when the block is scaled (their
    offsets are in ems of its font)."""
    settings = _manager(tmp_path)
    # Test-owned room in the block (its own text box extents), so the parts have somewhere to go.
    seeded = _seed(settings, now_playing={"media_controls": True, "text_width": 9.0, "text_height": 5.0})
    _draw(display, media=_Media(), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    _run(display, 60)
    assert not edit.layer_item("customLayoutChildEditLock-fullscreen_overlay.preset").isVisible()
    edit.open_children()
    assert edit.flips == [] and not edit.owner.fullscreen_draft_pending
    edit.child_move("title", 40, 20)
    assert edit.flips == [True] and edit.owner.fullscreen_draft_pending
    edit.child_resize("artwork", "bottom_right", -16)
    moved = _np_parts(display)
    block = edit.item("now_playing").current_global_rect

    def relative(parts: dict[str, QRect], frame: QRect) -> dict[str, tuple[float, float]]:
        return {role: ((rect.x() - frame.x()) / frame.width(), (rect.y() - frame.y()) / frame.height())
                for role, rect in parts.items()}

    edit.wheel("now_playing", 3)
    _run(display, 60)
    grown = edit.item("now_playing").current_global_rect
    assert grown.width() > block.width()
    for role, (fx, fy) in relative(_np_parts(display), grown).items():
        bx, by = relative(moved, block)[role]
        assert abs(fx - bx) <= 0.03 and abs(fy - by) <= 0.03, role
    # Whatever a record says, the overlay draws the part inside the block (card padding included): a record far past
    # its edge (here straight through the model, past the Edit layer's own containment) stops at the edge.
    edit.child_move("artist", 3 * WIDTH, 3 * HEIGHT)
    slot = _rect(_slot(display, "expandedOverlayNowPlaying"), _root(display)).toRect()
    artist = _np_parts(display)["artist"]
    assert slot.adjusted(-1, -1, 1, 1).contains(artist), (slot, artist)
    assert abs(artist.right() - slot.right()) <= 1 and abs(artist.bottom() - slot.bottom()) <= 1
    assert edit.owner.cancel()
    assert edit.flips == [True, False]


@pytest.mark.qt
def test_the_blocks_lock_exposes_its_parts_while_another_overlay_is_selected(display, tmp_path):
    """Operator, 8 Nov: "clicking the child lock open does not expose the child widgets. You have to edit/move/adjust
    the parent widget afterwards until they are exposed." The block's lock shows on hover while the toast is selected;
    with real pointer events its click alone opens the parts (focusing the block), at the frames a block edit would
    give them, and the block stays put."""
    from PySide6.QtCore import QEvent, Qt

    settings = _manager(tmp_path)
    seeded = _seed(settings, now_playing={"media_controls": True})
    _draw(display, media=_Media(title="A Track Title", artist="An Artist"), config=_projection(seeded))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    assert edit.model.selectItem(edit.row("preset"))
    _run(display, 60)
    frame = edit.layer_item(f"customLayoutEditFrame-{BLOCK}")
    lock = edit.layer_item(f"customLayoutChildEditLock-{BLOCK}")
    assert frame.property("selectedForChildEdit") is False and frame.property("childEditingLocked") is True
    block = QRect(edit.item("now_playing").current_global_rect)
    _send(display, QEvent.Type.MouseMove, _scene_point(frame, 0.5, 0.5), Qt.MouseButton.NoButton,
          Qt.MouseButton.NoButton)
    _settle(display, lambda: lock.isEnabled() and float(lock.opacity()) > 0.5)
    assert _real_click(display, _scene_point(lock)) == f"customLayoutChildEditLockHitArea-{BLOCK}"
    assert frame.property("childEditingLocked") is False and frame.property("selectedForChildEdit") is True
    layer = edit.layer_item(f"customLayoutChildRoleLayer-{BLOCK}")
    _settle(display, lambda: float(layer.opacity()) >= 1.0)

    def shown() -> dict[str, tuple[float, float, float, float]]:
        rects = {role: edit.child_frame(role) for role in NP_PARTS}  # each is asserted shown
        return {role: (item.x(), item.y(), item.width(), item.height()) for role, item in rects.items()}

    exposed = shown()
    assert all(width > 0 and height > 0 for _x, _y, width, height in exposed.values()), exposed
    assert edit.item("now_playing").current_global_rect == block
    # The operator's workaround, a block edit with no net change (one pixel and back), shows the same frames.
    local = edit._local(block)
    edit.model.moveItem(edit.row("now_playing"), local.x() + 1, local.y(), local.x() + 1, local.y())
    _run(display, 40)
    edit.model.moveItem(edit.row("now_playing"), local.x(), local.y(), local.x(), local.y())
    edit.model.finishMove()
    _run(display, 80)
    assert edit.item("now_playing").current_global_rect == block
    nudged = shown()
    for role, rect in exposed.items():
        assert nudged[role] == pytest.approx(rect, abs=0.01), role
    assert edit.owner.cancel()


# ------------------------------------------------------------------------------ guides on the Edit layer


@pytest.mark.qt
def test_a_move_snaps_to_the_safe_area_and_draws_its_guide_on_the_edit_layer(display, tmp_path):
    settings = _manager(tmp_path)
    _draw(display, media=_Media(), config=_projection(_seed(settings)))
    _open(display)
    edit = _Fullscreen(display, settings)
    assert edit.start()
    _shown_and_settled(display)
    layer = display.scene.custom_layout_overlay.item
    geometry = display.scene.expanded_overlay_edit_geometry()
    safe_left = round(geometry["stage"][0] + geometry["safe_inset"])
    safe_centre = round(geometry["stage"][0] + geometry["safe_inset"] + geometry["safe_width"] / 2.0)
    # Drag the toast to just short of the safe area's horizontal centre: it snaps onto it, with a guide.
    rect = edit._local(edit.item("preset").current_global_rect)
    edit.drag("preset", safe_centre - rect.width() // 2 - rect.x() - 5, 160, release=False)
    guides = layer.property("verticalGuides")
    guides = guides.toVariant() if hasattr(guides, "toVariant") else guides
    snapped = edit._local(edit.item("preset").current_global_rect)
    assert abs(snapped.center().x() - safe_centre) <= 1
    assert any(abs(int(guide["position"]) - safe_centre) <= 1 for guide in guides)
    edit.model.finishMove()
    cleared = layer.property("verticalGuides")
    assert not (cleared.toVariant() if hasattr(cleared, "toVariant") else cleared)
    # Back against the left edge: it stops at the safe area, never past it.
    edit.drag("preset", -WIDTH, 0)
    assert edit._local(edit.item("preset").current_global_rect).x() == safe_left
    edit.owner.cancel()


# --------------------------------------------------------------------------------------- the pure geometry


def test_offsets_are_fractions_of_the_safe_area_from_the_corner_anchor():
    from core.settings.fullscreen_overlays import OFFSET_MAX, OFFSET_MIN
    from rendering.quick.fullscreen_overlay_edit import offsets_for_position

    assert offsets_for_position((128.0, 40.0), (28.0, 40.0), (1000.0, 500.0)) == (0.1, 0.0)
    assert offsets_for_position((28.0, -9e9), (28.0, 40.0), (1000.0, 500.0)) == (0.0, OFFSET_MIN)
    assert offsets_for_position((9e9, 40.0), (28.0, 40.0), (1000.0, 500.0)) == (OFFSET_MAX, 0.0)


def test_the_same_offset_reflows_to_the_same_relative_place_on_another_display():
    """Placement is relative to the safe area: x = anchor + offset x safe width on every display."""
    from rendering.quick.fullscreen_overlay_edit import offsets_for_position

    small, large = (1196.0, 636.0), (2484.0, 1324.0)
    offset = offsets_for_position((28.0 + 299.0, 28.0 + 159.0), (28.0, 28.0), small)
    assert offset == (0.25, 0.25)
    placed = (28.0 + offset[0] * large[0], 28.0 + offset[1] * large[1])
    assert offsets_for_position(placed, (28.0, 28.0), large) == offset


def test_a_corner_drag_scales_by_the_dragged_corners_distance_from_the_fixed_one():
    from rendering.quick.fullscreen_overlay_edit import corner_drag_scale

    origin = QRect(0, 0, 300, 400)
    assert corner_drag_scale(origin, 1.0, "bottom_right", 0, 0) == pytest.approx(1.0)
    assert corner_drag_scale(origin, 1.0, "bottom_right", 300, 400) == pytest.approx(2.0)
    assert corner_drag_scale(origin, 1.0, "top_left", -300, -400) == pytest.approx(2.0)
    assert corner_drag_scale(origin, 2.0, "top_right", -150, 200) == pytest.approx(1.0)


def test_the_draft_value_carries_exactly_the_placement_members():
    from core.settings.fullscreen_overlays import PLACEMENT_KEYS, canonical_fullscreen_overlays
    from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSessionItem
    from rendering.quick.fullscreen_overlay_edit import PARTS, draft_value, edit_widget_id

    committed = canonical_fullscreen_overlays()
    # Now Playing's children: a test-owned record map in ordinary Edit's child_geometry form.
    children = {"title": {"width_scale": 1.5, "height_scale": 1.5, "x_offset": 0.375}}

    def expected(key):
        return children if key == "child_geometry" else (0.375 if key.startswith("offset") else 1.5)

    items = []
    for part, (overlay, keys) in PARTS.items():
        payload = {key: expected(key) for key in keys}
        items.append(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(edit_widget_id(part), "D"), model_identity=edit_widget_id(part),
            baseline_global_rect=QRect(0, 0, 10, 10), current_global_rect=QRect(0, 0, 10, 10),
            baseline_size_payload=payload, current_size_payload=payload, baseline_enabled=True,
            current_enabled=True))
    value = draft_value(committed, tuple(items))
    for overlay, keys in PLACEMENT_KEYS.items():
        for key in keys:
            assert value[overlay][key] == expected(key), (overlay, key)
        untouched = {k: v for k, v in committed[overlay].items() if k not in keys}
        assert {k: v for k, v in value[overlay].items() if k not in keys} == untouched
    assert (value["font_family"], value["font_size"]) == (committed["font_family"], committed["font_size"])

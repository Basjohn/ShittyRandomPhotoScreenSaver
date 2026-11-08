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
from PySide6.QtCore import QPoint, QRect, QRectF
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
PARTS = ("preset", "now_playing", "artwork")


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

    def __init__(self, display, settings) -> None:
        from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

        self.display = display
        self.settings = settings
        self.reloads: list[str] = []
        self.flips: list[bool] = []
        self.unit = SimpleNamespace(
            is_retired=False, screen_index=0, presenter=SimpleNamespace(bound_widget_ids=()),
            runtime=SimpleNamespace(scene_controller=display.scene, window=display.window,
                                    display_identity=SimpleNamespace(screen_key="hidden",
                                                                     geometry=(0, 0, WIDTH, HEIGHT))))
        self.owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (self.unit,),
            visualizer_provider=lambda: (None, None), reload_request=self.reloads.append,
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
    """One script exercising every Fullscreen Edit gesture: move, wheel, corner drags (text and artwork), the artwork
    moving Now Playing, side handles (width only, height only) and a two-axis diagonal on every part, and Restore
    Size."""
    edit.drag("preset", 180, 96)
    edit.wheel("now_playing", 2)
    edit.corner("artwork", "top_right", 36, -36)
    edit.drag("artwork", 60, -48)
    edit.corner("preset", "bottom_right", 40, 18)
    edit.wheel("preset", -1)
    edit.model.restoreSize(edit.row("preset"))
    edit.drag("preset", -24, 30)
    edit.side("preset", "right", -70)
    edit.side("preset", "bottom", 64)
    edit.side("now_playing", "right", 140)
    edit.side("now_playing", "top", -50)
    edit.side("artwork", "right", 44)
    edit.side("artwork", "content_bottom_right", -20)


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
        # The side handles really set every extent the script touched (each axis on its own).
        assert all(draft_value[overlay][key] != seeded[overlay][key] for key in ("text_width", "text_height"))
    assert all(draft_value["now_playing"][key] != seeded["now_playing"][key]
               for key in ("artwork_width", "artwork_height"))
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
    the other dimension and member stay exactly; on the text parts the opposite edge stays where it was (the artwork
    grows from its place beside the text, as its corner drag does)."""
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
    if part != "artwork":
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
    """A narrower text box elides; a taller one gives the text more lines (it wraps); a non-square artwork frame
    crops the image into it (the ordinary freeform artwork frame)."""
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
    artwork_before = QRect(edit.item("artwork").current_global_rect)
    edit.side("now_playing", "top", -140)                       # the title gets the extra lines, the artwork stays
    _run(display, 60)
    assert int(title.property("lineCount")) >= 2
    assert edit.item("artwork").current_global_rect.size() == artwork_before.size()

    edit.side("artwork", "right", 80)
    _run(display, 60)
    art = edit.item("artwork").current_global_rect
    assert art.width() > art.height()
    image = layer.findChild(QQuickItem, "expandedOverlayArtworkImage")
    assert int(image.property("fillMode")) == 2                 # Image.PreserveAspectCrop: never distorted
    assert edit.frames() == edit.drawn()
    edit.owner.cancel()


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
    for part, handle in (("preset", "right"), ("preset", "bottom"), ("artwork", "bottom")):
        edit.side(part, handle, 60)
    for part in ("preset", "artwork"):
        assert edit.model.restoreSize(edit.row(part))
        overlay = "preset" if part == "preset" else "now_playing"
        for key in EXTENT_KEYS[part]:
            assert edit.item(part).current_size_payload[key] == canonical[overlay][key], (part, key)
    _run(display, 60)
    assert edit.frames()["preset"][2:] == before[0]["preset"][2:]
    assert edit.frames()["artwork"][2:] == before[0]["artwork"][2:]
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
    items = []
    for part, (overlay, keys) in PARTS.items():
        payload = {key: 0.375 if key.startswith("offset") else 1.5 for key in keys}
        items.append(CustomLayoutSessionItem(
            source_key=CustomLayoutKey(edit_widget_id(part), "D"), model_identity=edit_widget_id(part),
            baseline_global_rect=QRect(0, 0, 10, 10), current_global_rect=QRect(0, 0, 10, 10),
            baseline_size_payload=payload, current_size_payload=payload, baseline_enabled=True,
            current_enabled=True))
    value = draft_value(committed, tuple(items))
    for overlay, keys in PLACEMENT_KEYS.items():
        for key in keys:
            assert value[overlay][key] == (0.375 if key.startswith("offset") else 1.5)
        untouched = {k: v for k, v in committed[overlay].items() if k not in keys}
        assert {k: v for k, v in value[overlay].items() if k not in keys} == untouched
    assert (value["font_family"], value["font_size"]) == (committed["font_family"], committed["font_size"])

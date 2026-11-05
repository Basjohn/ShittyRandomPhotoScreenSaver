"""Studio session lifecycle and the QML-facing bridge.

``StudioController`` is the single-instance owner of one authoring session: it
builds the edit session from the canonical store, presents the Studio surface,
conceals the originating Settings window only once the surface has presented a
frame, and on every exit path retires playback, the evaluator, GL resources and
the window before revealing and refreshing the *same* Settings window.

``StudioBridge`` is the only object QML sees. Its slots are plain methods (no
``result=``): QML signal handlers connected to result slots crash PySide during
Quick layout in this project.
"""
from __future__ import annotations

from typing import Any, Callable, ClassVar, Mapping

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

from core.logging.logger import get_logger
from ui.studio.adapter import RECORDED, StudioFixture, StudioModeAdapter
from ui.studio.schema import CHOICE, COLOUR, COUNT, GRADIENT, QUIET_PEAK, SCALAR, SWITCH, StudioProperty
from ui.studio.session import CanonicalStore, StudioEditSession, read_path
from ui.studio.transport import StudioTransport

logger = get_logger(__name__)


def _colour_hex(prop: StudioProperty, value: Any) -> str:
    if prop.colour_format == "linear01":
        from ui.studio.colour import display_hex
        return display_hex(value)
    channels = [max(0, min(255, int(round(float(c))))) for c in list(value)[:3]]
    return "#%02x%02x%02x" % tuple(channels)


def _colour_value(prop: StudioProperty, text: str, previous: Any) -> Any:
    from ui.studio.colour import linear_from_hex
    if prop.colour_format == "linear01":
        return linear_from_hex(text)
    digits = str(text).strip().lstrip("#")
    if len(digits) != 6:
        raise ValueError("Colour must be six hex digits")
    rgb = [int(digits[i:i + 2], 16) for i in (0, 2, 4)]
    alpha = list(previous)[3:4] or [255]
    return rgb + alpha


def _gradient_display(prop: StudioProperty, nodes: Any) -> list:
    return [{"pos": float(position), "hex": _colour_hex(prop, colour)} for position, colour in nodes]


def _gradient_value(prop: StudioProperty, display: Any, previous: Any) -> list:
    """Display nodes -> stored nodes. A node whose display colour is unchanged keeps its exact stored
    colour (no linear <-> display round-trip drift); only edited colours are converted."""
    import json
    nodes = json.loads(display) if isinstance(display, str) else list(display)
    if not prop.minimum <= len(nodes) <= prop.maximum:
        raise ValueError(f"{prop.label} needs {int(prop.minimum)} to {int(prop.maximum)} nodes")
    old = list(previous)
    out = []
    for node in nodes:
        source = node.get("from")
        colour = None
        if isinstance(source, int) and 0 <= source < len(old):
            original = old[source][1]
            if _colour_hex(prop, original).lower() == str(node["hex"]).lower():
                colour = list(original)
        if colour is None:
            colour = _colour_value(prop, node["hex"], [0, 0, 0, 255])[:3] if prop.colour_format != "linear01" \
                else _colour_value(prop, node["hex"], None)
        out.append([max(0.0, min(1.0, float(node["pos"]))), colour])
    out.sort(key=lambda item: item[0])
    return out


class StudioBridge(QObject):
    headerChanged = Signal()
    workspaceChanged = Signal()
    objectsChanged = Signal()
    inspectorChanged = Signal()
    valuesChanged = Signal()
    transportChanged = Signal()
    timeChanged = Signal()
    viewportChanged = Signal()
    messageChanged = Signal()
    themeChanged = Signal()
    closeRequested = Signal()
    framingChanged = Signal()
    measurementsChanged = Signal()
    responseChanged = Signal()

    def __init__(self, controller: "StudioController") -> None:
        super().__init__()
        self._c = controller
        schema = controller.session.schema
        self._schema = schema
        self._workspace = schema.workspaces[0].id
        objects = controller.adapter.scene_objects(controller.session.values)
        self._selected = objects[0].id if objects else ""
        self._inspector: list[dict] = []
        self._values: dict[str, Any] = {}
        self._objects: list[dict] = []
        self._viewport_status = "preparing"
        self._viewport_error = ""
        self._message = ""
        self._theme: dict[str, str] = {}
        self._framing_id = ""
        self._measurements: dict = {"sources": {}, "targets": {}, "signals": {}}
        from collections import deque
        self._trace_history: dict = {}
        self._deque = deque
        response = schema.response
        self._target = response.targets[0].id if response is not None and response.targets else ""
        self._source = response.sources[0].id if response is not None and response.sources else ""
        if self._target:
            self._source = self._dominant_source(self._target)
        self._rebuild_objects()
        self._rebuild_inspector()
        self._rebuild_values()

    # ------------------------------------------------------------ header
    def _title(self) -> str:
        return self._schema.title

    def _preset(self) -> str:
        return self._c.session.preset_label

    def _dirty(self) -> bool:
        return self._c.session.dirty

    def _can_undo(self) -> bool:
        return bool(self._c.session.undo_label)

    def _can_redo(self) -> bool:
        return bool(self._c.session.redo_label)

    def _undo_text(self) -> str:
        return self._c.session.undo_label

    def _redo_text(self) -> str:
        return self._c.session.redo_label

    title = Property(str, _title, constant=True)

    def _modes(self) -> list:
        return [{"id": mode_id, "title": title} for mode_id, title in self._c.modes()]

    def _capabilities(self) -> dict:
        return self._c.capabilities.as_map()

    capabilities = Property("QVariantMap", _capabilities, constant=True)

    def _mode_id(self) -> str:
        return self._c.adapter.mode_id

    modes = Property("QVariantList", _modes, constant=True)
    modeId = Property(str, _mode_id, constant=True)

    @Slot(str)
    def switchMode(self, mode_id: str) -> None:
        self._c.request_mode_switch(mode_id)
    presetLabel = Property(str, _preset, notify=headerChanged)
    dirty = Property(bool, _dirty, notify=headerChanged)
    canUndo = Property(bool, _can_undo, notify=headerChanged)
    canRedo = Property(bool, _can_redo, notify=headerChanged)
    undoText = Property(str, _undo_text, notify=headerChanged)
    redoText = Property(str, _redo_text, notify=headerChanged)

    # -------------------------------------------------------- workspaces
    def _workspaces(self) -> list:
        return [{"id": w.id, "title": w.title, "icon": w.icon, "help": w.help} for w in self._schema.workspaces]

    def _current_workspace(self) -> str:
        return self._workspace

    workspaces = Property("QVariantList", _workspaces, constant=True)
    workspace = Property(str, _current_workspace, notify=workspaceChanged)

    @Slot(str)
    def setWorkspace(self, workspace_id: str) -> None:
        if workspace_id == self._workspace or workspace_id not in {w.id for w in self._schema.workspaces}:
            return
        self._workspace = workspace_id
        self._rebuild_inspector()
        self.workspaceChanged.emit()
        self._c.refresh_handles()
        self._c.refresh_preset_previews()

    # ----------------------------------------------------------- objects
    def _rebuild_objects(self) -> None:
        objects = self._c.adapter.scene_objects(self._c.session.values)
        self._objects = [{"id": o.id, "label": o.label, "swatch": o.swatch, "visible": o.visible,
                          "toggleable": o.toggleable, "note": o.hidden_note} for o in objects]
        if self._selected not in {o["id"] for o in self._objects} and self._objects:
            self._selected = self._objects[0]["id"]

    def _object_list(self) -> list:
        return self._objects

    def _selected_object(self) -> str:
        return self._selected

    objects = Property("QVariantList", _object_list, notify=objectsChanged)
    selectedObject = Property(str, _selected_object, notify=objectsChanged)

    def _noun(self) -> str:
        return self._schema.object_noun

    def _can_add(self) -> bool:
        return self._c.adapter.add_object(self._c.session.values) is not None

    objectNoun = Property(str, _noun, constant=True)
    canAddObject = Property(bool, _can_add, notify=objectsChanged)

    @Slot(str, bool)
    def setObjectVisible(self, object_id: str, visible: bool) -> None:
        edit = self._c.adapter.set_object_visible(self._c.session.values, object_id, bool(visible))
        if edit is not None:
            self._guard(lambda: self._c.session.set(edit[0], edit[1], ("Show " if visible else "Hide ")
                                                    + self._schema.object_noun))

    @Slot()
    def addObject(self) -> None:
        edit = self._c.adapter.add_object(self._c.session.values)
        if edit is not None:
            self._guard(lambda: self._c.session.set(edit[0], edit[1], "Add " + self._schema.object_noun))

    @Slot(str)
    def selectObject(self, object_id: str) -> None:
        if object_id == self._selected:
            return
        self._selected = object_id
        self._rebuild_inspector()
        self.objectsChanged.emit()
        self._c.refresh_handles()
        self._c.refresh_preset_previews()

    # --------------------------------------------------------- inspector
    def _rebuild_inspector(self) -> None:
        workspace = next(w for w in self._schema.workspaces if w.id == self._workspace)
        groups = []
        ordered = sorted(self._schema.properties, key=lambda p: p.priority)   # stable: registry order otherwise
        for position, group in enumerate(workspace.groups):
            rows = []
            for prop in ordered:
                if prop.workspace != self._workspace or prop.group != group:
                    continue
                if prop.object_scope and prop.object_scope != self._selected:
                    continue
                if prop.instrument_only:
                    continue
                try:
                    read_path(self._c.session.values, prop.path)
                except (KeyError, IndexError, TypeError):
                    continue            # e.g. a gradient node slot this palette does not have
                rows.append(self._row(prop))
            if rows:
                title = group
                if "{object}" in group:          # per-object groups are titled by the selected scene object
                    label = next((o["label"] for o in self._objects if o["id"] == self._selected), "")
                    title = group.replace("{object}", label or "Selected")
                traces = dict(self._schema.group_traces).get(group, ())
                is_open = group in workspace.open_groups if workspace.open_groups else position < 2
                is_open = is_open or group in getattr(self, "_forced_open", ())
                icon = dict(self._schema.group_icons).get(group, "")
                presets = dict(self._schema.group_presets).get(group, ())
                lifecycle = next((spec for spec in self._schema.lifecycles if spec.group == group), None)
                card = next((spec for spec in self._schema.cards if spec.group == group), None)
                groups.append({"title": title, "rows": rows, "traces": list(traces), "open": is_open,
                               "icon": icon,
                               "presets": [{"id": p.id, "label": p.label, "description": p.description,
                                            "swatch": list(p.swatch)} for p in presets],
                               "lifecycle": ({"total": self._row(self._schema.find(lifecycle.total)),
                                              "fade": (self._row(self._schema.find(lifecycle.fade_share))
                                                       if lifecycle.fade_share else {}),
                                              "peel": (self._row(self._schema.find(lifecycle.peel))
                                                       if lifecycle.peel else {}),
                                              "label": lifecycle.label}
                                             if lifecycle is not None else {}),
                               "card": ({"kind": card.kind, "title": card.title, "roles": dict(card.roles),
                                         "rendered": card.rendered, "group": card.group,
                                         "labels": {role: self._schema.find(pid).label for role, pid in card.roles}}
                                        if card is not None else {}),
                               "group": group})
        self._inspector = groups
        self.inspectorChanged.emit()

    def _inspector_groups(self) -> list:
        return self._inspector

    inspector = Property("QVariantList", _inspector_groups, notify=inspectorChanged)

    def _rebuild_values(self) -> None:
        values = self._c.evaluation_values()
        out: dict[str, Any] = {}
        for prop in self._schema.properties:
            try:
                value = read_path(values, prop.path)
            except (KeyError, IndexError, TypeError):
                continue
            if prop.instrument == QUIET_PEAK:
                out[prop.id] = [float(value[0]), float(value[1])]
            elif prop.instrument in (SCALAR, COUNT):
                out[prop.id] = float(value)
            elif prop.instrument == SWITCH:
                out[prop.id] = bool(value)
            elif prop.instrument == CHOICE:
                out[prop.id] = str(value)
            elif prop.instrument == COLOUR:
                out[prop.id] = _colour_hex(prop, value)
            elif prop.instrument == GRADIENT:
                out[prop.id] = _gradient_display(prop, value)
        self._values = out
        self._active_presets = self._preset_state(values)
        self.valuesChanged.emit()

    def _value_map(self) -> dict:
        return self._values

    def _preset_state(self, values) -> dict:
        """group -> id of the preset the current values equal (none when edited away from all)."""
        state = {}
        baseline = self._c.session.baseline_values
        for group, presets in self._schema.group_presets:
            state[group] = next((p.id for p in presets
                                 if not self._c.adapter.apply_preset(group, p.id, baseline, values)), "")
        return state

    def _presets_active(self) -> dict:
        return getattr(self, "_active_presets", {})

    activePresets = Property("QVariantMap", _presets_active, notify=valuesChanged)

    @Slot(str, str)
    def applyPreset(self, group: str, preset_id: str) -> None:
        presets = dict(self._schema.group_presets).get(group, ())
        preset = next((p for p in presets if p.id == preset_id), None)
        if preset is None:
            return
        changes = self._c.adapter.apply_preset(group, preset_id, self._c.session.baseline_values,
                                               self._c.session.values)
        if changes:
            self._guard(lambda: self._c.session.set_many(changes, f"{group.replace('{object}', '').strip()}: "
                                                         f"{preset.label}"))

    @Slot(str, str)
    def previewGradient(self, property_id: str, nodes: str) -> None:
        def run():
            prop = self._schema.find(property_id)
            if not self._c.session.gesture_active:
                self._c.session.begin_gesture(prop.label)
            previous = read_path(self._c.session.values, prop.path)
            self._c.session.preview(prop.path, _gradient_value(prop, nodes, previous))
        self._guard(run)

    @Slot(str, str)
    def commitGradient(self, property_id: str, nodes: str) -> None:
        def run():
            prop = self._schema.find(property_id)
            previous = read_path(self._c.session.values, prop.path)
            self._c.session.set(prop.path, _gradient_value(prop, nodes, previous), f"Edit {prop.label}")
        self._guard(run)

    # ------------------------------------------------------------- handles
    def _handles(self) -> dict:
        return getattr(self, "_handle_state", {"outline": [], "handles": []})

    handlesChanged = Signal()
    handles = Property("QVariantMap", _handles, notify=handlesChanged)

    previewsChanged = Signal()

    def _previews(self) -> dict:
        return getattr(self, "_preview_urls", {})

    presetPreviews = Property("QVariantMap", _previews, notify=previewsChanged)
    previews = Property("QVariantMap", _previews, notify=previewsChanged)

    cardEndpointsChanged = Signal()

    def card_endpoint(self, group: str) -> int:
        """Which Quiet/Peak lane a rendered card shows: the lane last edited in its group (Peak at first)."""
        return int(getattr(self, "_card_endpoints", {}).get(group, 1))

    def _card_endpoints_map(self) -> dict:
        return {card.group: self.card_endpoint(card.group) for card in self._schema.cards}

    cardEndpoints = Property("QVariantMap", _card_endpoints_map, notify=cardEndpointsChanged)

    @Slot(str, int)
    def setCardEndpoint(self, group: str, endpoint: int) -> None:
        endpoints = dict(getattr(self, "_card_endpoints", {}))
        if endpoints.get(group) == int(endpoint):
            return
        endpoints[group] = int(endpoint)
        self._card_endpoints = endpoints
        self.cardEndpointsChanged.emit()
        self._c.refresh_preset_previews()

    def note_endpoint_edit(self, property_id: str, endpoint: int) -> None:
        """An edit on one lane of a Quiet/Peak value: that group's rendered card follows the lane."""
        prop = self._schema.find(property_id)
        if prop.instrument != QUIET_PEAK:
            return
        if any(card.group == prop.group and card.rendered for card in self._schema.cards):
            if self.card_endpoint(prop.group) != int(endpoint):
                endpoints = dict(getattr(self, "_card_endpoints", {}))
                endpoints[prop.group] = int(endpoint)
                self._card_endpoints = endpoints
                self.cardEndpointsChanged.emit()

    def set_preview(self, key: str, url: str) -> None:
        urls = dict(self._previews())
        urls[key] = url
        self._preview_urls = urls
        self.previewsChanged.emit()

    def set_handles(self, state: Mapping[str, Any]) -> None:
        self._handle_state = dict(state)
        self.handlesChanged.emit()

    values = Property("QVariantMap", _value_map, notify=valuesChanged)

    def on_session_changed(self, reason: str) -> None:
        self._rebuild_values()
        if reason in ("commit", "undo", "redo", "hydrate"):
            self._rebuild_inspector()           # structure can change (e.g. gradient node count)
            previous = [(o["id"], o["visible"], o["swatch"]) for o in self._objects]
            self._rebuild_objects()
            if previous != [(o["id"], o["visible"], o["swatch"]) for o in self._objects]:
                self.objectsChanged.emit()
            self.headerChanged.emit()

    # ------------------------------------------------------------ edits
    def _prop_path(self, property_id: str, endpoint: int):
        prop = self._schema.find(property_id)
        if not prop.view_pose:
            # An explicit edit of a value the viewport is previewing replaces that preview.
            self._c._pose.pop(prop.path[0], None)
        if prop.instrument == QUIET_PEAK:
            return prop, (*prop.path, 1 if int(endpoint) else 0)
        return prop, prop.path

    def _coerce(self, prop: StudioProperty, value: Any) -> Any:
        if prop.instrument in (SCALAR, COUNT, QUIET_PEAK):
            number = min(prop.maximum, max(prop.minimum, float(value)))
            return int(round(number)) if prop.integer else number
        if prop.instrument == SWITCH:
            return bool(value)
        if prop.instrument == COLOUR:
            return _colour_value(prop, value, read_path(self._c.session.values, prop.path))
        return value

    def _guard(self, action: Callable[[], Any]) -> None:
        try:
            action()
        except (ValueError, TypeError, KeyError) as exc:
            self._c.session.cancel_gesture()
            self.notify(f"Not applied: {exc}")

    @Slot(str, str)
    def beginEdit(self, property_id: str, label: str) -> None:
        prop = self._schema.find(property_id)
        if prop.view_pose:
            self._pose_edit = True
            return
        self._c.session.begin_gesture(label or prop.label)

    @Slot(str, int, float)
    def previewValue(self, property_id: str, endpoint: int, value: float) -> None:
        self.note_endpoint_edit(property_id, endpoint)

        def run():
            prop, path = self._prop_path(property_id, endpoint)
            if prop.view_pose:
                self._c.set_pose(prop.path[0], self._coerce(prop, value))
                return
            self._c.session.preview(path, self._coerce(prop, value))
        self._guard(run)

    @Slot()
    def endEdit(self) -> None:
        if getattr(self, "_pose_edit", False):
            self._pose_edit = False
            self._guard(self._c.end_orbit)
            return
        self._guard(self._c.session.end_gesture)

    @Slot(str, str)
    def previewColour(self, property_id: str, hex_text: str) -> None:
        """Live colour preview while a picker is dragged (one gesture; endEdit commits it)."""
        def run():
            prop = self._schema.find(property_id)
            if not self._c.session.gesture_active:
                self._c.session.begin_gesture(f"Set {prop.label}")
            self._c.session.preview(prop.path, self._coerce(prop, hex_text))
        self._guard(run)

    revealed = Signal(str, int)

    @Slot(str, int)
    def revealProperty(self, property_id: str, endpoint: int = 0) -> None:
        """Open the property's group in the inspector and focus its exact-entry field."""
        prop = self._schema.find(property_id)
        if prop.workspace != self._workspace:
            self.setWorkspace(prop.workspace)
        self._forced_open = set(getattr(self, "_forced_open", ())) | {prop.group}
        self._rebuild_inspector()
        self.revealed.emit(property_id, int(endpoint))

    @Slot()
    def cancelEdit(self) -> None:
        self._c.session.cancel_gesture()

    @Slot(str, int, "QVariant")
    def commitValue(self, property_id: str, endpoint: int, value: Any) -> None:
        self.note_endpoint_edit(property_id, endpoint)

        def run():
            prop, path = self._prop_path(property_id, endpoint)
            if prop.view_pose:
                self._c.set_pose(prop.path[0], self._coerce(prop, value))
                self._c.end_orbit()
                return
            self._c.session.set(path, self._coerce(prop, value), f"Set {prop.label}")
        self._guard(run)

    @Slot(str, int, str)
    def commitText(self, property_id: str, endpoint: int, text: str) -> None:
        """Exact numeric/hex entry; out-of-range numbers are clamped and the clamp is reported."""
        self.note_endpoint_edit(property_id, endpoint)

        def run():
            prop, path = self._prop_path(property_id, endpoint)
            if prop.instrument == COLOUR:
                current = read_path(self._c.session.values, prop.path)
                if _colour_hex(prop, current).lower() == str(text).strip().lower():
                    return                       # same display colour: keep the exact stored value
                value = self._coerce(prop, text)
            else:
                typed = float(str(text).strip().replace(prop.units.strip(), "") or "nan")
                if typed != typed:
                    raise ValueError("enter a number")
                value = self._coerce(prop, typed)
                if float(value) != typed:
                    self.notify(f"{prop.label} limited to {prop.minimum:g}..{prop.maximum:g}")
            if prop.view_pose:
                self._c.set_pose(prop.path[0], value)
                self._c.end_orbit()
                return
            self._c.session.set(path, value, f"Set {prop.label}")
        self._guard(run)

    @Slot(str)
    def resetProperty(self, property_id: str) -> None:
        prop = self._schema.find(property_id)
        self._guard(lambda: self._c.session.reset_property(prop.path, f"Reset {prop.label}"))

    @Slot()
    def undo(self) -> None:
        self._guard(self._c.session.undo)

    @Slot()
    def redo(self) -> None:
        self._guard(self._c.session.redo)

    @Slot()
    def revertAll(self) -> None:
        self._guard(self._c.session.revert_all)

    @Slot()
    def savePresetAs(self) -> None:
        save = getattr(self._c.store, "save_preset_as", None)
        if callable(save):
            save()
        else:
            self.notify("Save As is not available for this store")

    @Slot()
    def requestClose(self) -> None:
        self.closeRequested.emit()

    # --------------------------------------------------------- transport
    def _playing(self) -> bool:
        return self._c.transport.playing

    def _time(self) -> float:
        return float(self._c.transport.time)

    def _duration(self) -> float:
        return float(self._c.transport.duration)

    def _loop(self) -> bool:
        return self._c.transport.loop

    def _fixture_id(self) -> str:
        return self._c.evaluator.fixture.id

    def _fixtures(self) -> list:
        loaded = {f.id for f in self._c.evaluator.fixtures()}
        entries = [{"id": f.id, "label": f.label, "kind": f.kind, "description": f.description,
                    "status": "ready"} for f in self._c.evaluator.fixtures() if f.kind != RECORDED]
        for clip in self._c.adapter.recorded_clips():
            status = "ready" if clip.id in loaded else self._c.clip_status(clip.id)
            entries.append({"id": clip.id, "label": clip.label, "kind": clip.kind,
                            "description": "Recorded music, production analysis replay", "status": status})
        return entries

    playing = Property(bool, _playing, notify=transportChanged)
    loop = Property(bool, _loop, notify=transportChanged)
    duration = Property(float, _duration, notify=transportChanged)
    fixtureId = Property(str, _fixture_id, notify=transportChanged)
    fixtures = Property("QVariantList", _fixtures, notify=transportChanged)

    def _timeline(self) -> list:
        shape = getattr(self._c.evaluator, "timeline", None)
        if not callable(shape):
            return []
        key = self._c.evaluator.fixture.id
        if getattr(self, "_timeline_key", None) != key:
            self._timeline_key, self._timeline_cache = key, shape()
        return self._timeline_cache

    timeline = Property("QVariantList", _timeline, notify=transportChanged)
    time = Property(float, _time, notify=timeChanged)

    @Slot()
    def togglePlay(self) -> None:
        self._c.set_playing(not self._c.transport.playing)

    @Slot(float)
    def seek(self, seconds: float) -> None:
        self._c.seek(seconds)

    @Slot(bool)
    def setLoop(self, enabled: bool) -> None:
        self._c.transport.loop = bool(enabled)
        self.transportChanged.emit()

    @Slot(str)
    def selectFixture(self, fixture_id: str) -> None:
        self._c.select_fixture(fixture_id)

    # --------------------------------------------------------- viewport
    def _status(self) -> str:
        return self._viewport_status

    def _error(self) -> str:
        return self._viewport_error

    viewportStatus = Property(str, _status, notify=viewportChanged)
    viewportError = Property(str, _error, notify=viewportChanged)

    def set_viewport(self, status: str, error: str = "") -> None:
        if (status, error) != (self._viewport_status, self._viewport_error):
            self._viewport_status, self._viewport_error = status, error
            self.viewportChanged.emit()

    @Slot(float, float)
    def orbitBy(self, dx: float, dy: float) -> None:
        self._c.orbit_by(dx, dy)

    @Slot()
    def endOrbit(self) -> None:
        self._guard(self._c.end_orbit)

    @Slot()
    def resetCamera(self) -> None:
        self._c.reset_camera()

    @Slot(float, bool)
    def zoomBy(self, steps: float, dolly: bool) -> None:
        self._c.zoom_by(steps, dolly=dolly)

    @Slot(float, float, float, float)
    def panBy(self, dx: float, dy: float, width: float, height: float) -> None:
        self._c.pan_by(dx, dy, width, height)

    @Slot()
    def keepView(self) -> None:
        self._guard(self._c.keep_view)

    def _view_readout(self) -> list:
        return self._c.view_readout()

    def _view_modified(self) -> bool:
        return bool(self._c._pose)

    viewReadout = Property("QVariantList", _view_readout, notify=valuesChanged)
    viewModified = Property(bool, _view_modified, notify=valuesChanged)

    # ------------------------------------------------------------- framing
    def _framings(self) -> list:
        return [{"id": f.id, "label": f.label, "description": f.description,
                 "aspect": f.extent[0] / f.extent[1]} for f in self._c.framings]

    def _framing(self) -> str:
        return self._framing_id

    framings = Property("QVariantList", _framings, notify=framingChanged)
    framingId = Property(str, _framing, notify=framingChanged)

    @Slot(str)
    def selectFraming(self, framing_id: str) -> None:
        self._c.select_framing(framing_id)

    def set_framing(self, framing_id: str) -> None:
        self._framing_id = framing_id
        self.framingChanged.emit()

    # ---------------------------------------------------- measurements / traces
    TRACE_SAMPLES = 180

    def push_measurements(self, measurements: Mapping[str, Any]) -> None:
        self._measurements = {key: dict(measurements.get(key, {})) for key in ("sources", "targets", "signals")}
        for name, value in self._measurements["signals"].items():
            history = self._trace_history.get(name)
            if history is None:
                history = self._trace_history[name] = self._deque(maxlen=self.TRACE_SAMPLES)
            history.append(max(0.0, min(1.0, float(value))))
        self.measurementsChanged.emit()

    def clear_traces(self) -> None:
        self._trace_history.clear()
        self.measurementsChanged.emit()

    def _measurement_map(self) -> dict:
        return self._measurements

    def _trace_map(self) -> dict:
        return {name: list(values) for name, values in self._trace_history.items()}

    measurements = Property("QVariantMap", _measurement_map, notify=measurementsChanged)
    traces = Property("QVariantMap", _trace_map, notify=measurementsChanged)

    # ------------------------------------------------------------- response
    def _row(self, prop: StudioProperty) -> dict:
        return {"id": prop.id, "label": prop.label, "instrument": prop.instrument,
                "min": float(prop.minimum), "max": float(prop.maximum), "decimals": int(prop.decimals),
                "units": prop.units, "choices": list(prop.choices), "tooltip": prop.tooltip,
                "quietMeaning": prop.quiet_meaning, "peakMeaning": prop.peak_meaning, "integer": bool(prop.integer),
                "notes": list(prop.choice_notes)}

    def _response_model(self) -> dict:
        response = self._schema.response
        if response is None:
            return {}
        return {"sources": [{"id": s.id, "label": s.label} for s in response.sources],
                "targets": [{"id": t.id, "label": t.label, "description": t.description,
                             "range": t.range_property,
                             "cells": [{"source": c.source, "gain": c.gain, "power": c.power} for c in t.cells]}
                            for t in response.targets],
                "gainMin": response.gain_bounds[0], "gainMax": response.gain_bounds[1],
                "powerMin": response.power_bounds[0], "powerMax": response.power_bounds[1],
                "timing": [self._row(self._schema.find(pid)) for pid in response.timing_properties],
                "timingNote": response.timing_note,
                "presets": [{"label": label, "power": power} for label, power in response.curve_presets]}

    def _target_row(self) -> dict:
        response = self._schema.response
        target = next((t for t in response.targets if t.id == self._target), None) if response else None
        if target is None or not target.range_property:
            return {}
        return self._row(self._schema.find(target.range_property))

    def _selected_target(self) -> str:
        return self._target

    def _selected_source(self) -> str:
        return self._source

    response = Property("QVariantMap", _response_model, constant=True)
    selectedTarget = Property(str, _selected_target, notify=responseChanged)
    selectedSource = Property(str, _selected_source, notify=responseChanged)
    targetRange = Property("QVariantMap", _target_row, notify=responseChanged)

    def _dominant_source(self, target_id: str) -> str:
        """The source that currently drives a target most (by authored gain), so its curve shows first."""
        response = self._schema.response
        target = next((t for t in response.targets if t.id == target_id), None) if response else None
        if target is None or not target.cells:
            return self._source
        values = self._c.session.values

        def gain(cell):
            try:
                return float(read_path(values, self._schema.find(cell.gain).path))
            except (KeyError, IndexError, TypeError, ValueError):
                return 0.0
        return max(target.cells, key=gain).source

    @Slot(str)
    def selectTarget(self, target_id: str) -> None:
        if target_id != self._target:
            self._target = target_id
            self._source = self._dominant_source(target_id)
            self.responseChanged.emit()

    @Slot(str)
    def selectSource(self, source_id: str) -> None:
        if source_id != self._source:
            self._source = source_id
            self.responseChanged.emit()

    # ---------------------------------------------------------- notices/theme
    def _message_text(self) -> str:
        return self._message

    message = Property(str, _message_text, notify=messageChanged)

    def notify(self, text: str) -> None:
        self._message = str(text)
        self.messageChanged.emit()

    @Slot()
    def dismissMessage(self) -> None:
        self.notify("")

    def _theme_map(self) -> dict:
        return self._theme

    theme = Property("QVariantMap", _theme_map, notify=themeChanged)

    def set_theme(self, theme: Mapping[str, str]) -> None:
        self._theme = dict(theme)
        self.themeChanged.emit()


class StudioController(QObject):
    """One authoring session from open to the Settings reveal."""

    presented = Signal()
    closed = Signal()
    failed = Signal(str)

    _active: ClassVar["StudioController | None"] = None

    @classmethod
    def active(cls) -> "StudioController | None":
        return cls._active

    modeSwitched = Signal(str)

    def __init__(self, adapter: StudioModeAdapter, store: CanonicalStore, presence, surface_factory,
                 *, theme_provider: Callable[[], Mapping[str, str]] | None = None,
                 mode_switcher: Callable[[str], tuple] | None = None,
                 modes: Callable[[], tuple] | None = None) -> None:
        super().__init__()
        self.adapter = adapter
        self.store = store
        self.presence = presence
        self._surface_factory = surface_factory
        self._theme_provider = theme_provider
        self._mode_switcher = mode_switcher
        self._modes = modes
        self.session: StudioEditSession | None = None
        self.evaluator = None
        self.transport = StudioTransport()
        self.bridge: StudioBridge | None = None
        self.surface = None
        self.viewport = None
        self.state = "idle"           # idle -> opening -> presented -> closed
        self._eval_dirty = True
        self._pose: dict[str, float] = {}
        self._unsubscribe = None
        self._clip_jobs: dict[str, Any] = {}
        self._clip_errors: dict[str, str] = {}
        self.evaluations = 0
        self.last_frame = None
        self.framings: tuple = ()
        self.capabilities = adapter.capabilities()
        self._preview_jobs: list = []
        self._preview_sent: dict = {}
        self._preview_done: dict = {}
        self._preview_crops: dict = {}
        self._auto_clip: str | None = None

    # ---------------------------------------------------------------- open
    def open(self) -> bool:
        """Create and show the Studio. Settings stays visible until the first presented frame."""
        current = StudioController._active
        if current is not None and current is not self:
            current.raise_surface()
            return False
        if self.state != "idle":
            return False
        StudioController._active = self
        self.state = "opening"
        try:
            self.capabilities = self.adapter.capabilities()
            self.session = StudioEditSession(self.adapter.schema(), self.store)
            self.evaluator = self.adapter.create_evaluator()
            self.transport.set_duration(self.evaluator.fixture.duration)
            self.bridge = StudioBridge(self)
            if self._theme_provider is not None:
                self.bridge.set_theme(self._theme_provider())
            self._unsubscribe = self.session.subscribe(self._on_session_changed)
            self.bridge.closeRequested.connect(self.close)
            self.surface = self._surface_factory(self)
            self.viewport = self.surface.viewport
            self.viewport.rendered.connect(self._on_rendered, Qt.ConnectionType.QueuedConnection)
            self.viewport.renderError.connect(self._on_render_error, Qt.ConnectionType.QueuedConnection)
            self.viewport.preparing.connect(self._on_preparing, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotReady.connect(self._on_snapshot, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotFailed.connect(self._on_snapshot_failed, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotPending.connect(self._on_snapshot_pending, Qt.ConnectionType.QueuedConnection)
            self._preview_jobs = []
            self._preview_sent = {}
            self._preview_done = {}
            self.surface.frameStarted.connect(self.on_frame)
            self.surface.presented.connect(self._on_presented)
            self.surface.closeRequested.connect(self.close)
            self.surface.lost.connect(self._on_surface_lost)
            self.surface.failed.connect(self._fail)
            if self.capabilities.viewport:
                card_extent = getattr(self.store, "card_extent", lambda: None)()
                card_style = getattr(self.store, "card_style", lambda: None)()
                self.framings = tuple(self.adapter.framings(card_extent, card_style))
                if self.framings:
                    self.select_framing(self.framings[0].id)
            else:
                # Inspector-only Studio: the item never gets a scene-graph node, so no renderer exists.
                self.viewport.setVisible(False)
                self.framings = ()
                self.bridge.set_viewport("none")
            self._choose_default_source()
            self.surface.show()
        except Exception as exc:
            logger.exception("[STUDIO] Studio failed to open")
            self._fail(f"{type(exc).__name__}: {exc}")
            return False
        return True

    def modes(self) -> tuple:
        """(mode_id, title) of every mode the Studio can switch to (the active one included)."""
        if self._modes is None:
            return ((self.adapter.mode_id, self.adapter.title),)
        return tuple(self._modes())

    def request_mode_switch(self, mode_id: str) -> None:
        """Switch the Studio to another registered mode, keeping Settings concealed throughout.

        The integration's switcher prepares the canonical store for that mode and returns
        ``(adapter, store)``; the session, evaluator and surface are rebuilt for it. A failure
        leaves Settings revealed by the normal failure path."""
        if mode_id == self.adapter.mode_id or self._mode_switcher is None:
            return
        if self.state not in ("opening", "presented"):
            return
        try:
            adapter, store = self._mode_switcher(mode_id)
        except Exception as exc:
            logger.exception("[STUDIO] Mode switch failed")
            if self.bridge is not None:
                self.bridge.notify(f"Could not switch mode: {exc}")
            return
        self._retire(reveal=False)          # Settings stays concealed for the next session
        self.adapter, self.store = adapter, store
        self.transport = StudioTransport()
        self._pose = {}
        self._clip_errors.clear()
        self.state = "idle"
        self.modeSwitched.emit(mode_id)
        self.open()

    def raise_surface(self) -> None:
        if self.surface is not None:
            self.surface.raise_()

    def _on_presented(self) -> None:
        if self.state != "opening":
            return
        self.state = "presented"
        try:
            self.presence.conceal()          # no-op when a mode switch kept Settings concealed
        except Exception:
            logger.exception("[STUDIO] Could not conceal Settings; it stays visible")
        self.presented.emit()

    def _fail(self, message: str) -> None:
        """Opening or presenting failed: retire everything, keep/restore Settings, report."""
        self._retire(reveal=self.state == "presented" or bool(getattr(self.presence, "concealed", False)))
        self.state = "closed"
        self.failed.emit(str(message))

    # --------------------------------------------------------------- frames
    def _on_session_changed(self, reason: str) -> None:
        if self.bridge is not None:
            self.bridge.on_session_changed(reason)
        self._invalidate()
        if not self.session.gesture_active:
            self.refresh_preset_previews()

    # ------------------------------------------------------- preset tile previews
    def refresh_preset_previews(self) -> None:
        """Queue the small renders on screen whose inputs changed (commits only): starting-point tiles and
        rendered cards of the current workspace. Served one per frame by ``on_frame``; nothing runs at rest."""
        if self.bridge is None or self.viewport is None or not self.capabilities.viewport:
            return
        workspace = next((w for w in self.session.schema.workspaces if w.id == self.bridge.workspace), None)
        if workspace is None:
            return
        import hashlib
        from ui.studio.session import write_path
        values = self.evaluation_values()
        baseline = self.session.baseline_values
        selected = self.bridge.selectedObject
        framing = next((f for f in self.framings if f.id == self.bridge.framingId), None)
        jobs = []
        for group, presets in self.session.schema.group_presets:
            if group not in workspace.groups:
                continue
            for preset in presets:
                variant = dict(values)
                for path, value in self.adapter.apply_preset(group, preset.id, baseline, values).items():
                    variant[path[0]] = write_path(variant[path[0]], tuple(path[1:]), value)
                jobs.append((f"{group}/{preset.id}", (selected, variant),
                             lambda g=group, p=preset.id, v=variant: self.adapter.preset_preview(g, p, v, selected)))
        for card in self.session.schema.cards:
            if not card.rendered or card.group not in workspace.groups:
                continue
            endpoint = self.bridge.card_endpoint(card.group)
            instant = (self.evaluator.fixture.id, round(float(self.transport.time), 4))
            jobs.append((f"card/{card.group}", (endpoint, framing, instant, values),
                         lambda g=card.group, e=endpoint: self.adapter.card_preview(g, values, e, framing,
                                                                                     self.evaluator)))
        queued = False
        for key, inputs, compute in jobs:
            signature = hashlib.sha1(repr(inputs if not isinstance(inputs[-1], dict)
                                          else inputs[:-1] + (sorted(inputs[-1].items()),)).encode()).hexdigest()
            if self._preview_done.get(key) == signature or self._preview_sent.get(key) == signature:
                continue
            self._preview_jobs = [job for job in self._preview_jobs if job[0] != key]
            self._preview_jobs.append((key, signature, compute))
            queued = True
        if queued and self.surface is not None:
            self.surface.request_frame()

    @property
    def previews_pending(self) -> bool:
        return bool(self._preview_jobs) or any(self._preview_done.get(k) != s for k, s in self._preview_sent.items())

    def _serve_preview(self) -> None:
        if not getattr(self, "_preview_jobs", None) or self.viewport.snapshot_queue:
            return
        if any(key not in self._preview_done or self._preview_done[key] != sig
               for key, sig in self._preview_sent.items()):
            return                                    # one in flight at a time
        key, signature, compute = self._preview_jobs.pop(0)
        try:
            spec = compute()
        except Exception:
            logger.exception("[STUDIO] Preview evaluation failed")
            spec = None
        if spec is None:
            self._preview_done[key] = signature
            return
        self._preview_sent[key] = signature
        self._preview_crops[key] = tuple(spec.crop)
        logical = (float(spec.logical[0]), float(spec.logical[1]))
        size = (int(round(logical[0] * 2)), int(round(logical[1] * 2)))
        self.viewport.request_snapshot(f"{key}|{signature}", spec.frame, size, logical, spec.extent, spec.style)

    def _on_snapshot(self, key: str, width: int, height: int, pixels: bytes) -> None:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QImage
        name, _sep, signature = key.partition("|")
        image = QImage(pixels, width, height, width * 4, QImage.Format.Format_RGBA8888).flipped(Qt.Orientation.Vertical)
        cx, cy, cw, ch = self._preview_crops.get(name, (0.0, 0.0, 1.0, 1.0))
        if (cx, cy, cw, ch) != (0.0, 0.0, 1.0, 1.0):
            image = image.copy(int(round(cx * width)), int(round(cy * height)),
                               max(1, int(round(cw * width))), max(1, int(round(ch * height))))
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        self._preview_done[name] = signature
        if self.bridge is not None:
            self.bridge.set_preview(name, "data:image/png;base64," + bytes(data.toBase64()).decode("ascii"))
        if self._preview_jobs and self.surface is not None:
            self.surface.request_frame()

    def _on_snapshot_failed(self, key: str, signature_text: str) -> None:
        name, _sep, signature = key.partition("|")
        self._preview_done[name] = signature           # keep the swatch; never retry in a loop
        if self._preview_jobs and self.surface is not None:
            self.surface.request_frame()

    def _on_snapshot_pending(self) -> None:
        if self.surface is not None:
            self.surface.request_frame()

    def _invalidate(self) -> None:
        self._eval_dirty = True
        if self.surface is not None:
            self.surface.request_frame()

    def evaluation_values(self) -> dict[str, Any]:
        values = self.session.values
        if self._pose:
            values = dict(values)
            values.update(self._pose)
        return values

    def on_frame(self) -> None:
        """Quick frame start (GUI thread): advance playback, evaluate at most once."""
        if self.state not in ("opening", "presented") or self.transport.stopped:
            return
        moved = self.transport.on_frame()
        if moved and self.bridge is not None:
            self.bridge.timeChanged.emit()
        if self._eval_dirty or moved:
            self._eval_dirty = False
            try:
                # A live gesture re-publishes the current instant; anything else is the exact replay.
                live = self.session.gesture_active or bool(self._pose)
                revision = (self.session.revision, tuple(sorted(self._pose.items())))
                frame = self.evaluator.evaluate(self.transport.time, self.evaluation_values(), exact=not live,
                                                revision=revision)
            except Exception as exc:
                logger.exception("[STUDIO] Preview evaluation failed")
                if self.bridge is not None:
                    self.bridge.set_viewport("error", f"Evaluation failed: {type(exc).__name__}: {exc}")
                return
            self.evaluations += 1
            self.last_frame = frame
            self.viewport.set_frame(frame)
            measure = getattr(self.evaluator, "measurements", None)
            if callable(measure) and self.bridge is not None:
                self.bridge.push_measurements(measure())
            self.refresh_handles()
        if getattr(self, "_preview_jobs", None):
            self._serve_preview()
        if self.transport.wants_frames:
            self.surface.request_frame()

    def _on_rendered(self, _serial: int) -> None:
        if self.bridge is not None:
            self.bridge.set_viewport("live")

    def _on_render_error(self, signature: str) -> None:
        if self.bridge is not None:
            self.bridge.set_viewport("error", signature)

    def _on_preparing(self) -> None:
        if self.bridge is not None:
            self.bridge.set_viewport("preparing")
        if self.surface is not None and self.state in ("opening", "presented"):
            self.surface.request_frame()

    # -------------------------------------------------------------- handles
    def refresh_handles(self) -> None:
        """Project the selected object's handles through the mode's camera (direct manipulation)."""
        if self.bridge is None or self.viewport is None or self.last_frame is None:
            return
        if not self.capabilities.as_map()["handles"]:
            return
        if self.bridge.workspace != self.session.schema.workspaces[0].id:
            if self.bridge.handles.get("handles"):
                self.bridge.set_handles({"outline": [], "handles": []})
            return
        framing = next((f for f in self.framings if f.id == self.bridge.framingId), None)
        try:
            state = self.adapter.scene_handles(self.last_frame, self.evaluation_values(), self.bridge.selectedObject,
                                               (self.viewport.width(), self.viewport.height()),
                                               framing.extent if framing else None,
                                               framing.style if framing else ())
        except Exception:
            logger.exception("[STUDIO] Handle projection failed")
            state = {"outline": [], "handles": []}
        self.bridge.set_handles(state)

    # -------------------------------------------------------------- framing
    def select_framing(self, framing_id: str) -> None:
        framing = next((f for f in self.framings if f.id == framing_id), None)
        if framing is None or self.viewport is None:
            return
        self.viewport.set_extent(framing.extent, framing.style)
        if self.bridge is not None:
            self.bridge.set_framing(framing.id)
        self._invalidate()
        self.refresh_preset_previews()            # rendered cards use the live framing

    def _choose_default_source(self) -> None:
        """Recorded music when the mode has a clip (analysed in the background), else its default input."""
        default = self.adapter.default_fixture(self.evaluator)
        if default:
            self.evaluator.select(default)
            self.transport.set_duration(self.evaluator.fixture.duration)
        clips = self.adapter.recorded_clips()
        if clips:
            self._auto_clip = clips[0].id
            self._load_clip(clips[0].id)

    # ------------------------------------------------------------ transport
    def set_playing(self, playing: bool) -> None:
        if playing:
            self.transport.play()
            if self.surface is not None:
                self.surface.request_frame()
        else:
            self.transport.pause()
        if self.bridge is not None:
            self.bridge.transportChanged.emit()

    def seek(self, seconds: float) -> None:
        self.transport.seek(seconds)
        if self.bridge is not None:
            self.bridge.timeChanged.emit()
        self._invalidate()

    def select_fixture(self, fixture_id: str, *, user: bool = True) -> None:
        if user:
            self._auto_clip = None          # the user's choice wins over the background default
        if fixture_id.startswith("clip:") and fixture_id not in {f.id for f in self.evaluator.fixtures()}:
            self._load_clip(fixture_id)
            return
        self.evaluator.select(fixture_id)
        self.transport.set_duration(self.evaluator.fixture.duration)
        self.transport.seek(0.0)
        if self.bridge is not None:
            self.bridge.clear_traces()
            self.bridge.transportChanged.emit()
            self.bridge.timeChanged.emit()
        self._invalidate()

    def clip_status(self, clip_id: str) -> str:
        if clip_id in self._clip_jobs:
            return "loading"
        if clip_id in self._clip_errors:
            return "error"
        return "available"

    def _load_clip(self, clip_id: str) -> None:
        if clip_id in self._clip_jobs:
            return
        clip = next((c for c in self.adapter.recorded_clips() if c.id == clip_id), None)
        loader = getattr(self.adapter, "start_clip_load", None)
        if clip is None or not callable(loader):
            self.bridge.notify("Recorded clips are not available for this mode")
            return

        def finished(result, error: str = "") -> None:
            self._clip_jobs.pop(clip_id, None)
            if self.state not in ("opening", "presented"):
                return
            if error:
                self._clip_errors[clip_id] = error
                self.bridge.notify(f"Clip analysis failed: {error}")
            else:
                self._clip_errors.pop(clip_id, None)
                self.evaluator.add_recorded(result)
                if self._auto_clip in (None, clip_id):
                    automatic = self._auto_clip == clip_id
                    self.select_fixture(clip_id, user=not automatic)
                    if automatic:
                        self.bridge.notify(f"Preview source: {clip.label} (recorded music)")
            self.bridge.transportChanged.emit()

        try:
            job = loader(clip, self.session.committed_values, finished)
            if job is not None:
                self._clip_jobs[clip_id] = job
        except Exception as exc:
            self._clip_errors[clip_id] = str(exc)
            self.bridge.notify(f"Clip analysis could not start: {exc}")
        self.bridge.transportChanged.emit()

    # --------------------------------------------------------------- camera
    def navigation(self):
        """The mode's camera navigation, or None when the mode declares no camera (2D / camera-less)."""
        caps = getattr(self, "capabilities", None)
        if caps is None or not (caps.camera and caps.viewport):
            return None
        return self.adapter.navigation()

    def _nudge(self, axis, delta: float) -> None:
        if axis is None:
            return
        value = float(self.evaluation_values()[axis.key]) + float(delta)
        self.set_pose(axis.key, min(axis.bounds[1], max(axis.bounds[0], value)))

    def orbit_by(self, dx: float, dy: float) -> None:
        nav = self.navigation()
        if nav is None:
            return
        span_h = (nav.orbit_h.bounds[1] - nav.orbit_h.bounds[0]) if nav.orbit_h else 0.
        span_v = (nav.orbit_v.bounds[1] - nav.orbit_v.bounds[0]) if nav.orbit_v else 0.
        self._nudge(nav.orbit_h, float(dx) * span_h / 900.0)
        self._nudge(nav.orbit_v, float(dy) * span_v / 600.0)

    def pan_by(self, dx: float, dy: float, width: float, height: float) -> None:
        nav = self.navigation()
        if nav is None:
            return
        self._nudge(nav.pan_x, -float(dx) / max(1.0, float(width)))
        self._nudge(nav.pan_y, float(dy) / max(1.0, float(height)))

    def zoom_by(self, steps: float, *, dolly: bool = False) -> None:
        """Wheel: ``steps`` > 0 zooms in. Multiplicative, bounded by the mode's camera range."""
        nav = self.navigation()
        if nav is None:
            return
        axis = nav.dolly if dolly else nav.zoom
        if axis is None:
            return
        factor = 1.12 ** float(steps)
        if not dolly and nav.zoom_inverts:
            factor = 1.0 / factor
        value = float(self.evaluation_values()[axis.key]) * factor
        self.set_pose(axis.key, min(axis.bounds[1], max(axis.bounds[0], value)))

    def view_readout(self) -> list:
        nav = self.navigation()
        if nav is None:
            return []
        values = self.evaluation_values()
        out = []
        for axis in (nav.zoom, nav.dolly, nav.orbit_h, nav.orbit_v):
            if axis is not None:
                value = float(values[axis.key])
                out.append({"label": axis.label, "value": value, "units": axis.units,
                            "changed": axis.key in self._pose})
        return out

    def keep_view(self) -> None:
        """Save what may be saved of the previewed view: ordinary lens settings always (undoable),
        the orbit only when the store's camera policy allows; dolly and pan stay preview views."""
        nav = self.navigation()
        if nav is None or not self._pose:
            return
        allowed = getattr(self.store, "camera_commit_allowed", lambda: False)()
        saving = {key: value for key, value in self._pose.items()
                  if key in nav.saved_on_keep or (allowed and key in nav.saved_with_camera_policy)}
        if saving:
            for key in saving:
                self._pose.pop(key)
            self.session.begin_gesture("Keep View")
            for key, value in saving.items():
                self.session.preview((key,), value)
            self.session.end_gesture()
        if self.bridge is not None:
            kept = ", ".join(sorted(k.rsplit("_", 1)[-1] for k in saving)) or "nothing"
            rest = "; dolly/pan stay preview views" if self._pose else ""
            policy = "" if allowed else " (orbit saves only with the preset's camera checkbox)"
            self.bridge.notify(f"Kept: {kept}{rest}{policy}")

    def set_pose(self, key: str, value: float) -> None:
        """A live view-pose value (navigation): rendered at once, never an ordinary committed edit."""
        self._pose[key] = float(value)
        if self.bridge is not None:
            self.bridge.on_session_changed("pose")
        self._invalidate()

    def end_orbit(self) -> None:
        """A finished navigation: the mode's orbit keys are saved only when the store's camera policy
        allows it; every other view-pose value stays a preview view."""
        if not self._pose:
            return
        self.refresh_preset_previews()            # rendered cards follow the finished view
        nav = self.navigation()
        orbit_keys = set(nav.saved_with_camera_policy) if nav is not None else set()
        allowed = getattr(self.store, "camera_commit_allowed", lambda: False)()
        saved = {key: value for key, value in self._pose.items() if key in orbit_keys} if allowed else {}
        if saved:
            for key in saved:
                self._pose.pop(key)
            self.session.begin_gesture("Orbit Camera")
            for key, value in saved.items():
                self.session.preview((key,), value)
            self.session.end_gesture()
        if self._pose and self.bridge is not None and not allowed:
            self.bridge.notify("Preview view: Keep View saves the lens; the orbit saves only with the "
                               "preset's camera checkbox")

    def reset_camera(self) -> None:
        self._pose = {}
        if self.bridge is not None:
            self.bridge.on_session_changed("pose")
        self._invalidate()
        self.refresh_preset_previews()

    # ---------------------------------------------------------------- close
    def close(self) -> None:
        if self.state not in ("opening", "presented"):
            return
        reveal = self.state == "presented" or bool(getattr(self.presence, "concealed", False))
        self._retire(reveal=reveal)
        self.state = "closed"
        self.closed.emit()

    def _on_surface_lost(self) -> None:
        """The window disappeared without our close (crash/destroy): recover Settings."""
        if self.state in ("opening", "presented"):
            self.surface = None
            self.close()

    def _retire(self, *, reveal: bool) -> None:
        """Retire in a fixed order and record each step's cost (``close_timings``, milliseconds)."""
        import time
        timings: dict[str, float] = {}
        mark = time.perf_counter()

        def step(name: str) -> None:
            nonlocal mark
            now = time.perf_counter()
            timings[name] = round((now - mark) * 1000.0, 2)
            mark = now

        session = self.session
        if session is not None:
            session.cancel_gesture()          # an unaccepted drag is not a saved edit
        step("gesture")
        self.transport.stop()
        step("transport")
        for job in tuple(self._clip_jobs.values()):
            cancel = getattr(job, "cancel", None)
            if callable(cancel):
                cancel()
        self._clip_jobs.clear()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        step("jobs")
        surface, self.surface = self.surface, None
        if surface is not None:
            for signal, slot in ((surface.frameStarted, self.on_frame), (surface.presented, self._on_presented),
                                 (surface.closeRequested, self.close), (surface.lost, self._on_surface_lost),
                                 (surface.failed, self._fail)):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            try:
                surface.retire()
            except Exception:
                logger.exception("[STUDIO] Studio surface retirement failed")
        self.viewport = None
        step("surface")
        if self.evaluator is not None:
            self.evaluator.release()
        try:
            self.adapter.release()
        except Exception:
            logger.exception("[STUDIO] Adapter release failed")
        self._preview_jobs, self._preview_sent, self._preview_done = [], {}, {}
        if StudioController._active is self:
            StudioController._active = None
        step("evaluator")
        if reveal:
            try:
                self.presence.reveal()
            except Exception:
                logger.exception("[STUDIO] Settings reveal failed")
        step("settings")
        timings["total"] = round(sum(timings.values()), 2)
        self.close_timings = timings
        logger.info("[STUDIO] retire %s", " ".join(f"{k}={v}ms" for k, v in timings.items()))


__all__ = ["StudioBridge", "StudioController"]

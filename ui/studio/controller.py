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

import time
from typing import Any, Callable, ClassVar, Mapping

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtQml import QQmlPropertyMap

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


class StudioValueMap(QQmlPropertyMap):
    """The inspector's displayed values, one QML property per property id.

    Each key notifies on its own, so a value that changes re-evaluates only the bindings that read that key: a
    drag of one slider never re-binds the whole inspector. Python reads it like a mapping."""

    def __init__(self, parent: QObject) -> None:
        import warnings
        with warnings.catch_warnings():
            # PySide binds only QQmlPropertyMap(QObject *parent), which Qt marks deprecated for subclasses.
            warnings.simplefilter("ignore", DeprecationWarning)
            super().__init__(parent)
        self._shown: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        return self._shown[key]

    def __contains__(self, key: object) -> bool:
        return key in self._shown

    def get(self, key: str, default: Any = None) -> Any:
        return self._shown.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._shown)

    def publish(self, values: Mapping[str, Any], *, only: frozenset[str] | None = None) -> int:
        """Show ``values`` (every key, or just ``only``); a key absent from ``values`` reads as undefined.
        Only keys whose value differs notify. Returns how many did."""
        keys = set(values) | set(self._shown) if only is None else only
        changed = 0
        for key in keys:
            if key in values:
                value = values[key]
                if key in self._shown and self._shown[key] == value:
                    continue
                self._shown[key] = value
                self.insert(key, value)
                changed += 1
            elif key in self._shown:
                del self._shown[key]
                self.clear(key)
                changed += 1
        return changed


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
    busyChanged = Signal()

    def __init__(self, controller: "StudioController") -> None:
        super().__init__()
        self._c = controller
        schema = controller.session.schema
        self._schema = schema
        self._workspace = schema.workspaces[0].id
        objects = controller.adapter.scene_objects(controller.session.values)
        self._selected = objects[0].id if objects else ""
        self._inspector: list[dict] = []
        self._values = StudioValueMap(self)
        # Previews a drag hands over between frames: (property id, endpoint) -> (kind, payload). The newest
        # replaces the older one; ``apply_pending_previews`` applies them once, at the next frame start.
        self._pending: dict[tuple[str, int], tuple[str, Any]] = {}
        self.previews_applied = 0
        self._when_keys = schema.condition_keys
        self._objects: list[dict] = []
        self._viewport_status = "preparing"
        self._viewport_error = ""
        self._busy = ""
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
        self.brush = None
        if controller.capabilities.as_map().get("brush"):
            target = controller.adapter.brush_target()
            if target is not None:
                from ui.studio.brush import StudioBrush
                self.brush = StudioBrush(target, controller.session, controller.brush_scene,
                                         controller.request_preview_frame)
        self._rebuild_objects()
        self._rebuild_inspector()
        self._rebuild_values()

    # ------------------------------------------------------------ header
    def _title(self) -> str:
        return self._schema.title

    def _preset(self) -> str:
        return self._c.session.preset_label

    def _presets(self) -> list:
        """The preset slots the header's dropdown offers (empty: the store cannot switch presets)."""
        store = self._c.store
        names = getattr(store, "presets", None)
        if not callable(names):
            return []
        current = getattr(store, "preset_index", lambda: -1)()
        listed = list(names())
        return [{"index": i, "label": name, "current": i == current, "custom": i == len(listed) - 1}
                for i, name in enumerate(listed)]

    def _save_preset_target(self) -> str:
        reader = getattr(self._c.store, "save_target_label", None)
        return str(reader()) if callable(reader) else ""

    savePresetTarget = Property(str, _save_preset_target, notify=headerChanged)      # "": not offered

    @Slot(int)
    def selectPreset(self, index: int) -> None:
        self._c.select_preset(int(index))

    def _include_view(self):
        reader = getattr(self._c.store, "include_view", None)
        value = reader() if callable(reader) else None
        return -1 if value is None else int(bool(value))

    includeView = Property(int, _include_view, notify=headerChanged)      # -1: not offered

    @Slot(bool)
    def setIncludeView(self, include: bool) -> None:
        setter = getattr(self._c.store, "set_include_view", None)
        if callable(setter):
            setter(bool(include))
            self.headerChanged.emit()

    @Slot()
    def moveToCustom(self) -> None:
        action = getattr(self._c.store, "move_to_custom", None)
        if callable(action):
            self._c.store_switched(action)

    @Slot()
    def saveToPreset(self) -> None:
        """Save To <Preset>: the store confirms, writes the curated preset's file and reloads presets."""
        action = getattr(self._c.store, "save_to_preset", None)
        if not callable(action):
            return
        self._c.session.cancel_gesture()
        try:
            notice = action()
        except Exception as exc:
            logger.exception("[STUDIO] Save To Preset failed")
            notice = f"Could not save the preset: {exc}"
        self.headerChanged.emit()
        if notice:
            self.notify(notice)

    canSave = Property(bool, lambda self: callable(getattr(self._c.store, "save_current", None)),
                       notify=headerChanged)
    canSaveCamera = Property(bool, lambda self: callable(getattr(self._c.store, "save_camera", None)),
                             notify=headerChanged)

    @Slot()
    def saveCurrent(self) -> None:
        self._save_action("save_current")

    @Slot()
    def saveCamera(self) -> None:
        self._save_action("save_camera", camera=True)

    def _save_action(self, method: str, *, camera: bool = False) -> None:
        action = getattr(self._c.store, method, None)
        if not callable(action):
            self.notify("Camera saving is not available for this store" if camera
                        else "Saving is not available for this store")
            return
        self._c.session.end_gesture()
        try:
            values = self._c.evaluation_values() if camera else None
            notice = action(values) if camera else action()
            if camera and notice:
                from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys
                from core.settings.framed_camera import spec_for_mode
                keys = set(get_visualizer_view_pose_keys(self._c.adapter.mode_id))
                spec = spec_for_mode(self._c.adapter.mode_id)
                if spec is not None:
                    keys.update((spec.key("camera_position"), spec.key("camera_fov")))
                self._c.session.accept_saved_values({key: values[key] for key in keys})
                for key in keys:
                    self._c._pose.pop(key, None)
        except Exception as exc:
            logger.exception("[STUDIO] %s failed", method)
            notice = f"Could not save: {exc}"
        self.headerChanged.emit()
        if notice:
            self.notify(notice)

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
    presets = Property("QVariantList", _presets, notify=headerChanged)
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

    @Slot(int)
    def stepObject(self, step: int) -> None:
        """Select the previous / next scene object (the per-object panel's header arrows), wrapping."""
        ids = [o["id"] for o in self._objects]
        if not ids:
            return
        index = ids.index(self._selected) if self._selected in ids else 0
        self.selectObject(ids[(index + int(step)) % len(ids)])

    # ----------------------------------------------------------- frame copy
    frameCopied = Signal(str)

    @Slot()
    def copyFrame(self) -> None:
        """Copy the presented frame (production render, no overlays) to the clipboard as an image."""
        self._c.copy_frame()

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
                               "group": group, "objectScoped": "{object}" in group,
                               "actions": self._actions(dict(self._schema.group_actions).get(group, ()))})
        self._inspector = groups
        self._columns = self._dashboard_columns(workspace, groups)
        self.inspectorChanged.emit()

    def _dashboard_columns(self, workspace, groups: list) -> list:
        """The workspace's panels under the viewport. Every shown group lands in exactly one panel: groups a
        column spec does not name join the last group panel (nothing silently disappears)."""
        from ui.studio.schema import RESPONSE_PANEL
        has_response = self._schema.response is not None
        specs = list(workspace.columns)
        if not specs:
            keys = [g["group"] for g in groups]
            count = max(1, min(3, len(keys)))
            size = -(-len(keys) // count) if keys else 0
            specs = [type("Auto", (), {"title": workspace.title, "groups": tuple(keys[i:i + size]), "icon": workspace.icon,
                                       "subtitle": "", "weight": 1.0})() for i in range(0, max(1, len(keys)), max(1, size))]
        by_key = {g["group"]: g for g in groups}
        placed: set = set()
        columns = []
        for spec in specs:
            if RESPONSE_PANEL in spec.groups:
                if has_response:
                    columns.append({"kind": "response", "title": spec.title, "subtitle": spec.subtitle,
                                    "icon": spec.icon, "weight": float(spec.weight), "groups": []})
                continue
            chosen = [by_key[key] for key in spec.groups if key in by_key]
            placed.update(g["group"] for g in chosen)
            columns.append({"kind": "groups", "title": spec.title, "subtitle": spec.subtitle, "icon": spec.icon,
                            "weight": float(spec.weight), "groups": chosen})
        leftover = [g for g in groups if g["group"] not in placed]
        if leftover:
            target = next((c for c in reversed(columns) if c["kind"] == "groups"), None)
            if target is None:
                target = {"kind": "groups", "title": workspace.title, "subtitle": "", "icon": workspace.icon,
                          "weight": 1.0, "groups": []}
                columns.append(target)
            target["groups"] = target["groups"] + leftover
        return [c for c in columns if c["kind"] == "response" or c["groups"]]

    def _inspector_columns(self) -> list:
        return getattr(self, "_columns", [])

    inspectorColumns = Property("QVariantList", _inspector_columns, notify=inspectorChanged)

    def _inspector_groups(self) -> list:
        return self._inspector

    inspector = Property("QVariantList", _inspector_groups, notify=inspectorChanged)

    @staticmethod
    def _displayed(prop: StudioProperty, values: Mapping[str, Any]) -> tuple[bool, Any]:
        """(held, display value) of one property under ``values``."""
        try:
            value = read_path(values, prop.path)
        except (KeyError, IndexError, TypeError):
            return False, None
        if prop.instrument == QUIET_PEAK:
            return True, [float(value[0]), float(value[1])]
        if prop.instrument in (SCALAR, COUNT):
            return True, float(value)
        if prop.instrument == SWITCH:
            return True, bool(value)
        if prop.instrument == CHOICE:
            if prop.choice_values:
                return True, next((c for c, v in zip(prop.choices, prop.choice_values) if v == value), str(value))
            return True, str(value)
        if prop.instrument == COLOUR:
            return True, _colour_hex(prop, value)
        if prop.instrument == GRADIENT:
            return True, _gradient_display(prop, value)
        return False, None

    def _rebuild_values(self) -> None:
        values = self._c.evaluation_values()
        out: dict[str, Any] = {}
        for prop in self._schema.properties:
            held, shown = self._displayed(prop, values)
            if held:
                out[prop.id] = shown
        self._values.publish(out)
        self._refresh_condition_hidden(values, out)
        self._active_presets = self._preset_state(values)
        self.valuesChanged.emit()

    def _refresh_condition_hidden(self, values: Mapping[str, Any], shown: Mapping[str, Any]) -> None:
        # A property whose value the current values do not hold (an absent optional element, such as a curve node
        # slot the profile does not use) is not shown.
        from ui.studio.schema import condition_hidden
        hidden = {prop.id: True for prop in self._schema.properties if prop.id not in shown}
        hidden.update(condition_hidden(self._schema, values))
        self._condition_hidden = hidden

    def _update_live_values(self, keys: frozenset[str]) -> None:
        """A live gesture changed ``keys``: re-show only the properties stored under them (each notifies on its
        own). The whole map, the starting-point state and the condition map wait for the gesture's end, unless a
        changed key decides another property's visibility."""
        values = self._c.evaluation_values()
        out: dict[str, Any] = {}
        only = set()
        for prop in self._schema.properties:
            if prop.path[0] not in keys:
                continue
            only.add(prop.id)
            held, shown = self._displayed(prop, values)
            if held:
                out[prop.id] = shown
        self._values.publish(out, only=frozenset(only))
        if keys & self._when_keys:
            self._refresh_condition_hidden(values, self._values.as_dict())
            self.valuesChanged.emit()

    def _value_map(self) -> QObject:
        return self._values

    def _hidden_by_condition(self) -> dict:
        return getattr(self, "_condition_hidden", {})

    conditionHidden = Property("QVariantMap", _hidden_by_condition, notify=valuesChanged)

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
        self._queue_preview(property_id, 0, "gradient", nodes)

    def _apply_gradient(self, property_id: str, nodes: str) -> None:
        prop = self._schema.find(property_id)
        if not self._c.session.gesture_active:
            self._c.session.begin_gesture(prop.label)
        previous = read_path(self._c.session.values, prop.path)
        self._c.session.preview(prop.path, _gradient_value(prop, nodes, previous))

    # ---------------------------------------------------- coalesced drag previews
    def _queue_preview(self, property_id: str, endpoint: int, kind: str, payload: Any) -> None:
        """A drag's newest value: kept until the next frame start, replacing any older one for the same target.
        However many moves arrive between two frames, one preview is applied per frame (latest wins)."""
        key = (str(property_id), int(endpoint))
        self._pending.pop(key, None)
        self._pending[key] = (kind, payload)
        self._c.request_preview_frame()

    @property
    def pending_previews(self) -> int:
        return len(self._pending)

    def apply_pending_previews(self) -> None:
        """Frame start (and before anything that ends or replaces the gesture): apply the held previews."""
        self._flush_brush()
        while self._pending:
            (property_id, endpoint), (kind, payload) = next(iter(self._pending.items()))
            del self._pending[(property_id, endpoint)]
            self.previews_applied += 1
            if kind == "value":
                self._guard(lambda: self._apply_value(property_id, endpoint, payload))
            elif kind == "colour":
                self._guard(lambda: self._apply_colour(property_id, payload))
            else:
                self._guard(lambda: self._apply_gradient(property_id, payload))

    def drop_pending_previews(self) -> None:
        self._pending.clear()
        if self.brush is not None:
            self.brush.cancel()

    # --------------------------------------------------------- the terrain brush (shared instrument)
    brushChanged = Signal()
    brushCursorChanged = Signal()

    def _brush_map(self) -> dict:
        return self.brush.as_map() if self.brush is not None else {}

    def _brush_cursor(self) -> list:
        return list(self.brush.cursor) if self.brush is not None else []

    brushState = Property("QVariantMap", _brush_map, notify=brushChanged)
    brushCursor = Property("QVariantList", _brush_cursor, notify=brushCursorChanged)

    def _flush_brush(self) -> None:
        brush = self.brush
        if brush is None:
            return
        cursor = brush.cursor
        self._guard(brush.flush)
        if brush.cursor is not cursor:
            self.brushCursorChanged.emit()

    @Slot(bool)
    def setBrushActive(self, active: bool) -> None:
        if self.brush is None:
            return
        self.brush.set_active(bool(active))
        self.brushChanged.emit()
        self.brushCursorChanged.emit()

    @Slot(str, "QVariant")
    def setBrushValue(self, name: str, value: Any) -> None:
        """A brush setting (mode, radius, strength, falloff, flatten_height): tool state, never saved."""
        if self.brush is not None and self.brush.set_value(str(name), value):
            self.brushChanged.emit()

    @Slot(float, float)
    def brushPress(self, x: float, y: float) -> None:
        """A stroke starts at (x, y) in presented-frame pixels; the paint follows at the next frame start."""
        if self.brush is None or not self.brush.active:
            return
        if self._c.session.gesture_active:
            self.apply_pending_previews()
            self._guard(self._c.session.end_gesture)       # another gesture ends before a stroke starts
        self.brush.press((x, y))
        self.brushChanged.emit()

    @Slot(float, float)
    def brushMove(self, x: float, y: float) -> None:
        if self.brush is not None and self.brush.active:
            self.brush.move((x, y))

    @Slot(float, float)
    def brushHover(self, x: float, y: float) -> None:
        if self.brush is not None and self.brush.active:
            self.brush.hover((x, y))

    @Slot()
    def brushLeave(self) -> None:
        if self.brush is not None:
            self.brush.hover(None)
            self.brushCursorChanged.emit()

    @Slot()
    def brushRelease(self) -> None:
        """The stroke ends: the held points are painted and the record is saved once (one undo entry)."""
        if self.brush is None:
            return
        self._guard(self.brush.release)
        self.brushChanged.emit()
        self.brushCursorChanged.emit()

    @Slot()
    def brushCancel(self) -> None:
        if self.brush is None:
            return
        self.brush.cancel()
        self.brushChanged.emit()

    @Slot(str, str)
    def commitGradient(self, property_id: str, nodes: str) -> None:
        self.apply_pending_previews()

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

    values = Property(QObject, _value_map, constant=True)

    def on_session_changed(self, reason: str) -> None:
        if reason == "preview":
            self._update_live_values(frozenset(self._c.session.preview_keys))
            return
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
        if prop.instrument == CHOICE and prop.choice_values:
            if value in prop.choices:
                return prop.choice_values[prop.choices.index(value)]
            raise ValueError(f"{prop.label} has no choice {value!r}")
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
        self._queue_preview(property_id, endpoint, "value", float(value))

    def _apply_value(self, property_id: str, endpoint: int, value: float) -> None:
        prop, path = self._prop_path(property_id, endpoint)
        if prop.view_pose:
            self._c.set_pose(prop.path[0], self._coerce(prop, value))
            return
        self._c.session.preview(path, self._coerce(prop, value))

    @Slot()
    def endEdit(self) -> None:
        self.apply_pending_previews()          # the release position is the committed one
        if getattr(self, "_pose_edit", False):
            self._pose_edit = False
            self._guard(self._c.end_orbit)
            return
        self._guard(self._c.session.end_gesture)

    @Slot(str, str)
    def previewColour(self, property_id: str, hex_text: str) -> None:
        """Live colour preview while a picker is dragged (one gesture; endEdit commits it)."""
        self._queue_preview(property_id, 0, "colour", str(hex_text))

    def _apply_colour(self, property_id: str, hex_text: str) -> None:
        prop = self._schema.find(property_id)
        if not self._c.session.gesture_active:
            self._c.session.begin_gesture(f"Set {prop.label}")
        self._c.session.preview(prop.path, self._coerce(prop, hex_text))

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
        self.drop_pending_previews()
        self._c.session.cancel_gesture()

    @Slot(str, int, "QVariant")
    def commitValue(self, property_id: str, endpoint: int, value: Any) -> None:
        self.apply_pending_previews()
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
        self.apply_pending_previews()
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
        self.drop_pending_previews()
        self._guard(self._c.session.undo)

    @Slot()
    def redo(self) -> None:
        self.drop_pending_previews()
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
        self.requestCloseFrom("close request")

    @Slot(str)
    def requestCloseFrom(self, source: str) -> None:
        """A close asked for by the shell; ``source`` names the path (the Close button, Esc) for the log."""
        self.close_source = str(source) or "close request"
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
    def _pending_fixture(self) -> str:
        return self._c.pending_source_label()

    fixtureId = Property(str, _fixture_id, notify=transportChanged)
    fixtures = Property("QVariantList", _fixtures, notify=transportChanged)
    # The recorded clip asked for and still analysing ("" when none): the source picker names it at once.
    pendingFixture = Property(str, _pending_fixture, notify=transportChanged)

    def _preview_busy(self) -> str:
        return self._busy

    # What the preview is waiting for ("" when live): an analysis in the background, or a change being applied.
    previewBusy = Property(str, _preview_busy, notify=busyChanged)

    def set_busy(self, text: str) -> None:
        if text != self._busy:
            self._busy = text
            self.busyChanged.emit()

    def _timeline(self) -> list:
        shape = getattr(self._c.evaluator, "timeline", None)
        if not callable(shape):
            return []
        # An evaluator whose overview changes while a fixture stays selected (its analysis landed in the
        # background) says so through ``timeline_revision``.
        key = (self._c.evaluator.fixture.id, getattr(self._c.evaluator, "timeline_revision", 0))
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
        label = prop.label
        if self._schema.row_label is not None:
            try:
                label = self._schema.row_label(prop, self._c.session.values) or prop.label
            except (KeyError, IndexError, TypeError, ValueError):
                label = prop.label
        return {"id": prop.id, "label": label, "instrument": prop.instrument,
                "min": float(prop.minimum), "max": float(prop.maximum), "decimals": int(prop.decimals),
                "units": prop.units, "choices": list(prop.choices), "tooltip": prop.tooltip,
                "quietMeaning": prop.quiet_meaning, "peakMeaning": prop.peak_meaning, "integer": bool(prop.integer),
                "notes": list(prop.choice_notes), "icon": prop.icon, "actions": self._actions(prop.actions),
                "releaseOnly": prop.path[0] in self._c.release_only_keys}

    # ------------------------------------------------------------ structural actions
    def _actions(self, actions) -> list:
        """Action buttons, each enabled only while the adapter can admit it under the current values."""
        values = self._c.session.values
        return [{"id": a.id, "label": a.label, "icon": a.icon, "tooltip": a.tooltip,
                 "enabled": self._c.adapter.structure_edit(a.id, values) is not None} for a in actions]

    @Slot(str)
    def runAction(self, action_id: str) -> None:
        """Run a structural edit (add / remove / reorder) as ONE undoable edit through the session."""
        edit = self._c.adapter.structure_edit(str(action_id), self._c.session.values)
        if edit is None:
            self.notify("Not available now")
            return
        label, changes = edit
        self._guard(lambda: self._c.session.set_many(dict(changes), label))

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

    def _message_action_label(self) -> str:
        return getattr(self, "_message_action", ("", None))[0]

    messageAction = Property(str, _message_action_label, notify=messageChanged)     # "" : the notice has no action

    def notify(self, text: str, action: str = "", callback: Callable[[], Any] | None = None) -> None:
        """Show a notice; with ``action`` the notice offers one button that runs ``callback`` (e.g. Retry)."""
        self._message = str(text)
        self._message_action = (str(action), callback) if action and callback is not None else ("", None)
        self.messageChanged.emit()

    @Slot()
    def runMessageAction(self) -> None:
        _label, callback = getattr(self, "_message_action", ("", None))
        self.notify("")
        if callback is not None:
            callback()

    @Slot()
    def dismissMessage(self) -> None:
        self.notify("")

    def _theme_map(self) -> dict:
        return self._theme

    theme = Property("QVariantMap", _theme_map, notify=themeChanged)

    def set_theme(self, theme: Mapping[str, str]) -> None:
        self._theme = dict(theme)
        self.themeChanged.emit()

    # ------------------------------------------------------------ window chrome
    # The shell's custom title bar and edges act on the window through the surface (a hidden surface ignores them).
    windowStateChanged = Signal()

    def _surface_call(self, name: str, *args) -> Any:
        method = getattr(self._c.surface, name, None)
        return method(*args) if callable(method) else None

    def _window_maximized(self) -> bool:
        return bool(getattr(self._c.surface, "maximized", False))

    windowMaximized = Property(bool, _window_maximized, notify=windowStateChanged)

    @Slot()
    def startWindowMove(self) -> None:
        self._surface_call("start_move")
        self.windowStateChanged.emit()          # a drag from maximised restores first

    @Slot(int)
    def startWindowResize(self, edges: int) -> None:
        self._surface_call("start_resize", int(edges))

    @Slot()
    def toggleMaximize(self) -> None:
        self._surface_call("toggle_maximize")
        self.windowStateChanged.emit()

    @Slot()
    def minimizeWindow(self) -> None:
        self._surface_call("minimize")


class StudioController(QObject):
    """One authoring session from open to the Settings reveal."""

    presented = Signal()
    closed = Signal()
    failed = Signal(str)

    _active: ClassVar["StudioController | None"] = None
    # GUI-thread time one evaluation may spend on an exact replay (the rest of a ~16 ms frame stays free).
    EVALUATION_BUDGET_S: ClassVar[float] = 0.008
    # A replay converging longer than this many frames says so ("Updating…"); a click's one-frame live-applied
    # frame does not flash the notice.
    APPLYING_AFTER_FRAMES: ClassVar[int] = 3
    # A preview that should be moving (playing, or applying a change) and showed no new frame for longer than this
    # logs the gap and its cause (``logs/screensaver_studio.log``).
    PREVIEW_GAP_LOG_S: ClassVar[float] = 0.25
    # A change whose replay took longer than this (or converged over frames, or restarted the pass) is logged.
    REPLAY_LOG_S: ClassVar[float] = 0.03

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
        self._clip_analysis: dict[str, str] = {}   # clip id -> the analysis values its loaded inputs were made under
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
        self._source_notice = ""            # the notice naming the automatically chosen source, while it is shown
        self._wanted_source: str | None = None
        self._failure_shown = ""
        self._converging_frames = 0         # consecutive evaluations an exact replay has been converging
        # Sidecar log (``logs/screensaver_studio.log``) of what the preview waited for: the change being replayed
        # (its trigger, start, frames and whether it restarted the pass), the last fresh preview frame while the
        # preview should be moving, and when each clip analysis started. Read on the frame and job edges only.
        self._replay_reason: str | None = None
        self._replay_started = 0.0
        self._replay_frames = 0
        self._replay_restarted = False
        self._last_fresh_at: float | None = None
        self._clip_job_started: dict[str, float] = {}

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
        import time
        self._opened_at = time.perf_counter()
        logger.info("[STUDIO] open mode=%s", self.adapter.mode_id)
        try:
            self.capabilities = self.adapter.capabilities()
            self.session = StudioEditSession(self.adapter.schema(), self.store)
            self.evaluator = self.adapter.create_evaluator()
            budget = getattr(self.evaluator, "set_frame_budget", None)
            if callable(budget):
                # An evaluator whose exact replay can outgrow a frame spreads it over frames within this budget.
                budget(self.EVALUATION_BUDGET_S)
            notify = getattr(self.evaluator, "set_invalidate", None)
            if callable(notify):
                # An evaluator that analyses in the background asks for a fresh evaluation when its result lands.
                notify(self._on_evaluator_changed)
            environment = getattr(self.evaluator, "set_environment", None)
            source = getattr(self.store, "environment_image", None)
            if callable(environment) and callable(source):
                # A reflecting mode mirrors what the saver would show (production reflects the photograph).
                try:
                    environment(source())
                except Exception:
                    logger.exception("[STUDIO] No reflection environment")
            self.transport.set_duration(self.evaluator.fixture.duration)
            self._release_only = None            # derived from this session's evaluator
            self.bridge = StudioBridge(self)
            if self._theme_provider is not None:
                self.bridge.set_theme(self._theme_provider())
            self._unsubscribe = self.session.subscribe(self._on_session_changed)
            self.bridge.closeRequested.connect(self._on_bridge_close)
            self.surface = self._surface_factory(self)
            self.viewport = self.surface.viewport
            self.viewport.rendered.connect(self._on_rendered, Qt.ConnectionType.QueuedConnection)
            self.viewport.renderError.connect(self._on_render_error, Qt.ConnectionType.QueuedConnection)
            self.viewport.preparing.connect(self._on_preparing, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotReady.connect(self._on_snapshot, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotFailed.connect(self._on_snapshot_failed, Qt.ConnectionType.QueuedConnection)
            self.viewport.snapshotPending.connect(self._on_snapshot_pending, Qt.ConnectionType.QueuedConnection)
            # Handles are projected in presented-frame pixels: a resized frame (window, expanded viewport,
            # a filling framing) re-projects them.
            self.viewport.widthChanged.connect(self._on_viewport_resized, Qt.ConnectionType.QueuedConnection)
            self.viewport.heightChanged.connect(self._on_viewport_resized, Qt.ConnectionType.QueuedConnection)
            self._preview_jobs = []
            self._preview_sent = {}
            self._preview_done = {}
            self.surface.frameStarted.connect(self.on_frame)
            self.surface.presented.connect(self._on_presented)
            self.surface.closeRequested.connect(self._on_window_close)
            self.surface.lost.connect(self._on_surface_lost)
            self.surface.failed.connect(self._fail)
            if self.capabilities.viewport:
                card_extent = getattr(self.store, "card_extent", lambda: None)()
                card_style = getattr(self.store, "card_style", lambda: None)()
                self.framings = tuple(self.adapter.framings(card_extent, card_style))
                if self.framings:
                    wanted = self.adapter.default_framing()
                    self.select_framing(next((f.id for f in self.framings if f.id == wanted), self.framings[0].id))
            else:
                # Inspector-only Studio: the item never gets a scene-graph node, so no renderer exists.
                self.viewport.setVisible(False)
                self.framings = ()
                self.bridge.set_viewport("none")
            self._choose_default_source()
            self.surface.show()
            logger.info("[STUDIO] shown mode=%s preset=%s", self.adapter.mode_id, self.session.preset_label)
        except Exception as exc:
            logger.exception("[STUDIO] Studio failed to open")
            self._fail(f"{type(exc).__name__}: {exc}")
            return False
        return True

    def store_switched(self, action: Callable[[], Any]) -> None:
        """Run a store action that changes the preset slot, then re-open the session on the result."""
        self.session.cancel_gesture()
        try:
            action()
        except Exception as exc:
            logger.exception("[STUDIO] Preset action failed")
            if self.bridge is not None:
                self.bridge.notify(f"Could not change preset: {exc}")
            return
        self._pose = {}
        self.session.hydrate()
        if self.bridge is not None:
            self.bridge.notify(f"Preset: {self.session.preset_label}")
        self._invalidate()

    def select_preset(self, index: int) -> None:
        """Switch the edited preset through the store (Settings' own preset authority), then re-open the
        session on it. Edits on Custom are already saved (and Custom is snapshotted before a curated preset is
        applied); unsaved edits of a curated preset are settled first with the store's prompt (staying cancels the
        switch). An unfinished drag is dropped."""
        select = getattr(self.store, "select_preset", None)
        if not callable(select) or self.session is None:
            return
        current = getattr(self.store, "preset_index", lambda: -1)()
        if int(index) == int(current):
            return
        self.session.cancel_gesture()
        if not self.settle_draft(interactive=True):     # unsaved edits of the current preset: ask first
            return
        try:
            select(int(index))
        except Exception as exc:
            logger.exception("[STUDIO] Preset switch failed")
            if self.bridge is not None:
                self.bridge.notify(f"Could not switch preset: {exc}")
            return
        self._pose = {}
        self.session.hydrate()
        if self.bridge is not None:
            self.bridge.notify(f"Preset: {self.session.preset_label}")
        self._invalidate()

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
        if not self.settle_draft(interactive=True):     # the next mode's page replaces this one's widgets
            return
        try:
            adapter, store = self._mode_switcher(mode_id)
        except Exception as exc:
            logger.exception("[STUDIO] Mode switch failed")
            if self.bridge is not None:
                self.bridge.notify(f"Could not switch mode: {exc}")
            return
        logger.info("[STUDIO] mode switch %s -> %s", self.adapter.mode_id, mode_id)
        self._retire(reveal=False)          # Settings stays concealed for the next session
        self.adapter, self.store = adapter, store
        self.transport = StudioTransport()
        self._pose = {}
        self._clip_errors.clear()
        self._failure_shown = ""
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
        import time
        logger.info("[STUDIO] presented mode=%s first frame %.0f ms after open", self.adapter.mode_id,
                    (time.perf_counter() - getattr(self, "_opened_at", time.perf_counter())) * 1000.0)
        try:
            self.presence.conceal()          # no-op when a mode switch kept Settings concealed
        except Exception:
            logger.exception("[STUDIO] Could not conceal Settings; it stays visible")
        self.presented.emit()

    def _fail(self, message: str) -> None:
        """Opening or presenting failed: retire everything, keep/restore Settings, report."""
        logger.error("[STUDIO] failed mode=%s state=%s: %s", self.adapter.mode_id, self.state, message)
        try:
            self._retire(reveal=self.state == "presented" or bool(getattr(self.presence, "concealed", False)))
        finally:
            self.state = "closed"
            if StudioController._active is self:
                StudioController._active = None
            self.failed.emit(str(message))

    # --------------------------------------------------------------- frames
    def _on_session_changed(self, reason: str) -> None:
        if reason in ("commit", "undo", "redo"):
            session = self.session
            label = session.redo_label if reason == "undo" else session.undo_label
            logger.info("[STUDIO] %s mode=%s edit=%r saves=%d preset=%s", reason, self.adapter.mode_id, label,
                        session.commit_count, session.preset_label)
        if self.bridge is not None:
            self.bridge.on_session_changed(reason)
        if reason in ("commit", "undo", "redo"):
            self._note_replay(f"{reason} {label!r}")
        self._invalidate()
        if not self.session.gesture_active:
            self.refresh_preset_previews()
            if reason in ("commit", "undo", "redo", "hydrate"):
                self._refresh_clip_analysis()

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
        if key == getattr(self, "_copy_key", None):
            self._copy_key = None
            self._deliver_copied_frame(width, height, pixels)
            return
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
        if key == getattr(self, "_copy_key", None):
            self._copy_key = None
            if self.bridge is not None:
                self.bridge.notify("Could not copy the frame")
            return
        name, _sep, signature = key.partition("|")
        self._preview_done[name] = signature           # keep the swatch; never retry in a loop
        if self._preview_jobs and self.surface is not None:
            self.surface.request_frame()

    def _on_snapshot_pending(self) -> None:
        if self.surface is not None:
            self.surface.request_frame()

    def _on_evaluator_changed(self) -> None:
        if self.state not in ("opening", "presented"):
            return
        logger.info("[STUDIO] analysis landed mode=%s source=%s", self.adapter.mode_id, self.evaluator.fixture.id)
        self._note_replay("analysis landed")
        self._invalidate()
        if self.bridge is not None:
            self.bridge.transportChanged.emit()
        self._refresh_busy()

    def _invalidate(self) -> None:
        self._eval_dirty = True
        if self.surface is not None:
            self.surface.request_frame()

    def request_preview_frame(self) -> None:
        """A drag handed over a new value: the next frame start applies it (no timer, no per-move work)."""
        if self.surface is not None:
            self.surface.request_frame()

    @property
    def release_only_keys(self) -> frozenset[str]:
        """Keys whose edits the preview follows only on release (an evaluator that re-analyses for them, such
        as the engine-answer modes' engine-owned keys: the analysis runs once, when the gesture ends)."""
        keys = getattr(self, "_release_only", None)
        if keys is None:
            deferred = getattr(self.evaluator, "release_only_keys", None)
            keys = frozenset(deferred(self.session.schema.keys)) if callable(deferred) else frozenset()
            # A clip re-analysed for some keys (``clip_analysis_keys``) re-runs its worker once, on release.
            keys |= self._clip_analysis_keys() & self.session.schema.keys
            self._release_only = keys
        return keys

    def evaluation_values(self) -> dict[str, Any]:
        values = self.session.values
        if self._pose:
            values = dict(values)
            values.update(self._pose)
        return values

    def evaluation_time(self) -> float:
        """The time the evaluator is asked for: the transport's time into the clip, or, for a seamless loop, its
        unrolled time (passes played plus the time into this one), so the evaluator plays on through the wrap."""
        return self.transport.evaluation_time(bool(getattr(self.evaluator.fixture, "loop", False)))

    def on_frame(self) -> None:
        """Quick frame start (GUI thread): advance playback, evaluate at most once."""
        if self.state not in ("opening", "presented") or self.transport.stopped:
            return
        if self.bridge is not None:
            self.bridge.apply_pending_previews()     # a drag's newest value, once per frame
        if getattr(self.evaluator, "converging", False) and self.transport.playing:
            # An exact replay is converging on the instant shown: the transport waits for it instead of running
            # ahead (a replay chasing a moving instant froze the preview for seconds).
            self.transport.hold()
            moved = False
        else:
            moved = self.transport.on_frame()
        if moved and self.bridge is not None:
            self.bridge.timeChanged.emit()
        if self._eval_dirty or moved:
            self._eval_dirty = False
            try:
                # A live gesture re-publishes the current instant; anything else is the exact replay.
                live = self.session.gesture_active or bool(self._pose)
                revision = (self.session.revision, tuple(sorted(self._pose.items())))
                spatial = getattr(self.evaluator, "set_viewport_extent", None)
                if callable(spatial):
                    # A mode whose logical step reads the card's world extent (Bubble's domain) is evaluated at
                    # the extent actually presented.
                    spatial(self.presented_extent())
                playing = getattr(self.evaluator, "set_playing", None)
                if callable(playing):
                    # While playing, a change whose exact replay would chase the moving instant restarts the pass.
                    playing(self.transport.playing and not live)
                started = time.perf_counter()
                frame = self.evaluator.evaluate(self.evaluation_time(), self.evaluation_values(), exact=not live,
                                                revision=revision)
                evaluated = time.perf_counter() - started
                restarted = getattr(self.evaluator, "take_restart", None)
                if callable(restarted) and restarted():
                    # The evaluator applied a change by replaying to the start of the pass: the transport follows.
                    self._replay_restarted = True
                    self.transport.restart_pass()
                    if self.bridge is not None:
                        self.bridge.timeChanged.emit()
            except Exception as exc:
                logger.exception("[STUDIO] Preview evaluation failed")
                if self.bridge is not None:
                    self.bridge.set_viewport("error", f"Evaluation failed: {type(exc).__name__}: {exc}")
                return
            self.evaluations += 1
            fresh = frame is not self.last_frame
            self.last_frame = frame
            self.viewport.set_frame(frame)
            self._check_analysis_failure()
            converging = bool(getattr(self.evaluator, "converging", False))
            if converging:
                self._eval_dirty = True          # the exact replay continues on the next frame
                self._converging_frames += 1
                self.surface.request_frame()
            else:
                self._converging_frames = 0
            self._log_frame(fresh, converging, evaluated)
            measure = getattr(self.evaluator, "measurements", None)
            if callable(measure) and self.bridge is not None:
                self.bridge.push_measurements(measure())
            self.refresh_handles()
            self._refresh_busy()
        if getattr(self, "_preview_jobs", None):
            self._serve_preview()
        if self.transport.wants_frames:
            self.surface.request_frame()

    def _note_replay(self, reason: str) -> None:
        """A change the preview has to replay (an edit, undo/redo, answers or inputs landing) starts now."""
        self._replay_reason = reason
        self._replay_started = time.perf_counter()
        self._replay_frames = 0
        self._replay_restarted = False

    def _log_frame(self, fresh: bool, converging: bool, evaluated: float) -> None:
        """Sidecar log on the frame edge: a change's replay when it completes, and a gap with no new preview frame
        while the preview should be moving. One line per event, never per frame."""
        now = time.perf_counter()
        reason = self._replay_reason
        if reason is not None:
            self._replay_frames += 1
            if not converging:
                took = now - self._replay_started
                if self._replay_restarted or self._replay_frames > 1 or took >= self.REPLAY_LOG_S:
                    logger.info("[STUDIO] replay after %s mode=%s %.0f ms over %d frames, %s at %.2f s",
                                reason, self.adapter.mode_id, took * 1000.0, self._replay_frames,
                                "restarted the pass" if self._replay_restarted else "resumed",
                                self.transport.time)
                self._replay_reason = None
        if fresh:
            last = self._last_fresh_at
            if last is not None and now - last > self.PREVIEW_GAP_LOG_S:
                if reason is not None:
                    cause = f"replaying {reason}"
                elif evaluated > self.PREVIEW_GAP_LOG_S:
                    cause = f"one evaluation took {evaluated * 1000.0:.0f} ms"
                else:
                    cause = "no frame was requested (window not rendering)"
                logger.info("[STUDIO] preview gap %.0f ms mode=%s: %s", (now - last) * 1000.0,
                            self.adapter.mode_id, cause)
            moving = self.transport.playing or converging or self._replay_reason is not None
            self._last_fresh_at = now if moving else None

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

    def presented_geometry(self) -> tuple:
        """(presented-frame size, the live card's world extent, the framing's card style) of the viewport: what
        handles and the brush project through."""
        framing = next((f for f in self.framings if f.id == self.bridge.framingId), None)
        return ((self.viewport.width(), self.viewport.height()), self.presented_extent(),
                framing.style if framing else ())

    def brush_scene(self):
        """(frame on screen, the values it shows, presented geometry) for the brush, or None before a frame."""
        if self.bridge is None or self.viewport is None or self.last_frame is None:
            return None
        return self.last_frame, self.evaluation_values(), self.presented_geometry()

    # -------------------------------------------------------------- handles
    def refresh_handles(self) -> None:
        """Project the selected object's handles through the mode's camera (direct manipulation)."""
        if self.bridge is None or self.viewport is None or self.last_frame is None:
            return
        if not self.capabilities.as_map()["handles"]:
            return
        if self.bridge.workspace != self.session.schema.workspaces[0].id:
            if self.bridge.handles.get("handles") or self.bridge.handles.get("outline"):
                self.bridge.set_handles({"outline": [], "handles": []})    # an outline may stand alone
            return
        size, extent, style = self.presented_geometry()
        try:
            state = self.adapter.scene_handles(self.last_frame, self.evaluation_values(), self.bridge.selectedObject,
                                               size, extent, style)
        except Exception:
            logger.exception("[STUDIO] Handle projection failed")
            state = {"outline": [], "handles": []}
        self.bridge.set_handles(state)

    # -------------------------------------------------------------- framing
    def _on_viewport_resized(self, *_args) -> None:
        if self.viewport is not None and self.state == "presented":
            self.refresh_handles()
            if callable(getattr(self.evaluator, "set_viewport_extent", None)):
                self._invalidate()          # a filling framing's extent followed the new size

    def copy_frame(self) -> None:
        """Render the current frame once more, off screen at the presented size, and put it on the clipboard."""
        if self.viewport is None or self.last_frame is None:
            return
        width, height = int(round(self.viewport.width())), int(round(self.viewport.height()))
        if width <= 0 or height <= 0:
            return
        framing = next((f for f in self.framings if f.id == self.bridge.framingId), None)
        self._copy_key = f"copy-frame/{id(self.last_frame)}"
        try:
            ratio = float(self.viewport.window().effectiveDevicePixelRatio()) if self.viewport.window() else 1.0
        except Exception:
            ratio = 1.0
        self.viewport.request_snapshot(self._copy_key, self.last_frame,
                                       (max(1, int(width * ratio)), max(1, int(height * ratio))),
                                       (float(width), float(height)), self.presented_extent(),
                                       framing.style if framing else ())
        if self.surface is not None:
            self.surface.request_frame()

    def _deliver_copied_frame(self, width: int, height: int, pixels: bytes) -> None:
        from PySide6.QtGui import QGuiApplication, QImage
        image = QImage(pixels, width, height, width * 4, QImage.Format.Format_RGBA8888).flipped(Qt.Orientation.Vertical)
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setImage(image)
        self.copied_frame = image
        if self.bridge is not None:
            self.bridge.notify(f"Frame copied ({width} x {height})")
            self.bridge.frameCopied.emit(f"{width}x{height}")

    def presented_extent(self) -> tuple[float, float] | None:
        """The world extent the viewport presents now (a filling framing follows the viewport's shape)."""
        if self.viewport is not None and self.viewport.extent is not None:
            return self.viewport.extent
        framing = next((f for f in self.framings if f.id == getattr(self.bridge, "framingId", "")), None)
        return framing.extent if framing else None

    def select_framing(self, framing_id: str) -> None:
        framing = next((f for f in self.framings if f.id == framing_id), None)
        if framing is None or self.viewport is None:
            return
        self.viewport.set_extent(framing.extent, framing.style, fill=framing.fill)
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
            self._auto_clip = self._wanted_source = clips[0].id
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
            # The notice naming the automatic source would now name the wrong one: withdraw it (only that notice).
            notice = self._source_notice
            if notice and self.bridge is not None and self.bridge.message == notice:
                self.bridge.notify("")
            self._source_notice = ""
        # The selection the user (or, before any user choice, the default) asked for last: a background clip
        # load landing later selects itself only while it is still this one.
        self._wanted_source = fixture_id
        self._retire_other_clip_jobs(fixture_id)
        if fixture_id.startswith("clip:") and fixture_id not in {f.id for f in self.evaluator.fixtures()}:
            logger.info("[STUDIO] source select %s (%s): accepted, analysing first", fixture_id,
                        "user" if user else "default")
            self._load_clip(fixture_id)
            return
        logger.info("[STUDIO] source select %s (%s): accepted, selected", fixture_id, "user" if user else "default")
        self.evaluator.select(fixture_id)
        self.transport.set_duration(self.evaluator.fixture.duration)
        self.transport.seek(0.0)
        if self.bridge is not None:
            self.bridge.clear_traces()
            self.bridge.transportChanged.emit()
            self.bridge.timeChanged.emit()
        self._refresh_clip_analysis()
        self._invalidate()

    def pending_source_label(self) -> str:
        """The label of the recorded clip last asked for while it is still analysing ("" otherwise)."""
        wanted = self._wanted_source
        if not wanted or wanted not in self._clip_jobs or self.evaluator is None or self.evaluator.fixture.id == wanted:
            return ""
        clip = next((c for c in self.adapter.recorded_clips() if c.id == wanted), None)
        return clip.label if clip is not None else ""

    def preview_busy(self) -> str:
        """What the preview waits for: the clip on screen (or the evaluator's answers) analysing for the current
        values, or an exact replay converging (a change applied, a seek) for more than a moment ("" when live)."""
        if self.evaluator is None:
            return ""
        if self.evaluator.fixture.id in self._clip_jobs or getattr(self.evaluator, "analysing", False):
            return "Analysing…"
        if self._converging_frames >= self.APPLYING_AFTER_FRAMES:
            return "Updating…"
        return ""

    def _refresh_busy(self) -> None:
        if self.bridge is not None:
            self.bridge.set_busy(self.preview_busy())

    def _retire_other_clip_jobs(self, fixture_id: str) -> None:
        """Latest wins: every clip analysis but ``fixture_id``'s is retired when a source is asked for (it could only
        compete with this one for the CPU and land as something nobody asked for any more). A retired refresh of a
        clip runs again when that clip is picked again (its analysis signature stayed the old one)."""
        for other in [clip_id for clip_id in self._clip_jobs if clip_id != fixture_id]:
            self._clip_jobs.pop(other).cancel()
            self._log_job_end(other, f"cancelled: superseded by {fixture_id}")

    def _log_job_end(self, clip_id: str, outcome: str) -> None:
        started = self._clip_job_started.pop(clip_id, None)
        took = "" if started is None else f" after {(time.perf_counter() - started) * 1000.0:.0f} ms"
        logger.info("[STUDIO] clip analysis %s %s%s", clip_id, outcome, took)

    def clip_status(self, clip_id: str) -> str:
        if clip_id in self._clip_jobs:
            return "loading"
        if clip_id in self._clip_errors:
            return "error"
        return "available"

    # ------------------------------------------------ recorded clips re-analysed for the analysis values
    def _clip_analysis_keys(self) -> frozenset[str]:
        """The values a recorded clip's analysis depends on, for a mode whose clip worker answers them
        (``clip_analysis_keys``: Bubble, Extruded Bubble, Sphere: the Audio Analysis values)."""
        keys = getattr(self.adapter, "clip_analysis_keys", None)
        return frozenset(keys()) if callable(keys) else frozenset()

    def _analysis_signature(self, values) -> str:
        import json
        keys = self._clip_analysis_keys()
        return json.dumps({key: values.get(key) for key in sorted(keys)}, sort_keys=True, default=repr)

    def _refresh_clip_analysis(self) -> None:
        """The recorded clip on screen was analysed under other analysis values (an Audio Analysis edit, undo or
        redo): analyse it again in the background; its previous inputs stay on screen until the new ones land."""
        if not self._clip_analysis_keys() or self.evaluator is None or self.state not in ("opening", "presented"):
            return
        fixture = self.evaluator.fixture
        clip_id = fixture.id
        if not clip_id.startswith("clip:") or clip_id not in self._clip_analysis:
            return
        wanted = self._analysis_signature(self.session.committed_values)
        if self._clip_analysis[clip_id] == wanted:
            return
        job = self._clip_jobs.pop(clip_id, None)
        if job is not None:
            job.cancel()
            self._log_job_end(clip_id, "cancelled: the analysis values changed again")
        self._load_clip(clip_id, refresh=True)

    def _load_clip(self, clip_id: str, *, refresh: bool = False) -> None:
        if clip_id in self._clip_jobs:
            logger.info("[STUDIO] clip analysis %s already running (kept)", clip_id)
            return
        clip = next((c for c in self.adapter.recorded_clips() if c.id == clip_id), None)
        loader = getattr(self.adapter, "start_clip_load", None)
        if clip is None or not callable(loader):
            logger.info("[STUDIO] source select %s rejected: recorded clips are not available for mode=%s",
                        clip_id, self.adapter.mode_id)
            self.bridge.notify("Recorded clips are not available for this mode")
            return

        values = self.session.committed_values
        signature = self._analysis_signature(values)
        completed = [False]

        def finished(result, error: str = "") -> None:
            completed[0] = True
            if self._clip_jobs.get(clip_id) is not job_ref[0] and job_ref[0] is not None:
                return                                   # a newer analysis of this clip replaced this one
            self._clip_jobs.pop(clip_id, None)
            if self.state not in ("opening", "presented"):
                return
            if error:
                outcome = f"failed: {error}"
            elif refresh:
                outcome = "finished (re-analysed, replaces the inputs on screen)"
            elif self._wanted_source == clip_id:
                outcome = "finished, selected"
            else:
                outcome = f"finished, not selected (superseded by {self._wanted_source})"
            self._log_job_end(clip_id, outcome)
            if error:
                self._clip_errors[clip_id] = error
                self.bridge.notify(f"Clip analysis failed: {error}", "Retry", lambda: self.retry_clip(clip_id))
            elif refresh:
                # The clip on screen, re-analysed for new analysis values: its new inputs replace the old at the
                # same instant (the transport keeps its place).
                self._clip_errors.pop(clip_id, None)
                self._clip_analysis[clip_id] = signature
                self.evaluator.add_recorded(result)
                if self.evaluator.fixture.id == clip_id:
                    self.evaluator.select(clip_id)
                    self._note_replay("clip re-analysed")
                    self._invalidate()
                self._refresh_clip_analysis()           # values edited again while it ran
            else:
                self._clip_errors.pop(clip_id, None)
                self._clip_analysis[clip_id] = signature
                self.evaluator.add_recorded(result)
                # Only the source last asked for (by the user, or the default while the user has asked for
                # nothing) is selected when its analysis lands; any other landing load only becomes available.
                if self._wanted_source == clip_id:
                    automatic = self._auto_clip == clip_id
                    self.select_fixture(clip_id, user=not automatic)
                    if automatic:
                        self._source_notice = f"Preview source: {clip.label} (recorded music)"
                        self.bridge.notify(self._source_notice)
            self.bridge.transportChanged.emit()
            self._refresh_busy()

        job_ref = [None]
        self._clip_job_started[clip_id] = time.perf_counter()
        logger.info("[STUDIO] clip analysis %s started (%s)", clip_id, "refresh" if refresh else "load")
        try:
            job = loader(clip, values, finished)
            # A job that already finished inside the loader (a cached result, a worker that failed to start) is not
            # running: registering it would leave the clip "analysing" for good and ignore every later selection.
            if job is not None and not completed[0]:
                job_ref[0] = job
                self._clip_jobs[clip_id] = job
        except Exception as exc:
            self._clip_errors[clip_id] = str(exc)
            self._log_job_end(clip_id, f"could not start: {exc}")
            self.bridge.notify(f"Clip analysis could not start: {exc}", "Retry", lambda: self.retry_clip(clip_id))
        self.bridge.transportChanged.emit()
        self._refresh_busy()

    def retry_clip(self, clip_id: str) -> None:
        """Analyse a clip whose analysis failed again; it is selected when it lands (the user asked for it)."""
        if self.state not in ("opening", "presented"):
            return
        self._clip_errors.pop(clip_id, None)
        self.select_fixture(clip_id)

    # ---------------------------------------------------- background analysis failures
    def _check_analysis_failure(self) -> None:
        """An evaluator analysis that failed is reported once (with Retry); the previous answers stay on screen."""
        failure = str(getattr(self.evaluator, "analysis_failure", "") or "")
        if failure and failure != self._failure_shown and self.bridge is not None:
            self.bridge.notify(f"Analysis failed: {failure}. The previous preview stays on screen.", "Retry",
                               self.retry_analysis)
        self._failure_shown = failure

    def retry_analysis(self) -> None:
        retry = getattr(self.evaluator, "retry_analysis", None)
        if self.state not in ("opening", "presented") or not callable(retry):
            return
        self._failure_shown = ""
        retry()
        self._invalidate()
        if self.bridge is not None:
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
        if key in self.session.schema.keys:
            value = self.session.schema.admit(key, value, self.session.values[key])
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
        self.close_from("close()")

    def _on_bridge_close(self) -> None:
        self.close_from(getattr(self.bridge, "close_source", "") or "close request")

    def _on_window_close(self) -> None:
        self.close_from("window close (X / Alt+F4)")

    def close_for_quit(self, *_args) -> None:
        self.close_from("application quit")

    def close_for_settings_gone(self, *_args) -> None:
        self.close_from("Settings destroyed")

    def close_from(self, source: str) -> None:
        """Every exit path (Close, Esc, window X / Alt+F4, a lost window, app quit, Settings going away) ends
        here. Settings is revealed *before* anything is torn down, so no teardown failure or hang can keep it
        hidden, and the controller always ends closed."""
        if self.state not in ("opening", "presented"):
            return
        if not self.settle_draft(interactive=source in self.INTERACTIVE_CLOSES):
            logger.info("[STUDIO] close via %s kept open: unsaved preset changes not settled", source)
            return
        reveal = self.state == "presented" or bool(getattr(self.presence, "concealed", False))
        logger.info("[STUDIO] close requested mode=%s via %s (state=%s, reveal=%s)", self.adapter.mode_id,
                    source, self.state, reveal)
        try:
            # The request is on disk before any teardown runs (a native fault or hang leaves this trace).
            from core.logging.logger import flush_logging
            flush_logging(0.25)
        except Exception:
            pass
        try:
            self._retire(reveal=reveal)
        finally:
            self.state = "closed"
            if StudioController._active is self:
                StudioController._active = None
            try:
                self.closed.emit()
            except Exception:
                logger.exception("[STUDIO] closed notification failed")

    # The user's own ways out: these ask what to do with unsaved edits of a curated preset. Every other exit (quit,
    # Settings going away, a lost window, a failure, a programmatic close) keeps them in Custom without asking.
    INTERACTIVE_CLOSES: ClassVar[frozenset[str]] = frozenset(
        {"close button", "escape", "title bar close", "window close (X / Alt+F4)"})

    def settle_draft(self, *, interactive: bool) -> bool:
        """Edits held on a curated preset are settled before the session ends or leaves that preset (the store's
        prompt, or Custom when nobody can be asked). False: the user chose to stay."""
        holds = getattr(self.store, "holds_draft", None)
        if not callable(holds) or not holds():
            return True
        if self.session is not None:
            self.session.cancel_gesture()     # an unfinished drag is not an edit
        try:
            return bool(self.store.resolve_draft(interactive=interactive))
        except Exception:
            logger.exception("[STUDIO] Settling unsaved preset changes failed")
            return True                       # never trap the user in the Studio

    def _on_surface_lost(self) -> None:
        """The window disappeared without our close (crash/destroy): recover Settings."""
        if self.state in ("opening", "presented"):
            self.surface = None
            self.close_from("window lost")

    def _retire(self, *, reveal: bool) -> None:
        """Retire in a fixed order and record each step's cost (``close_timings``, milliseconds).

        Each step is isolated: a failing step is logged and the next one still runs. Settings is revealed
        right after the edit and playback stop, *before* the clip jobs, the window and the models are retired,
        and again (idempotently) in ``finally``, so neither a failing nor a hanging teardown step can leave
        Settings concealed."""
        import time
        timings: dict[str, float] = {}
        failures: list[str] = []
        mark = time.perf_counter()
        # One transition out: while the Studio's window is still on screen, Settings is revealed beneath it (shown and
        # painted, not activated) and comes forward once the window is gone. Raising and activating it over the still
        # shown application-modal window made Settings and the Studio swap places twice (the 8 Nov double flicker).
        covering = None
        if reveal:
            find = getattr(self.surface, "covering_window", None)
            try:
                covering = find() if callable(find) else None
            except Exception:
                logger.exception("[STUDIO] Could not read the Studio window's state; Settings comes forward at once")
        awaiting_window = False

        def reveal_settings() -> None:
            if covering is not None:
                self.presence.reveal(beneath=covering)
            else:
                self.presence.reveal()

        def step(name: str, action: Callable[[], Any] | None = None) -> None:
            nonlocal mark
            if action is not None:
                try:
                    action()
                except Exception:
                    failures.append(name)
                    logger.exception("[STUDIO] retire step %s failed", name)
            now = time.perf_counter()
            timings[name] = round((now - mark) * 1000.0, 2)
            mark = now
            logger.info("[STUDIO] retire step %s %s %.1f ms", name, "failed" if name in failures else "done",
                        timings[name])

        def cancel_jobs() -> None:
            for clip_id in tuple(self._clip_jobs):
                self._log_job_end(clip_id, "cancelled: the Studio closed")
            jobs, self._clip_jobs = tuple(self._clip_jobs.values()), {}
            for job in jobs:
                cancel = getattr(job, "cancel", None)
                if callable(cancel):
                    try:
                        cancel()
                    except Exception:
                        failures.append("jobs")
                        logger.exception("[STUDIO] clip job cancel failed")
            unsubscribe, self._unsubscribe = self._unsubscribe, None
            if unsubscribe is not None:
                unsubscribe()

        def retire_surface() -> None:
            nonlocal awaiting_window
            surface, self.surface = self.surface, None
            self.viewport = None
            if surface is None:
                return
            for signal, slot in ((surface.frameStarted, self.on_frame), (surface.presented, self._on_presented),
                                 (surface.closeRequested, self._on_window_close), (surface.lost, self._on_surface_lost),
                                 (surface.failed, self._fail)):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            watch = getattr(self.presence, "watch", None)
            window = getattr(surface, "window", None)
            if watch is not None and watch.active and window is not None:
                window.destroyed.connect(lambda *_a: watch.note("studio window destroyed"))
            forward = (getattr(self.presence, "bring_forward", None)
                       or getattr(self.presence, "repaint_revealed", None))
            if reveal and forward is not None and window is not None and getattr(self.presence, "reveal_count", 0):
                # Once the modal Studio window is gone, Settings comes forward (when it was revealed beneath it) and
                # repaints once more (see WindowPresence.bring_forward / repaint_revealed).
                window.destroyed.connect(lambda *_a: forward())
                awaiting_window = True
            surface.retire()

        def release_models() -> None:
            evaluator = self.evaluator
            try:
                if evaluator is not None:
                    evaluator.release()
            finally:
                try:
                    self.adapter.release()
                finally:
                    self._preview_jobs, self._preview_sent, self._preview_done = [], {}, {}

        try:
            session = self.session
            step("gesture", session.cancel_gesture if session is not None else None)   # a drag is not a save
            step("transport", self.transport.stop)
            step("settings", reveal_settings if reveal else None)                       # Settings back first
            step("jobs", cancel_jobs)
            step("surface", retire_surface)
            step("evaluator", release_models)
        finally:
            if StudioController._active is self:
                StudioController._active = None
            if reveal and getattr(self.presence, "concealed", False):
                step("settings_retry", self.presence.reveal)   # the first reveal raised before un-concealing
            forward = getattr(self.presence, "bring_forward", None)
            if reveal and covering is not None and callable(forward) and (not awaiting_window or "surface" in failures):
                # Revealed beneath a window whose going is not awaited (or whose retirement failed, so it may stay):
                # Settings comes forward now, never left behind it.
                step("settings_forward", forward)
            timings["total"] = round(sum(timings.values()), 2)
            self.close_timings = timings
            self.close_failures = tuple(failures)
            logger.info("[STUDIO] retire reveal=%s %s%s", reveal,
                        " ".join(f"{k}={v}ms" for k, v in timings.items()),
                        f" failed={','.join(failures)}" if failures else "")


__all__ = ["StudioBridge", "StudioController"]

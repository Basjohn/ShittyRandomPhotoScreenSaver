"""Cross-display retained scene coordination for one CUSTOM session."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect

from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)

from .scene_controller import QuickSceneController


@dataclass(frozen=True, slots=True)
class _PresentationPlacement:
    display_identity: str
    monitor_route: str
    global_rect: QRect

    @classmethod
    def from_item(cls, item: CustomLayoutSessionItem) -> "_PresentationPlacement":
        return cls(
            display_identity=item.current_display_identity,
            monitor_route=item.current_monitor_route,
            global_rect=QRect(item.current_global_rect),
        )


class QuickCustomLayoutSceneCoordinator:
    """Keep each retained presentation on its shared session item's display."""

    def __init__(self, session: CustomLayoutSession) -> None:
        self._session: CustomLayoutSession | None = session
        self._scenes: dict[str, QuickSceneController] = {}
        self._placement_by_key: dict[
            CustomLayoutKey,
            _PresentationPlacement,
        ] = {
            item.source_key: _PresentationPlacement.from_item(item)
            for item in session.items()
        }
        session.subscribe_changes(self._on_session_item_changed)

    def register_scene(
        self,
        display_identity: str,
        scene: QuickSceneController,
    ) -> None:
        identity = str(display_identity or "").strip()
        if not identity:
            raise ValueError("display_identity must not be empty")
        existing = self._scenes.get(identity)
        if existing is not None and existing is not scene:
            raise ValueError(f"display scene already registered: {identity}")
        self._scenes[identity] = scene

    def unregister_scene(
        self,
        display_identity: str,
        scene: QuickSceneController,
    ) -> None:
        identity = str(display_identity or "").strip()
        if self._scenes.get(identity) is scene:
            del self._scenes[identity]

    def retire(self) -> None:
        session = self._session
        self._session = None
        if session is not None:
            session.unsubscribe_changes(self._on_session_item_changed)
        self._scenes.clear()
        self._placement_by_key.clear()

    def _on_session_item_changed(self, item: CustomLayoutSessionItem) -> None:
        prior = self._placement_by_key.get(
            item.source_key,
            _PresentationPlacement(
                display_identity=item.source_key.display_identity,
                monitor_route=item.source_monitor_route,
                global_rect=QRect(item.baseline_global_rect),
            ),
        )
        target_identity = item.current_display_identity
        if prior.display_identity == target_identity:
            self._placement_by_key[item.source_key] = (
                _PresentationPlacement.from_item(item)
            )
            return
        source = self._scenes.get(prior.display_identity)
        target = self._scenes.get(target_identity)
        if source is None or target is None:
            self._restore_item_placement(item, prior)
            raise RuntimeError(
                "CUSTOM transfer display has no retained scene"
            )
        try:
            if item.model_identity == "spotify_visualizer":
                if source.visualizer_render_identity is None:
                    self._placement_by_key[item.source_key] = (
                        _PresentationPlacement.from_item(item)
                    )
                    return
                if target.visualizer_render_identity is not None:
                    raise RuntimeError(
                        "CUSTOM Visualizer target already has a retained scene admission"
                    )
                source.transfer_visualizer_to(target)
            else:
                source.transfer_ordinary_widget_to(
                    target,
                    item.model_identity,
                )
        except Exception:
            self._restore_item_placement(item, prior)
            raise
        self._placement_by_key[item.source_key] = (
            _PresentationPlacement.from_item(item)
        )

    @staticmethod
    def _restore_item_placement(
        item: CustomLayoutSessionItem,
        placement: _PresentationPlacement,
    ) -> None:
        item.set_current_display(
            placement.display_identity,
            monitor_route=placement.monitor_route,
        )
        item.set_geometry(placement.global_rect)


__all__ = ["QuickCustomLayoutSceneCoordinator"]

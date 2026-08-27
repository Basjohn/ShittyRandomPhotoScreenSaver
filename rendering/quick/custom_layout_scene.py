"""Cross-display retained scene coordination for one CUSTOM session."""

from __future__ import annotations

from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)

from .scene_controller import QuickSceneController


class QuickCustomLayoutSceneCoordinator:
    """Keep Visualizer presentation admission on the session item's display."""

    def __init__(self, session: CustomLayoutSession) -> None:
        self._session: CustomLayoutSession | None = session
        self._scenes: dict[str, QuickSceneController] = {}
        self._visualizer_display_by_key: dict[CustomLayoutKey, str] = {
            item.source_key: item.current_display_identity
            for item in session.items()
            if item.model_identity == "spotify_visualizer"
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
        self._visualizer_display_by_key.clear()

    def _on_session_item_changed(self, item: CustomLayoutSessionItem) -> None:
        if item.model_identity != "spotify_visualizer":
            return
        source_identity = self._visualizer_display_by_key.get(
            item.source_key,
            item.source_key.display_identity,
        )
        target_identity = item.current_display_identity
        if source_identity == target_identity:
            return
        source = self._scenes.get(source_identity)
        target = self._scenes.get(target_identity)
        if source is None or target is None:
            raise RuntimeError(
                "CUSTOM Visualizer transfer display has no retained scene"
            )
        if source.visualizer_render_identity is None:
            self._visualizer_display_by_key[item.source_key] = target_identity
            return
        if target.visualizer_render_identity is not None:
            raise RuntimeError(
                "CUSTOM Visualizer target already has a retained scene admission"
            )
        source.transfer_visualizer_to(target)
        self._visualizer_display_by_key[item.source_key] = target_identity


__all__ = ["QuickCustomLayoutSceneCoordinator"]

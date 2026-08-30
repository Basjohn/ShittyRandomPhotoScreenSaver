"""Pins the retained first-frame semantics that survived the black-flash work.

Only two contracts remain here after the failed deferred-show and event-driven
surface-refresh experiments were removed: production must not paint the migration
proof colour bands, and an empty/proof render is not an intentional product first
frame. The show gate and the forced-redraw bars they used to sit beside are gone.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication

from rendering.quick.render.background_item import BackgroundRenderItem
from rendering.quick.render.background_node import BackgroundRenderNode
from rendering.quick.scene_controller import _render_snapshot_has_intentional_base_frame


@pytest.fixture(scope="module")
def gui_app():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def test_migration_proof_background_is_opt_in(gui_app):
    owner = QObject()
    item = BackgroundRenderItem()
    item.setParent(owner)

    # A production no-image state must not create the colour-band proof node.
    assert item._proof_enabled is False
    assert item.updatePaintNode(None, None) is None

    # Harnesses can still request the deterministic proof explicitly.
    item.setProofProgress(0.5)
    node = item.updatePaintNode(None, None)
    assert item._proof_enabled is True
    assert isinstance(node, BackgroundRenderNode)


def test_empty_or_proof_render_is_not_product_first_frame():
    assert not _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity=None, error=None)
    )
    assert not _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity="image:a", error="boom")
    )
    assert _render_snapshot_has_intentional_base_frame(
        SimpleNamespace(render_count=1, active_image_identity="image:a", error=None)
    )

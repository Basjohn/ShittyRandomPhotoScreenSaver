"""Source-level permanent contracts for shared/lazy Widget card materials.

Qt runtime/visual behavior still requires the PySide6 user-environment gate. These
checks prevent architectural regressions that would recreate per-card capture/blur
owners or make Normal pay the material-renderer cost.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_surface_style_uses_themed_combo_and_exposes_all_material_modes() -> None:
    source = _text(ROOT / "ui" / "tabs" / "widgets_tab_defaults.py")
    assert "widget_surface_style_combo = StyledComboBox()" in source
    assert 'addItem("Theme Default", "theme")' in source
    assert 'addItem("Normal", "normal")' in source
    assert 'addItem("Glass", "glass")' in source
    assert 'addItem("Acrylic", "acrylic")' in source
    assert "item.setEnabled(False)" not in source


def test_material_capture_and_blur_exist_only_in_shared_backdrop_component() -> None:
    backdrop = _text(QML / "CardMaterialBackdrop.qml")
    assert backdrop.count("ShaderEffectSource") >= 1
    assert backdrop.count("MultiEffect") >= 1

    for filename in (
        "OverlayCard.qml",
        "OverlayWidget.qml",
        "OverlayCardMaterialMask.qml",
        "VisualizerPresentation.qml",
        "ContextMenu.qml",
    ):
        source = _text(QML / filename)
        assert "ShaderEffectSource" not in source, filename
        # ContextMenu legitimately uses RectangularShadow from QtQuick.Effects;
        # the card material contract specifically forbids a card-local MultiEffect.
        assert "MultiEffect" not in source, filename


def test_shared_blur_uses_one_layered_background_source_without_proxy_capture() -> None:
    backdrop = _text(QML / "CardMaterialBackdrop.qml")
    scene = _text(QML / "DisplayScene.qml")

    # The displayed background layer is the single Glass/Acrylic source texture.
    # Do not add a second display-wide ShaderEffectSource/FBO in front of it.
    assert "layer.enabled: displayScene.cardMaterialBackdropNeeded" in scene
    assert "layer.live: true" in scene
    assert 'objectName: "cardMaterialBackdropCapture"' not in backdrop
    assert "downsampleScale" not in backdrop
    assert "textureSize: Qt.size(" not in backdrop
    assert "source: materialBackdrop.sourceItem" in backdrop
    assert "autoPaddingEnabled: false" in backdrop

    # Exactly one explicit ShaderEffectSource remains: the display-wide alpha mask.
    assert backdrop.count("ShaderEffectSource {") == 1
    assert 'objectName: "cardMaterialMaskCapture"' in backdrop
    assert "live: materialBackdrop.visible" in backdrop
    assert "recursive: false" in backdrop
    assert "hideSource: true" in backdrop
    assert "maskSource: materialMaskCapture" in backdrop

    # Normal has no layer/FBO/material cost because admission is the layer gate.
    assert 'cardMaterialMode !== "normal"' in scene



def test_layered_background_render_node_tracks_the_active_render_target() -> None:
    """The custom background must remain legal when an ancestor becomes layered.

    Qt changes a QSGRenderNode's active render target when an ancestor is rendered
    into a layer.  The material architecture therefore depends on the background
    node deriving its viewport from renderTarget() on every draw rather than
    caching the window/backbuffer dimensions as a permanent target assumption.
    """

    node = _text(ROOT / "rendering" / "quick" / "render" / "background_node.py")
    assert "render_target = self.renderTarget()" in node
    assert "target_size = render_target.pixelSize()" in node
    assert "viewport = (0, 0, *render_target_size)" in node
    assert "self.renderTarget()" in node


def test_normal_mode_keeps_shared_material_loader_dormant() -> None:
    scene = _text(QML / "DisplayScene.qml")
    assert 'cardMaterialMode !== "normal"' in scene
    assert "active: displayScene.cardMaterialBackdropNeeded" in scene
    assert "sourceComponent: cardMaterialBackdropComponent" in scene
    assert "CardMaterialBackdrop {" in scene
    assert "sourceItem: backgroundPresentationHost" in scene
    assert "maskItem: cardMaterialMaskSource" in scene
    assert "onLoaded:" not in scene

    host = _text(ROOT / "rendering" / "quick" / "widgets" / "host.py")
    assert 'self._card_material_mode == "normal"' in host
    assert "_sync_material_mask" in host
    assert "_retire_material_mask" in host
    assert 'widget.item.property("cardShellEnabled")' in host



def test_material_layer_does_not_capture_visualizer_or_add_cadence_owners() -> None:
    """Special materials may redirect only the wallpaper/transition subtree.

    Visualizer and ordinary widget presentation stay above/outside the layered
    background source, and the material implementation must not acquire a frame
    pacer/timer/polling owner to make the effect work.
    """

    scene = _text(QML / "DisplayScene.qml")
    backdrop = _text(QML / "CardMaterialBackdrop.qml")

    background_pos = scene.index("id: backgroundPresentationHost")
    material_loader_pos = scene.index("id: cardMaterialBackdropLoader")
    pixel_shift_pos = scene.index("id: pixelShiftLayer")
    visualizer_pos = scene.index("id: visualizerPresentationLoader")

    assert background_pos < material_loader_pos < pixel_shift_pos < visualizer_pos
    assert "ordinaryWidgetHost" not in scene[background_pos:material_loader_pos]

    combined = scene + "\n" + backdrop
    for forbidden in (
        "Timer {",
        "FrameAnimation",
        "requestAnimationFrame",
        "onFrameSwapped",
    ):
        assert forbidden not in combined

    frame_pacer = _text(ROOT / "rendering" / "quick" / "frame_pacer.py")
    presenter = _text(ROOT / "rendering" / "quick" / "display_presenter.py")
    scene_controller = _text(ROOT / "rendering" / "quick" / "scene_controller.py")
    visualizer_node = _text(ROOT / "rendering" / "quick" / "visualizer" / "node.py")
    # v3.1 reuses the pre-existing transition pacer solely to dirty the layered
    # source. No material timer/cadence owner is allowed, and Normal unregisters
    # the callback entirely.
    assert "def set_layered_background_sync(" in frame_pacer
    assert "if self._demands & QuickFrameDemand.TRANSITION:" in frame_pacer
    assert "synchronize_background()" in frame_pacer
    assert "QTimer(" in frame_pacer  # the one historical display pacer only
    assert "set_layered_background_sync(" in presenter
    assert 'if material_mode in {"glass", "acrylic"}' in presenter
    assert "else None" in presenter
    assert "def request_layered_background_present(self) -> bool:" in scene_controller
    assert "item.update()" in scene_controller
    assert "cardMaterial" not in visualizer_node

def test_runtime_publishes_resolved_material_instead_of_clamping_to_normal() -> None:
    selection = _text(ROOT / "ui" / "widget_theme_selection.py")
    assert "material_mode=resolved.effective_card_material_mode" in selection
    assert 'material_mode="normal"' not in selection


def test_widget_theme_link_control_is_bidirectional_and_present_on_both_theme_pages() -> None:
    source = _text(ROOT / "ui" / "tabs" / "themes_tab.py")
    styles = _text(ROOT / "ui" / "tabs" / "shared_styles.py")
    selection = _text(ROOT / "ui" / "widget_theme_selection.py")

    assert "self.settings_keep_synced=self._make_link_button()" in source
    assert "self.widget_keep_synced=self._make_link_button()" in source
    assert "button.setMinimumWidth(240)" in source
    assert '"THEME_LINK_BUTTON_STYLE"' in source
    assert "THEME_LINK_BUTTON_STYLE = _build_theme_link_button_style()" in styles
    assert "_theme_link_icon(linked)" in source
    assert 'text="Linked" if linked else "Independent"' in source

    # Linked selection is symmetric: selecting a Widget theme resolves and applies
    # its explicit Settings counterpart rather than silently breaking the link.
    assert "synced_settings_theme_id_for_widget" in source
    assert "activate_catalog_theme(settings_entry)" in source
    assert "keep_synced=True" in source
    assert "def synced_settings_theme_id_for_widget(" in selection


def test_primary_text_semantic_baseline_is_consumed_by_all_ordinary_families() -> None:
    projection = _text(ROOT / "rendering" / "quick" / "widgets" / "theme_projection.py")
    assert 'get_active_widget_theme().color("card.text")' in projection
    for filename in (
        "weather.py",
        "clock.py",
        "media.py",
        "gmail.py",
        "reddit.py",
        "achievement_pulse.py",
        "abandonment_issues.py",
    ):
        source = _text(ROOT / "rendering" / "quick" / "widgets" / filename)
        assert "resolve_primary_text_color(" in source, filename


def test_shared_material_captures_only_the_below_widgets_background_host() -> None:
    scene_controller = _text(ROOT / "rendering" / "quick" / "scene_controller.py")
    scene = _text(QML / "DisplayScene.qml")
    assert 'root.setProperty("materialBackdropSourceItem"' not in scene_controller
    assert 'objectName: "backgroundPresentationHost"' in scene
    assert 'sourceItem: backgroundPresentationHost' in scene
    assert 'maskItem: cardMaterialMaskSource' in scene
    assert 'layer.enabled: displayScene.cardMaterialBackdropNeeded' in scene
    # The capture source must never be the whole display scene/widget layer: doing
    # so would recursively capture cards/Visualizer/Context Menu into their blur.
    assert 'materialBackdropSourceItem' not in scene


def test_material_admission_uses_explicit_retained_consumer_count() -> None:
    scene = _text(QML / "DisplayScene.qml")
    host = _text(ROOT / "rendering" / "quick" / "widgets" / "host.py")

    assert "property int materialConsumerCount: 0" in scene
    assert "ordinaryCardMaterialMaskHost.materialConsumerCount > 0" in scene
    assert "ordinaryCardMaterialMaskHost.children.length" not in scene
    assert '"materialConsumerCount", int(self._material_consumer_count)' in host
    assert "_increment_material_consumer_count()" in host
    assert "_decrement_material_consumer_count()" in host


def test_secondary_mail_and_reddit_metadata_use_sparse_theme_roles() -> None:
    roles = _text(ROOT / "ui" / "widget_visual_roles.py")
    gmail = _text(ROOT / "rendering" / "quick" / "widgets" / "gmail.py")
    reddit = _text(ROOT / "rendering" / "quick" / "widgets" / "reddit.py")
    generator = _text(ROOT / "tools" / "generate_widget_theme_mirrors.py")

    for role in ("gmail.sender", "gmail.read_sender", "gmail.read_subject", "gmail.timestamp"):
        assert f'"{role}"' in roles
        assert f'"{role}"' in gmail
        assert f'"{role}"' in generator
    assert '"reddit.age"' in roles
    assert '"reddit2.age"' in roles
    assert 'f"{self.config.widget_id}.age"' in reddit
    assert '"reddit.age"' in generator
    assert '"reddit2.age"' in generator


def test_general_card_style_controls_are_grouped_in_style_overrides_before_layout() -> None:
    source = _text(ROOT / "ui" / "tabs" / "widgets_tab_defaults.py")
    style_bucket = source.index('"Style Overrides"')
    layout_bucket = source.index('"Layout"', style_bucket)
    assert style_bucket < layout_bucket
    assert 'style_overrides_layout,\n        "Card Surface:"' in source
    assert 'style_overrides_layout,\n        "Card Border:"' in source
    assert 'style_overrides_layout,\n        "Surface Style:"' in source
    assert 'style_overrides_layout,\n        "Card Border Width:"' in source
    assert '"Theme Default follows the selected Widget Theme material.' in source
    assert '"Theme-owned card surface. Editing this colour forks' in source
    assert '"Theme-owned card border. Editing this colour forks' in source
    assert '"Global card geometry override. This changes border width without editing or forking' in source


def test_material_state_is_exposed_at_existing_lifecycle_edges() -> None:
    controller = _text(ROOT / "rendering" / "quick" / "scene_controller.py")
    presenter = _text(ROOT / "rendering" / "quick" / "display_presenter.py")
    assert "def describe_card_material_state(self)" in controller
    assert '"card_material": self.describe_card_material_state()' in controller
    assert 'root.property("cardMaterialBackdropNeeded")' in controller
    assert 'root.property("cardMaterialSourceLayerEnabled")' in controller
    assert 'root.property("cardMaterialSourceLayerLive")' in controller
    assert 'root.property("cardMaterialMaskTreeVisible")' in controller
    assert 'mask_host.property("materialConsumerCount")' in controller
    assert 'loader.property("active")' in controller
    assert 'loader.property("item")' in controller
    assert 'backdrop.property("sourceItem")' in controller
    assert 'backdrop.property("maskItem")' in controller
    assert 'mask_capture.property("live")' in controller
    assert 'shared_blur.property("visible")' in controller
    assert 'shared_blur.property("source")' in controller
    assert 'shared_blur.property("hasProxySource")' in controller
    assert '"[CARD_MATERIAL] screen=%s generation=%s mode=%s source_layer=%s source_layer_live=%s ordinary_consumers=%s "' in presenter
    assert '"blur_visible=%s blur_source_bound=%s blur_proxy=%s"' in presenter

"""Source contracts for CHK21 steady retained-background ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_steady_background_is_native_retained_scenegraph_content():
    source = _read("rendering/quick/render/background_image_node.py")
    assert "class RetainedBackgroundSceneNode(QSGNode)" in source
    assert "QSGImageNode" in source
    assert "createImageNode()" in source
    assert "createTextureFromImage" in source
    assert "setOwnsTexture(True)" in source
    assert "QSGOpacityNode" in source
    assert "self._custom_opacity.setOpacity(0.0)" in source
    assert "self._image_opacity.setOpacity(1.0 if visible else 0.0)" in source


def test_custom_background_node_is_retained_but_blocked_during_steady_frames():
    source = _read("rendering/quick/render/background_image_node.py")
    assert source.count("BackgroundRenderNode(") == 1
    assert "self._custom_opacity.appendChildNode(self._custom_node)" in source
    assert "if self._custom_active:" in source
    assert "self._custom_node.release_presentation_textures()" in source
    assert "self._custom_node.releaseResources()" in source
    # Transition/program resources must not be torn down merely because one
    # transition ended; only presentation textures are retired at that edge.
    steady_block = source[source.index("if self._custom_active:") : source.index("def release_resources")]
    assert "releaseResources()" not in steady_block


def test_transition_and_pixel_oracle_paths_keep_custom_renderer_authority():
    item = _read("rendering/quick/render/background_item.py")
    root = _read("rendering/quick/render/background_image_node.py")
    assert "self._transition_run is not None" in item
    assert "self._proof_enabled" in item
    assert "self._telemetry.capture_pixels_enabled" in item
    assert "if custom_required:" in root
    assert "self._custom_opacity.setOpacity(1.0)" in root
    assert "self._set_native_visible(False)" in root
    assert "self._custom_node.synchronize(" in root


def test_steady_path_has_no_python_render_callback_or_gl_draw():
    root = _read("rendering/quick/render/background_image_node.py")
    # The retained root itself has no QSGRenderNode render() implementation and
    # never issues PyOpenGL calls.  The custom child exists only behind the
    # blocked branch for transitions/proofs.
    assert "def render(" not in root
    assert "glDrawArrays" not in root
    assert "from OpenGL" not in root


def test_native_reveal_readiness_remains_frame_swapped_gated():
    controller = _read("rendering/quick/scene_controller.py")
    telemetry = _read("rendering/quick/render/telemetry.py")
    assert "native_background_active" in controller
    assert "def note_native_background_visibility(" in telemetry
    assert "native_background_active=bool(visible and identity is not None)" in telemetry
    # Retained texture admission alone is not a new GUI show/update loop.
    assert "frameSwapped -> requestUpdate" not in controller
    assert "frameSwapped -> requestUpdate" not in telemetry


def test_transition_end_releases_only_duplicate_custom_image_textures():
    node = _read("rendering/quick/render/background_node.py")
    start = node.index("def release_presentation_textures")
    end = node.index("def releaseResources", start)
    method = node[start:end]
    assert "self._image_textures.release()" in method
    assert "self._transition_renderer.release_resources()" not in method
    assert "glDeleteProgram" not in method
    assert "glDeleteVertexArrays" not in method

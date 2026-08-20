"""Render-thread ownership for the current immutable presentation texture."""

from __future__ import annotations

from dataclasses import dataclass

from OpenGL import GL as gl

from ..image_state import PresentationImage
from .telemetry import RenderNodeTelemetry


def _int_state(name: int) -> int:
    value = gl.glGetIntegerv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


@dataclass(frozen=True, slots=True)
class _TextureRecord:
    texture_id: int
    identity: str
    byte_count: int
    counted_upload: bool = True


class ImageTextureOwner:
    """Own one base-image texture and any deletion still awaiting success."""

    def __init__(self, telemetry: RenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._current: _TextureRecord | None = None
        self._pending_deletions: dict[int, _TextureRecord] = {}

    @property
    def texture_id(self) -> int:
        return 0 if self._current is None else self._current.texture_id

    @property
    def identity(self) -> str | None:
        return None if self._current is None else self._current.identity

    @property
    def has_resources(self) -> bool:
        return self._current is not None or bool(self._pending_deletions)

    def ensure_uploaded(self, image: PresentationImage | None) -> int:
        """Upload a changed identity once, retaining no source-side Qt object."""

        self._drain_pending_deletions()
        if image is None:
            self.release()
            return 0
        if self._current is not None and self._current.identity == image.identity:
            return self._current.texture_id

        texture_id = self._upload(image)
        previous = self._current
        self._current = _TextureRecord(
            texture_id=texture_id,
            identity=image.identity,
            byte_count=image.byte_count,
        )
        if previous is not None:
            self._pending_deletions[previous.texture_id] = previous
        self._telemetry.note_image_uploaded(
            identity=image.identity,
            byte_count=image.byte_count,
            pending_release_count=len(self._pending_deletions),
        )
        self._drain_pending_deletions()
        return texture_id

    def release(self) -> None:
        """Delete all owned names; failed deletes remain tracked for retry."""

        if self._current is not None:
            current, self._current = self._current, None
            self._pending_deletions[current.texture_id] = current
            self._telemetry.note_image_release_pending(
                active_identity=None,
                pending_release_count=len(self._pending_deletions),
            )
        self._drain_pending_deletions()

    def _upload(self, image: PresentationImage) -> int:
        prior_active_texture = _int_state(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        prior_texture = _int_state(gl.GL_TEXTURE_BINDING_2D)
        prior_unpack_alignment = _int_state(gl.GL_UNPACK_ALIGNMENT)
        prior_unpack_row_length = _int_state(gl.GL_UNPACK_ROW_LENGTH)
        prior_unpack_skip_rows = _int_state(gl.GL_UNPACK_SKIP_ROWS)
        prior_unpack_skip_pixels = _int_state(gl.GL_UNPACK_SKIP_PIXELS)
        texture_id = 0
        try:
            texture_id = int(gl.glGenTextures(1))
            if texture_id <= 0:
                raise RuntimeError("OpenGL did not allocate a presentation texture")
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D,
                gl.GL_TEXTURE_MIN_FILTER,
                gl.GL_LINEAR,
            )
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D,
                gl.GL_TEXTURE_MAG_FILTER,
                gl.GL_LINEAR,
            )
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D,
                gl.GL_TEXTURE_WRAP_S,
                gl.GL_CLAMP_TO_EDGE,
            )
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D,
                gl.GL_TEXTURE_WRAP_T,
                gl.GL_CLAMP_TO_EDGE,
            )
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, 0)
            gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, 0)
            gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, 0)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA8,
                image.pixel_size[0],
                image.pixel_size[1],
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                image.rgba8,
            )
        except Exception:
            if texture_id:
                try:
                    gl.glDeleteTextures(1, [texture_id])
                except Exception:
                    self._pending_deletions[texture_id] = _TextureRecord(
                        texture_id=texture_id,
                        identity=image.identity,
                        byte_count=image.byte_count,
                        counted_upload=False,
                    )
                    self._telemetry.note_image_release_pending(
                        active_identity=self.identity,
                        pending_release_count=len(self._pending_deletions),
                    )
            raise
        finally:
            gl.glPixelStorei(gl.GL_UNPACK_SKIP_PIXELS, prior_unpack_skip_pixels)
            gl.glPixelStorei(gl.GL_UNPACK_SKIP_ROWS, prior_unpack_skip_rows)
            gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH, prior_unpack_row_length)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, prior_unpack_alignment)
            gl.glBindTexture(gl.GL_TEXTURE_2D, prior_texture)
            gl.glActiveTexture(prior_active_texture)
        return texture_id

    def _drain_pending_deletions(self) -> None:
        for texture_id, record in tuple(self._pending_deletions.items()):
            try:
                gl.glDeleteTextures(1, [texture_id])
            except Exception:
                self._telemetry.note_image_release_pending(
                    active_identity=self.identity,
                    pending_release_count=len(self._pending_deletions),
                )
                raise
            del self._pending_deletions[texture_id]
            if record.counted_upload:
                self._telemetry.note_image_released(
                    active_identity=self.identity,
                    byte_count=record.byte_count,
                    pending_release_count=len(self._pending_deletions),
                )
            else:
                self._telemetry.note_image_release_pending(
                    active_identity=self.identity,
                    pending_release_count=len(self._pending_deletions),
                )

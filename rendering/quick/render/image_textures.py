"""Render-thread ownership for base and transition presentation textures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from OpenGL import GL as gl

from ..image_state import PresentationImage
from .telemetry import RenderNodeTelemetry

if TYPE_CHECKING:
    from ..transitions.state import TransitionRun


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


@dataclass(frozen=True, slots=True)
class PresentationTextureBinding:
    """Current base texture and optional old/new pair for one transition run."""

    base_texture_id: int
    transition_run_id: int | None = None
    source_texture_id: int = 0
    destination_texture_id: int = 0

    @property
    def has_transition_pair(self) -> bool:
        return bool(
            self.transition_run_id is not None
            and self.source_texture_id
            and self.destination_texture_id
        )


class PresentationTextureHost:
    """Own shared base/old/new textures for one render-node context generation."""

    def __init__(self, telemetry: RenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._records: dict[str, _TextureRecord] = {}
        self._pending_deletions: dict[int, _TextureRecord] = {}
        self._base_identity: str | None = None
        self._transition_run_id: int | None = None
        self._source_identity: str | None = None
        self._destination_identity: str | None = None

    @property
    def texture_id(self) -> int:
        return self._texture_id_for(self._base_identity)

    @property
    def identity(self) -> str | None:
        return self._base_identity

    @property
    def has_resources(self) -> bool:
        return bool(self._records or self._pending_deletions)

    def synchronize(
        self,
        base_image: PresentationImage | None,
        transition_run: TransitionRun | None,
    ) -> PresentationTextureBinding:
        """Bind immutable base/run images without duplicating shared identities."""

        self._drain_pending_deletions()
        base_identity = None if base_image is None else base_image.identity
        desired: dict[str, PresentationImage] = {}
        if base_image is not None:
            desired[base_image.identity] = base_image

        run_id: int | None = None
        source_identity: str | None = None
        destination_identity: str | None = None
        if transition_run is not None:
            source = transition_run.request.source_image
            destination = transition_run.request.destination_image
            if base_identity != source.identity:
                raise RuntimeError(
                    "Quick transition source texture does not match the base image"
                )
            run_id = transition_run.run_id
            source_identity = source.identity
            destination_identity = destination.identity
            desired[source.identity] = source
            desired[destination.identity] = destination

        for identity, image in desired.items():
            if identity in self._records:
                continue
            texture_id = self._upload(image)
            self._records[identity] = _TextureRecord(
                texture_id=texture_id,
                identity=identity,
                byte_count=image.byte_count,
            )
            self._telemetry.note_image_uploaded(
                identity=identity,
                active_identity=base_identity,
                byte_count=image.byte_count,
                pending_release_count=len(self._pending_deletions),
            )

        self._base_identity = base_identity
        self._transition_run_id = run_id
        self._source_identity = source_identity
        self._destination_identity = destination_identity

        for identity in tuple(self._records):
            if identity in desired:
                continue
            record = self._records.pop(identity)
            self._pending_deletions[record.texture_id] = record
        if self._pending_deletions:
            self._telemetry.note_image_release_pending(
                active_identity=self.identity,
                pending_release_count=len(self._pending_deletions),
            )
        self._drain_pending_deletions()
        return self.binding()

    def binding(self) -> PresentationTextureBinding:
        return PresentationTextureBinding(
            base_texture_id=self.texture_id,
            transition_run_id=self._transition_run_id,
            source_texture_id=self._texture_id_for(self._source_identity),
            destination_texture_id=self._texture_id_for(
                self._destination_identity
            ),
        )

    def release(self) -> None:
        """Delete all owned names; failed deletes remain tracked for retry."""

        for record in self._records.values():
            self._pending_deletions[record.texture_id] = record
        self._records.clear()
        self._base_identity = None
        self._transition_run_id = None
        self._source_identity = None
        self._destination_identity = None
        if self._pending_deletions:
            self._telemetry.note_image_release_pending(
                active_identity=None,
                pending_release_count=len(self._pending_deletions),
            )
        self._drain_pending_deletions()

    def _texture_id_for(self, identity: str | None) -> int:
        if identity is None:
            return 0
        record = self._records.get(identity)
        return 0 if record is None else record.texture_id

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

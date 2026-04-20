"""Per-mode GL uniform renderers for the Spotify visualizer.

Each renderer encapsulates the uniform uploads for a single visualizer mode,
eliminating the monolithic ``if mode == 'xxx':`` blocks in the overlay's
``_render_with_shader`` method.

Every renderer exposes two functions:
    get_uniform_names() -> list[str]
        Returns the uniform names this mode requires (for GL location queries).
    upload_uniforms(gl, u: dict[str, int], state) -> bool
        Pushes all mode-specific uniforms.  *state* is the overlay instance.
        Returns False if the mode cannot render (e.g. missing bar data).
"""

from widgets.spotify_visualizer.renderers.spectrum import (
    get_uniform_names as spectrum_uniform_names,
    upload_uniforms as spectrum_upload,
)
from widgets.spotify_visualizer.renderers.oscilloscope import (
    get_uniform_names as oscilloscope_uniform_names,
    upload_uniforms as oscilloscope_upload,
)
from widgets.spotify_visualizer.renderers.blob import (
    get_uniform_names as blob_uniform_names,
    upload_uniforms as blob_upload,
)
from widgets.spotify_visualizer.renderers.sine_wave import (
    get_uniform_names as sine_wave_uniform_names,
    upload_uniforms as sine_wave_upload,
)
from widgets.spotify_visualizer.renderers.bubble import (
    get_uniform_names as bubble_uniform_names,
    upload_uniforms as bubble_upload,
)
from widgets.spotify_visualizer.renderers.goo import (
    get_uniform_names as goo_uniform_names,
    upload_uniforms as goo_upload,
)

RENDERERS = {
    'spectrum': (spectrum_uniform_names, spectrum_upload),
    'oscilloscope': (oscilloscope_uniform_names, oscilloscope_upload),
    'blob': (blob_uniform_names, blob_upload),
    'sine_wave': (sine_wave_uniform_names, sine_wave_upload),
    'bubble': (bubble_uniform_names, bubble_upload),
    'goo': (goo_uniform_names, goo_upload),
}


def get_all_uniform_names(mode: str) -> list:
    """Return the list of uniform names for *mode*."""
    entry = RENDERERS.get(mode)
    if entry is None:
        return []
    return entry[0]()


def upload_mode_uniforms(mode: str, gl, u: dict, state) -> bool:
    """Upload all mode-specific uniforms for *mode*.  Returns False on failure."""
    entry = RENDERERS.get(mode)
    if entry is None:
        return False
    return entry[1](gl, u, state)

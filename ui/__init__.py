"""UI module for screensaver configuration."""

# Register the ordinary binary Qt resource pack before any stylesheet or QML
# consumer resolves qrc:/srpss/... URLs. Guided Setup remains lazy.
from .resources.registration import ensure_core_resources

ensure_core_resources()

__all__: list[str] = []

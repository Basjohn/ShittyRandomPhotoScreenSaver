"""Neon Basin's canonical surface/body choices. Retired values migrate at input only."""
from types import MappingProxyType

BASIN_SURFACE_STYLES = MappingProxyType({
    "Vertices": 2, "Glass": 4, "Glass + Vertices": 6,
})
BASIN_BODY_MODES = MappingProxyType({"Sun": 0, "Moon": 1})

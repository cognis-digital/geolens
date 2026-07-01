"""geolens — part of the Cognis Neural Suite."""
try:  # re-export the tool's public API + identity from core
    from geolens.core import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass
try:
    from geolens.core import TOOL_NAME, TOOL_VERSION
except Exception:  # pragma: no cover
    TOOL_NAME = "geolens"
    TOOL_VERSION = "0.2.0"
__version__ = TOOL_VERSION

try:  # native, zero-dep intel export (GeoJSON / STIX 2.1 / KML)
    from geolens import intel  # noqa: F401
    from geolens.intel import to_geojson, to_stix, to_kml, export  # noqa: F401
except Exception:  # pragma: no cover
    pass

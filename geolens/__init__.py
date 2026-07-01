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

try:  # native, zero-dep intel export (GeoJSON / STIX 2.1)
    from geolens import intel  # noqa: F401
    from geolens.intel import to_geojson, to_stix, export  # noqa: F401
except Exception:  # pragma: no cover
    pass

try:  # forensics & analytical geolocation (offline, stdlib only)
    from geolens import forensics  # noqa: F401
    from geolens.forensics import (  # noqa: F401
        haversine_km,
        initial_bearing,
        destination_point,
        resection,
        reverse_heading,
        horizon_distance_km,
        max_visible_distance_km,
        is_peak_visible,
        timezone_crosscheck,
        camera_fingerprint,
        fingerprint_consistency,
        cluster_locations,
        batch_triage,
        build_timeline,
        timeline_to_geojson,
    )
except Exception:  # pragma: no cover
    pass

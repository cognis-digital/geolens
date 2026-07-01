"""GEOLENS forensics & analytical geolocation — offline, standard-library only.

This module *multiplies* what :mod:`geolens.core` can do for a verification /
OSINT analyst. Everything here is defensive and analytical: it reasons about
scene geometry, cross-checks metadata for internal consistency, and organises
sets of images. Nothing here targets anything or leaves the machine — there are
no network calls and no side effects beyond returning plain dicts.

Capabilities
------------

* **Geodesy** (:func:`destination_point`, :func:`initial_bearing`,
  :func:`haversine_km`, :func:`resection`) — walk a bearing/distance from a
  known point, measure a bearing between points, and *resect* an observer
  position from two known landmarks and the bearings to them. This turns a
  photo with two identifiable landmarks into a candidate camera position.

* **Reverse heading** (:func:`reverse_heading`) — a landmark seen at pixel
  offset ``x`` in a frame of known horizontal field-of-view, combined with the
  camera's compass heading, yields the true bearing to that landmark (and,
  with the landmark's coordinates, a back-bearing line the analyst can plot).

* **Horizon / terrain cues** (:func:`horizon_distance_km`,
  :func:`max_visible_distance_km`, :func:`is_peak_visible`) — geometric-horizon
  math (with standard atmospheric refraction) to sanity-check whether a distant
  peak *could* appear over the horizon from a claimed vantage height. A useful
  falsification test for "shot from here" claims.

* **Timezone cross-check** (:func:`timezone_crosscheck`) — compares the EXIF
  local capture timestamp against the GPS UTC timestamp to infer the camera's
  UTC offset, converts that to a plausible longitude band, and flags an image
  whose GPS longitude is inconsistent with its own clock.

* **Camera fingerprint consistency** (:func:`camera_fingerprint`,
  :func:`fingerprint_consistency`) — extracts a device/lens fingerprint from
  EXIF and compares fingerprints across an image set to surface tampering /
  splicing signals (mixed makes, impossible dimension changes, missing-but-
  expected tags).

All angles are degrees, all distances kilometres, all bearings measured
clockwise from true north unless stated otherwise.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Mean Earth radius (km), IUGG.
EARTH_RADIUS_KM = 6371.0088
# Standard terrestrial refraction coefficient (k ~= 0.13) folds into the 3.57
# vs 3.86 constant in the horizon formula; we use the refraction-corrected one.
_HORIZON_K = 3.86  # km per sqrt(metre) with standard refraction (3.57 geometric)


# ---------------------------------------------------------------------------
# Geodesy
# ---------------------------------------------------------------------------

def _validate_latlon(lat: float, lon: float) -> Tuple[float, float]:
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        raise ValueError("lat and lon must be numeric")
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("lat and lon must be finite")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"lat {lat} out of range [-90, 90]")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"lon {lon} out of range [-180, 180]")
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    lat1, lon1 = _validate_latlon(lat1, lon1)
    lat2, lon2 = _validate_latlon(lat2, lon2)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return round(2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a))), 4)


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2 (deg from N)."""
    lat1, lon1 = _validate_latlon(lat1, lon1)
    lat2, lon2 = _validate_latlon(lat2, lon2)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(y, x)) + 360.0) % 360.0, 4)


def destination_point(lat: float, lon: float, bearing_deg: float,
                      distance_km: float) -> Dict[str, float]:
    """Point reached by travelling ``distance_km`` along ``bearing_deg``.

    Direct geodesic (spherical) solution — the inverse of
    :func:`initial_bearing` + :func:`haversine_km`.
    """
    lat, lon = _validate_latlon(lat, lon)
    try:
        bearing_deg = float(bearing_deg)
        distance_km = float(distance_km)
    except (TypeError, ValueError):
        raise ValueError("bearing and distance must be numeric")
    if not (math.isfinite(bearing_deg) and math.isfinite(distance_km)):
        raise ValueError("bearing and distance must be finite")
    if distance_km < 0:
        raise ValueError("distance_km must be non-negative")
    ang = distance_km / EARTH_RADIUS_KM
    br = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(ang)
                   + math.cos(p1) * math.sin(ang) * math.cos(br))
    l2 = l1 + math.atan2(math.sin(br) * math.sin(ang) * math.cos(p1),
                         math.cos(ang) - math.sin(p1) * math.sin(p2))
    out_lon = (math.degrees(l2) + 540.0) % 360.0 - 180.0  # normalise to [-180,180)
    return {"latitude": round(math.degrees(p2), 6),
            "longitude": round(out_lon, 6)}


def resection(landmark1: Tuple[float, float], bearing1_deg: float,
              landmark2: Tuple[float, float], bearing2_deg: float,
              *, max_km: float = 500.0) -> Dict[str, Any]:
    """Estimate observer position from two landmarks and the bearing to each.

    Classic map-and-compass *resection*: the observer lies where the two
    back-bearing lines cross. We solve it robustly by projecting each landmark's
    back-bearing as a great-circle and finding the along-line distance that
    minimises the gap between the two lines (a 1-D search that is stable for the
    short-to-medium ranges OSINT photos actually cover).

    Returns the estimated observer ``latitude``/``longitude`` plus a
    ``residual_km`` quality figure (how close the two lines actually came).
    """
    lat1, lon1 = _validate_latlon(*landmark1)
    lat2, lon2 = _validate_latlon(*landmark2)
    back1 = (float(bearing1_deg) + 180.0) % 360.0
    back2 = (float(bearing2_deg) + 180.0) % 360.0
    if max_km <= 0:
        raise ValueError("max_km must be positive")

    def gap(d1: float) -> Tuple[float, Dict[str, float]]:
        obs = destination_point(lat1, lon1, back1, d1)
        # distance from landmark2 to this candidate, and the required bearing2
        d2 = haversine_km(lat2, lon2, obs["latitude"], obs["longitude"])
        proj = destination_point(lat2, lon2, back2, d2)
        return haversine_km(obs["latitude"], obs["longitude"],
                            proj["latitude"], proj["longitude"]), obs

    # Golden-section-ish coarse+fine scan over distance along line 1.
    best_gap = float("inf")
    best_obs: Dict[str, float] = {"latitude": lat1, "longitude": lon1}
    steps = 400
    for i in range(1, steps + 1):
        d1 = max_km * i / steps
        g, obs = gap(d1)
        if g < best_gap:
            best_gap, best_obs = g, obs
    # local refinement
    span = max_km / steps
    center = haversine_km(lat1, lon1, best_obs["latitude"], best_obs["longitude"])
    for i in range(-20, 21):
        d1 = center + span * i / 20.0
        if d1 <= 0:
            continue
        g, obs = gap(d1)
        if g < best_gap:
            best_gap, best_obs = g, obs
    return {
        "latitude": best_obs["latitude"],
        "longitude": best_obs["longitude"],
        "residual_km": round(best_gap, 4),
        "converged": best_gap < 1.0,
    }


# ---------------------------------------------------------------------------
# Reverse heading — landmark bearing from a photo frame
# ---------------------------------------------------------------------------

def reverse_heading(camera_heading_deg: float, landmark_px_x: float,
                    image_width_px: float, horizontal_fov_deg: float,
                    ) -> Dict[str, float]:
    """True bearing to a landmark given where it sits in the frame.

    ``camera_heading_deg`` is the compass direction of the optical axis (frame
    centre). A landmark at pixel column ``landmark_px_x`` in an image
    ``image_width_px`` wide, shot with a lens of ``horizontal_fov_deg``, sits at
    an angular offset from centre using the rectilinear (pinhole) projection
    ``offset = atan((2x/W - 1) * tan(FOV/2))`` — not a naive linear map, which
    would be wrong toward the frame edges.
    """
    for name, v in (("image_width_px", image_width_px),
                    ("horizontal_fov_deg", horizontal_fov_deg)):
        if float(v) <= 0:
            raise ValueError(f"{name} must be positive")
    if not (0.0 <= float(landmark_px_x) <= float(image_width_px)):
        raise ValueError("landmark_px_x must lie within [0, image_width_px]")
    if not (0.0 < float(horizontal_fov_deg) < 180.0):
        raise ValueError("horizontal_fov_deg must be in (0, 180)")
    half = math.tan(math.radians(horizontal_fov_deg) / 2.0)
    norm = (2.0 * landmark_px_x / image_width_px) - 1.0  # -1 (left) .. +1 (right)
    offset_deg = math.degrees(math.atan(norm * half))
    bearing = (float(camera_heading_deg) + offset_deg) % 360.0
    return {
        "landmark_bearing_deg": round(bearing, 4),
        "offset_from_center_deg": round(offset_deg, 4),
    }


# ---------------------------------------------------------------------------
# Horizon / terrain visibility cues
# ---------------------------------------------------------------------------

def horizon_distance_km(observer_height_m: float) -> float:
    """Distance to the visible sea-level horizon from a given eye height.

    Uses the refraction-corrected constant (``d ~= 3.86 * sqrt(h)`` km with
    ``h`` in metres), matching real-world visibility rather than the pure
    geometric ``3.57``.
    """
    h = float(observer_height_m)
    if h < 0:
        raise ValueError("observer_height_m must be non-negative")
    return round(_HORIZON_K * math.sqrt(h), 4)


def max_visible_distance_km(observer_height_m: float, target_height_m: float,
                            ) -> float:
    """Max distance at which a target of given height can top the horizon.

    The sum of each object's horizon distance: the observer sees to their own
    horizon, and the target pokes up from its own. This is the standard
    "can I see that mountain from the beach?" bound.
    """
    return round(horizon_distance_km(observer_height_m)
                 + horizon_distance_km(target_height_m), 4)


def is_peak_visible(observer_height_m: float, target_height_m: float,
                    actual_distance_km: float) -> Dict[str, Any]:
    """Falsification test: could a peak be seen from the claimed vantage?

    Returns the geometric bound and whether the *claimed* separation is within
    it. A ``visible=False`` result means the peak is geometrically below the
    horizon at that range — a strong signal against a "shot from here" claim.
    """
    d = float(actual_distance_km)
    if d < 0:
        raise ValueError("actual_distance_km must be non-negative")
    limit = max_visible_distance_km(observer_height_m, target_height_m)
    return {
        "max_visible_distance_km": limit,
        "actual_distance_km": round(d, 4),
        "visible": d <= limit,
        "margin_km": round(limit - d, 4),
    }


# ---------------------------------------------------------------------------
# Timezone / longitude cross-check
# ---------------------------------------------------------------------------

def _parse_exif_datetime(s: str) -> Optional[_dt.datetime]:
    """Parse the EXIF ``YYYY:MM:DD HH:MM:SS`` local timestamp (naive)."""
    if not s or not isinstance(s, str):
        return None
    try:
        return _dt.datetime.strptime(s.strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _gps_utc_from_exif(gps: Dict[str, Any]) -> Optional[_dt.datetime]:
    """Reconstruct the GPS UTC instant from GPSDateStamp + GPSTimeStamp."""
    ds = gps.get("GPSDateStamp")
    ts = gps.get("GPSTimeStamp")
    if not ds or not ts:
        return None
    try:
        y, m, d = [int(x) for x in str(ds).replace("-", ":").split(":")[:3]]
    except (ValueError, TypeError):
        return None

    def rat(v):
        if isinstance(v, tuple) and len(v) == 2 and v[1]:
            return v[0] / v[1]
        return float(v)

    try:
        hh, mm, ss = (rat(ts[0]), rat(ts[1]), rat(ts[2]))
    except (TypeError, IndexError, ZeroDivisionError, ValueError):
        return None
    try:
        base = _dt.datetime(y, m, d, tzinfo=_dt.timezone.utc)
        return base + _dt.timedelta(hours=hh, minutes=mm, seconds=ss)
    except ValueError:
        return None


def timezone_crosscheck(exif: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-check the EXIF local clock against GPS UTC + GPS longitude.

    Camera clocks record *local* civil time; the GPS block records *UTC*. The
    difference implies the camera's UTC offset, which maps to a longitude band
    (15° of longitude per hour). If the image also carries a GPS longitude, we
    flag it as inconsistent when it falls far outside the band implied by its
    own clock — a classic sign of a spoofed/edited timestamp or transplanted
    GPS.
    """
    out: Dict[str, Any] = {
        "has_local_time": False,
        "has_gps_time": False,
        "utc_offset_hours": None,
        "implied_longitude_center": None,
        "gps_longitude": None,
        "consistent": None,
        "notes": [],
    }
    local_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
    local = _parse_exif_datetime(local_str) if local_str else None
    gps = exif.get("GPS") or {}
    gps_utc = _gps_utc_from_exif(gps)
    out["has_local_time"] = local is not None
    out["has_gps_time"] = gps_utc is not None

    if local is not None and gps_utc is not None:
        # Local minus UTC, rounded to the nearest quarter hour (real offsets
        # include :30 and :45 zones).
        delta_h = (local - gps_utc.replace(tzinfo=None)).total_seconds() / 3600.0
        offset = round(delta_h * 4) / 4.0
        out["utc_offset_hours"] = offset
        center = max(-180.0, min(180.0, offset * 15.0))
        out["implied_longitude_center"] = round(center, 3)

    # GPS longitude, if the DMS is present, via a light local conversion.
    lon = None
    if "GPSLongitude" in gps:
        try:
            dms = gps["GPSLongitude"]
            def r(x):
                return x[0] / x[1] if x[1] else 0.0
            lon = r(dms[0]) + r(dms[1]) / 60.0 + r(dms[2]) / 3600.0
            if str(gps.get("GPSLongitudeRef", "E")).upper().startswith("W"):
                lon = -lon
            out["gps_longitude"] = round(lon, 6)
        except (TypeError, IndexError, ZeroDivisionError):
            lon = None

    if out["implied_longitude_center"] is not None and lon is not None:
        # A time zone spans ~15deg; allow one zone of slack either side (zones
        # are drawn generously and DST shifts them), so ±22.5deg is "plausible".
        diff = abs(((lon - out["implied_longitude_center"] + 180) % 360) - 180)
        out["longitude_gap_deg"] = round(diff, 3)
        out["consistent"] = diff <= 22.5
        if not out["consistent"]:
            out["notes"].append(
                "GPS longitude is far from the band implied by the camera clock "
                "vs GPS-UTC offset — possible edited timestamp or transplanted GPS."
            )
    elif not out["has_gps_time"]:
        out["notes"].append("No GPS time present; cannot derive UTC offset.")
    return out


# ---------------------------------------------------------------------------
# Camera / lens fingerprint consistency
# ---------------------------------------------------------------------------

_SOFTWARE_TAG = "Tag0x0131"  # EXIF Software tag id


def camera_fingerprint(exif: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a stable device/lens fingerprint from EXIF for comparison."""
    def g(key):
        v = exif.get(key)
        return str(v).strip() if v is not None else None

    dims = None
    px = exif.get("PixelXDimension")
    py = exif.get("PixelYDimension")
    if px is not None and py is not None:
        try:
            dims = (int(px), int(py))
        except (TypeError, ValueError):
            dims = None
    return {
        "make": g("Make"),
        "model": g("Model"),
        "software": g("Software") or g(_SOFTWARE_TAG),
        "orientation": exif.get("Orientation"),
        "dimensions": dims,
        "has_gps": bool(exif.get("GPS")),
    }


def fingerprint_consistency(exifs: Sequence[Dict[str, Any]],
                            ) -> Dict[str, Any]:
    """Compare fingerprints across an image set and surface tampering signals.

    Flags raised (each a plain-language note):

    * mixed camera makes/models where a single-source set was expected
    * an editing-software tag on an otherwise-camera-native set (re-save signal)
    * multiple distinct sensor dimensions from the same model (crop/splice hint)
    """
    prints = [camera_fingerprint(e) for e in exifs]
    makes = sorted({p["make"] for p in prints if p["make"]})
    models = sorted({p["model"] for p in prints if p["model"]})
    softwares = sorted({p["software"] for p in prints if p["software"]})
    dims = sorted({p["dimensions"] for p in prints if p["dimensions"]})

    flags: List[str] = []
    if len(makes) > 1:
        flags.append(f"multiple camera makes present: {makes}")
    if len(models) > 1:
        flags.append(f"multiple camera models present: {models}")
    if softwares:
        flags.append(f"editing/processing software tag(s) present: {softwares}")
    # same model, several dimension pairs => likely cropping/splicing
    by_model: Dict[str, set] = {}
    for p in prints:
        if p["model"] and p["dimensions"]:
            by_model.setdefault(p["model"], set()).add(p["dimensions"])
    for model, ds in by_model.items():
        if len(ds) > 1:
            flags.append(
                f"model {model!r} appears with differing dimensions {sorted(ds)}")
    return {
        "count": len(prints),
        "distinct_makes": makes,
        "distinct_models": models,
        "distinct_software": softwares,
        "distinct_dimensions": [list(d) for d in dims],
        "single_source_likely": len(makes) <= 1 and len(models) <= 1,
        "flags": flags,
        "fingerprints": prints,
    }


# ---------------------------------------------------------------------------
# Batch triage + spatial clustering
# ---------------------------------------------------------------------------

def cluster_locations(points: Sequence[Dict[str, float]],
                      radius_km: float = 1.0) -> List[Dict[str, Any]]:
    """Single-link cluster a set of GPS points by great-circle distance.

    ``points`` is a sequence of dicts with ``latitude``/``longitude`` (extra
    keys such as an image ``id`` are carried through into each cluster's
    ``members``). Two points join the same cluster when they are within
    ``radius_km`` of *any* current member (single-linkage), which groups a
    walked route or a venue into one place without needing a fixed k.
    """
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")
    pts = [p for p in points
           if p.get("latitude") is not None and p.get("longitude") is not None]
    n = len(pts)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if haversine_km(pts[i]["latitude"], pts[i]["longitude"],
                            pts[j]["latitude"], pts[j]["longitude"]) <= radius_km:
                parent[find(i)] = find(j)

    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters: List[Dict[str, Any]] = []
    for members_idx in groups.values():
        members = [pts[i] for i in members_idx]
        clat = sum(m["latitude"] for m in members) / len(members)
        clon = sum(m["longitude"] for m in members) / len(members)
        clusters.append({
            "centroid": {"latitude": round(clat, 6), "longitude": round(clon, 6)},
            "size": len(members),
            "members": members,
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


def batch_triage(records: Sequence[Dict[str, Any]],
                 radius_km: float = 1.0) -> Dict[str, Any]:
    """Triage a set of analysed images: split geotagged vs scrubbed, cluster.

    Each ``record`` is expected to look like an :func:`geolens.core.analyze_image`
    result with an added ``id`` (e.g. the filename). Returns a summary plus the
    spatial clusters of the geotagged subset — the "who was where" view of a
    seized/collected folder.
    """
    geotagged: List[Dict[str, Any]] = []
    scrubbed: List[Dict[str, Any]] = []
    for rec in records:
        gps = rec.get("gps")
        rid = rec.get("id")
        if gps and gps.get("latitude") is not None:
            geotagged.append({
                "id": rid,
                "latitude": gps["latitude"],
                "longitude": gps["longitude"],
            })
        else:
            scrubbed.append({"id": rid})
    clusters = cluster_locations(geotagged, radius_km=radius_km)
    return {
        "total": len(records),
        "geotagged": len(geotagged),
        "scrubbed": len(scrubbed),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "scrubbed_ids": [s["id"] for s in scrubbed],
    }


# ---------------------------------------------------------------------------
# Timeline exporter (chain-of-thought / GeoJSON)
# ---------------------------------------------------------------------------

def _record_time(rec: Dict[str, Any]) -> Optional[_dt.datetime]:
    for key in ("datetimeoriginal", "datetime"):
        v = rec.get(key)
        if v:
            t = _parse_exif_datetime(v) if isinstance(v, str) else None
            if t:
                return t
    exif = rec.get("exif") or {}
    return _parse_exif_datetime(exif.get("DateTimeOriginal") or exif.get("DateTime") or "")


def build_timeline(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Order geotagged, time-stamped images into a movement timeline.

    Returns an ordered list of ``events`` (id, time, lat/lon) plus inter-event
    ``legs`` with distance, elapsed time and implied speed — a reasoned
    ("chain-of-thought") reconstruction of a subject's movement, and the input
    to :func:`timeline_to_geojson`.
    """
    events: List[Dict[str, Any]] = []
    for rec in records:
        gps = rec.get("gps")
        t = _record_time(rec)
        if gps and gps.get("latitude") is not None and t is not None:
            events.append({
                "id": rec.get("id"),
                "time": t,
                "latitude": gps["latitude"],
                "longitude": gps["longitude"],
            })
    events.sort(key=lambda e: e["time"])
    legs: List[Dict[str, Any]] = []
    for a, b in zip(events, events[1:]):
        dist = haversine_km(a["latitude"], a["longitude"],
                            b["latitude"], b["longitude"])
        secs = (b["time"] - a["time"]).total_seconds()
        speed = round(dist / (secs / 3600.0), 3) if secs > 0 else None
        legs.append({
            "from": a["id"], "to": b["id"],
            "distance_km": dist,
            "elapsed_s": secs,
            "implied_speed_kmh": speed,
        })
    return {
        "event_count": len(events),
        "events": [
            {"id": e["id"], "time": e["time"].isoformat(),
             "latitude": e["latitude"], "longitude": e["longitude"]}
            for e in events
        ],
        "legs": legs,
        "_events_dt": events,  # internal, consumed by timeline_to_geojson
    }


def timeline_to_geojson(timeline: Dict[str, Any]) -> str:
    """Render a :func:`build_timeline` result as GeoJSON.

    Emits one ``Point`` Feature per event (ordered, with time + a ``seq``
    property) and, when there are two or more events, a ``LineString`` tracing
    the path — ready to drop into Leaflet / QGIS / kepler.gl.
    """
    import json

    events = timeline.get("_events_dt")
    if events is None:
        # reconstruct from serialised events
        events = []
        for e in timeline.get("events", []):
            events.append({
                "id": e["id"],
                "time": _dt.datetime.fromisoformat(e["time"]),
                "latitude": e["latitude"], "longitude": e["longitude"],
            })
    feats: List[Dict[str, Any]] = []
    for seq, e in enumerate(events):
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [e["longitude"], e["latitude"]]},
            "properties": {"id": e["id"], "seq": seq,
                           "time": e["time"].isoformat(),
                           "source": "geolens:timeline"},
        })
    if len(events) >= 2:
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[e["longitude"], e["latitude"]]
                                         for e in events]},
            "properties": {"source": "geolens:timeline", "kind": "path",
                           "point_count": len(events)},
        })
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=2)

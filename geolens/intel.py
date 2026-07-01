"""Native, dependency-free intel export for geolens image analysis.

Turns an :func:`~geolens.core.analyze_image` result into shareable geospatial
intelligence for an OSINT case file:

* **GeoJSON** — the image's recovered GPS fix as a map point (camera make/model,
  capture time, and an OSM link travel along as properties).
* **STIX 2.1** — a ``location`` + ``observed-data`` + ``note`` bundle so the fix
  drops into OpenCTI / a TIP alongside the rest of an investigation.

When no GPS is present the exporters still emit a valid (point-less) document, so
they're safe to run unconditionally in a pipeline. Standard library only;
complements :mod:`geolens.connect` (the cognis-connect bridge).
"""

from __future__ import annotations

import json
import uuid

_NS = uuid.UUID("9e0107e5-0000-4000-8000-636f676e6973")
_TS = "2026-01-01T00:00:00.000Z"


def _props(result: dict) -> dict:
    keep = ("make", "model", "datetimeoriginal", "datetime", "maps_url", "has_exif")
    return {k: result[k] for k in keep if k in result}


def _seed(result: dict) -> str:
    gps = result.get("gps") or {}
    return json.dumps({"gps": gps, "p": _props(result)}, sort_keys=True, default=str)


def _altitude(gps: dict):
    """Read altitude regardless of key spelling.

    ``core.gps_from_exif`` emits ``altitude_m``; older/hand-built records used
    ``altitude``. Accept either so real EXIF altitude actually reaches output.
    """
    if "altitude_m" in gps:
        return gps["altitude_m"]
    if "altitude" in gps:
        return gps["altitude"]
    return None


def to_geojson(result: dict) -> str:
    feats = []
    gps = result.get("gps")
    if gps and gps.get("latitude") is not None and gps.get("longitude") is not None:
        alt = _altitude(gps)
        coords = [gps["longitude"], gps["latitude"]]  # [lon,lat]
        if alt is not None:
            coords.append(alt)  # GeoJSON position may carry elevation
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {"source": "geolens:exif-gps", **_props(result),
                           **({"altitude": alt} if alt is not None else {})},
        })
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=2)


def to_stix(result: dict) -> str:
    objects: list = []
    refs: list = []
    gps = result.get("gps")
    note_id = f"note--{uuid.uuid5(_NS, 'note:' + _seed(result))}"
    obj_refs = []
    if gps and gps.get("latitude") is not None:
        lat, lon = gps["latitude"], gps["longitude"]
        loc_id = f"location--{uuid.uuid5(_NS, f'loc:{lat},{lon}')}"
        objects.append({
            "type": "location", "spec_version": "2.1", "id": loc_id,
            "created": _TS, "modified": _TS,
            "latitude": lat, "longitude": lon,
            "name": "geolens EXIF GPS fix",
        })
        obs_id = f"observed-data--{uuid.uuid5(_NS, 'obs:' + _seed(result))}"
        objects.append({
            "type": "observed-data", "spec_version": "2.1", "id": obs_id,
            "created": _TS, "modified": _TS,
            "first_observed": _TS, "last_observed": _TS, "number_observed": 1,
            "object_refs": [loc_id],
        })
        obj_refs = [loc_id, obs_id]
        refs.extend([loc_id, obs_id])
    cam = " ".join(str(result[k]) for k in ("make", "model") if k in result).strip()
    objects.append({
        "type": "note", "spec_version": "2.1", "id": note_id,
        "created": _TS, "modified": _TS,
        "abstract": "geolens image geolocation",
        "content": (f"EXIF GPS fix at {gps['latitude']},{gps['longitude']}"
                    if gps else "No GPS present in EXIF.")
                   + (f" Camera: {cam}." if cam else ""),
        "labels": ["image-geolocation", "exif" if result.get("has_exif") else "no-exif"],
        "object_refs": obj_refs or [note_id],
        **({"external_references": [{"source_name": "openstreetmap", "url": result["maps_url"]}]}
           if result.get("maps_url") else {}),
    })
    refs.append(note_id)
    report_id = f"report--{uuid.uuid5(_NS, 'report:' + '|'.join(refs))}"
    report = {
        "type": "report", "spec_version": "2.1", "id": report_id,
        "created": _TS, "modified": _TS, "name": "geolens geolocation report",
        "report_types": ["observed-data"], "published": _TS, "object_refs": refs,
    }
    return json.dumps({
        "type": "bundle",
        "id": f"bundle--{uuid.uuid5(_NS, report_id)}",
        "objects": [report] + objects,
    }, indent=2)


def _xml_escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def to_kml(result: dict) -> str:
    """Render the fix as a KML ``Placemark`` for Google Earth / QGIS / Maps.

    KML coordinates are ``lon,lat[,alt]`` (note: altitude, when present, uses
    ``absolute`` altitude mode so Earth places it against sea level). With no
    GPS the document is a valid, empty ``<Document>`` — safe in a pipeline,
    mirroring :func:`to_geojson` / :func:`to_stix`.
    """
    gps = result.get("gps") or {}
    lat, lon = gps.get("latitude"), gps.get("longitude")
    placemarks = ""
    if lat is not None and lon is not None:
        alt = _altitude(gps)
        coord = f"{lon},{lat}" + (f",{alt}" if alt is not None else "")
        cam = " ".join(str(result[k]) for k in ("make", "model") if k in result).strip()
        desc_bits = []
        if cam:
            desc_bits.append(f"Camera: {cam}")
        for k in ("datetimeoriginal", "datetime"):
            if result.get(k):
                desc_bits.append(f"Captured: {result[k]}")
                break
        if result.get("maps_url"):
            desc_bits.append(result["maps_url"])
        desc = _xml_escape("; ".join(desc_bits)) if desc_bits else ""
        altitude_mode = ("<altitudeMode>absolute</altitudeMode>"
                         if alt is not None else "")
        placemarks = (
            "\n    <Placemark>"
            "\n      <name>geolens EXIF GPS fix</name>"
            f"\n      <description>{desc}</description>"
            f"\n      <Point>{altitude_mode}<coordinates>{coord}</coordinates></Point>"
            "\n    </Placemark>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '\n<kml xmlns="http://www.opengis.net/kml/2.2">'
        "\n  <Document>"
        "\n    <name>geolens geolocation</name>"
        f"{placemarks}"
        "\n  </Document>"
        "\n</kml>\n"
    )


_EXPORTERS = {"geojson": to_geojson, "stix": to_stix, "kml": to_kml}


def export(result: dict, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in _EXPORTERS:
        raise ValueError(f"unknown export format {fmt!r}; choose one of {sorted(_EXPORTERS)}")
    return _EXPORTERS[fmt](result)

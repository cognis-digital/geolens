"""GEOLENS core engine — real EXIF parsing + solar geolocation math.

Everything here is pure standard library:

* ``extract_exif`` walks the TIFF/EXIF IFD structure of a JPEG (APP1 marker)
  and the EXIF SubIFD + GPS IFD, decoding the common tag types. This is a real
  binary parser, not a wrapper.
* ``gps_from_exif`` converts the rational DMS GPS tags into decimal degrees.
* ``sun_position`` implements the NOAA solar-position algorithm (azimuth +
  elevation) for a given UTC instant and observer location.
* ``estimate_latitude_from_shadow`` inverts solar noon shadow geometry to
  recover an observer latitude from a shadow length ratio — the classic
  Bellingcat \"shadow stick\" geolocation technique.
"""
from __future__ import annotations

import datetime as _dt
import math
import os as _os
import struct
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = "geolens"


def _read_version() -> str:
    """Single source of truth: the repo-root ``VERSION`` file, if present."""
    here = _os.path.dirname(_os.path.abspath(__file__))
    vfile = _os.path.join(_os.path.dirname(here), "VERSION")
    try:
        with open(vfile, encoding="utf-8") as fh:
            v = fh.read().strip()
            if v:
                return v
    except OSError:
        pass
    return "0.0.0"


TOOL_VERSION = _read_version()

# ---------------------------------------------------------------------------
# EXIF / TIFF tag parsing
# ---------------------------------------------------------------------------

# TIFF field type -> (struct code, byte size)
_TYPE_SIZES = {
    1: ("B", 1),   # BYTE
    2: ("c", 1),   # ASCII
    3: ("H", 2),   # SHORT
    4: ("I", 4),   # LONG
    5: ("II", 8),  # RATIONAL (num/den)
    7: ("B", 1),   # UNDEFINED
    9: ("i", 4),   # SLONG
    10: ("ii", 8), # SRATIONAL
}

# Subset of tags we name; everything else is reported by numeric id.
_TAG_NAMES = {
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x0132: "DateTime",
    0x8769: "ExifIFDPointer",
    0x8825: "GPSInfoIFDPointer",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
}

_GPS_TAG_NAMES = {
    0x0000: "GPSVersionID",
    0x0001: "GPSLatitudeRef",
    0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef",
    0x0004: "GPSLongitude",
    0x0005: "GPSAltitudeRef",
    0x0006: "GPSAltitude",
    0x0007: "GPSTimeStamp",
    0x0012: "GPSMapDatum",
    0x001D: "GPSDateStamp",
}


def _find_exif_segment(data: bytes) -> Optional[bytes]:
    """Locate the APP1 EXIF payload (after the 'Exif\\x00\\x00' header)."""
    if data[:2] != b"\xff\xd8":  # not a JPEG
        return None
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:  # start of scan; image data follows
            break
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        seg = data[i + 4 : i + 2 + seg_len]
        if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
            return seg[6:]
        i += 2 + seg_len
    return None


def _read_value(buf: bytes, endian: str, ftype: int, count: int, voff: int):
    code, size = _TYPE_SIZES.get(ftype, ("B", 1))
    total = size * count
    raw = buf[voff : voff + total]
    if ftype == 2:  # ASCII
        return raw.split(b"\x00", 1)[0].decode("latin-1", "replace")
    if ftype in (5, 10):  # rationals
        vals = []
        for k in range(count):
            a, b = struct.unpack(
                endian + ("II" if ftype == 5 else "ii"),
                raw[k * 8 : k * 8 + 8],
            )
            vals.append((a, b))
        return vals[0] if count == 1 else vals
    fmt = endian + {1: "B", 3: "H", 4: "I", 7: "B", 9: "i"}.get(ftype, "B") * count
    vals = list(struct.unpack(fmt, raw))
    return vals[0] if count == 1 else vals


def _parse_ifd(buf: bytes, endian: str, offset: int) -> Tuple[Dict[int, Any], List[int]]:
    """Parse one IFD; returns {tag_id: value} and trailing sub-IFD pointers."""
    entries: Dict[int, Any] = {}
    if offset + 2 > len(buf):
        return entries, []
    (count,) = struct.unpack(endian + "H", buf[offset : offset + 2])
    pos = offset + 2
    for _ in range(count):
        if pos + 12 > len(buf):
            break
        tag, ftype, cnt = struct.unpack(endian + "HHI", buf[pos : pos + 8])
        _, size = _TYPE_SIZES.get(ftype, ("B", 1))
        total = size * cnt
        if total <= 4:
            value = _read_value(buf, endian, ftype, cnt, pos + 8)
        else:
            (voff,) = struct.unpack(endian + "I", buf[pos + 8 : pos + 12])
            value = _read_value(buf, endian, ftype, cnt, voff)
        entries[tag] = value
        pos += 12
    return entries, []


def extract_exif(image_bytes: bytes) -> Dict[str, Any]:
    """Return a dict of decoded EXIF/GPS tags, or ``{}`` if none present.

    :raises TypeError: if ``image_bytes`` is not bytes-like.
    """
    if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"image_bytes must be bytes-like, got {type(image_bytes).__name__}"
        )
    image_bytes = bytes(image_bytes)
    if len(image_bytes) < 2:
        return {}
    seg = _find_exif_segment(image_bytes)
    if seg is None:
        return {}
    bo = seg[:2]
    if bo == b"II":
        endian = "<"
    elif bo == b"MM":
        endian = ">"
    else:
        return {}
    (ifd0_off,) = struct.unpack(endian + "I", seg[4:8])
    ifd0, _ = _parse_ifd(seg, endian, ifd0_off)

    out: Dict[str, Any] = {}
    for tag, val in ifd0.items():
        out[_TAG_NAMES.get(tag, f"Tag{tag:#06x}")] = val

    if 0x8769 in ifd0:
        sub, _ = _parse_ifd(seg, endian, int(ifd0[0x8769]))
        for tag, val in sub.items():
            out[_TAG_NAMES.get(tag, f"Tag{tag:#06x}")] = val

    if 0x8825 in ifd0:
        gps, _ = _parse_ifd(seg, endian, int(ifd0[0x8825]))
        gps_out: Dict[str, Any] = {}
        for tag, val in gps.items():
            gps_out[_GPS_TAG_NAMES.get(tag, f"GPSTag{tag:#06x}")] = val
        out["GPS"] = gps_out
    return out


def _dms_to_deg(dms, ref: str) -> float:
    def r(x):
        return x[0] / x[1] if x[1] else 0.0
    deg = r(dms[0]) + r(dms[1]) / 60.0 + r(dms[2]) / 3600.0
    if ref.upper() in ("S", "W"):
        deg = -deg
    return deg


def gps_from_exif(exif: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Extract decimal lat/lon (and altitude if present) from EXIF GPS tags."""
    gps = exif.get("GPS")
    if not gps:
        return None
    if "GPSLatitude" not in gps or "GPSLongitude" not in gps:
        return None
    lat = _dms_to_deg(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
    lon = _dms_to_deg(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
    result = {"latitude": round(lat, 6), "longitude": round(lon, 6)}
    if "GPSAltitude" in gps:
        a = gps["GPSAltitude"]
        if isinstance(a, tuple) and a[1]:
            alt = a[0] / a[1]
            if gps.get("GPSAltitudeRef") in (1, b"\x01"):
                alt = -alt
            result["altitude_m"] = round(alt, 2)
    return result


# ---------------------------------------------------------------------------
# Solar geolocation
# ---------------------------------------------------------------------------

def _julian_day(when: _dt.datetime) -> float:
    when = when.astimezone(_dt.timezone.utc)
    y, m = when.year, when.month
    d = (
        when.day
        + (when.hour + (when.minute + when.second / 60.0) / 60.0) / 24.0
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (y + 4716))
        + math.floor(30.6001 * (m + 1))
        + d + b - 1524.5
    )


def sun_position(lat: float, lon: float, when: _dt.datetime) -> Dict[str, float]:
    """NOAA solar position: returns azimuth & elevation (degrees).

    ``when`` may be naive (treated as UTC) or timezone-aware.

    :raises TypeError: if ``when`` is not a ``datetime``.
    :raises ValueError: if ``lat``/``lon`` are non-finite or out of range.
    """
    if not isinstance(when, _dt.datetime):
        raise TypeError(f"when must be a datetime, got {type(when).__name__}")
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        raise ValueError("lat and lon must be numeric")
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("lat and lon must be finite numbers")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"lat {lat} out of range [-90, 90]")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"lon {lon} out of range [-180, 180]")
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)
    jd = _julian_day(when)
    jc = (jd - 2451545.0) / 36525.0

    geom_mean_long = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    geom_mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    eccent = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)

    m = math.radians(geom_mean_anom)
    sun_eq = (
        math.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + math.sin(2 * m) * (0.019993 - 0.000101 * jc)
        + math.sin(3 * m) * 0.000289
    )
    true_long = geom_mean_long + sun_eq
    app_long = true_long - 0.00569 - 0.00478 * math.sin(
        math.radians(125.04 - 1934.136 * jc)
    )

    mean_obliq = (
        23.0
        + (26.0 + ((21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813)))) / 60.0)
        / 60.0
    )
    obliq_corr = mean_obliq + 0.00256 * math.cos(math.radians(125.04 - 1934.136 * jc))

    decl = math.degrees(
        math.asin(
            math.sin(math.radians(obliq_corr)) * math.sin(math.radians(app_long))
        )
    )

    vy = math.tan(math.radians(obliq_corr / 2.0)) ** 2
    eq_time = 4 * math.degrees(
        vy * math.sin(2 * math.radians(geom_mean_long))
        - 2 * eccent * math.sin(m)
        + 4 * eccent * vy * math.sin(m) * math.cos(2 * math.radians(geom_mean_long))
        - 0.5 * vy * vy * math.sin(4 * math.radians(geom_mean_long))
        - 1.25 * eccent * eccent * math.sin(2 * m)
    )

    utc = when.astimezone(_dt.timezone.utc)
    minutes = utc.hour * 60 + utc.minute + utc.second / 60.0
    true_solar_time = (minutes + eq_time + 4 * lon) % 1440

    hour_angle = true_solar_time / 4.0 - 180.0
    if hour_angle < -180:
        hour_angle += 360

    lat_r = math.radians(lat)
    decl_r = math.radians(decl)
    ha_r = math.radians(hour_angle)

    zenith = math.degrees(
        math.acos(
            max(-1.0, min(1.0,
                math.sin(lat_r) * math.sin(decl_r)
                + math.cos(lat_r) * math.cos(decl_r) * math.cos(ha_r)
            ))
        )
    )
    elevation = 90.0 - zenith

    if abs(zenith) < 1e-9 or abs(zenith - 180) < 1e-9:
        azimuth = 0.0
    else:
        cos_az = (
            (math.sin(lat_r) * math.cos(math.radians(zenith)) - math.sin(decl_r))
            / (math.cos(lat_r) * math.sin(math.radians(zenith)))
        )
        cos_az = max(-1.0, min(1.0, cos_az))
        az = math.degrees(math.acos(cos_az))
        azimuth = (az + 180.0) if hour_angle > 0 else (180.0 - az)
        azimuth %= 360.0

    return {
        "azimuth_deg": round(azimuth, 3),
        "elevation_deg": round(elevation, 3),
        "declination_deg": round(decl, 3),
    }


def shadow_bearing_to_azimuth(shadow_bearing_deg: float) -> float:
    """A shadow points away from the sun; sun azimuth is the opposite bearing."""
    return (shadow_bearing_deg + 180.0) % 360.0


def estimate_latitude_from_shadow(
    object_height: float,
    shadow_length: float,
    when: _dt.datetime,
    assume_local_noon: bool = True,
) -> Dict[str, float]:
    """Recover observer latitude from a vertical object and its shadow.

    At local solar noon the sun elevation ``h`` satisfies
    ``tan(h) = height / shadow``. With the solar declination for the date,
    ``latitude = declination ± (90 - h)``. Both candidate latitudes are
    returned (the shadow direction disambiguates north vs. south).
    """
    if not isinstance(when, _dt.datetime):
        raise TypeError(f"when must be a datetime, got {type(when).__name__}")
    try:
        object_height = float(object_height)
        shadow_length = float(shadow_length)
    except (TypeError, ValueError):
        raise ValueError("object_height and shadow_length must be numeric")
    if not (math.isfinite(object_height) and math.isfinite(shadow_length)):
        raise ValueError("object_height and shadow_length must be finite")
    if shadow_length <= 0 or object_height <= 0:
        raise ValueError("object_height and shadow_length must be positive")
    elevation = math.degrees(math.atan2(object_height, shadow_length))
    # declination changes slowly; evaluate at the given instant.
    decl = sun_position(0.0, 0.0, when)["declination_deg"]
    zenith = 90.0 - elevation
    north = decl + zenith
    south = decl - zenith
    # A recovered latitude outside [-90, 90] is physically impossible: at very
    # low sun the geometry pushes a candidate off the pole. Flag it and clamp
    # the reported value so downstream mapping code never sees a bad coordinate.
    out_of_range = not (-90.0 <= north <= 90.0) or not (-90.0 <= south <= 90.0)
    return {
        "sun_elevation_deg": round(elevation, 3),
        "declination_deg": round(decl, 3),
        "latitude_candidate_north": round(max(-90.0, min(90.0, north)), 3),
        "latitude_candidate_south": round(max(-90.0, min(90.0, south)), 3),
        "candidate_out_of_range": out_of_range,
        "assume_local_noon": assume_local_noon,
    }


# ---------------------------------------------------------------------------
# Reverse search
# ---------------------------------------------------------------------------

def reverse_search_urls(image_url: Optional[str] = None,
                        keywords: Optional[List[str]] = None) -> Dict[str, str]:
    """Build reverse-image / keyword search URLs across OSINT engines.

    No requests are made; this just composes query URLs the analyst opens.
    """
    from urllib.parse import quote_plus

    urls: Dict[str, str] = {}
    if image_url:
        u = quote_plus(image_url)
        urls["google_lens"] = f"https://lens.google.com/uploadbyurl?url={u}"
        urls["yandex"] = f"https://yandex.com/images/search?rpt=imageview&url={u}"
        urls["bing"] = f"https://www.bing.com/images/search?q=imgurl:{u}&view=detailv2&iss=sbi"
        urls["tineye"] = f"https://tineye.com/search?url={u}"
    if keywords:
        kw = quote_plus(" ".join(keywords))
        urls["google_text"] = f"https://www.google.com/search?q={kw}"
        urls["openstreetmap"] = f"https://www.openstreetmap.org/search?query={kw}"
    return urls


def analyze_image(image_bytes: bytes,
                  image_url: Optional[str] = None) -> Dict[str, Any]:
    """One-shot analysis: EXIF + GPS + reverse-search hints for an image."""
    exif = extract_exif(image_bytes)
    gps = gps_from_exif(exif) if exif else None
    result: Dict[str, Any] = {
        "has_exif": bool(exif),
        "exif": exif,
        "gps": gps,
    }
    # Surface a few human-relevant keys at the top.
    for key in ("Make", "Model", "DateTimeOriginal", "DateTime"):
        if key in exif:
            result[key.lower()] = exif[key]
    kw = [str(exif[k]) for k in ("Make", "Model") if k in exif]
    result["reverse_search"] = reverse_search_urls(image_url, kw or None)
    if gps:
        result["maps_url"] = (
            f"https://www.openstreetmap.org/?mlat={gps['latitude']}"
            f"&mlon={gps['longitude']}#map=16/{gps['latitude']}/{gps['longitude']}"
        )
    return result

"""Shared helpers for the GEOLENS demo scenarios.

Everything here is offline and standard-library only. Two of the demos need a
JPEG that carries camera make/model and a full GPS fix; rather than ship more
binaries we *synthesize* a real EXIF JPEG in memory (genuine TIFF/IFD bytes the
same parser reads), so the demos exercise the real ``geolens.core`` API end to
end without touching the network.
"""
from __future__ import annotations

import datetime as _dt
import os
import struct
import sys

# allow `python demos/NN_name.py` from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS_DIR = os.path.join(REPO_ROOT, "demos")

# Bundled sample images (already in the repo).
SAMPLE_GEOTAGGED = os.path.join(DEMOS_DIR, "01-basic", "sample_geotagged.jpg")
SAMPLE_NO_EXIF = os.path.join(DEMOS_DIR, "02-clean-photo", "no-exif.jpg")
BATCH_DIR = os.path.join(DEMOS_DIR, "03-batch-folder-mixed")


def rule(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def read_image(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _rat(n: int, d: int) -> bytes:
    return struct.pack(">II", n, d)


def _deg_to_dms_rationals(deg: float):
    """Decimal degrees -> three big-endian RATIONALs (deg, min, sec*100/100)."""
    deg = abs(deg)
    d = int(deg)
    m_full = (deg - d) * 60
    m = int(m_full)
    s = round((m_full - m) * 60, 2)
    return _rat(d, 1) + _rat(m, 1) + _rat(int(s * 100), 100)


def make_exif_jpeg(
    lat: float,
    lon: float,
    make: str = "GEOLENS",
    model: str = "DemoCam X1",
    when: _dt.datetime | None = None,
    altitude_m: float | None = None,
) -> bytes:
    """Build a minimal but real big-endian EXIF JPEG with Make/Model/DateTime + GPS.

    Returns raw JPEG bytes that :func:`geolens.core.extract_exif` parses. No file
    is written; this is purely in-memory fixture data for the demos.
    """
    when = when or _dt.datetime(2026, 6, 21, 12, 0, 0, tzinfo=_dt.timezone.utc)
    dt_str = when.strftime("%Y:%m:%d %H:%M:%S").encode("ascii")

    def asciiz(s: bytes) -> bytes:
        return s + b"\x00"

    def entry(tag, ft, ct, payload):
        return struct.pack(">HHI", tag, ft, ct) + payload

    # ---- value-block strings/rationals laid out after both IFDs ----
    make_b = asciiz(make.encode("ascii"))
    model_b = asciiz(model.encode("ascii"))
    dt_b = asciiz(dt_str)

    # IFD0 has: Make, Model, DateTime, GPSInfoIFDPointer  => 4 entries.
    ifd0_off = 8
    ifd0_size = 2 + 4 * 12 + 4
    # GPS IFD: LatRef, Lat, LonRef, Lon (+ AltRef, Alt when altitude given).
    gps_tags = 4 + (2 if altitude_m is not None else 0)
    gps_ifd_off = ifd0_off + ifd0_size
    gps_ifd_size = 2 + gps_tags * 12 + 4

    vals_off = gps_ifd_off + gps_ifd_size
    make_off = vals_off
    model_off = make_off + len(make_b)
    dt_off = model_off + len(model_b)
    lat_off = dt_off + len(dt_b)
    lon_off = lat_off + 24
    alt_off = lon_off + 24

    lat_ref = b"N\x00\x00\x00" if lat >= 0 else b"S\x00\x00\x00"
    lon_ref = b"E\x00\x00\x00" if lon >= 0 else b"W\x00\x00\x00"

    ifd0 = struct.pack(">H", 4)
    ifd0 += entry(0x010F, 2, len(make_b), struct.pack(">I", make_off))
    ifd0 += entry(0x0110, 2, len(model_b), struct.pack(">I", model_off))
    ifd0 += entry(0x0132, 2, len(dt_b), struct.pack(">I", dt_off))
    ifd0 += entry(0x8825, 4, 1, struct.pack(">I", gps_ifd_off))
    ifd0 += struct.pack(">I", 0)

    gps = struct.pack(">H", gps_tags)
    gps += entry(0x0001, 2, 2, lat_ref)
    gps += entry(0x0002, 5, 3, struct.pack(">I", lat_off))
    gps += entry(0x0003, 2, 2, lon_ref)
    gps += entry(0x0004, 5, 3, struct.pack(">I", lon_off))
    if altitude_m is not None:
        gps += entry(0x0005, 1, 1, struct.pack(">BBBB", 0, 0, 0, 0))
        gps += entry(0x0006, 5, 1, struct.pack(">I", alt_off))
    gps += struct.pack(">I", 0)

    values = make_b + model_b + dt_b
    values += _deg_to_dms_rationals(lat)
    values += _deg_to_dms_rationals(lon)
    if altitude_m is not None:
        values += _rat(int(round(altitude_m * 10)), 10)

    tiff = b"MM" + struct.pack(">H", 42) + struct.pack(">I", ifd0_off)
    tiff += ifd0 + gps + values

    payload = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return b"\xff\xd8" + app1 + b"\xff\xd9"

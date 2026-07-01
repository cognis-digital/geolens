"""GEOLENS command-line interface."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from typing import Any, List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    analyze_image,
    estimate_latitude_from_shadow,
    extract_exif,
    reverse_search_urls,
    sun_position,
)
from .forensics import (
    batch_triage,
    build_timeline,
    fingerprint_consistency,
    is_peak_visible,
    resection,
    reverse_heading,
    timeline_to_geojson,
    timezone_crosscheck,
)


def _parse_when(s: Optional[str]) -> _dt.datetime:
    if not s:
        return _dt.datetime.now(_dt.timezone.utc)
    try:
        dt = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise SystemExit(f"error: bad --when timestamp '{s}': {e}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _emit(data: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    # table: flat key/value
    def walk(obj: Any, prefix: str = "") -> List[str]:
        rows: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                rows.extend(walk(v, f"{prefix}{k}."))
        elif isinstance(obj, (list, tuple)):
            rows.append(f"{prefix.rstrip('.')} = {obj}")
        else:
            rows.append(f"{prefix.rstrip('.')} = {obj}")
        return rows

    rows = walk(data)
    width = max((len(r.split(" = ")[0]) for r in rows), default=0)
    for r in rows:
        if " = " in r:
            key, val = r.split(" = ", 1)
            print(f"{key.ljust(width)}  {val}")
        else:
            print(r)


def _cmd_exif(args) -> int:
    with open(args.image, "rb") as fh:
        data = fh.read()
    result = analyze_image(data, image_url=args.url)
    if args.format in ("geojson", "stix"):
        from . import intel
        print(intel.export(result, args.format))
    else:
        _emit(result, args.format)
    return 0 if result["has_exif"] else 2


def _cmd_sun(args) -> int:
    when = _parse_when(args.when)
    result = sun_position(args.lat, args.lon, when)
    result["utc"] = when.astimezone(_dt.timezone.utc).isoformat()
    _emit(result, args.format)
    return 0


def _cmd_shadow(args) -> int:
    when = _parse_when(args.when)
    result = estimate_latitude_from_shadow(args.height, args.shadow, when)
    _emit(result, args.format)
    return 0


def _cmd_reverse(args) -> int:
    result = reverse_search_urls(args.url, args.keyword)
    if not result:
        print("error: provide --url and/or --keyword", file=sys.stderr)
        return 2
    _emit(result, args.format)
    return 0


def _analyze_folder(folder: str) -> List[dict]:
    """Analyze every JPEG in a folder into records tagged with their id."""
    import os

    records: List[dict] = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith((".jpg", ".jpeg")):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        rec = analyze_image(data)
        rec["id"] = name
        records.append(rec)
    return records


def _cmd_resect(args) -> int:
    result = resection((args.lm1_lat, args.lm1_lon), args.bearing1,
                       (args.lm2_lat, args.lm2_lon), args.bearing2)
    _emit(result, args.format)
    return 0


def _cmd_heading(args) -> int:
    result = reverse_heading(args.heading, args.px, args.width, args.fov)
    _emit(result, args.format)
    return 0


def _cmd_horizon(args) -> int:
    result = is_peak_visible(args.height, args.target_height, args.distance)
    _emit(result, args.format)
    return 0 if result["visible"] else 3


def _cmd_tzcheck(args) -> int:
    with open(args.image, "rb") as fh:
        exif = extract_exif(fh.read())
    result = timezone_crosscheck(exif)
    _emit(result, args.format)
    # exit 3 when we could check and found an inconsistency
    return 3 if result.get("consistent") is False else 0


def _cmd_fingerprint(args) -> int:
    records = _analyze_folder(args.folder)
    result = fingerprint_consistency([r["exif"] for r in records])
    _emit(result, args.format)
    return 3 if result["flags"] else 0


def _cmd_triage(args) -> int:
    records = _analyze_folder(args.folder)
    result = batch_triage(records, radius_km=args.radius)
    _emit(result, args.format)
    return 0


def _cmd_timeline(args) -> int:
    records = _analyze_folder(args.folder)
    timeline = build_timeline(records)
    if args.format == "geojson":
        print(timeline_to_geojson(timeline))
    else:
        timeline.pop("_events_dt", None)
        _emit(timeline, args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="GEOLENS — image geolocation toolkit (EXIF, sun/shadow, reverse-search).",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=["table", "json", "geojson", "stix"], default="table",
                   help="output format (default: table)")
    sub = p.add_subparsers(dest="command", required=True)

    pe = sub.add_parser("exif", help="extract EXIF/GPS + reverse-search hints from an image")
    pe.add_argument("image", help="path to a JPEG image")
    pe.add_argument("--url", help="public image URL for reverse-image search links")
    pe.set_defaults(func=_cmd_exif)

    ps = sub.add_parser("sun", help="compute sun azimuth/elevation for a location & time")
    ps.add_argument("--lat", type=float, required=True)
    ps.add_argument("--lon", type=float, required=True)
    ps.add_argument("--when", help="ISO-8601 UTC timestamp (default: now)")
    ps.set_defaults(func=_cmd_sun)

    psh = sub.add_parser("shadow", help="estimate latitude from object height & shadow length")
    psh.add_argument("--height", type=float, required=True, help="object height (any unit)")
    psh.add_argument("--shadow", type=float, required=True, help="shadow length (same unit)")
    psh.add_argument("--when", help="ISO-8601 UTC timestamp of the photo (default: now)")
    psh.set_defaults(func=_cmd_shadow)

    pr = sub.add_parser("reverse", help="build reverse-image / keyword search URLs")
    pr.add_argument("--url", help="public image URL")
    pr.add_argument("--keyword", action="append", help="keyword (repeatable)")
    pr.set_defaults(func=_cmd_reverse)

    prs = sub.add_parser(
        "resect", help="estimate observer position from two landmarks + bearings")
    prs.add_argument("--lm1-lat", type=float, required=True, dest="lm1_lat")
    prs.add_argument("--lm1-lon", type=float, required=True, dest="lm1_lon")
    prs.add_argument("--bearing1", type=float, required=True,
                     help="compass bearing from observer to landmark 1 (deg)")
    prs.add_argument("--lm2-lat", type=float, required=True, dest="lm2_lat")
    prs.add_argument("--lm2-lon", type=float, required=True, dest="lm2_lon")
    prs.add_argument("--bearing2", type=float, required=True,
                     help="compass bearing from observer to landmark 2 (deg)")
    prs.set_defaults(func=_cmd_resect)

    ph = sub.add_parser(
        "heading", help="true bearing to a landmark from its pixel position")
    ph.add_argument("--heading", type=float, required=True,
                    help="camera compass heading of frame centre (deg)")
    ph.add_argument("--px", type=float, required=True,
                    help="landmark horizontal pixel position")
    ph.add_argument("--width", type=float, required=True, help="image width (px)")
    ph.add_argument("--fov", type=float, required=True,
                    help="horizontal field of view (deg)")
    ph.set_defaults(func=_cmd_heading)

    phz = sub.add_parser(
        "horizon", help="can a peak be seen over the horizon from a vantage?")
    phz.add_argument("--height", type=float, required=True,
                     help="observer eye height above sea level (m)")
    phz.add_argument("--target-height", type=float, required=True,
                     dest="target_height", help="target/peak height (m)")
    phz.add_argument("--distance", type=float, required=True,
                     help="claimed distance to the target (km)")
    phz.set_defaults(func=_cmd_horizon)

    ptz = sub.add_parser(
        "tzcheck", help="cross-check EXIF local clock vs GPS-UTC / longitude")
    ptz.add_argument("image", help="path to a JPEG image")
    ptz.set_defaults(func=_cmd_tzcheck)

    pfp = sub.add_parser(
        "fingerprint", help="camera/lens fingerprint consistency across a folder")
    pfp.add_argument("folder", help="folder of JPEG images")
    pfp.set_defaults(func=_cmd_fingerprint)

    ptr = sub.add_parser(
        "triage", help="batch triage a folder: geotagged vs scrubbed + clusters")
    ptr.add_argument("folder", help="folder of JPEG images")
    ptr.add_argument("--radius", type=float, default=1.0,
                     help="cluster join radius in km (default: 1.0)")
    ptr.set_defaults(func=_cmd_triage)

    ptl = sub.add_parser(
        "timeline", help="build a movement timeline from a folder of images")
    ptl.add_argument("folder", help="folder of JPEG images")
    ptl.set_defaults(func=_cmd_timeline)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

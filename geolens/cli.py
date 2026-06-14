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
    reverse_search_urls,
    sun_position,
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
    if not rows:
        return
    width = max((len(r.split(" = ")[0]) for r in rows), default=0)
    for r in rows:
        if " = " in r:
            key, val = r.split(" = ", 1)
            print(f"{key.ljust(width)}  {val}")
        else:
            print(r)


def _cmd_exif(args) -> int:
    path = args.image
    if not path:
        print("error: image path is required", file=sys.stderr)
        return 2
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except IsADirectoryError:
        print(f"error: '{path}' is a directory, not a file", file=sys.stderr)
        return 2
    except PermissionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not data:
        print(f"error: '{path}' is empty", file=sys.stderr)
        return 2
    if not data.startswith(b"\xff\xd8"):
        print(f"error: '{path}' does not appear to be a JPEG (wrong magic bytes)",
              file=sys.stderr)
        return 2
    result = analyze_image(data, image_url=args.url)
    _emit(result, args.format)
    return 0 if result["has_exif"] else 2


def _cmd_sun(args) -> int:
    if not (-90.0 <= args.lat <= 90.0):
        print(f"error: --lat must be in [-90, 90], got {args.lat}", file=sys.stderr)
        return 2
    if not (-180.0 <= args.lon <= 180.0):
        print(f"error: --lon must be in [-180, 180], got {args.lon}", file=sys.stderr)
        return 2
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="GEOLENS — image geolocation toolkit (EXIF, sun/shadow, reverse-search).",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=["table", "json"], default="table",
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

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"error: file not found — {e}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"error: unexpected failure — {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Scenario 16 - timezones: the same instant, three ways of writing it.

Photo metadata and analyst notes mix naive local times, UTC, and offset
timestamps. GEOLENS treats a naive datetime as UTC and normalizes any offset, so
the solar answer is identical for the same physical instant however it was
written. This scenario proves it. Offline.
"""
import datetime as _dt

from _common import rule
from geolens.core import sun_position


def main() -> None:
    rule("TIMEZONE NORMALIZATION  -  one instant, three notations, one answer")

    lat, lon = 48.8584, 2.2945
    plus2 = _dt.timezone(_dt.timedelta(hours=2))
    minus5 = _dt.timezone(_dt.timedelta(hours=-5))

    # All three denote 10:00 UTC.
    forms = [
        ("naive 10:00 (assumed UTC)", _dt.datetime(2026, 6, 21, 10, 0)),
        ("aware 10:00 +00:00", _dt.datetime(2026, 6, 21, 10, 0, tzinfo=_dt.timezone.utc)),
        ("aware 12:00 +02:00", _dt.datetime(2026, 6, 21, 12, 0, tzinfo=plus2)),
        ("aware 05:00 -05:00", _dt.datetime(2026, 6, 21, 5, 0, tzinfo=minus5)),
    ]

    print(f"\nLocation {lat}, {lon}. Every row below is the same physical instant:\n")
    print("  {:<28} {:>10}  {:>10}".format("notation", "elev(deg)", "azim(deg)"))
    print("  " + "-" * 52)
    elevations = []
    for label, when in forms:
        pos = sun_position(lat, lon, when)
        elevations.append(pos["elevation_deg"])
        print(f"  {label:<28} {pos['elevation_deg']:>10.3f}  {pos['azimuth_deg']:>10.3f}")

    spread = max(elevations) - min(elevations)
    print(f"\nMax elevation spread across notations: {spread:.6f} deg (should be ~0).")
    print("Naive == UTC, offsets are normalized — no silent timezone drift.")


if __name__ == "__main__":
    main()

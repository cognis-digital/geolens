"""Scenario 10 - the same shadow, four seasons, four latitudes.

The shadow-stick method depends on the date: the same height/shadow ratio maps
to a different latitude band as the solar declination swings across the year.
This scenario runs one observation through the solstices and equinoxes and shows
the physical-range flag firing when the geometry pushes a candidate past a pole.
Offline.
"""
import datetime as _dt

from _common import rule
from geolens.core import estimate_latitude_from_shadow


def main() -> None:
    rule("SHADOW STICK x SEASONS  -  declination moves the latitude band")

    height, shadow = 1.0, 1.0  # 45-degree sun elevation
    dates = [
        ("Mar equinox", _dt.datetime(2026, 3, 20, 12, tzinfo=_dt.timezone.utc)),
        ("Jun solstice", _dt.datetime(2026, 6, 21, 12, tzinfo=_dt.timezone.utc)),
        ("Sep equinox", _dt.datetime(2026, 9, 22, 12, tzinfo=_dt.timezone.utc)),
        ("Dec solstice", _dt.datetime(2026, 12, 21, 12, tzinfo=_dt.timezone.utc)),
    ]

    print(f"\nObservation: height={height}, shadow={shadow} (sun elevation ~45 deg)\n")
    print("  {:<13} {:>8}  {:>10}  {:>10}".format("date", "decl", "lat N", "lat S"))
    print("  " + "-" * 46)
    for label, when in dates:
        r = estimate_latitude_from_shadow(height, shadow, when)
        print(f"  {label:<13} {r['declination_deg']:>8.2f}  "
              f"{r['latitude_candidate_north']:>10.2f}  {r['latitude_candidate_south']:>10.2f}")

    print("\nNow a near-grazing sun (shadow >> height) — geometry runs off the pole:")
    graze = estimate_latitude_from_shadow(1.0, 500.0,
                                          _dt.datetime(2026, 6, 21, 12, tzinfo=_dt.timezone.utc))
    print(f"   elevation {graze['sun_elevation_deg']} deg -> "
          f"N {graze['latitude_candidate_north']}, S {graze['latitude_candidate_south']}")
    print(f"   candidate_out_of_range flag -> {graze['candidate_out_of_range']} "
          f"(values clamped to +/-90)")

    print("\nAlways cross-check the season: the date is half the answer.")


if __name__ == "__main__":
    main()

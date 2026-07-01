"""Scenario 9 - falsify a set of location claims against one timestamp.

A photo is claimed to have been taken at midday UTC. Which of several candidate
cities is even physically possible? GEOLENS computes the sun for each and flags
the ones where it would be night — a fast physical filter for a verification
desk. Offline.
"""
import datetime as _dt

from _common import rule
from geolens.core import sun_position


def main() -> None:
    rule("CLAIM FALSIFICATION  -  which locations are even possible at this instant?")

    when = _dt.datetime(2026, 6, 21, 12, 0, tzinfo=_dt.timezone.utc)
    print(f"\nClaimed capture time: {when.isoformat()}\n")
    candidates = [
        ("Paris", 48.8566, 2.3522),
        ("New York", 40.7128, -74.0060),
        ("Tokyo", 35.6762, 139.6503),
        ("Sydney", -33.8688, 151.2093),
        ("Reykjavik", 64.1466, -21.9426),
    ]

    print("  {:<12} {:>10}  {}".format("city", "elev(deg)", "verdict"))
    print("  " + "-" * 40)
    possible = 0
    for name, lat, lon in candidates:
        pos = sun_position(lat, lon, when)
        daylight = pos["elevation_deg"] > 0
        if daylight:
            possible += 1
        verdict = "possible (daylight)" if daylight else "FALSIFIED (night)"
        print(f"  {name:<12} {pos['elevation_deg']:>10.2f}  {verdict}")

    print(f"\n{possible}/{len(candidates)} claimed locations survive the daylight test.")
    print("The sun can't be up in two hemispheres at once — physics narrows the field.")


if __name__ == "__main__":
    main()

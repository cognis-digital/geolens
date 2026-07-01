"""Scenario 8 - track the sun across a day (shadow-length planning).

Given one place, GEOLENS's solar model draws the whole arc: elevation and
azimuth hour by hour. Analysts use this to predict shadow length/direction for
any frame, or to find the window when a target facade is lit. Offline math.
"""
import datetime as _dt

from _common import rule
from geolens.core import sun_position


def main() -> None:
    rule("SUN TRACK  -  elevation & azimuth across a day at one location")

    lat, lon = 40.6892, -74.0445  # Statue of Liberty
    day = _dt.date(2026, 6, 21)
    print(f"\nLocation {lat}, {lon} on {day} (UTC hours):\n")
    print("  {:>5}  {:>10}  {:>10}  {}".format("UTC", "elev(deg)", "azim(deg)", "state"))
    print("  " + "-" * 46)

    daylight_hours = 0
    for hour in range(8, 24, 2):
        when = _dt.datetime(day.year, day.month, day.day, hour, tzinfo=_dt.timezone.utc)
        pos = sun_position(lat, lon, when)
        up = pos["elevation_deg"] > 0
        if up:
            daylight_hours += 2
        state = "day" if up else "night"
        print(f"  {hour:>3}:00  {pos['elevation_deg']:>10.2f}  "
              f"{pos['azimuth_deg']:>10.2f}  {state}")

    print(f"\nSun above the horizon for ~{daylight_hours}h of the sampled window.")
    print("Elevation gives shadow LENGTH (tan h), azimuth gives its DIRECTION.")


if __name__ == "__main__":
    main()

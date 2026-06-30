"""Scenario 4 - researchers & the chronolocation method.

The classic Bellingcat "shadow stick": with no GPS in the metadata, you can
still recover a latitude band from the geometry of a vertical object and its
shadow at (or near) local solar noon. GEOLENS inverts the solar-noon geometry
to return both candidate latitudes; the shadow's direction breaks the tie.

Pure math, fully offline, reproducible - good for a methods appendix.
"""
import datetime as _dt

from _common import rule
from geolens.core import (
    estimate_latitude_from_shadow,
    shadow_bearing_to_azimuth,
    sun_position,
)


def main() -> None:
    rule("SHADOW GEOLOCATION  -  recover latitude from a stick and its shadow")

    when = _dt.datetime(2026, 6, 21, 12, 0, 0, tzinfo=_dt.timezone.utc)  # solstice noon
    height, shadow = 2.0, 1.0  # a 2 m pole casting a 1 m shadow

    print(f"\nObservation: a {height} m vertical object casts a {shadow} m shadow,")
    print(f"             measured at local solar noon on {when.date()}.\n")

    est = estimate_latitude_from_shadow(height, shadow, when)
    print(f"1) sun elevation (from tan h = height/shadow) -> {est['sun_elevation_deg']} deg")
    print(f"2) solar declination for the date            -> {est['declination_deg']} deg")
    print("3) two candidate latitudes (shadow direction disambiguates):")
    print(f"     northern candidate -> {est['latitude_candidate_north']} deg")
    print(f"     southern candidate -> {est['latitude_candidate_south']} deg")

    print("\n4) cross-check: a shadow pointing on a compass bearing tells you where the sun is.")
    for bearing in (0.0, 90.0, 315.0):
        az = shadow_bearing_to_azimuth(bearing)
        print(f"     shadow toward {bearing:5.1f} deg  =>  sun azimuth {az:5.1f} deg")

    print("\n5) sanity-check the northern candidate against the full solar model:")
    cand = est["latitude_candidate_north"]
    back = sun_position(cand, 0.0, when)
    print(f"     sun_position(lat={cand}) -> elevation {back['elevation_deg']} deg "
          f"(should match step 1 at solar noon)")

    print("\nNo coordinates were in the file - the latitude came out of the light itself.")


if __name__ == "__main__":
    main()

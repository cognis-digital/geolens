"""Scenario 21 - geometry-based geolocation: resection, heading, and horizon.

Three analytical techniques that need no metadata at all, only the *picture*:

1. Reverse-heading  - a landmark's pixel position + the camera compass heading
   + the lens field-of-view give the true bearing to that landmark.
2. Resection        - two landmarks with known coordinates and the measured
   bearing to each fix the camera position where the back-bearings cross.
3. Horizon test     - a distant peak can only appear if it clears the geometric
   horizon from the claimed vantage height; a fast falsification check.

All offline, standard-library math.
"""
from _common import rule
from geolens.forensics import (
    haversine_km,
    initial_bearing,
    is_peak_visible,
    resection,
    reverse_heading,
)


def main() -> None:
    rule("GEOMETRIC GEOLOCATION  -  resection, reverse-heading, horizon test")

    # --- 1. reverse-heading: where is that tower in the frame pointing? -----
    print("\n1) Reverse-heading from a photo frame")
    print("   camera heading 300deg, tower at x=3200 in a 3840px frame, 65deg FOV")
    rh = reverse_heading(300.0, 3200, 3840, 65.0)
    print(f"   -> landmark bearing = {rh['landmark_bearing_deg']}deg "
          f"(offset {rh['offset_from_center_deg']:+.2f}deg from centre)")

    # --- 2. resection: recover the observer from two landmarks --------------
    print("\n2) Resection from two known landmarks")
    observer = (48.8600, 2.3050)  # ground truth (analyst does NOT know this)
    eiffel = (48.8584, 2.2945)
    louvre = (48.8606, 2.3376)
    b1 = initial_bearing(*observer, *eiffel)
    b2 = initial_bearing(*observer, *louvre)
    print(f"   measured bearing to Eiffel = {b1:.1f}deg, to Louvre = {b2:.1f}deg")
    fix = resection(eiffel, b1, louvre, b2, max_km=30)
    err_m = haversine_km(*observer, fix["latitude"], fix["longitude"]) * 1000
    print(f"   -> observer at {fix['latitude']:.5f}, {fix['longitude']:.5f} "
          f"(residual {fix['residual_km']} km, converged={fix['converged']})")
    print(f"   -> recovered to within {err_m:.0f} m of the true position")

    # --- 3. horizon falsification test --------------------------------------
    print("\n3) Horizon visibility test")
    print("   claim: Mont Blanc (4808 m) shot from a 2 m eye height, 400 km away")
    r = is_peak_visible(2.0, 4808.0, 400.0)
    verdict = "PLAUSIBLE" if r["visible"] else "FALSIFIED (below horizon)"
    print(f"   -> max visible distance = {r['max_visible_distance_km']} km; "
          f"claim {verdict} (margin {r['margin_km']:+.0f} km)")

    print("\nNo EXIF required - the scene geometry alone geolocates and falsifies.")


if __name__ == "__main__":
    main()

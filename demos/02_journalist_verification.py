"""Scenario 2 - journalists & verification desks.

A source sends a photo claiming "shot in Paris, midday on the summer solstice."
Before you publish, you verify the claim against physics: the sun cannot be in
two places at once. GEOLENS computes the true solar azimuth/elevation for the
claimed place and time, so you can check it against the shadows in the frame.

This demo synthesizes a real EXIF JPEG in memory (genuine metadata bytes) to
stand in for the source's file, then runs the real solar-position math.
"""
import datetime as _dt

from _common import rule, make_exif_jpeg
from geolens.core import analyze_image, sun_position


def main() -> None:
    rule("VERIFICATION DESK  -  does the claimed time & place match the light?")

    claim_when = _dt.datetime(2026, 6, 21, 12, 0, 0, tzinfo=_dt.timezone.utc)
    claim_lat, claim_lon = 48.8584, 2.2945  # Paris, claimed

    print('\nSource claim: "Paris, 2026-06-21 12:00 UTC (summer solstice, midday)."')
    print("Step 1 - read the file the source actually sent us:\n")

    img = make_exif_jpeg(claim_lat, claim_lon, make="Apple", model="iPhone 15 Pro",
                         when=claim_when, altitude_m=35.0)
    meta = analyze_image(img)
    print(f"   camera     -> {meta.get('make')} {meta.get('model')}")
    print(f"   exif time  -> {meta.get('datetime')}")
    print(f"   embedded GPS -> {meta['gps']}")

    print("\nStep 2 - what should the sun look like, if the claim is true?\n")
    sun = sun_position(claim_lat, claim_lon, claim_when)
    print(f"   sun elevation -> {sun['elevation_deg']} deg above horizon")
    print(f"   sun azimuth   -> {sun['azimuth_deg']} deg (compass bearing of the sun)")
    shadow_bearing = (sun["azimuth_deg"] + 180.0) % 360.0
    print(f"   => shadows fall toward {shadow_bearing:.1f} deg, and should be SHORT.")

    print("\nStep 3 - now test a FALSE claim with the same image / time:")
    fake_lat, fake_lon = -33.8688, 151.2093  # Sydney
    fake = sun_position(fake_lat, fake_lon, claim_when)
    print(f"   if it were Sydney at that instant: elevation {fake['elevation_deg']} deg")
    print("   (sun below the horizon - it would be NIGHT). Claim falsifiable.")

    print("\nThe metadata says where; the solar geometry says whether to believe it.")


if __name__ == "__main__":
    main()

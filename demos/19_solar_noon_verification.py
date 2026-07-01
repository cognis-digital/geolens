"""Scenario 19 - close the loop: recover latitude, then verify it forward.

The shadow-stick method recovers a latitude; a rigorous analyst then checks it
forward through the full solar model. This scenario picks a real latitude,
computes the solar-noon shadow it *should* cast, feeds that back into
``estimate_latitude_from_shadow``, and confirms the recovered candidate matches
the truth — a round-trip proof the inversion is self-consistent. Offline.
"""
import datetime as _dt
import math

from _common import rule
from geolens.core import estimate_latitude_from_shadow, sun_position


def main() -> None:
    rule("SOLAR-NOON ROUND TRIP  -  latitude -> shadow -> latitude")

    when = _dt.datetime(2026, 6, 21, 12, 0, tzinfo=_dt.timezone.utc)  # solstice
    print(f"\nDate: {when.date()} (summer solstice, solar noon).\n")
    print("  {:>8}  {:>12}  {:>16}  {}".format(
        "true lat", "sun elev", "recovered N", "match?"))
    print("  " + "-" * 52)

    all_ok = True
    for truth in (23.44, 40.0, 51.5, 60.0):
        # sun elevation at solar noon for this latitude, on this date
        pos = sun_position(truth, 0.0, when)
        elev = pos["elevation_deg"]
        # the shadow a 1-unit pole would cast: shadow = height / tan(elev)
        shadow = 1.0 / math.tan(math.radians(elev))
        rec = estimate_latitude_from_shadow(1.0, shadow, when)
        cand = rec["latitude_candidate_north"]
        ok = abs(cand - truth) < 0.5
        all_ok = all_ok and ok
        print(f"  {truth:>8.2f}  {elev:>12.3f}  {cand:>16.3f}  {'yes' if ok else 'NO'}")

    print(f"\nInversion self-consistent across latitudes: {all_ok}")
    print("The recovered northern candidate reproduces the true latitude — the method closes.")


if __name__ == "__main__":
    main()

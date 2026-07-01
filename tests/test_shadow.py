"""Shadow (chronolocation) geolocation: geometry corners and guards.

Covers the tan(h)=height/shadow inversion, declination-based latitude
candidates, the physical-range clamp/flag added for very low sun, and the
input validation on ``estimate_latitude_from_shadow``.
"""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens.core import estimate_latitude_from_shadow  # noqa: E402

UTC = dt.timezone.utc
SOLSTICE = dt.datetime(2026, 6, 21, 12, tzinfo=UTC)
EQUINOX = dt.datetime(2026, 3, 20, 12, tzinfo=UTC)


class TestElevationGeometry(unittest.TestCase):
    def test_equal_height_and_shadow_is_45deg(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, SOLSTICE)
        self.assertAlmostEqual(r["sun_elevation_deg"], 45.0, places=1)

    def test_tall_short_shadow_high_sun(self):
        r = estimate_latitude_from_shadow(10.0, 1.0, SOLSTICE)
        self.assertGreater(r["sun_elevation_deg"], 80.0)

    def test_short_long_shadow_low_sun(self):
        r = estimate_latitude_from_shadow(1.0, 10.0, EQUINOX)
        self.assertLess(r["sun_elevation_deg"], 10.0)

    def test_units_are_ratio_only(self):
        a = estimate_latitude_from_shadow(2.0, 2.0, SOLSTICE)
        b = estimate_latitude_from_shadow(5.0, 5.0, SOLSTICE)
        self.assertAlmostEqual(a["sun_elevation_deg"], b["sun_elevation_deg"], places=6)


class TestLatitudeCandidates(unittest.TestCase):
    def test_two_candidates_returned(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, SOLSTICE)
        self.assertIn("latitude_candidate_north", r)
        self.assertIn("latitude_candidate_south", r)

    def test_candidates_bracket_declination(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, SOLSTICE)
        decl = r["declination_deg"]
        self.assertGreaterEqual(r["latitude_candidate_north"], decl)
        self.assertLessEqual(r["latitude_candidate_south"], decl)

    def test_equinox_declination_near_zero(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, EQUINOX)
        self.assertLess(abs(r["declination_deg"]), 1.0)


class TestPhysicalRangeClamp(unittest.TestCase):
    def test_very_low_sun_flags_out_of_range(self):
        # near-grazing sun + solstice declination pushes a candidate past the pole:
        # north = decl(~23.4) + zenith(~89.9) > 90
        r = estimate_latitude_from_shadow(1.0, 1000.0, SOLSTICE)
        self.assertTrue(r["candidate_out_of_range"])

    def test_clamped_candidates_stay_within_bounds(self):
        r = estimate_latitude_from_shadow(1.0, 1000.0, SOLSTICE)
        self.assertGreaterEqual(r["latitude_candidate_north"], -90.0)
        self.assertLessEqual(r["latitude_candidate_north"], 90.0)
        self.assertGreaterEqual(r["latitude_candidate_south"], -90.0)
        self.assertLessEqual(r["latitude_candidate_south"], 90.0)

    def test_normal_case_not_flagged(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, SOLSTICE)
        self.assertFalse(r["candidate_out_of_range"])


class TestInputGuards(unittest.TestCase):
    def test_zero_shadow_raises(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(1.0, 0.0, SOLSTICE)

    def test_zero_height_raises(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(0.0, 1.0, SOLSTICE)

    def test_negative_values_raise(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(-1.0, 1.0, SOLSTICE)
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(1.0, -1.0, SOLSTICE)

    def test_non_numeric_raises_valueerror(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow("tall", 1.0, SOLSTICE)

    def test_nan_raises(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(float("nan"), 1.0, SOLSTICE)

    def test_inf_raises(self):
        with self.assertRaises(ValueError):
            estimate_latitude_from_shadow(1.0, float("inf"), SOLSTICE)

    def test_non_datetime_when_raises_typeerror(self):
        with self.assertRaises(TypeError):
            estimate_latitude_from_shadow(1.0, 1.0, "noon")

    def test_assume_local_noon_flag_passthrough(self):
        r = estimate_latitude_from_shadow(1.0, 1.0, SOLSTICE, assume_local_noon=False)
        self.assertFalse(r["assume_local_noon"])


if __name__ == "__main__":
    unittest.main()

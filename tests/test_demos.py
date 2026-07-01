"""Tests for the demo scenarios and their shared fixture builder.

Confirms the in-memory EXIF synthesizer in demos/_common.py produces bytes the
real parser reads, and that every scenario runs offline and returns 0.
"""
import datetime as dt
import importlib
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMOS = os.path.join(ROOT, "demos")
sys.path.insert(0, ROOT)
sys.path.insert(0, DEMOS)

import _common  # noqa: E402
from geolens.core import analyze_image, extract_exif, gps_from_exif  # noqa: E402

SCENARIOS = [
    "01_osint_exif_triage",
    "02_journalist_verification",
    "03_le_batch_triage",
    "04_researcher_shadow_geolocation",
    "05_geojson_stix_export",
    "06_altitude_recovery",
    "07_corrupt_and_scrubbed_inputs",
    "08_sun_track_day",
    "09_claim_falsification_matrix",
    "10_shadow_stick_seasons",
    "11_hemisphere_matrix",
    "12_cli_pipeline",
    "13_batch_geojson_map",
    "14_reverse_search_dossier",
    "15_stix_case_bundle",
    "16_timezone_normalization",
    "17_altitude_sign",
    "18_seized_folder_report",
    "19_solar_noon_verification",
    "20_export_format_gallery",
    "21_resection_and_horizon",
    "22_batch_triage_timeline",
]


class TestFixtureBuilder(unittest.TestCase):
    def test_roundtrip_make_model_gps(self):
        img = _common.make_exif_jpeg(
            48.8584, 2.2945, make="Apple", model="iPhone 15 Pro",
            when=dt.datetime(2026, 6, 21, 17, 3, 12, tzinfo=dt.timezone.utc),
            altitude_m=33.0)
        exif = extract_exif(img)
        self.assertEqual(exif.get("Make"), "Apple")
        self.assertEqual(exif.get("Model"), "iPhone 15 Pro")
        self.assertEqual(exif.get("DateTime"), "2026:06:21 17:03:12")
        gps = gps_from_exif(exif)
        self.assertAlmostEqual(gps["latitude"], 48.8584, places=3)
        self.assertAlmostEqual(gps["longitude"], 2.2945, places=3)
        self.assertAlmostEqual(gps["altitude_m"], 33.0, places=1)

    def test_southern_western_hemisphere(self):
        img = _common.make_exif_jpeg(-33.8688, 151.2093)
        gps = gps_from_exif(extract_exif(img))
        self.assertLess(gps["latitude"], 0)   # S
        self.assertGreater(gps["longitude"], 0)
        img2 = _common.make_exif_jpeg(38.8895, -77.0353)
        gps2 = gps_from_exif(extract_exif(img2))
        self.assertLess(gps2["longitude"], 0)  # W

    def test_no_altitude(self):
        img = _common.make_exif_jpeg(51.5007, -0.1246, altitude_m=None)
        gps = gps_from_exif(extract_exif(img))
        self.assertNotIn("altitude_m", gps)

    def test_bundled_samples_exist(self):
        self.assertTrue(os.path.exists(_common.SAMPLE_GEOTAGGED))
        self.assertTrue(os.path.exists(_common.SAMPLE_NO_EXIF))
        analyzed = analyze_image(_common.read_image(_common.SAMPLE_GEOTAGGED))
        self.assertTrue(analyzed["has_exif"])
        self.assertIsNotNone(analyzed["gps"])


class TestScenariosRun(unittest.TestCase):
    def test_each_scenario_runs_silently(self):
        for name in SCENARIOS:
            mod = importlib.import_module(name)
            with redirect_stdout(io.StringIO()) as buf:
                rc = mod.main()
            self.assertIn(rc, (None, 0), f"{name} returned {rc}")
            self.assertTrue(buf.getvalue().strip(), f"{name} printed nothing")

    def test_run_all(self):
        run_all = importlib.import_module("run_all")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run_all.main(), 0)


if __name__ == "__main__":
    unittest.main()

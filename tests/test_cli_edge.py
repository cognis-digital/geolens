"""CLI edge cases, error paths, and exit codes.

The CLI is the primary integration surface — these lock down exit codes
(0 success, 1 error, 2 usage/no-result), output formats, and the file/time
error handling in ``geolens.cli``.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geolens.cli import main  # noqa: E402

DEMOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demos")
sys.path.insert(0, DEMOS)
import _common  # noqa: E402

GEOTAGGED = _common.SAMPLE_GEOTAGGED
NO_EXIF = _common.SAMPLE_NO_EXIF


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


class TestExifCommand(unittest.TestCase):
    def test_geotagged_exit0(self):
        rc, _, _ = _run(["--format", "json", "exif", GEOTAGGED])
        self.assertEqual(rc, 0)

    def test_no_exif_returns_2(self):
        rc, _, _ = _run(["--format", "json", "exif", NO_EXIF])
        self.assertEqual(rc, 2)

    def test_missing_file_returns_1(self):
        rc, _, err = _run(["exif", os.path.join(tempfile.gettempdir(), "nope_xyz.jpg")])
        self.assertEqual(rc, 1)
        self.assertIn("error", err.lower())

    def test_json_output_parses(self):
        rc, out, _ = _run(["--format", "json", "exif", GEOTAGGED])
        doc = json.loads(out)
        self.assertTrue(doc["has_exif"])

    def test_geojson_format(self):
        rc, out, _ = _run(["--format", "geojson", "exif", GEOTAGGED])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["type"], "FeatureCollection")

    def test_stix_format(self):
        rc, out, _ = _run(["--format", "stix", "exif", GEOTAGGED])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["type"], "bundle")

    def test_table_format_default(self):
        rc, out, _ = _run(["exif", GEOTAGGED])
        self.assertEqual(rc, 0)
        self.assertIn("latitude", out)

    def test_url_flag_produces_reverse_links(self):
        rc, out, _ = _run(["--format", "json", "exif", GEOTAGGED,
                           "--url", "https://e.com/x.jpg"])
        doc = json.loads(out)
        self.assertIn("tineye", doc["reverse_search"])


class TestSunCommand(unittest.TestCase):
    def test_basic(self):
        rc, out, _ = _run(["--format", "json", "sun", "--lat", "48.86",
                           "--lon", "2.29", "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 0)
        self.assertIn("elevation_deg", json.loads(out))

    def test_default_when_is_now(self):
        rc, _, _ = _run(["sun", "--lat", "0", "--lon", "0"])
        self.assertEqual(rc, 0)

    def test_bad_timestamp_exits(self):
        with self.assertRaises(SystemExit):
            _run(["sun", "--lat", "0", "--lon", "0", "--when", "not-a-date"])

    def test_out_of_range_lat_returns_1(self):
        rc, _, err = _run(["sun", "--lat", "999", "--lon", "0",
                           "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 1)
        self.assertIn("range", err.lower())

    def test_missing_required_lat(self):
        with self.assertRaises(SystemExit):
            _run(["sun", "--lon", "2.29"])

    def test_naive_timestamp_accepted(self):
        rc, _, _ = _run(["sun", "--lat", "0", "--lon", "0",
                         "--when", "2026-06-21T12:00:00"])
        self.assertEqual(rc, 0)


class TestShadowCommand(unittest.TestCase):
    def test_basic(self):
        rc, out, _ = _run(["--format", "json", "shadow", "--height", "1",
                           "--shadow", "1.3", "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 0)
        self.assertIn("sun_elevation_deg", json.loads(out))

    def test_zero_shadow_returns_1(self):
        rc, _, err = _run(["shadow", "--height", "1", "--shadow", "0",
                           "--when", "2026-06-21T12:00:00Z"])
        self.assertEqual(rc, 1)
        self.assertIn("positive", err.lower())

    def test_missing_required_height(self):
        with self.assertRaises(SystemExit):
            _run(["shadow", "--shadow", "1"])


class TestReverseCommand(unittest.TestCase):
    def test_needs_args_returns_2(self):
        rc, _, err = _run(["reverse"])
        self.assertEqual(rc, 2)
        self.assertIn("provide", err.lower())

    def test_url_only(self):
        rc, out, _ = _run(["--format", "json", "reverse", "--url",
                           "https://e.com/a.jpg"])
        self.assertEqual(rc, 0)
        self.assertIn("tineye", json.loads(out))

    def test_keywords_only(self):
        rc, out, _ = _run(["--format", "json", "reverse",
                           "--keyword", "paris", "--keyword", "tower"])
        self.assertEqual(rc, 0)
        self.assertIn("google_text", json.loads(out))


class TestForensicsCommands(unittest.TestCase):
    def _folder(self):
        import datetime as _dt

        d = tempfile.mkdtemp()
        imgs = {
            "a.jpg": _common.make_exif_jpeg(
                48.8584, 2.2945,
                when=_dt.datetime(2026, 6, 21, 10, tzinfo=_dt.timezone.utc)),
            "b.jpg": _common.make_exif_jpeg(
                48.8600, 2.2960,
                when=_dt.datetime(2026, 6, 21, 11, tzinfo=_dt.timezone.utc)),
            "scrub.jpg": b"\xff\xd8\xff\xd9",
        }
        for name, data in imgs.items():
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(data)
        return d

    def test_resect_recovers_position(self):
        rc, out, _ = _run(["--format", "json", "resect",
                           "--lm1-lat", "48.8584", "--lm1-lon", "2.2945",
                           "--bearing1", "356.45",
                           "--lm2-lat", "48.8606", "--lm2-lon", "2.3376",
                           "--bearing2", "22.2"])
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertIn("latitude", doc)
        self.assertIn("residual_km", doc)

    def test_heading_center(self):
        rc, out, _ = _run(["--format", "json", "heading", "--heading", "90",
                           "--px", "1920", "--width", "3840", "--fov", "70"])
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(json.loads(out)["landmark_bearing_deg"], 90.0, places=2)

    def test_horizon_visible_exit0(self):
        rc, out, _ = _run(["--format", "json", "horizon", "--height", "2",
                           "--target-height", "4808", "--distance", "200"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out)["visible"])

    def test_horizon_not_visible_exit3(self):
        rc, _, _ = _run(["horizon", "--height", "2",
                         "--target-height", "100", "--distance", "500"])
        self.assertEqual(rc, 3)

    def test_triage_folder(self):
        d = self._folder()
        rc, out, _ = _run(["--format", "json", "triage", d])
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual(doc["geotagged"], 2)
        self.assertEqual(doc["scrubbed"], 1)

    def test_timeline_geojson(self):
        d = self._folder()
        rc, out, _ = _run(["--format", "geojson", "timeline", d])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["type"], "FeatureCollection")

    def test_fingerprint_folder(self):
        d = self._folder()
        rc, out, _ = _run(["--format", "json", "fingerprint", d])
        self.assertIn(rc, (0, 3))
        self.assertIn("flags", json.loads(out))


class TestParserErrors(unittest.TestCase):
    def test_no_subcommand_exits(self):
        with self.assertRaises(SystemExit):
            _run([])

    def test_unknown_subcommand_exits(self):
        with self.assertRaises(SystemExit):
            _run(["teleport"])

    def test_version_flag_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            _run(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()

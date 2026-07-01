"""Tests for geolens.forensics — geodesy, reverse-heading, horizon, timezone
cross-check, camera fingerprinting, clustering, and the movement timeline.

Everything here is offline and standard-library only; where a real EXIF image is
needed we synthesize one with demos/_common.make_exif_jpeg.
"""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demos")
sys.path.insert(0, DEMOS)

import _common  # noqa: E402
from geolens.core import extract_exif  # noqa: E402
from geolens.forensics import (  # noqa: E402
    batch_triage,
    build_timeline,
    camera_fingerprint,
    cluster_locations,
    destination_point,
    fingerprint_consistency,
    haversine_km,
    horizon_distance_km,
    initial_bearing,
    is_peak_visible,
    max_visible_distance_km,
    resection,
    reverse_heading,
    timeline_to_geojson,
    timezone_crosscheck,
)


class TestGeodesy(unittest.TestCase):
    def test_haversine_known_distance(self):
        # Paris -> London ~ 344 km
        d = haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
        self.assertAlmostEqual(d, 343.9, delta=2.0)

    def test_haversine_zero(self):
        self.assertEqual(haversine_km(10.0, 20.0, 10.0, 20.0), 0.0)

    def test_bearing_due_north(self):
        self.assertAlmostEqual(initial_bearing(0, 0, 10, 0), 0.0, places=3)

    def test_bearing_due_east(self):
        self.assertAlmostEqual(initial_bearing(0, 0, 0, 10), 90.0, places=3)

    def test_destination_roundtrip(self):
        # go out then measure the way back
        d = destination_point(48.8, 2.3, 45.0, 100.0)
        back = haversine_km(48.8, 2.3, d["latitude"], d["longitude"])
        self.assertAlmostEqual(back, 100.0, delta=0.5)
        brg = initial_bearing(48.8, 2.3, d["latitude"], d["longitude"])
        self.assertAlmostEqual(brg, 45.0, delta=0.5)

    def test_destination_negative_distance_raises(self):
        with self.assertRaises(ValueError):
            destination_point(0, 0, 90, -5)

    def test_latlon_validation(self):
        with self.assertRaises(ValueError):
            haversine_km(200, 0, 0, 0)
        with self.assertRaises(ValueError):
            haversine_km(0, 0, 0, 999)


class TestResection(unittest.TestCase):
    def test_recovers_synthetic_observer(self):
        obs = (48.80, 2.30)
        lm1 = (48.8584, 2.2945)
        lm2 = (48.8606, 2.3376)
        b1 = initial_bearing(obs[0], obs[1], *lm1)
        b2 = initial_bearing(obs[0], obs[1], *lm2)
        r = resection(lm1, b1, lm2, b2, max_km=50)
        err = haversine_km(obs[0], obs[1], r["latitude"], r["longitude"])
        self.assertLess(err, 0.5)
        self.assertTrue(r["converged"])
        self.assertLess(r["residual_km"], 1.0)

    def test_bad_max_km(self):
        with self.assertRaises(ValueError):
            resection((0, 0), 0, (1, 1), 90, max_km=0)


class TestReverseHeading(unittest.TestCase):
    def test_center_pixel_equals_heading(self):
        r = reverse_heading(120.0, 1920, 3840, 70.0)
        self.assertAlmostEqual(r["landmark_bearing_deg"], 120.0, places=3)
        self.assertAlmostEqual(r["offset_from_center_deg"], 0.0, places=3)

    def test_right_edge_offset_is_half_fov(self):
        r = reverse_heading(0.0, 3840, 3840, 90.0)
        # right edge -> +half FOV = +45
        self.assertAlmostEqual(r["offset_from_center_deg"], 45.0, places=2)
        self.assertAlmostEqual(r["landmark_bearing_deg"], 45.0, places=2)

    def test_left_edge_negative_offset_wraps(self):
        r = reverse_heading(10.0, 0, 3840, 90.0)
        self.assertAlmostEqual(r["offset_from_center_deg"], -45.0, places=2)
        self.assertAlmostEqual(r["landmark_bearing_deg"], 325.0, places=2)

    def test_nonlinear_projection(self):
        # halfway to the right edge is NOT half the FOV (rectilinear, not linear)
        r = reverse_heading(0.0, 2880, 3840, 90.0)  # 3/4 across = norm 0.5
        self.assertNotAlmostEqual(r["offset_from_center_deg"], 22.5, places=1)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            reverse_heading(0, 5000, 3840, 70)  # px beyond width
        with self.assertRaises(ValueError):
            reverse_heading(0, 100, 3840, 200)  # fov >= 180


class TestHorizon(unittest.TestCase):
    def test_horizon_distance_scales_with_sqrt(self):
        d1 = horizon_distance_km(2.0)
        d4 = horizon_distance_km(8.0)  # 4x height -> 2x distance
        self.assertAlmostEqual(d4, 2 * d1, delta=0.01)

    def test_zero_height(self):
        self.assertEqual(horizon_distance_km(0.0), 0.0)

    def test_negative_height_raises(self):
        with self.assertRaises(ValueError):
            horizon_distance_km(-1.0)

    def test_mont_blanc_visible_from_beach(self):
        # 4808 m peak, 2 m eye height: visible well past 200 km
        r = is_peak_visible(2.0, 4808.0, 200.0)
        self.assertTrue(r["visible"])
        self.assertGreater(r["max_visible_distance_km"], 260)

    def test_peak_beyond_horizon_flagged(self):
        r = is_peak_visible(2.0, 100.0, 500.0)
        self.assertFalse(r["visible"])
        self.assertLess(r["margin_km"], 0)

    def test_max_visible_is_sum(self):
        self.assertAlmostEqual(
            max_visible_distance_km(2.0, 8.0),
            horizon_distance_km(2.0) + horizon_distance_km(8.0), places=3)


class TestTimezoneCrosscheck(unittest.TestCase):
    def _exif(self, local, utc_h, lon_dms, lon_ref):
        return {
            "DateTimeOriginal": local,
            "GPS": {
                "GPSDateStamp": "2026:06:21",
                "GPSTimeStamp": ((utc_h, 1), (0, 1), (0, 1)),
                "GPSLongitude": lon_dms,
                "GPSLongitudeRef": lon_ref,
            },
        }

    def test_consistent_tokyo(self):
        e = self._exif("2026:06:21 21:00:00", 12, ((139, 1), (42, 1), (0, 1)), "E")
        r = timezone_crosscheck(e)
        self.assertEqual(r["utc_offset_hours"], 9.0)
        self.assertEqual(r["implied_longitude_center"], 135.0)
        self.assertTrue(r["consistent"])

    def test_inconsistent_spoofed(self):
        e = self._exif("2026:06:21 21:00:00", 12, ((30, 1), (0, 1), (0, 1)), "W")
        r = timezone_crosscheck(e)
        self.assertFalse(r["consistent"])
        self.assertTrue(r["notes"])

    def test_no_gps_time(self):
        r = timezone_crosscheck({"DateTimeOriginal": "2026:06:21 12:00:00"})
        self.assertFalse(r["has_gps_time"])
        self.assertIsNone(r["consistent"])

    def test_quarter_hour_offset(self):
        # India Standard Time = UTC+5:30
        e = self._exif("2026:06:21 17:30:00", 12, ((77, 1), (0, 1), (0, 1)), "E")
        r = timezone_crosscheck(e)
        self.assertEqual(r["utc_offset_hours"], 5.5)


class TestFingerprint(unittest.TestCase):
    def _exif(self, **kw):
        return extract_exif(_common.make_exif_jpeg(1, 2, **kw))

    def test_single_source(self):
        exifs = [self._exif(make="Apple", model="iPhone 15") for _ in range(3)]
        r = fingerprint_consistency(exifs)
        self.assertTrue(r["single_source_likely"])
        self.assertEqual(r["flags"], [])

    def test_mixed_makes_flagged(self):
        exifs = [self._exif(make="Apple", model="iPhone 15"),
                 self._exif(make="Nikon", model="Z9")]
        r = fingerprint_consistency(exifs)
        self.assertFalse(r["single_source_likely"])
        self.assertTrue(any("makes" in f for f in r["flags"]))

    def test_fingerprint_fields(self):
        # NB: the demo fixture builder always stores strings via an offset
        # pointer, so tags must be >4 bytes to round-trip (a fixture quirk,
        # not a parser bug); use realistic camera strings.
        fp = camera_fingerprint(self._exif(make="Sony", model="ILCE-7M4"))
        self.assertEqual(fp["make"], "Sony")
        self.assertEqual(fp["model"], "ILCE-7M4")
        self.assertTrue(fp["has_gps"])

    def test_empty_set(self):
        r = fingerprint_consistency([])
        self.assertEqual(r["count"], 0)
        self.assertTrue(r["single_source_likely"])


class TestClustering(unittest.TestCase):
    def test_two_clusters(self):
        pts = [
            {"id": "a", "latitude": 48.8584, "longitude": 2.2945},
            {"id": "b", "latitude": 48.8600, "longitude": 2.2960},
            {"id": "c", "latitude": -33.8688, "longitude": 151.2093},
        ]
        clusters = cluster_locations(pts, radius_km=1.0)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0]["size"], 2)  # sorted by size desc

    def test_all_one_cluster_large_radius(self):
        pts = [{"latitude": 0, "longitude": 0},
               {"latitude": 0.001, "longitude": 0.001}]
        self.assertEqual(len(cluster_locations(pts, radius_km=10)), 1)

    def test_skips_missing_coords(self):
        pts = [{"id": "x"}, {"latitude": 1, "longitude": 1}]
        clusters = cluster_locations(pts)
        self.assertEqual(sum(c["size"] for c in clusters), 1)

    def test_bad_radius(self):
        with self.assertRaises(ValueError):
            cluster_locations([], radius_km=0)


class TestBatchTriage(unittest.TestCase):
    def test_split_and_cluster(self):
        records = [
            {"id": "a.jpg", "gps": {"latitude": 48.8584, "longitude": 2.2945}},
            {"id": "b.jpg", "gps": {"latitude": 48.8600, "longitude": 2.2960}},
            {"id": "c.jpg", "gps": {"latitude": -33.8688, "longitude": 151.2093}},
            {"id": "scrub.jpg", "gps": None},
        ]
        r = batch_triage(records, radius_km=1.0)
        self.assertEqual(r["total"], 4)
        self.assertEqual(r["geotagged"], 3)
        self.assertEqual(r["scrubbed"], 1)
        self.assertEqual(r["cluster_count"], 2)
        self.assertEqual(r["scrubbed_ids"], ["scrub.jpg"])


class TestTimeline(unittest.TestCase):
    def _rec(self, rid, lat, lon, when):
        return {"id": rid, "gps": {"latitude": lat, "longitude": lon},
                "datetimeoriginal": when.strftime("%Y:%m:%d %H:%M:%S")}

    def test_ordered_events_and_legs(self):
        recs = [
            self._rec("b", 48.86, 2.30, dt.datetime(2026, 6, 21, 11)),
            self._rec("a", 48.85, 2.29, dt.datetime(2026, 6, 21, 10)),
        ]
        tl = build_timeline(recs)
        self.assertEqual(tl["event_count"], 2)
        self.assertEqual([e["id"] for e in tl["events"]], ["a", "b"])  # sorted by time
        self.assertEqual(len(tl["legs"]), 1)
        self.assertIsNotNone(tl["legs"][0]["implied_speed_kmh"])

    def test_geojson_has_points_and_line(self):
        recs = [
            self._rec("a", 48.85, 2.29, dt.datetime(2026, 6, 21, 10)),
            self._rec("b", 48.86, 2.30, dt.datetime(2026, 6, 21, 11)),
        ]
        gj = json.loads(timeline_to_geojson(build_timeline(recs)))
        kinds = [f["geometry"]["type"] for f in gj["features"]]
        self.assertEqual(kinds.count("Point"), 2)
        self.assertIn("LineString", kinds)

    def test_single_event_no_line(self):
        recs = [self._rec("a", 48.85, 2.29, dt.datetime(2026, 6, 21, 10))]
        gj = json.loads(timeline_to_geojson(build_timeline(recs)))
        self.assertEqual(len(gj["features"]), 1)
        self.assertEqual(gj["features"][0]["geometry"]["type"], "Point")

    def test_records_without_time_or_gps_dropped(self):
        recs = [
            self._rec("a", 48.85, 2.29, dt.datetime(2026, 6, 21, 10)),
            {"id": "notime", "gps": {"latitude": 1, "longitude": 1}},
            {"id": "nogps", "datetimeoriginal": "2026:06:21 12:00:00"},
        ]
        tl = build_timeline(recs)
        self.assertEqual(tl["event_count"], 1)


if __name__ == "__main__":
    unittest.main()

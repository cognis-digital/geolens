"""Run every GEOLENS demo scenario end to end.

    python demos/run_all.py

Each scenario is independent and offline: it either reads a bundled sample image
or synthesizes real EXIF bytes in memory, then exercises the real geolens API.
On Windows consoles set PYTHONUTF8=1 first.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    "21_kml_google_earth",
]


def main() -> int:
    for name in SCENARIOS:
        mod = importlib.import_module(name)
        mod.main()
    print("\n" + "=" * 70)
    print("  All demo scenarios completed.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

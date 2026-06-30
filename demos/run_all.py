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

"""Scenario 12 - drive the CLI in-process (exit codes as a contract).

Automation wraps the CLI, so its exit codes matter: 0 on a hit, 2 when there is
no result to act on (scrubbed image / missing args), 1 on an error. This
scenario writes a synthesized EXIF JPEG to a temp file, then calls the real CLI
``main()`` for each command and asserts the contract. Offline.
"""
import io
import os
import tempfile
from contextlib import redirect_stdout

from _common import rule, make_exif_jpeg, SAMPLE_NO_EXIF
from geolens.cli import main as cli_main


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(argv)
    return rc, buf.getvalue()


def main_demo() -> None:
    rule("CLI PIPELINE  -  exit codes are the automation contract")

    tmp = os.path.join(tempfile.gettempdir(), "geolens_demo_geo.jpg")
    with open(tmp, "wb") as fh:
        fh.write(make_exif_jpeg(48.8584, 2.2945, make="Apple", model="iPhone 15"))

    checks = [
        ("exif on geotagged (expect 0)", ["--format", "json", "exif", tmp], 0),
        ("exif on scrubbed  (expect 2)", ["--format", "json", "exif", SAMPLE_NO_EXIF], 2),
        ("sun               (expect 0)", ["sun", "--lat", "48.86", "--lon", "2.29",
                                          "--when", "2026-06-21T12:00:00Z"], 0),
        ("shadow            (expect 0)", ["--format", "json", "shadow", "--height", "2",
                                          "--shadow", "1", "--when", "2026-06-21T12:00:00Z"], 0),
        ("reverse no args   (expect 2)", ["reverse"], 2),
        ("geojson export    (expect 0)", ["--format", "geojson", "exif", tmp], 0),
    ]

    print("\n  {:<32} {:>4}  {}".format("command", "rc", "verdict"))
    print("  " + "-" * 52)
    all_ok = True
    for label, argv, expected in checks:
        rc, _ = _run(argv)
        ok = rc == expected
        all_ok = all_ok and ok
        print(f"  {label:<32} {rc:>4}  {'OK' if ok else 'MISMATCH'}")

    try:
        os.remove(tmp)
    except OSError:
        pass

    print(f"\nExit-code contract upheld across all commands: {all_ok}")


def main() -> None:
    main_demo()


if __name__ == "__main__":
    main()

# Demos

Twenty-two runnable scenarios in [`../demos/`](../demos/), each targeting a
different audience or failure mode. Every scenario is **offline**: it reads a
bundled sample image or synthesizes real EXIF bytes in memory, then exercises
the real `geolens` API — no network, no fabricated output. Each returns 0.

```bash
# Windows consoles: set PYTHONUTF8=1 first (cp1252 console)
python demos/run_all.py                          # all twenty-two, end to end
python demos/02_journalist_verification.py       # or just one
```

| # | Scenario | Audience | What it shows |
|---|----------|----------|---------------|
| 1 | `01_osint_exif_triage.py` | OSINT analysts | EXIF/GPS recovered off the bytes + a map link + reverse-image search leads, on the bundled geotagged sample |
| 2 | `02_journalist_verification.py` | Journalists / verification desks | Test a source's "Paris, solstice noon" claim against the real solar azimuth/elevation; falsify a bad claim (sun below the horizon) |
| 3 | `03_le_batch_triage.py` | Law enforcement / IR | First pass over a mixed seized folder: who is geotagged, who is scrubbed, plus a STIX 2.1 bundle for the case platform |
| 4 | `04_researcher_shadow_geolocation.py` | Researchers | Recover a latitude band from a stick and its shadow (Bellingcat "shadow stick"), then cross-check it against the full solar model |
| 5 | `05_geojson_stix_export.py` | Platform / SOC engineers | One analyzed fix exported as GeoJSON (Leaflet/QGIS/kepler) and STIX 2.1 (OpenCTI/TIP), degrading gracefully with no GPS |
| 6 | `06_altitude_recovery.py` | Mapping / 3D | GPS altitude recovered as `altitude_m` and carried into the GeoJSON position as a third `[lon, lat, alt]` coordinate |
| 7 | `07_corrupt_and_scrubbed_inputs.py` | Everyone | A gallery of hostile inputs (empty, PNG, truncated APP1, garbage) — every one degrades to a clean result, never a crash |
| 8 | `08_sun_track_day.py` | Analysts | The sun's elevation/azimuth arc hour by hour at one location — predict shadow length and direction for any frame |
| 9 | `09_claim_falsification_matrix.py` | Verification desks | Test one timestamp against many candidate cities; flag the ones where it would be night |
| 10 | `10_shadow_stick_seasons.py` | Researchers | The same shadow ratio maps to different latitudes across the seasons; shows the out-of-range clamp/flag firing |
| 11 | `11_hemisphere_matrix.py` | QA / regression | N/S/E/W landmark round-trips through EXIF prove the hemisphere signs survive |
| 12 | `12_cli_pipeline.py` | Automation | Drives the CLI in-process and asserts the exit-code contract (0 hit / 2 no-result / 1 error) |
| 13 | `13_batch_geojson_map.py` | Analysts | Merge a whole folder of fixes into one GeoJSON FeatureCollection ready for a map layer |
| 14 | `14_reverse_search_dossier.py` | OSINT analysts | Build a full reverse-image + keyword search dossier; every URL https and percent-encoded |
| 15 | `15_stix_case_bundle.py` | TIP engineers | Build a STIX 2.1 bundle and self-validate its invariants (refs resolve, spec_version present) |
| 16 | `16_timezone_normalization.py` | Analysts | One physical instant written four ways (naive/UTC/offsets) yields one solar answer — no timezone drift |
| 17 | `17_altitude_sign.py` | Mapping | Above vs below sea level: the GPS altitude-reference byte signs the metres correctly |
| 18 | `18_seized_folder_report.py` | Law enforcement / IR | A printable triage summary: counts (geotagged/scrubbed/EXIF-no-GPS) and distinct cameras |
| 19 | `19_solar_noon_verification.py` | Researchers | Round-trip proof: latitude → its solar-noon shadow → recovered latitude matches |
| 20 | `20_export_format_gallery.py` | Everyone | One fix rendered through every output surface (table, GeoJSON, STIX) side by side |

## 1. OSINT EXIF triage — *where, with what, where next*
**Audience:** OSINT analysts.
Reads the bundled geotagged JPEG, recovers the decimal GPS fix and a map link,
and prints ready-to-open reverse-image search URLs (Google Lens, Yandex, Bing,
TinEye). The coordinate is the starting pin; the URLs widen the net — all from
metadata, no pixels analyzed, no upload.

## 2. Verification desk — *does the light match the claim?*
**Audience:** journalists and verification desks.
A source claims a place and time. `sun_position` computes where the sun must be
for that claim, so you can check it against the shadows in the frame — and the
demo falsifies a false claim by showing the sun would be below the horizon.

## 3. Seized-folder triage — *who is geotagged, who is scrubbed*
**Audience:** law enforcement and incident response.
A fast, defensible first pass over a folder of images: per-file geotag status
and a STIX 2.1 bundle ready to drop into OpenCTI or a TIP. Every determination
is reproducible from the bytes.

## 4. Shadow geolocation — *latitude from light*
**Audience:** researchers writing a methods appendix.
With no GPS in the file, invert the solar-noon shadow geometry to two candidate
latitudes, map shadow bearings to sun azimuths, and verify the result against
the full solar model.

## 5. Export & interop — *one fix, every platform*
**Audience:** platform and SOC engineers.
Run the native GeoJSON and STIX 2.1 exporters off one analyzed image, and show
they still emit valid documents when the image has been scrubbed of metadata.

## 6–20. Depth scenarios

Scenarios 6–20 stress the same real API across altitude handling, hostile
inputs, whole-day sun tracks, claim-falsification matrices, seasonal
shadow-stick geometry, hemisphere round-trips, the CLI exit-code contract,
batch-to-map merging, reverse-search dossiers, self-validating STIX bundles,
timezone normalization, altitude sign, a printable seized-folder report, a
latitude→shadow→latitude round-trip proof, and a side-by-side export gallery.
Several double as regression guards for real fixes (altitude reaching GeoJSON,
the physical-range clamp on shadow latitudes, input-type guards).

## 21. Geometric geolocation — *no metadata required*
**Audience:** verification desks and GEOINT analysts.
Reverse-heading (landmark bearing from its pixel position + lens FOV),
two-landmark resection (recover the observer position), and the horizon
falsification test — geolocating and falsifying from the picture alone. See
[`FORENSICS.md`](FORENSICS.md).

## 22. Batch triage & movement timeline — *one folder, three products*
**Audience:** law-enforcement / incident-response analysts.
Split a collected folder into geotagged vs scrubbed, spatially cluster it, build
a time-ordered movement timeline (with implied speeds) exported as a GeoJSON
track, and run a camera-fingerprint consistency check that flags a spliced-in,
different-camera image.

---

Each demo prints clear, narrated output and returns 0, so they double as smoke
tests — `tests/test_demos.py` imports and runs every one under `pytest`.

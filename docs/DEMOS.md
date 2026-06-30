# Demos

Five runnable scenarios in [`../demos/`](../demos/), each targeting a different
audience. Every scenario is **offline**: it reads a bundled sample image or
synthesizes real EXIF bytes in memory, then exercises the real `geolens` API —
no network, no fabricated output.

```bash
# Windows consoles: set PYTHONUTF8=1 first (cp1252 console)
python demos/run_all.py                          # all five, end to end
python demos/02_journalist_verification.py       # or just one
```

| # | Scenario | Audience | What it shows |
|---|----------|----------|---------------|
| 1 | `01_osint_exif_triage.py` | OSINT analysts | EXIF/GPS recovered off the bytes + a map link + reverse-image search leads, on the bundled geotagged sample |
| 2 | `02_journalist_verification.py` | Journalists / verification desks | Test a source's "Paris, solstice noon" claim against the real solar azimuth/elevation; falsify a bad claim (sun below the horizon) |
| 3 | `03_le_batch_triage.py` | Law enforcement / IR | First pass over a mixed seized folder: who is geotagged, who is scrubbed, plus a STIX 2.1 bundle for the case platform |
| 4 | `04_researcher_shadow_geolocation.py` | Researchers | Recover a latitude band from a stick and its shadow (Bellingcat "shadow stick"), then cross-check it against the full solar model |
| 5 | `05_geojson_stix_export.py` | Platform / SOC engineers | One analyzed fix exported as GeoJSON (Leaflet/QGIS/kepler) and STIX 2.1 (OpenCTI/TIP), degrading gracefully with no GPS |

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

---

Each demo prints clear, narrated output and returns 0, so they double as smoke
tests — `tests/test_demos.py` covers the same code paths under `pytest`.

# Forensics & analytical geolocation

`geolens.forensics` adds a layer of **defensive, offline** reasoning on top of
the EXIF/solar core. Everything here is pure standard-library math — no network,
no side effects, plain dicts in and out — and is designed for verification,
OSINT, and incident-response analysts. It is **additive**: the existing public
API is unchanged, and every new symbol is re-exported from the `geolens`
package.

> Scope: verification / analysis / defense only. Nothing here targets anything.

## Techniques

### Geodesy — `haversine_km`, `initial_bearing`, `destination_point`, `resection`

Great-circle distance, bearing, and the direct geodesic (walk a bearing +
distance to a new point). `resection` estimates an **observer position** from
two landmarks of known coordinates plus the compass bearing to each — the
classic map-and-compass technique. It recovers a synthetic observer to within a
few metres and reports a `residual_km` quality figure.

```bash
geolens --format json resect \
  --lm1-lat 48.8584 --lm1-lon 2.2945 --bearing1 356.4 \
  --lm2-lat 48.8606 --lm2-lon 2.3376 --bearing2 22.2
```

### Reverse heading — `reverse_heading`

A landmark's horizontal pixel position, the camera's compass heading of the
frame centre, and the lens horizontal field-of-view give the **true bearing to
that landmark**. Uses the rectilinear (pinhole) projection, so edge landmarks
are handled correctly rather than with a naive linear map.

```bash
geolens heading --heading 300 --px 3200 --width 3840 --fov 65
```

### Horizon / terrain cues — `horizon_distance_km`, `max_visible_distance_km`, `is_peak_visible`

Refraction-corrected geometric-horizon math. `is_peak_visible` is a fast
**falsification test**: a distant peak can only appear in a photo if it clears
the horizon from the claimed vantage height. `visible=False` is a strong signal
against a "shot from here" claim. The CLI exits `3` when the peak is below the
horizon.

```bash
geolens horizon --height 2 --target-height 4808 --distance 400   # exit 3: falsified
```

### Timezone cross-check — `timezone_crosscheck`

Camera clocks record **local** civil time; the GPS block records **UTC**. The
difference implies the camera's UTC offset, which maps to a longitude band
(15° per hour). If the image's GPS longitude falls far outside that band, the
timestamp or GPS is flagged as possibly edited/transplanted. The CLI exits `3`
on a detected inconsistency.

```bash
geolens tzcheck photo.jpg
```

### Camera fingerprint consistency — `camera_fingerprint`, `fingerprint_consistency`

Extracts a device/lens fingerprint (make, model, software, dimensions,
orientation, GPS presence) and compares fingerprints across a set to surface
tampering/splicing signals: mixed makes/models, an editing-software tag on an
otherwise camera-native set, or one model appearing at multiple sensor
dimensions.

```bash
geolens fingerprint ./seized_folder     # exit 3 if any flags raised
```

### Batch triage + clustering — `cluster_locations`, `batch_triage`

Splits a folder into geotagged vs scrubbed, then **single-linkage clusters** the
geotagged subset by great-circle distance — the "who was where" view of a
collected set, with no fixed *k*.

```bash
geolens --format json triage ./folder --radius 2.0
```

### Movement timeline — `build_timeline`, `timeline_to_geojson`

Orders geotagged, time-stamped images into a movement timeline with per-leg
distance, elapsed time, and **implied speed** (an implausible speed is itself a
signal), then exports it as a GeoJSON `Point` series + a `LineString` track for
Leaflet / QGIS / kepler.gl.

```bash
geolens --format geojson timeline ./folder > track.geojson
```

## Demos

- [`21_resection_and_horizon.py`](../demos/21_resection_and_horizon.py) —
  reverse-heading, resection, and the horizon falsification test, no metadata
  required.
- [`22_batch_triage_timeline.py`](../demos/22_batch_triage_timeline.py) —
  triage → cluster → timeline → GeoJSON track + a camera-fingerprint tampering
  flag over a synthesised folder.

Both run offline and exit 0 (`PYTHONUTF8=1` on Windows consoles).

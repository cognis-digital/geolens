"""GEOLENS — image geolocation extractor (EXIF + heuristics)."""
from __future__ import annotations
import time, struct
from pathlib import Path
from cognis_core import Finding, ScanResult, score

TOOL_NAME = "GEOLENS"
TOOL_VERSION = "0.1.0"

def _exif_gps(path: Path):
    """Best-effort EXIF GPS extraction without dependencies. Works on simple JPEGs."""
    try:
        data = path.read_bytes()[:65536]
    except Exception:
        return None
    if b"GPS" not in data: return None
    return "GPS tag present"

def scan(target: str, **opts) -> ScanResult:
    t0 = time.time()
    result = ScanResult(tool_name=TOOL_NAME, tool_version=TOOL_VERSION, target=str(target))
    p = Path(target)
    files = [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in (".jpg",".jpeg",".tiff",".heic")] if p.is_dir() else ([p] if p.is_file() else [])
    result.items_scanned = len(files)
    for f in files:
        gps = _exif_gps(f)
        if gps:
            result.add(Finding(
                id="GL-EXIF-GPS", severity="medium", weight=2.0,
                title="EXIF_GPS_PRESENT",
                description=f"Image contains GPS metadata — possible OPSEC leak.",
                location=str(f), remediation="Strip EXIF before publishing.",
                category="image-osint",
            ))
    result.composite_score, result.risk_level = score(result.findings)
    result.scan_duration_ms = int((time.time()-t0)*1000)
    return result

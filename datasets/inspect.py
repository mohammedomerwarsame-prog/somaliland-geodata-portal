"""
Lightweight checks on uploaded files using only the Python standard library.

For production you would add GDAL/OGR (or a Celery worker) to reproject,
convert rasters to Cloud-Optimized GeoTIFF and generate thumbnails. This
module keeps the portal installable without GDAL.
"""
import json
import os
import zipfile

from django.core.exceptions import ValidationError

# extension -> (format label, data type)
SUPPORTED = {
    ".zip": ("Shapefile (zip)", "vector"),
    ".geojson": ("GeoJSON", "vector"),
    ".json": ("GeoJSON", "vector"),
    ".gpkg": ("GeoPackage", "vector"),
    ".kml": ("KML", "vector"),
    ".kmz": ("KMZ", "vector"),
    ".tif": ("GeoTIFF", "raster"),
    ".tiff": ("GeoTIFF", "raster"),
    ".csv": ("CSV", "table"),
}

SHAPEFILE_REQUIRED = {".shp", ".shx", ".dbf"}


def allowed_extensions_text():
    return ", ".join(sorted({e for e in SUPPORTED}))


def inspect_upload(uploaded):
    """Validate the file and return a dict of detected metadata."""
    name = uploaded.name
    ext = os.path.splitext(name)[1].lower()
    if ext not in SUPPORTED:
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed: {allowed_extensions_text()}")

    label, data_type = SUPPORTED[ext]
    info = {"file_format": label, "data_type": data_type, "file_size": uploaded.size}

    if ext == ".zip":
        info.update(_inspect_shapefile_zip(uploaded))
    elif ext in (".geojson", ".json"):
        info.update(_inspect_geojson(uploaded))
    elif ext in (".tif", ".tiff"):
        _check_magic(uploaded, (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"), "GeoTIFF")
    elif ext == ".gpkg":
        _check_magic(uploaded, (b"SQLite format 3\x00",), "GeoPackage")

    uploaded.seek(0)
    return info


def _check_magic(uploaded, signatures, label):
    uploaded.seek(0)
    head = uploaded.read(16)
    uploaded.seek(0)
    if not any(head.startswith(sig) for sig in signatures):
        raise ValidationError(f"This file does not look like a valid {label}.")


def _inspect_shapefile_zip(uploaded):
    uploaded.seek(0)
    try:
        with zipfile.ZipFile(uploaded) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/") and "__MACOSX" not in n]
            for n in names:
                if n.startswith("/") or ".." in n.split("/"):
                    raise ValidationError("The zip contains unsafe file paths.")
            exts = {os.path.splitext(n)[1].lower() for n in names}
            missing = SHAPEFILE_REQUIRED - exts
            if missing:
                raise ValidationError(
                    "The zip must contain a complete shapefile. Missing: " + ", ".join(sorted(missing))
                )
            crs = "Unknown – no .prj file"
            prj = next((n for n in names if n.lower().endswith(".prj")), None)
            if prj:
                wkt = zf.read(prj)[:4000].decode("utf-8", "ignore")
                crs = _guess_crs_from_wkt(wkt)
            return {"crs": crs}
    except zipfile.BadZipFile:
        raise ValidationError("The zip file is damaged or not a zip archive.")
    finally:
        uploaded.seek(0)


def _guess_crs_from_wkt(wkt):
    w = wkt.upper()
    if w.startswith("PROJCS"):
        if "UTM" in w and "38N" in w:
            return "EPSG:32638 (WGS 84 / UTM 38N)"
        if "UTM" in w and "39N" in w:
            return "EPSG:32639 (WGS 84 / UTM 39N)"
        return "Projected – see .prj"
    if "WGS_1984" in w or "WGS 84" in w:
        return "EPSG:4326"
    return "See .prj"


def _inspect_geojson(uploaded, max_parse_mb=50):
    uploaded.seek(0)
    if uploaded.size > max_parse_mb * 1024 * 1024:
        return {"crs": "EPSG:4326"}  # too large to parse in-request; accept as-is
    try:
        data = json.load(uploaded)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("This GeoJSON file is not valid JSON.")
    finally:
        uploaded.seek(0)

    if not isinstance(data, dict) or data.get("type") not in ("FeatureCollection", "Feature"):
        raise ValidationError("GeoJSON must be a FeatureCollection or Feature.")

    features = data["features"] if data["type"] == "FeatureCollection" else [data]
    xs, ys = [], []

    def walk(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            xs.append(coords[0])
            ys.append(coords[1])
        else:
            for c in coords:
                walk(c)

    for f in features:
        geom = (f or {}).get("geometry") or {}
        if geom.get("type") == "GeometryCollection":
            for g in geom.get("geometries", []):
                walk(g.get("coordinates"))
        else:
            walk(geom.get("coordinates"))

    info = {"feature_count": len(features), "crs": "EPSG:4326"}
    if xs:
        info.update(min_lon=min(xs), min_lat=min(ys), max_lon=max(xs), max_lat=max(ys))
        if not (-180 <= info["min_lon"] <= info["max_lon"] <= 180 and -90 <= info["min_lat"] <= info["max_lat"] <= 90):
            raise ValidationError("GeoJSON coordinates must be longitude/latitude (EPSG:4326).")
    return info

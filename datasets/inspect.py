"""
Checks on uploaded files using only the Python standard library.

The portal accepts the formats used by ArcGIS (ArcMap, ArcCatalog, ArcGIS Pro)
and QGIS. Files are stored exactly as uploaded, so users download the original
and open it in their own GIS software.
"""
import json
import os
import zipfile

from django.core.exceptions import ValidationError

# extension -> (format label, data type)
SUPPORTED = {
    # --- vector ---
    ".geojson": ("GeoJSON", "vector"),
    ".json": ("GeoJSON", "vector"),
    ".gpkg": ("GeoPackage", "vector"),
    ".kml": ("KML", "vector"),
    ".kmz": ("KMZ", "vector"),
    ".gml": ("GML", "vector"),
    ".gpx": ("GPS Exchange (GPX)", "vector"),
    ".sqlite": ("SpatiaLite", "vector"),
    ".fgb": ("FlatGeobuf", "vector"),
    ".dxf": ("CAD (DXF)", "vector"),
    ".dwg": ("CAD (DWG)", "vector"),
    # --- raster ---
    ".tif": ("GeoTIFF", "raster"),
    ".tiff": ("GeoTIFF", "raster"),
    ".img": ("ERDAS Imagine", "raster"),
    ".jp2": ("JPEG 2000", "raster"),
    ".ecw": ("ECW", "raster"),
    ".sid": ("MrSID", "raster"),
    ".asc": ("ASCII Grid", "raster"),
    ".dem": ("DEM", "raster"),
    ".hgt": ("SRTM HGT", "raster"),
    ".nc": ("NetCDF", "raster"),
    ".vrt": ("GDAL Virtual Raster", "raster"),
    ".las": ("LiDAR (LAS)", "raster"),
    ".laz": ("LiDAR (LAZ)", "raster"),
    # --- tables ---
    ".csv": ("CSV", "table"),
    ".xlsx": ("Excel", "table"),
    ".xls": ("Excel", "table"),
    # --- ArcGIS / QGIS packages and projects ---
    ".ppkx": ("ArcGIS Pro Project Package", "other"),
    ".mpkx": ("ArcGIS Pro Map Package", "other"),
    ".lpkx": ("ArcGIS Pro Layer Package", "other"),
    ".mpk": ("ArcMap Map Package", "other"),
    ".lpk": ("ArcMap Layer Package", "other"),
    ".qgz": ("QGIS Project", "other"),
    ".qgs": ("QGIS Project", "other"),
    # --- archives (contents are inspected) ---
    ".zip": ("ZIP archive", "other"),
    ".7z": ("7-Zip archive", "other"),
    ".rar": ("RAR archive", "other"),
}

SHAPEFILE_REQUIRED = {".shp", ".shx", ".dbf"}
RASTER_EXTS = {".tif", ".tiff", ".img", ".jp2", ".ecw", ".sid", ".asc", ".dem", ".hgt", ".nc", ".vrt", ".adf"}
VECTOR_EXTS = {".geojson", ".json", ".gpkg", ".kml", ".kmz", ".gml", ".gpx", ".sqlite", ".fgb", ".dxf", ".dwg"}
GIS_EXTS = set(SUPPORTED) | RASTER_EXTS | {".shp", ".tab", ".mif", ".gdbtable", ".prj", ".aux", ".tfw", ".ovr", ".lyrx", ".lyr", ".mxd", ".aprx"}


def allowed_extensions_text():
    return ", ".join(sorted(SUPPORTED))


def accept_attribute():
    return ",".join(sorted(SUPPORTED))


def inspect_upload(uploaded):
    """Validate the file and return a dict of detected metadata."""
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in SUPPORTED:
        raise ValidationError(
            f"Unsupported file type '{ext}'. If this is GIS data in a folder (for example a File "
            f"Geodatabase .gdb or a shapefile), zip the folder and upload the .zip."
        )

    label, data_type = SUPPORTED[ext]
    info = {"file_format": label, "data_type": data_type, "file_size": uploaded.size}

    if ext == ".zip":
        info.update(_inspect_zip(uploaded))
    elif ext in (".geojson", ".json"):
        info.update(_inspect_geojson(uploaded))
    elif ext in (".tif", ".tiff"):
        _check_magic(uploaded, (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"), "GeoTIFF")
    elif ext in (".gpkg", ".sqlite"):
        _check_magic(uploaded, (b"SQLite format 3\x00",), label)
    elif ext in (".ppkx", ".mpkx", ".lpkx", ".mpk", ".lpk", ".kmz", ".qgz", ".xlsx"):
        _check_magic(uploaded, (b"PK\x03\x04", b"7z\xbc\xaf"), label)
    elif ext in (".las", ".laz"):
        _check_magic(uploaded, (b"LASF",), "LAS/LAZ point cloud")

    info.setdefault("crs", "See file metadata")
    uploaded.seek(0)
    return info


def _check_magic(uploaded, signatures, label):
    uploaded.seek(0)
    head = uploaded.read(16)
    uploaded.seek(0)
    if not any(head.startswith(sig) for sig in signatures):
        raise ValidationError(f"This file does not look like a valid {label}.")


def _inspect_zip(uploaded):
    """Work out what GIS data a zip contains (shapefile, File Geodatabase, rasters...)."""
    uploaded.seek(0)
    try:
        with zipfile.ZipFile(uploaded) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/") and "__MACOSX" not in n]
            for n in names:
                if n.startswith("/") or ".." in n.replace("\\", "/").split("/"):
                    raise ValidationError("The zip contains unsafe file paths.")
            lower = [n.lower().replace("\\", "/") for n in names]
            exts = {os.path.splitext(n)[1] for n in lower}

            # ArcGIS File Geodatabase (folder ending in .gdb)
            if any(".gdb/" in n for n in lower):
                gdbs = sorted({n.split(".gdb/")[0].split("/")[-1] + ".gdb" for n in lower if ".gdb/" in n})
                label = "File Geodatabase (zip)" if len(gdbs) == 1 else f"File Geodatabases (zip, {len(gdbs)})"
                return {"file_format": label, "data_type": "vector", "crs": "See geodatabase"}

            # Shapefile(s)
            if ".shp" in exts:
                missing = SHAPEFILE_REQUIRED - exts
                if missing:
                    raise ValidationError(
                        "The zip contains a .shp but is missing: " + ", ".join(sorted(missing))
                        + ". Include all the shapefile parts (.shp, .shx, .dbf, .prj)."
                    )
                crs = "Unknown – no .prj file"
                prj = next((n for n in names if n.lower().endswith(".prj")), None)
                if prj:
                    crs = _guess_crs_from_wkt(zf.read(prj)[:4000].decode("utf-8", "ignore"))
                n_shp = sum(1 for n in lower if n.endswith(".shp"))
                label = "Shapefile (zip)" if n_shp == 1 else f"Shapefiles (zip, {n_shp} layers)"
                return {"file_format": label, "data_type": "vector", "crs": crs}

            # MapInfo
            if ".tab" in exts or ".mif" in exts:
                return {"file_format": "MapInfo (zip)", "data_type": "vector", "crs": "See .tab/.mif"}

            # ESRI GRID (folder with .adf files) or other rasters
            if exts & RASTER_EXTS:
                fmt = "ESRI Grid (zip)" if ".adf" in exts else "Raster files (zip)"
                return {"file_format": fmt, "data_type": "raster", "crs": "See files"}

            if exts & VECTOR_EXTS:
                return {"file_format": "Vector files (zip)", "data_type": "vector", "crs": "See files"}

            if exts & {".lyrx", ".lyr", ".mxd", ".aprx", ".qgz", ".qgs"}:
                return {"file_format": "GIS project files (zip)", "data_type": "other", "crs": "See files"}

            if not exts & GIS_EXTS:
                raise ValidationError("No GIS data was found in this zip file.")
            return {"crs": "See files"}
    except zipfile.BadZipFile:
        raise ValidationError("The zip file is damaged or not a zip archive.")
    finally:
        uploaded.seek(0)


def _guess_crs_from_wkt(wkt):
    w = wkt.upper()
    if w.startswith("PROJCS") or w.startswith("PROJCRS"):
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

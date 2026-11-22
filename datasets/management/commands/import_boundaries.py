"""
Download regional boundaries from geoBoundaries (CC BY 4.0) and keep the
five northern regions shown on the portal map.

    python manage.py import_boundaries

What it does:
1. Downloads geoBoundaries "SOM ADM1" (simplified) from www.geoboundaries.org
2. Keeps Awdal, Woqooyi Galbeed (Maroodi Jeex), Togdheer, Sanaag and Sool
3. Saves static/data/somaliland_boundary.geojson  -> drawn on the homepage and Map Viewer
4. Creates/updates a published "Regional Boundaries" dataset in the catalog

If you have an OFFICIAL boundary file from a ministry, use that instead:
    python manage.py import_boundaries --file path/to/boundary.geojson
"""
import json
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from datasets.models import Category, Dataset
from organizations.models import Organization

API_URL = "https://www.geoboundaries.org/api/current/gbOpen/SOM/ADM1/"

# Name variants used by different sources for each region
REGIONS = {
    "Awdal": ["awdal"],
    "Maroodi Jeex": ["woqooyi galbeed", "waqooyi galbeed", "woqooyi-galbeed", "maroodi jeex", "maroodi jeh"],
    "Togdheer": ["togdheer", "toghdeer"],
    "Sanaag": ["sanaag", "sanag"],
    "Sool": ["sool"],
}

DISCLAIMER = (
    "Regional outlines from geoBoundaries (CC BY 4.0), covering the five northern regions "
    "(former British Somaliland, 1960). Boundaries are approximate and for reference only. "
    "Parts of Sool and Sanaag are disputed. Replace with the official boundary from the "
    "responsible ministry when available."
)

NAME_KEYS = ("shapeName", "name", "NAME_1", "ADM1_EN", "admin1Name", "region", "REGION")


def _fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "SomalilandGeoDataPortal/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _round_coords(coords, nd=5):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], nd), round(coords[1], nd)]
    return [_round_coords(c, nd) for c in coords]


def _feature_name(props):
    for k in NAME_KEYS:
        if props.get(k):
            return str(props[k])
    return ""


def _match_region(name):
    n = name.lower().strip()
    for label, variants in REGIONS.items():
        if any(v in n for v in variants):
            return label
    return None


class Command(BaseCommand):
    help = "Import the Somaliland regional boundaries for the map and catalog."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Use a local GeoJSON file instead of downloading")
        parser.add_argument("--keep-all", action="store_true",
                            help="Use every feature in --file as-is (for an official boundary file)")

    def handle(self, *args, **opts):
        if opts["file"]:
            data = json.loads(Path(opts["file"]).read_text(encoding="utf-8"))
            source = f"Local file: {Path(opts['file']).name}"
        else:
            self.stdout.write("Contacting geoBoundaries…")
            try:
                meta = json.loads(_fetch(API_URL))
                url = meta.get("simplifiedGeometryGeoJSON") or meta.get("gjDownloadURL")
                self.stdout.write(f"Downloading {url}")
                data = json.loads(_fetch(url, timeout=180))
            except Exception as exc:  # network problems, API changes
                raise CommandError(f"Download failed: {exc}. Try again, or use --file with a GeoJSON file.")
            source = "geoBoundaries gbOpen SOM ADM1 (www.geoboundaries.org), CC BY 4.0"

        features = data.get("features", []) if isinstance(data, dict) else []
        if not features:
            raise CommandError("No features found in the boundary data.")

        kept, seen = [], []
        for f in features:
            props = f.get("properties") or {}
            name = _feature_name(props)
            seen.append(name)
            region = name if opts["keep_all"] else _match_region(name)
            if region and f.get("geometry"):
                geom = f["geometry"]
                kept.append({
                    "type": "Feature",
                    "properties": {"region": region, "source_name": name},
                    "geometry": {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"])},
                })

        found = sorted({k["properties"]["region"] for k in kept})
        if not kept:
            raise CommandError("None of the regions matched. Names in the file were: " + ", ".join(sorted(set(seen))))
        if not opts["keep_all"] and len(found) < len(REGIONS):
            missing = set(REGIONS) - set(found)
            self.stdout.write(self.style.WARNING(
                f"Missing regions: {', '.join(sorted(missing))}. Names in the file were: {', '.join(sorted(set(seen)))}"
            ))

        out = {"type": "FeatureCollection", "features": kept}
        content = json.dumps(out, separators=(",", ":")).encode()

        # 1) Static file for the homepage + Map Viewer
        static_path = Path(settings.BASE_DIR) / "static" / "data" / "somaliland_boundary.geojson"
        static_path.parent.mkdir(parents=True, exist_ok=True)
        static_path.write_bytes(content)
        self.stdout.write(self.style.SUCCESS(f"Saved {static_path} ({len(content)//1024} KB, regions: {', '.join(found)})"))

        # 2) Published dataset in the catalog
        xs, ys = [], []

        def walk(c):
            if isinstance(c[0], (int, float)):
                xs.append(c[0]); ys.append(c[1])
            else:
                for i in c:
                    walk(i)

        for k in kept:
            walk(k["geometry"]["coordinates"])

        category, _ = Category.objects.get_or_create(slug="boundaries", defaults={"name": "Boundaries"})
        org, _ = Organization.objects.get_or_create(
            name=settings.PORTAL_ORGANIZATION, defaults={"short_name": "Team", "kind": "agency"}
        )
        uploader = User.objects.filter(is_superuser=True).order_by("id").first() or User.objects.order_by("id").first()
        if uploader is None:
            self.stdout.write(self.style.WARNING("No users yet, so the catalog dataset was skipped. Create a superuser and run again."))
            return

        ds = Dataset.objects.filter(slug="somaliland-regional-boundaries").first() or Dataset(slug="somaliland-regional-boundaries")
        ds.title = "Somaliland Regional Boundaries"
        ds.summary = "Outlines of the five regions: Awdal, Maroodi Jeex, Togdheer, Sanaag and Sool."
        ds.description = (
            "Regional boundary polygons for the map. Each feature has a 'region' attribute.\n\n"
            "Source: " + source
        )
        ds.category = category
        ds.organization = org
        ds.uploaded_by = uploader
        ds.keywords = "boundaries, regions, administrative, borders"
        ds.coverage_area = "National"
        ds.source = source
        ds.disclaimer = DISCLAIMER if not opts["keep_all"] else ds.disclaimer
        ds.license = Dataset.License.CC_BY
        ds.access_level = Dataset.Access.PUBLIC
        ds.file_format = "GeoJSON"
        ds.data_type = Dataset.DataType.VECTOR
        ds.crs = "EPSG:4326"
        ds.feature_count = len(kept)
        ds.file_size = len(content)
        ds.min_lon, ds.min_lat, ds.max_lon, ds.max_lat = min(xs), min(ys), max(xs), max(ys)
        ds.status = Dataset.Status.PUBLISHED
        ds.published_at = ds.published_at or timezone.now()
        ds.is_featured = True
        ds.file.save("somaliland-regional-boundaries.geojson", ContentFile(content), save=False)
        ds.save()
        self.stdout.write(self.style.SUCCESS("Published dataset: Somaliland Regional Boundaries"))

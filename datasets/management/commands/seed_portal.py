"""
python manage.py seed_portal           -> categories + example institutions
python manage.py seed_portal --demo    -> also demo users and one sample dataset
"""
import json

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from datasets.models import Category, Dataset
from organizations.models import Organization

CATEGORIES = [
    ("Boundaries", "boundaries"), ("Roads & Transport", "roads"), ("Water & Rivers", "water"),
    ("Elevation", "elevation"), ("Land Cover", "land-cover"), ("Satellite Imagery", "imagery"),
    ("Settlements", "settlements"), ("Agriculture", "agriculture"), ("Health & Education", "services"),
    ("Climate & Environment", "environment"),
]

# Edit these to match the real institutions before going live.
INSTITUTIONS = [
    ("Ministry of Agriculture Development", "MoAD", "ministry"),
    ("Ministry of Water Resources Development", "MoWRD", "ministry"),
    ("Ministry of Environment and Climate Change", "MoECC", "ministry"),
    ("Ministry of Planning and National Development", "MoPND", "ministry"),
    ("National Statistics Office", "NSO", "agency"),
    ("Hargeisa Local Government", "HLG", "local_gov"),
]


class Command(BaseCommand):
    help = "Create starter categories and institutions (and optional demo data)."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create demo users and a sample dataset")

    def handle(self, *args, **opts):
        for i, (name, slug) in enumerate(CATEGORIES):
            Category.objects.get_or_create(slug=slug, defaults={"name": name, "order": i})
        for name, short, kind in INSTITUTIONS:
            Organization.objects.get_or_create(name=name, defaults={"short_name": short, "kind": kind})
        self.stdout.write(self.style.SUCCESS(f"{len(CATEGORIES)} categories, {len(INSTITUTIONS)} institutions ready."))

        if opts["demo"]:
            self._demo()

    def _demo(self):
        planning = Organization.objects.get(short_name="MoPND")
        water = Organization.objects.get(short_name="MoWRD")
        users = [
            ("specialist", "GIS", "Specialist", User.Role.SPECIALIST, water),
            ("reviewer", "Data", "Reviewer", User.Role.REVIEWER, planning),
            ("citizen", "Public", "User", User.Role.PUBLIC, None),
        ]
        for username, first, last, role, org in users:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username, email=f"{username}@example.org", password="ChangeMe-2026!",
                    first_name=first, last_name=last, role=role, organization=org,
                )
        self.stdout.write("Demo users: specialist / reviewer / citizen  (password: ChangeMe-2026!)")

        if not Dataset.objects.filter(slug="sample-water-points").exists():
            geojson = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"name": "Sample point A", "type": "borehole"},
                     "geometry": {"type": "Point", "coordinates": [44.065, 9.560]}},
                    {"type": "Feature", "properties": {"name": "Sample point B", "type": "berkad"},
                     "geometry": {"type": "Point", "coordinates": [45.014, 10.439]}},
                    {"type": "Feature", "properties": {"name": "Sample point C", "type": "shallow well"},
                     "geometry": {"type": "Point", "coordinates": [43.183, 9.936]}},
                ],
            }
            content = json.dumps(geojson).encode()
            ds = Dataset(
                title="Sample Water Points", slug="sample-water-points",
                summary="Demonstration dataset with three example water points. Replace with real data.",
                category=Category.objects.get(slug="water"), organization=water,
                uploaded_by=User.objects.get(username="specialist"),
                file_format="GeoJSON", data_type=Dataset.DataType.VECTOR, file_size=len(content),
                feature_count=3, min_lon=43.183, min_lat=9.560, max_lon=45.014, max_lat=10.439,
                status=Dataset.Status.PUBLISHED, published_at=timezone.now(), is_featured=True,
                keywords="water, boreholes, demo", coverage_area="National (sample)",
            )
            ds.file.save("sample-water-points.geojson", ContentFile(content), save=False)
            ds.save()
            self.stdout.write("Sample dataset created.")

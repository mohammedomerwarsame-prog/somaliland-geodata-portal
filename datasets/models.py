import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def private_storage():
    """Dataset files live outside MEDIA_ROOT; only the download view serves them."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def dataset_upload_path(instance, filename):
    org = instance.organization.slug if instance.organization_id else "unassigned"
    base, ext = os.path.splitext(filename)
    safe = slugify(base)[:80] or "dataset"
    return f"datasets/{org}/{timezone.now():%Y/%m}/{safe}-{uuid.uuid4().hex[:8]}{ext.lower()}"


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=255, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class DatasetQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Dataset.Status.PUBLISHED)

    def visible_to(self, user):
        qs = self.published()
        if not user.is_authenticated:
            qs = qs.filter(access_level=Dataset.Access.PUBLIC)
        return qs


class Dataset(models.Model):
    class DataType(models.TextChoices):
        VECTOR = "vector", "Vector"
        RASTER = "raster", "Raster"
        TABLE = "table", "Table"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Changes requested"
        ARCHIVED = "archived", "Archived"

    class Access(models.TextChoices):
        PUBLIC = "public", "Open – anyone can download"
        REGISTERED = "registered", "Registered users only"

    class License(models.TextChoices):
        CC_BY = "cc-by-4.0", "CC BY 4.0 (open, credit required)"
        ODBL = "odbl", "Open Database License (ODbL)"
        GOV_OPEN = "gov-open", "Government open data licence"
        RESTRICTED = "restricted", "Restricted – terms on request"

    # Description
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=230, unique=True, blank=True)
    summary = models.CharField(max_length=300, help_text="One or two sentences shown in the catalog.")
    description = models.TextField(blank=True, help_text="Methodology, attributes, known limitations.")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="datasets")
    keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated")
    coverage_area = models.CharField(max_length=150, blank=True, help_text="e.g. 'National', 'Maroodi Jeex'")
    source = models.CharField(max_length=255, blank=True, help_text="How and by whom the data was produced")
    data_date = models.DateField(null=True, blank=True, help_text="Date the data represents")
    disclaimer = models.TextField(blank=True, help_text="Shown on the dataset page (e.g. for boundary data)")

    # Ownership
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="datasets")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploads")

    # File + technical metadata
    file = models.FileField(upload_to=dataset_upload_path, storage=private_storage, max_length=300)
    file_format = models.CharField(max_length=30, blank=True)
    file_size = models.BigIntegerField(default=0)
    data_type = models.CharField(max_length=10, choices=DataType.choices, default=DataType.VECTOR)
    crs = models.CharField("Coordinate system", max_length=120, default="EPSG:4326")
    feature_count = models.PositiveIntegerField(null=True, blank=True)
    min_lon = models.FloatField(null=True, blank=True)
    min_lat = models.FloatField(null=True, blank=True)
    max_lon = models.FloatField(null=True, blank=True)
    max_lat = models.FloatField(null=True, blank=True)
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True)

    # Access and licence
    license = models.CharField(max_length=20, choices=License.choices, default=License.CC_BY)
    access_level = models.CharField(max_length=20, choices=Access.choices, default=Access.PUBLIC)

    # Workflow
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)

    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DatasetQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "dataset"
            slug, n = base, 2
            while Dataset.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("datasets:detail", args=[self.slug])

    @property
    def has_bbox(self):
        return None not in (self.min_lon, self.min_lat, self.max_lon, self.max_lat)

    @property
    def can_preview_on_map(self):
        return self.file_format == "GeoJSON" and self.file_size <= settings.MAX_MAP_PREVIEW_MB * 1024 * 1024

    @property
    def keyword_list(self):
        return [k.strip() for k in self.keywords.split(",") if k.strip()]

    def can_be_viewed_by(self, user):
        if self.status == self.Status.PUBLISHED:
            return True
        if not user.is_authenticated:
            return False
        return user.can_review or self.uploaded_by_id == user.id

    def can_be_downloaded_by(self, user):
        if self.status != self.Status.PUBLISHED:
            return self.can_be_viewed_by(user)  # owner / reviewer can fetch while reviewing
        if self.access_level == self.Access.REGISTERED:
            return user.is_authenticated
        return True

    def can_be_edited_by(self, user):
        return (
            user.is_authenticated
            and self.uploaded_by_id == user.id
            and self.status in (self.Status.PENDING, self.Status.REJECTED)
        )

    def __str__(self):
        return self.title


class DownloadLog(models.Model):
    """Simple audit trail of downloads (useful for annual reporting)."""

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="downloads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

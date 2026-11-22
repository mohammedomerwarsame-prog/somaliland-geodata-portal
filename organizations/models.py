from django.db import models
from django.utils.text import slugify


class Organization(models.Model):
    """A government institution that publishes data (ministry, agency, local government)."""

    class Kind(models.TextChoices):
        MINISTRY = "ministry", "Ministry"
        AGENCY = "agency", "Agency / Authority"
        LOCAL_GOV = "local_gov", "Local government"
        ACADEMIC = "academic", "University / Research"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200, unique=True)
    short_name = models.CharField(max_length=30, blank=True, help_text="e.g. MoA, NSO")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.MINISTRY)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="org_logos/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

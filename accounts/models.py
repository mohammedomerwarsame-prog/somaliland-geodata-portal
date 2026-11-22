from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Portal user. Three roles:

    * PUBLIC      – everyone who registers; can browse and download data.
    * SPECIALIST  – staff of the organization that runs the portal; uploads
                    data, including data received from other institutions
                    (by Telegram, email, etc.). Uploads wait for review.
    * REVIEWER    – senior staff of the same organization; approves or
                    returns uploads. Reviewers can also upload.

    Superusers (Django admin) can do everything.
    Public sign-up always creates PUBLIC accounts. Only an administrator can
    give someone the SPECIALIST or REVIEWER role (Admin → Users).
    """

    class Role(models.TextChoices):
        PUBLIC = "public", "Public user"
        SPECIALIST = "specialist", "GIS specialist (uploader)"
        REVIEWER = "reviewer", "Data reviewer"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PUBLIC)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
        help_text="Required for specialists and reviewers.",
    )
    job_title = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    @property
    def can_upload(self):
        if self.is_superuser:
            return True
        return self.role in (self.Role.SPECIALIST, self.Role.REVIEWER)

    @property
    def can_review(self):
        return self.is_superuser or self.role == self.Role.REVIEWER

    def __str__(self):
        return self.get_full_name() or self.username


class SpecialistRequest(models.Model):
    """A registered user asks for upload rights on behalf of an institution."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="specialist_requests")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    job_title = models.CharField(max_length=120)
    work_email = models.EmailField(help_text="Official institutional email address")
    justification = models.TextField(help_text="What data will you publish, and why?")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.organization} ({self.get_status_display()})"

from django.contrib import admin
from django.utils import timezone

from .models import Category, Dataset, DownloadLog


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "category", "data_type", "status", "is_featured",
                    "download_count", "created_at")
    list_filter = ("status", "data_type", "category", "organization", "access_level", "is_featured")
    search_fields = ("title", "summary", "keywords")
    readonly_fields = ("file_size", "file_format", "feature_count", "download_count",
                       "created_at", "updated_at", "reviewed_by", "reviewed_at", "published_at")
    actions = ["publish", "archive", "feature"]
    fieldsets = (
        (None, {"fields": ("title", "slug", "summary", "description", "category", "keywords",
                           "coverage_area", "source", "data_date", "disclaimer")}),
        ("Ownership", {"fields": ("organization", "uploaded_by")}),
        ("File", {"fields": ("file", "file_format", "file_size", "data_type", "crs", "feature_count",
                             ("min_lon", "min_lat", "max_lon", "max_lat"), "thumbnail")}),
        ("Access", {"fields": ("license", "access_level")}),
        ("Workflow", {"fields": ("status", "is_featured", "review_note", "reviewed_by", "reviewed_at",
                                 "published_at", "download_count", "created_at", "updated_at")}),
    )

    @admin.action(description="Publish selected datasets")
    def publish(self, request, queryset):
        now = timezone.now()
        n = queryset.update(status=Dataset.Status.PUBLISHED, reviewed_by=request.user, reviewed_at=now)
        queryset.filter(published_at__isnull=True).update(published_at=now)
        self.message_user(request, f"{n} dataset(s) published.")

    @admin.action(description="Archive (hide) selected datasets")
    def archive(self, request, queryset):
        n = queryset.update(status=Dataset.Status.ARCHIVED)
        self.message_user(request, f"{n} dataset(s) archived.")

    @admin.action(description="Feature on homepage")
    def feature(self, request, queryset):
        queryset.update(is_featured=True)


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ("dataset", "user", "created_at")
    list_filter = ("created_at",)
    date_hierarchy = "created_at"

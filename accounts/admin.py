from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .models import SpecialistRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "get_full_name", "role", "organization", "is_active")
    list_filter = ("role", "organization", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Portal role", {"fields": ("role", "organization", "job_title", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Contact & portal role", {"fields": ("email", "first_name", "last_name", "role", "organization")}),
    )
    actions = ["make_specialist", "make_reviewer", "make_public"]

    @admin.action(description="Set role: GIS specialist (must have an institution)")
    def make_specialist(self, request, queryset):
        missing = queryset.filter(organization__isnull=True).count()
        n = queryset.exclude(organization__isnull=True).update(role=User.Role.SPECIALIST)
        self.message_user(request, f"{n} user(s) are now specialists.")
        if missing:
            self.message_user(request, f"{missing} user(s) skipped: assign an institution first.", messages.WARNING)

    @admin.action(description="Set role: Data reviewer (must have an institution)")
    def make_reviewer(self, request, queryset):
        n = queryset.exclude(organization__isnull=True).update(role=User.Role.REVIEWER)
        self.message_user(request, f"{n} user(s) are now reviewers.")

    @admin.action(description="Set role: Public user")
    def make_public(self, request, queryset):
        n = queryset.update(role=User.Role.PUBLIC)
        self.message_user(request, f"{n} user(s) set to public.")


@admin.register(SpecialistRequest)
class SpecialistRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "job_title", "work_email", "status", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("user__username", "user__email", "work_email")
    readonly_fields = ("created_at", "decided_by", "decided_at")
    actions = ["approve", "reject"]

    @admin.action(description="Approve: grant specialist upload rights")
    def approve(self, request, queryset):
        count = 0
        for req in queryset.filter(status=SpecialistRequest.Status.PENDING).select_related("user"):
            user = req.user
            user.organization = req.organization
            user.job_title = req.job_title or user.job_title
            if user.role == User.Role.PUBLIC:
                user.role = User.Role.SPECIALIST
            user.save(update_fields=["organization", "job_title", "role"])
            req.status = SpecialistRequest.Status.APPROVED
            req.decided_by = request.user
            req.decided_at = timezone.now()
            req.save()
            count += 1
        self.message_user(request, f"{count} request(s) approved.")

    @admin.action(description="Reject selected requests")
    def reject(self, request, queryset):
        n = queryset.filter(status=SpecialistRequest.Status.PENDING).update(
            status=SpecialistRequest.Status.REJECTED, decided_by=request.user, decided_at=timezone.now()
        )
        self.message_user(request, f"{n} request(s) rejected.")

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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

    @admin.action(description="Set role: Team uploader (specialist)")
    def make_specialist(self, request, queryset):
        n = queryset.update(role=User.Role.SPECIALIST)
        self.message_user(request, f"{n} user(s) can now upload data.")

    @admin.action(description="Set role: Team reviewer")
    def make_reviewer(self, request, queryset):
        n = queryset.update(role=User.Role.REVIEWER)
        self.message_user(request, f"{n} user(s) are now reviewers.")

    @admin.action(description="Set role: Public user")
    def make_public(self, request, queryset):
        n = queryset.update(role=User.Role.PUBLIC)
        self.message_user(request, f"{n} user(s) set to public.")

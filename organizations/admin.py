from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "kind", "is_active", "member_count")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "short_name")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()

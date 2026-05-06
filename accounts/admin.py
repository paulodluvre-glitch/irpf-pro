from django.contrib import admin

from .models import TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "role", "allowed_sectors", "can_manage_records", "permission_level", "active")
    list_filter = ("active", "permission_level", "can_manage_records")
    search_fields = ("name", "display_name", "email")

# Register your models here.

from django.contrib import admin

from .models import Client, ClientPrivate


class ClientPrivateInline(admin.StackedInline):
    model = ClientPrivate
    extra = 0


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    inlines = [ClientPrivateInline]
    list_display = (
        "full_name",
        "group_name",
        "tax_status",
        "documentation_status",
        "assigned_preparer",
        "preparation_queue_status",
        "active",
    )
    list_filter = ("tax_status", "documentation_status", "preparation_queue_status", "active")
    search_fields = ("full_name", "normalized_name", "group_name", "assigned_preparer")

# Register your models here.

from django.contrib import admin

from .models import ContactLog, Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("client", "document_type", "institution", "status", "last_update")
    list_filter = ("document_type", "status")
    search_fields = ("client__full_name", "institution", "control_key")
    autocomplete_fields = ("client",)


@admin.register(ContactLog)
class ContactLogAdmin(admin.ModelAdmin):
    list_display = ("client", "contact_date", "channel", "subject")
    list_filter = ("channel",)
    search_fields = ("client__full_name", "subject", "notes")
    autocomplete_fields = ("client",)

# Register your models here.

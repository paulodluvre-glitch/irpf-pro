from django.contrib import admin

from .models import DailySnapshot, DeclarationCheckpoint


@admin.register(DeclarationCheckpoint)
class DeclarationCheckpointAdmin(admin.ModelAdmin):
    list_display = ("client", "step_key", "step_label", "completed", "updated_by", "updated_at")
    list_filter = ("completed", "step_key")
    search_fields = ("client__full_name", "step_key", "step_label", "note", "updated_by")
    autocomplete_fields = ("client",)


@admin.register(DailySnapshot)
class DailySnapshotAdmin(admin.ModelAdmin):
    list_display = ("reference_date", "declaracoes", "transmitidas", "em_revisao", "clientes_docs_completos")
    date_hierarchy = "reference_date"

# Register your models here.

from django.db import models

from clients.models import Client


class DeclarationCheckpoint(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="checkpoints")
    step_key = models.CharField(max_length=120)
    step_label = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    updated_by = models.CharField(max_length=120, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "declaration_checkpoints"
        constraints = [
            models.UniqueConstraint(fields=["client", "step_key"], name="unique_client_checkpoint_step"),
        ]
        indexes = [
            models.Index(fields=["client"]),
            models.Index(fields=["step_key"]),
        ]
        ordering = ["client__full_name", "step_key"]

    def __str__(self) -> str:
        return f"{self.client.full_name} - {self.step_label}"


class DailySnapshot(models.Model):
    reference_date = models.DateField(unique=True)
    declaracoes = models.PositiveIntegerField(default=0)
    transmitidas = models.PositiveIntegerField(default=0)
    em_revisao = models.PositiveIntegerField(default=0)
    clientes_com_alguma_documentacao = models.PositiveIntegerField(default=0)
    clientes_docs_completos = models.PositiveIntegerField(default=0)
    clientes_docs_parciais = models.PositiveIntegerField(default=0)
    clientes_sem_documentacao = models.PositiveIntegerField(default=0)
    pct_transmitidas = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pct_docs_completos = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "daily_snapshots"
        ordering = ["-reference_date"]

    def __str__(self) -> str:
        return f"Snapshot {self.reference_date:%d/%m/%Y}"

# Create your models here.

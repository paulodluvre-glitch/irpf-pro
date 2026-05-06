from django.db import models

from clients.models import Client


class DocumentType(models.TextChoices):
    DEDUCTIBLE_EXPENSES = "Despesas Dedutíveis", "Despesas dedutíveis"
    INCOME_REPORT = "Informe de Rendimentos", "Informe de rendimentos"
    BANK_REPORTS = "Informes Bancários", "Informes bancários"


class DocumentStatus(models.TextChoices):
    PENDING = "PENDENTE", "Pendente"
    RECEIVED = "RECEBIDO", "Recebido"
    REQUEST = "SOLICITAR DOCUMENTO", "Solicitar documento"
    NO_STATUS = "SEM STATUS", "Sem status"


class Document(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=120, choices=DocumentType.choices)
    institution = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=80, choices=DocumentStatus.choices, default=DocumentStatus.PENDING)
    last_update = models.DateField(blank=True, null=True)
    control_key = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "documents"
        indexes = [
            models.Index(fields=["client"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["client__full_name", "document_type", "institution"]

    def __str__(self) -> str:
        return f"{self.document_type} - {self.institution or 'Sem instituição'}"


class ContactLog(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="contacts")
    contact_date = models.DateTimeField()
    channel = models.CharField(max_length=80, blank=True)
    subject = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contact_log"
        ordering = ["-contact_date"]

    def __str__(self) -> str:
        return f"{self.client.full_name} - {self.contact_date:%d/%m/%Y}"

# Create your models here.

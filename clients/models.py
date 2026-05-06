from django.db import models


class DeclarationStatus(models.TextChoices):
    PENDING = "PENDENTE", "Pendente"
    READY_TO_PREPARE = "PRONTO PARA PREENCHER", "Pronto para preencher"
    IN_PREPARATION = "EM PREENCHIMENTO", "Em preenchimento"
    READY_FOR_REVIEW = "PRONTO PARA REVISÃO", "Pronto para revisão"
    HEVERTON_ADJUSTMENT = "AJUSTE - HEVERTON", "Ajuste - Heverton"
    AWAITING_MEETING = "AGUARDANDO REUNIÃO", "Aguardando reunião"
    TRANSMITTED = "TRANSMITIDO", "Transmitido"
    NO_STATUS = "SEM STATUS", "Sem status"


class DocumentationStatus(models.TextChoices):
    NO_DOCUMENTATION = "Sem documentação", "Sem documentação"
    PARTIAL = "Recebido parcial", "Recebido parcial"
    COMPLETE = "Recebido total", "Recebido total"


class PreparationQueueStatus(models.TextChoices):
    READY = "Pronta para Preenchimento", "Pronta para preenchimento"
    WAITING = "Aguardando documentação", "Aguardando documentação"


class Client(models.Model):
    normalized_name = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    group_name = models.CharField(max_length=180, blank=True)
    meeting_status = models.CharField(max_length=120, blank=True)
    complexity_level = models.CharField(max_length=80, blank=True)
    tax_status = models.CharField(
        max_length=80,
        choices=DeclarationStatus.choices,
        default=DeclarationStatus.PENDING,
    )
    assigned_preparer = models.CharField(max_length=120, blank=True, default="Não atribuído")
    post_filing_status = models.CharField(max_length=120, blank=True)
    documentation_status = models.CharField(
        max_length=80,
        choices=DocumentationStatus.choices,
        default=DocumentationStatus.NO_DOCUMENTATION,
    )
    preparation_queue_status = models.CharField(
        max_length=80,
        choices=PreparationQueueStatus.choices,
        default=PreparationQueueStatus.WAITING,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "clients"
        indexes = [
            models.Index(fields=["tax_status"]),
            models.Index(fields=["assigned_preparer"]),
            models.Index(fields=["documentation_status"]),
            models.Index(fields=["preparation_queue_status"]),
        ]
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class ClientPrivate(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name="private_data", primary_key=True)
    cpf = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    gov_password = models.CharField(max_length=255, blank=True)
    has_digital_certificate = models.BooleanField(default=False)
    power_of_attorney = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client_private"

    def __str__(self) -> str:
        return f"Dados sensíveis - {self.client.full_name}"

# Create your models here.

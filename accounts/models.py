from django.db import models


class PermissionLevel(models.TextChoices):
    FULL = "full", "Acesso completo"
    STATUS_ONLY = "status_only", "Status e responsável"
    READ_ONLY = "read_only", "Somente consulta"


class TeamMember(models.Model):
    name = models.CharField(max_length=120, unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    role = models.CharField(max_length=80, blank=True)
    allowed_sectors = models.CharField(max_length=255, blank=True)
    can_manage_records = models.BooleanField(default=False)
    permission_level = models.CharField(
        max_length=30,
        choices=PermissionLevel.choices,
        default=PermissionLevel.FULL,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "team_members"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.display_name or self.name

# Create your models here.

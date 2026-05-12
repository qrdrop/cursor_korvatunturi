from django.conf import settings
from django.db import models

from repositories.models import Repository


class AuditEvent(models.Model):
    action = models.CharField(max_length=120)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    repository = models.ForeignKey(Repository, on_delete=models.SET_NULL, null=True, blank=True)
    artifact_id = models.BigIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.action}@{self.created_at.isoformat()}"

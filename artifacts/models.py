from django.conf import settings
from django.db import models

from repositories.models import Repository


class Artifact(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="artifacts")
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=512)
    version = models.CharField(max_length=128, blank=True)
    architecture = models.CharField(max_length=64, blank=True)
    checksum = models.CharField(max_length=64)
    size = models.BigIntegerField()
    storage_path = models.CharField(max_length=1024)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_artifacts",
    )
    is_cached = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("repository", "path"), name="uniq_artifact_repo_path"),
        ]
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"{self.repository.name}/{self.path}"


class PackageMetadata(models.Model):
    artifact = models.OneToOneField(Artifact, on_delete=models.CASCADE, related_name="package_metadata")
    package_name = models.CharField(max_length=255)
    version = models.CharField(max_length=128, blank=True)
    architecture = models.CharField(max_length=64, blank=True)
    dependencies = models.JSONField(default=list, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.package_name}-{self.version}"


class DownloadLog(models.Model):
    artifact = models.ForeignKey(Artifact, on_delete=models.CASCADE, related_name="download_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self) -> str:
        return f"{self.artifact_id}@{self.timestamp.isoformat()}"

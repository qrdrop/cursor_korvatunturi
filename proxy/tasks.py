from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from artifacts.models import Artifact
from auditing.services import log_audit_event
from artifact_storage.backends import LocalFileStorageBackend


@shared_task
def cleanup_proxy_cache(days: int = 30) -> int:
    threshold = timezone.now() - timedelta(days=days)
    candidates = Artifact.objects.filter(is_cached=True, uploaded_at__lt=threshold)
    storage = LocalFileStorageBackend()
    deleted = 0
    for artifact in candidates:
        storage.delete(artifact.storage_path)
        log_audit_event(
            action="artifact.proxy_cache_deleted",
            actor=None,
            repository=artifact.repository,
            artifact=artifact,
            payload={"days": days},
        )
        artifact.delete()
        deleted += 1
    return deleted

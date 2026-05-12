from __future__ import annotations

from auditing.models import AuditEvent


def log_audit_event(*, action: str, actor=None, repository=None, artifact=None, payload=None, ip_address=None):
    return AuditEvent.objects.create(
        action=action,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        repository=repository,
        artifact_id=getattr(artifact, "id", None),
        payload=payload or {},
        ip_address=ip_address,
    )

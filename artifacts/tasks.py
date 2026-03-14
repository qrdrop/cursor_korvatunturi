from celery import shared_task

from artifacts.models import Artifact, PackageMetadata
from artifacts.services import ArtifactMetadataExtractor
from auditing.services import log_audit_event


@shared_task
def extract_metadata_for_artifact(artifact_id: int) -> int:
    artifact = Artifact.objects.select_related("repository").get(id=artifact_id)
    metadata = ArtifactMetadataExtractor.extract(artifact.repository.type, artifact.name)
    PackageMetadata.objects.update_or_create(
        artifact=artifact,
        defaults={
            "package_name": metadata.package_name,
            "version": metadata.version,
            "architecture": metadata.architecture,
            "dependencies": metadata.dependencies,
            "metadata_json": metadata.metadata_json,
        },
    )
    log_audit_event(
        action="artifact.metadata_extracted",
        actor=artifact.uploaded_by,
        repository=artifact.repository,
        artifact=artifact,
        payload={"artifact_id": artifact.id},
    )
    return artifact.id

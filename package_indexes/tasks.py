from celery import shared_task

from auditing.services import log_audit_event
from package_indexes.services import regenerate_indexes_for_repository
from repositories.models import Repository


@shared_task
def regenerate_repository_indexes(repository_id: int) -> list[str]:
    repository = Repository.objects.get(id=repository_id)
    generated_paths = regenerate_indexes_for_repository(repository)
    log_audit_event(
        action="repository.index_regenerated",
        actor=None,
        repository=repository,
        payload={"generated": generated_paths},
    )
    return generated_paths

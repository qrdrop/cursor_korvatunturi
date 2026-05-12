from django.db.models.signals import post_delete
from django.dispatch import receiver

from artifacts.models import Artifact
from package_indexes.tasks import regenerate_repository_indexes


@receiver(post_delete, sender=Artifact)
def regenerate_indexes_after_delete(sender, instance: Artifact, **kwargs) -> None:
    regenerate_repository_indexes.delay(instance.repository_id)

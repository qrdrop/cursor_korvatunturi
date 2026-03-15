from django.apps import AppConfig


class ArtifactStorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "artifact_storage"
    label = "storage"

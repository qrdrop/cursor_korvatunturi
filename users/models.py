from django.conf import settings
from django.db import models

from repositories.models import Repository


class UserRole(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MAINTAINER = "maintainer", "Maintainer"
        READER = "reader", "Reader"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "repository"), name="uniq_user_repo_role"),
        ]
        ordering = ("repository_id", "user_id")

    def __str__(self) -> str:
        return f"{self.user_id}:{self.repository_id}:{self.role}"

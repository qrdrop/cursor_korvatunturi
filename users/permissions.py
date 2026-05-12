from __future__ import annotations

from repositories.models import Repository
from users.models import UserRole


def user_role_for_repository(user, repository: Repository) -> str | None:
    """Resolve repository-scoped role for authenticated user."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserRole.Role.ADMIN
    role = (
        UserRole.objects.filter(user=user, repository=repository)
        .values_list("role", flat=True)
        .first()
    )
    return role


def can_read(user, repository: Repository) -> bool:
    role = user_role_for_repository(user, repository)
    return role in {UserRole.Role.ADMIN, UserRole.Role.MAINTAINER, UserRole.Role.READER}


def can_write(user, repository: Repository) -> bool:
    role = user_role_for_repository(user, repository)
    return role in {UserRole.Role.ADMIN, UserRole.Role.MAINTAINER}

from __future__ import annotations

from repositories.models import Repository, RepositoryTypePolicy


def enabled_repository_types() -> list[str]:
    policy = RepositoryTypePolicy.load()
    return policy.enabled_types()


def is_repository_type_enabled(repository_type: str) -> bool:
    return repository_type in set(enabled_repository_types())


def repository_type_choices() -> list[tuple[str, str]]:
    enabled = set(enabled_repository_types())
    return [choice for choice in Repository.Type.choices if choice[0] in enabled]

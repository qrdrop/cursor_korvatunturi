from __future__ import annotations

from package_indexes.generators import get_generator_for_repository
from repositories.models import Repository


def regenerate_indexes_for_repository(repository: Repository) -> list[str]:
    generator = get_generator_for_repository(repository)
    generated = generator.regenerate(repository)
    return [item.relative_path for item in generated]

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings


class StorageBackend(ABC):
    @abstractmethod
    def store(self, uploaded_file, *, repository: str, relative_path: str) -> str:
        """Store file and return resolved storage path."""

    @abstractmethod
    def retrieve(self, path: str) -> str:
        """Return absolute filesystem path for stored file."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete file from backing storage."""


class LocalFileStorageBackend(StorageBackend):
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir or settings.ARTIFACT_STORAGE_ROOT)

    def store(self, uploaded_file, *, repository: str, relative_path: str) -> str:
        target = self.base_dir / "repositories" / repository / "packages" / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        uploaded_file.seek(0)
        with target.open("wb") as handle:
            for chunk in uploaded_file.chunks():
                handle.write(chunk)
        uploaded_file.seek(0)
        return str(target)

    def retrieve(self, path: str) -> str:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = (self.base_dir / path).resolve()
            if not str(resolved).startswith(str(self.base_dir.resolve())):
                raise FileNotFoundError("Invalid artifact path")
        if not resolved.exists():
            raise FileNotFoundError(f"Artifact does not exist: {resolved}")
        return str(resolved)

    def delete(self, path: str) -> None:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = self.base_dir / path
        if resolved.exists():
            resolved.unlink()


class S3StorageBackend(StorageBackend):
    """Placeholder for future S3-compatible object storage support."""

    def store(self, uploaded_file, *, repository: str, relative_path: str) -> str:
        raise NotImplementedError("S3 storage support not implemented yet.")

    def retrieve(self, path: str) -> str:
        raise NotImplementedError("S3 storage support not implemented yet.")

    def delete(self, path: str) -> None:
        raise NotImplementedError("S3 storage support not implemented yet.")

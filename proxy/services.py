from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
from django.core.cache import cache
from django.db import transaction

from artifacts.models import Artifact, PackageMetadata
from artifacts.services import ArtifactMetadataExtractor
from auditing.services import log_audit_event
from repositories.models import Repository
from artifact_storage.backends import LocalFileStorageBackend, StorageBackend


class _TempUploadedFile:
    def __init__(self, tmp_file, original_name: str, size: int):
        self._tmp_file = tmp_file
        self.name = original_name
        self.size = size

    def seek(self, position: int) -> None:
        self._tmp_file.seek(position)

    def chunks(self, chunk_size: int = 1024 * 1024):
        self._tmp_file.seek(0)
        while True:
            chunk = self._tmp_file.read(chunk_size)
            if not chunk:
                break
            yield chunk


@transaction.atomic
def fetch_and_cache_remote_artifact(
    *,
    repository: Repository,
    artifact_path: str,
    user=None,
    storage_backend: StorageBackend | None = None,
) -> Artifact:
    if repository.mode != Repository.Mode.REMOTE:
        raise ValueError("Repository mode must be remote")
    if not repository.remote_url:
        raise ValueError("Remote repository missing remote_url")

    cached = Artifact.objects.filter(repository=repository, path=artifact_path).first()
    if cached:
        return cached

    cache_key = f"proxy:artifact:{repository.id}:{artifact_path}"
    cached_id = cache.get(cache_key)
    if cached_id:
        artifact = Artifact.objects.filter(id=cached_id).first()
        if artifact:
            return artifact

    remote_url = urljoin(f"{repository.remote_url.rstrip('/')}/", artifact_path)
    response = requests.get(remote_url, stream=True, timeout=20)
    response.raise_for_status()

    filename = Path(artifact_path).name
    sha256 = hashlib.sha256()
    total_size = 0
    with tempfile.TemporaryFile() as temp_file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            temp_file.write(chunk)
            total_size += len(chunk)
            sha256.update(chunk)

        temp_uploaded = _TempUploadedFile(temp_file, filename, total_size)
        metadata = ArtifactMetadataExtractor.extract(repository.type, filename)
        storage_backend = storage_backend or LocalFileStorageBackend()
        storage_path = storage_backend.store(
            temp_uploaded,
            repository=repository.name,
            relative_path=artifact_path,
        )
        artifact = Artifact.objects.create(
            repository=repository,
            name=filename,
            path=artifact_path,
            version=metadata.version,
            architecture=metadata.architecture,
            checksum=sha256.hexdigest(),
            size=total_size,
            storage_path=storage_path,
            uploaded_by=user if user and user.is_authenticated else None,
            is_cached=True,
        )
        PackageMetadata.objects.create(
            artifact=artifact,
            package_name=metadata.package_name,
            version=metadata.version,
            architecture=metadata.architecture,
            dependencies=metadata.dependencies,
            metadata_json=metadata.metadata_json,
        )

    cache.set(cache_key, artifact.id, timeout=300)
    log_audit_event(
        action="artifact.proxy_fetched",
        actor=user if user and user.is_authenticated else None,
        repository=repository,
        artifact=artifact,
        payload={"remote_url": remote_url, "path": artifact_path},
    )
    return artifact

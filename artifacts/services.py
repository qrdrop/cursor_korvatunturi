from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction
from packaging.utils import InvalidWheelFilename, parse_wheel_filename

from artifacts.models import Artifact, PackageMetadata
from auditing.services import log_audit_event
from repositories.models import Repository
from storage.backends import LocalFileStorageBackend, StorageBackend

RPM_FILE_RE = re.compile(
    r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<release>[^-]+)\.(?P<arch>[^.]+)\.rpm$"
)
DEB_FILE_RE = re.compile(r"^(?P<name>.+)_(?P<version>[^_]+)_(?P<arch>[^.]+)\.deb$")
MSI_FILE_RE = re.compile(r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<arch>[^.]+)\.msi$")
PYPI_SDIST_RE = re.compile(r"^(?P<name>.+)-(?P<version>[^-]+)\.tar\.gz$")


@dataclass
class ExtractedMetadata:
    package_name: str
    version: str
    architecture: str
    dependencies: list[str]
    metadata_json: dict


class ArtifactMetadataExtractor:
    """Metadata extractor with per-format parsing hooks."""

    @classmethod
    def detect_repository_type(cls, filename: str) -> str:
        lowered = filename.lower()
        if lowered.endswith(".deb"):
            return Repository.Type.DEB
        if lowered.endswith(".rpm"):
            return Repository.Type.RPM
        if lowered.endswith(".msi"):
            return Repository.Type.MSI
        if lowered.endswith(".whl") or lowered.endswith(".tar.gz"):
            return Repository.Type.PYPI
        return Repository.Type.GENERIC

    @classmethod
    def extract(cls, repository_type: str, filename: str) -> ExtractedMetadata:
        if repository_type == Repository.Type.DEB:
            return cls._extract_deb(filename)
        if repository_type == Repository.Type.RPM:
            return cls._extract_rpm(filename)
        if repository_type == Repository.Type.PYPI:
            return cls._extract_pypi(filename)
        if repository_type == Repository.Type.MSI:
            return cls._extract_msi(filename)
        stem = Path(filename).stem
        return ExtractedMetadata(stem, "", "", [], {"filename": filename, "parser": "generic"})

    @classmethod
    def _extract_deb(cls, filename: str) -> ExtractedMetadata:
        match = DEB_FILE_RE.match(filename)
        if not match:
            return ExtractedMetadata(
                package_name=Path(filename).stem,
                version="",
                architecture="all",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "deb-fallback"},
            )
        return ExtractedMetadata(
            package_name=match.group("name"),
            version=match.group("version"),
            architecture=match.group("arch"),
            dependencies=[],
            metadata_json={"filename": filename, "parser": "deb-filename"},
        )

    @classmethod
    def _extract_rpm(cls, filename: str) -> ExtractedMetadata:
        match = RPM_FILE_RE.match(filename)
        if not match:
            return ExtractedMetadata(
                package_name=Path(filename).stem,
                version="",
                architecture="noarch",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "rpm-fallback"},
            )
        version = f"{match.group('version')}-{match.group('release')}"
        return ExtractedMetadata(
            package_name=match.group("name"),
            version=version,
            architecture=match.group("arch"),
            dependencies=[],
            metadata_json={
                "filename": filename,
                "parser": "rpm-filename",
                "release": match.group("release"),
            },
        )

    @classmethod
    def _extract_pypi(cls, filename: str) -> ExtractedMetadata:
        if filename.endswith(".whl"):
            try:
                name, version, *_rest = parse_wheel_filename(filename)
                return ExtractedMetadata(
                    package_name=str(name),
                    version=str(version),
                    architecture="any",
                    dependencies=[],
                    metadata_json={"filename": filename, "parser": "wheel-filename"},
                )
            except InvalidWheelFilename:
                pass
        sdist_match = PYPI_SDIST_RE.match(filename)
        if sdist_match:
            return ExtractedMetadata(
                package_name=sdist_match.group("name"),
                version=sdist_match.group("version"),
                architecture="source",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "sdist-filename"},
            )
        return ExtractedMetadata(
            package_name=Path(filename).stem,
            version="",
            architecture="any",
            dependencies=[],
            metadata_json={"filename": filename, "parser": "pypi-fallback"},
        )

    @classmethod
    def _extract_msi(cls, filename: str) -> ExtractedMetadata:
        match = MSI_FILE_RE.match(filename)
        if not match:
            return ExtractedMetadata(
                package_name=Path(filename).stem,
                version="",
                architecture="x64",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "msi-fallback"},
            )
        return ExtractedMetadata(
            package_name=match.group("name"),
            version=match.group("version"),
            architecture=match.group("arch"),
            dependencies=[],
            metadata_json={"filename": filename, "parser": "msi-filename"},
        )


def calculate_sha256(uploaded_file) -> str:
    sha256 = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        sha256.update(chunk)
    uploaded_file.seek(0)
    return sha256.hexdigest()


def _default_repo_relative_path(repository: Repository, package_name: str, filename: str) -> str:
    safe_name = package_name.replace(" ", "-").lower()
    if repository.type == Repository.Type.DEB:
        return f"pool/main/{safe_name}/{filename}"
    if repository.type == Repository.Type.RPM:
        return f"packages/{filename}"
    if repository.type == Repository.Type.PYPI:
        return f"packages/{safe_name}/{filename}"
    if repository.type == Repository.Type.MSI:
        return f"packages/{filename}"
    return f"packages/{filename}"


@transaction.atomic
def process_artifact_upload(
    *,
    repository: Repository,
    uploaded_file,
    user,
    expected_checksum: str | None = None,
    storage_backend: StorageBackend | None = None,
) -> Artifact:
    """Persist uploaded file, extract metadata, and trigger index refresh."""
    if uploaded_file.size > settings.MAX_ARTIFACT_SIZE:
        raise ValueError("Artifact exceeds MAX_ARTIFACT_SIZE")

    detected_type = ArtifactMetadataExtractor.detect_repository_type(uploaded_file.name)
    if repository.type != Repository.Type.GENERIC and detected_type != repository.type:
        raise ValueError(f"Uploaded artifact type '{detected_type}' does not match repository type.")

    storage_backend = storage_backend or LocalFileStorageBackend()
    metadata = ArtifactMetadataExtractor.extract(repository.type, uploaded_file.name)
    checksum = calculate_sha256(uploaded_file)
    if expected_checksum and checksum != expected_checksum:
        raise ValueError("Checksum validation failed")

    artifact_path = _default_repo_relative_path(repository, metadata.package_name, uploaded_file.name)
    storage_path = storage_backend.store(
        uploaded_file,
        repository=repository.name,
        relative_path=artifact_path,
    )

    artifact = Artifact.objects.create(
        repository=repository,
        name=uploaded_file.name,
        path=artifact_path,
        version=metadata.version,
        architecture=metadata.architecture,
        checksum=checksum,
        size=uploaded_file.size,
        storage_path=storage_path,
        uploaded_by=user if user and user.is_authenticated else None,
    )
    PackageMetadata.objects.create(
        artifact=artifact,
        package_name=metadata.package_name,
        version=metadata.version,
        architecture=metadata.architecture,
        dependencies=metadata.dependencies,
        metadata_json=metadata.metadata_json,
    )

    log_audit_event(
        action="artifact.uploaded",
        actor=user if user and user.is_authenticated else None,
        repository=repository,
        artifact=artifact,
        payload={"filename": uploaded_file.name, "checksum": checksum},
    )

    from package_indexes.tasks import regenerate_repository_indexes
    from artifacts.tasks import extract_metadata_for_artifact

    extract_metadata_for_artifact.delay(artifact.id)
    regenerate_repository_indexes.delay(repository.id)
    return artifact

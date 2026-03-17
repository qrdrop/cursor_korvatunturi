from __future__ import annotations

import hashlib
import re
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path

from django.conf import settings
from django.db import transaction
from packaging.utils import InvalidWheelFilename, parse_wheel_filename

from artifacts.models import Artifact, PackageMetadata
from auditing.services import log_audit_event
from repositories.models import Repository
from artifact_storage.backends import LocalFileStorageBackend, StorageBackend

try:
    from debian.debfile import DebFile
except Exception:  # pragma: no cover - optional dependency fallback.
    DebFile = None

try:
    import rpmfile
except Exception:  # pragma: no cover - optional dependency fallback.
    rpmfile = None

try:
    import olefile
except Exception:  # pragma: no cover - optional dependency fallback.
    olefile = None

RPM_FILE_RE = re.compile(
    r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<release>[^-]+)\.(?P<arch>[^.]+)\.rpm$"
)
DEB_FILE_RE = re.compile(r"^(?P<name>.+)_(?P<version>[^_]+)_(?P<arch>[^.]+)\.deb$")
MSI_FILE_RE = re.compile(r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<arch>[^.]+)\.msi$")
MSU_FILE_RE = re.compile(r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<arch>[^.]+)\.msu$")
MSU_KB_RE = re.compile(r"^(?P<name>.*?)(?P<kb>KB\d+)(?:-(?P<arch>x64|x86|arm64))?\.msu$", re.IGNORECASE)
PYPI_SDIST_RE = re.compile(r"^(?P<name>.+)-(?P<version>[^-]+)\.tar\.gz$")


@dataclass
class ExtractedMetadata:
    package_name: str
    version: str
    architecture: str
    dependencies: list[str]
    metadata_json: dict


def _safe_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _safe_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_safe_string(item).strip() for item in value if _safe_string(item).strip()]
    string_value = _safe_string(value).strip()
    return [string_value] if string_value else []


def _normalize_architecture(value: str, default: str = "x64") -> str:
    lowered = value.lower().strip()
    if lowered in {"amd64", "x64", "64", "x86_64"}:
        return "x64"
    if lowered in {"i386", "i686", "x86", "32"}:
        return "x86"
    if lowered in {"arm64", "aarch64"}:
        return "arm64"
    return value or default


def _read_prefix_bytes(file_path: str, size: int = 8 * 1024 * 1024) -> bytes:
    with open(file_path, "rb") as handle:
        return handle.read(size)


def _split_debian_dependencies(*fields: str) -> list[str]:
    dependencies: list[str] = []
    for field in fields:
        for raw_item in field.split(","):
            trimmed = raw_item.strip()
            if not trimmed:
                continue
            first_alternative = trimmed.split("|")[0].strip()
            pkg_name = first_alternative.split("(", 1)[0].strip()
            if pkg_name:
                dependencies.append(pkg_name)
    deduped = []
    seen = set()
    for dep in dependencies:
        if dep not in seen:
            seen.add(dep)
            deduped.append(dep)
    return deduped


class ArtifactMetadataExtractor:
    """Metadata extractor with per-format parsing hooks."""

    @classmethod
    def detect_repository_type(cls, filename: str) -> str:
        lowered = filename.lower()
        if lowered.endswith(".deb"):
            return Repository.Type.DEB
        if lowered.endswith(".rpm"):
            return Repository.Type.RPM
        if lowered.endswith(".msi") or lowered.endswith(".msu"):
            return Repository.Type.MSI
        if lowered.endswith(".whl") or lowered.endswith(".tar.gz"):
            return Repository.Type.PYPI
        return Repository.Type.GENERIC

    @classmethod
    def validate_upload_content(cls, repository_type: str, filename: str, uploaded_file) -> None:
        """Validate file content against intended repository/package type."""
        lowered = filename.lower()
        if repository_type == Repository.Type.GENERIC:
            return
        if repository_type == Repository.Type.DEB:
            if not lowered.endswith(".deb"):
                raise ValueError("Repository expects .deb packages.")
            cls._validate_deb_content(uploaded_file)
            return
        if repository_type == Repository.Type.RPM:
            if not lowered.endswith(".rpm"):
                raise ValueError("Repository expects .rpm packages.")
            cls._validate_rpm_content(uploaded_file)
            return
        if repository_type == Repository.Type.PYPI:
            if lowered.endswith(".whl"):
                cls._validate_wheel_content(uploaded_file)
                return
            if lowered.endswith(".tar.gz"):
                cls._validate_sdist_content(uploaded_file)
                return
            raise ValueError("PyPI repository accepts only .whl or .tar.gz packages.")
        if repository_type == Repository.Type.MSI:
            if lowered.endswith(".msi"):
                cls._validate_msi_content(uploaded_file)
                return
            if lowered.endswith(".msu"):
                cls._validate_msu_content(uploaded_file)
                return
            raise ValueError("Windows repository accepts only .msi or .msu packages.")

    @classmethod
    def _read_uploaded_prefix(cls, uploaded_file, size: int = 64 * 1024) -> bytes:
        try:
            position = uploaded_file.tell()
        except Exception:
            position = 0
        uploaded_file.seek(0)
        prefix = uploaded_file.read(size)
        uploaded_file.seek(position)
        return prefix

    @classmethod
    def _validate_deb_content(cls, uploaded_file) -> None:
        prefix = cls._read_uploaded_prefix(uploaded_file, size=128 * 1024)
        if not prefix.startswith(b"!<arch>\n"):
            raise ValueError("Invalid .deb package content (missing ar archive header).")
        if b"debian-binary" not in prefix and DebFile is None:
            raise ValueError("Invalid .deb package content.")

    @classmethod
    def _validate_rpm_content(cls, uploaded_file) -> None:
        prefix = cls._read_uploaded_prefix(uploaded_file, size=8)
        if not prefix.startswith(b"\xed\xab\xee\xdb"):
            raise ValueError("Invalid .rpm package content (RPM magic mismatch).")

    @classmethod
    def _validate_wheel_content(cls, uploaded_file) -> None:
        try:
            uploaded_file.seek(0)
            if not zipfile.is_zipfile(uploaded_file):
                raise ValueError("Invalid .whl package content (not a zip archive).")
            uploaded_file.seek(0)
            with zipfile.ZipFile(uploaded_file, "r") as wheel_archive:
                names = wheel_archive.namelist()
            if not any(name.endswith(".dist-info/METADATA") for name in names):
                raise ValueError("Invalid .whl package content (missing .dist-info/METADATA).")
        except ValueError:
            raise
        except Exception:
            raise ValueError("Invalid .whl package content.")
        finally:
            uploaded_file.seek(0)

    @classmethod
    def _validate_sdist_content(cls, uploaded_file) -> None:
        try:
            uploaded_file.seek(0)
            with tarfile.open(fileobj=uploaded_file, mode="r:gz") as sdist_archive:
                names = sdist_archive.getnames()
            has_expected = any(name.endswith("PKG-INFO") for name in names) or any(
                name.endswith("setup.py") or name.endswith("pyproject.toml") for name in names
            )
            if not has_expected:
                raise ValueError("Invalid .tar.gz package content (missing packaging metadata files).")
        except ValueError:
            raise
        except Exception:
            raise ValueError("Invalid .tar.gz package content.")
        finally:
            uploaded_file.seek(0)

    @classmethod
    def _validate_msi_content(cls, uploaded_file) -> None:
        prefix = cls._read_uploaded_prefix(uploaded_file, size=8)
        if not prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise ValueError("Invalid .msi package content (OLE signature mismatch).")

    @classmethod
    def _validate_msu_content(cls, uploaded_file) -> None:
        prefix = cls._read_uploaded_prefix(uploaded_file, size=8)
        if prefix.startswith(b"MSCF"):
            return
        # Some repackaged update bundles are ZIP containers with CAB/XML payloads.
        try:
            uploaded_file.seek(0)
            if zipfile.is_zipfile(uploaded_file):
                uploaded_file.seek(0)
                with zipfile.ZipFile(uploaded_file, "r") as archive:
                    names = [name.lower() for name in archive.namelist()]
                if any(name.endswith(".cab") for name in names) or any(name.endswith(".xml") for name in names):
                    return
        except Exception:
            pass
        finally:
            uploaded_file.seek(0)
        raise ValueError("Invalid .msu package content (expected CAB/ZIP update package).")

    @classmethod
    def extract(cls, repository_type: str, filename: str, file_path: str | None = None) -> ExtractedMetadata:
        if repository_type == Repository.Type.DEB:
            return cls._extract_deb(filename, file_path)
        if repository_type == Repository.Type.RPM:
            return cls._extract_rpm(filename, file_path)
        if repository_type == Repository.Type.PYPI:
            return cls._extract_pypi(filename, file_path)
        if repository_type == Repository.Type.MSI:
            return cls._extract_msi(filename, file_path)
        stem = Path(filename).stem
        return ExtractedMetadata(
            stem,
            "",
            "",
            [],
            {"filename": filename, "parser": "generic", "parsed_from_content": False},
        )

    @classmethod
    def _extract_deb(cls, filename: str, file_path: str | None = None) -> ExtractedMetadata:
        if file_path and DebFile is not None:
            try:
                deb = DebFile(file_path)
                control = deb.debcontrol()
                control_map = {str(key): _safe_string(value) for key, value in control.items()}
                package_name = control_map.get("Package", Path(filename).stem)
                version = control_map.get("Version", "")
                architecture = control_map.get("Architecture", "all")
                dependencies = _split_debian_dependencies(
                    control_map.get("Depends", ""),
                    control_map.get("Pre-Depends", ""),
                )
                return ExtractedMetadata(
                    package_name=package_name,
                    version=version,
                    architecture=architecture,
                    dependencies=dependencies,
                    metadata_json={
                        "filename": filename,
                        "parser": "deb-control",
                        "parsed_from_content": True,
                        "control_fields": control_map,
                    },
                )
            except Exception:
                pass

        match = DEB_FILE_RE.match(filename)
        if not match:
            return ExtractedMetadata(
                package_name=Path(filename).stem,
                version="",
                architecture="all",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "deb-fallback", "parsed_from_content": False},
            )
        return ExtractedMetadata(
            package_name=match.group("name"),
            version=match.group("version"),
            architecture=match.group("arch"),
            dependencies=[],
            metadata_json={"filename": filename, "parser": "deb-filename", "parsed_from_content": False},
        )

    @classmethod
    def _extract_rpm(cls, filename: str, file_path: str | None = None) -> ExtractedMetadata:
        if file_path and rpmfile is not None:
            try:
                with rpmfile.open(file_path) as rpm_pkg:
                    headers = rpm_pkg.headers or {}
                normalized = {str(key).lower(): value for key, value in headers.items()}
                package_name = _safe_string(normalized.get("name")) or Path(filename).stem
                version = _safe_string(normalized.get("version"))
                release = _safe_string(normalized.get("release"))
                arch = _safe_string(normalized.get("arch")) or "noarch"
                combined_version = version
                if release and version:
                    combined_version = f"{version}-{release}"
                elif release and not version:
                    combined_version = release

                dependencies = _safe_list(normalized.get("requirename"))
                dependencies = [dep for dep in dependencies if dep and not dep.startswith("rpmlib(")]
                metadata_subset = {
                    "summary": _safe_string(normalized.get("summary")),
                    "description": _safe_string(normalized.get("description")),
                    "vendor": _safe_string(normalized.get("vendor")),
                    "license": _safe_string(normalized.get("license")),
                    "release": release,
                    "url": _safe_string(normalized.get("url")),
                }
                return ExtractedMetadata(
                    package_name=package_name,
                    version=combined_version,
                    architecture=arch,
                    dependencies=dependencies,
                    metadata_json={
                        "filename": filename,
                        "parser": "rpm-headers",
                        "parsed_from_content": True,
                        "rpm_headers": metadata_subset,
                    },
                )
            except Exception:
                pass

        match = RPM_FILE_RE.match(filename)
        if not match:
            return ExtractedMetadata(
                package_name=Path(filename).stem,
                version="",
                architecture="noarch",
                dependencies=[],
                metadata_json={"filename": filename, "parser": "rpm-fallback", "parsed_from_content": False},
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
                "parsed_from_content": False,
            },
        )

    @classmethod
    def _extract_pypi(cls, filename: str, file_path: str | None = None) -> ExtractedMetadata:
        if file_path and filename.endswith(".whl"):
            try:
                with zipfile.ZipFile(file_path, "r") as wheel_archive:
                    metadata_filename = next(
                        (
                            name
                            for name in wheel_archive.namelist()
                            if name.endswith(".dist-info/METADATA")
                        ),
                        None,
                    )
                    if metadata_filename:
                        metadata_text = wheel_archive.read(metadata_filename).decode("utf-8", errors="replace")
                        parsed = Parser().parsestr(metadata_text)
                        package_name = parsed.get("Name") or Path(filename).stem
                        version = parsed.get("Version", "")
                        dependencies = parsed.get_all("Requires-Dist", []) or []
                        return ExtractedMetadata(
                            package_name=package_name,
                            version=version,
                            architecture="any",
                            dependencies=dependencies,
                            metadata_json={
                                "filename": filename,
                                "parser": "wheel-metadata",
                                "parsed_from_content": True,
                                "summary": parsed.get("Summary", ""),
                                "home_page": parsed.get("Home-page", ""),
                                "license": parsed.get("License", ""),
                                "metadata_version": parsed.get("Metadata-Version", ""),
                            },
                        )
            except Exception:
                pass

        if file_path and filename.endswith(".tar.gz"):
            try:
                with tarfile.open(file_path, "r:*") as sdist_archive:
                    pkg_info_member = next(
                        (member for member in sdist_archive.getmembers() if member.name.endswith("PKG-INFO")),
                        None,
                    )
                    if pkg_info_member:
                        pkg_info_file = sdist_archive.extractfile(pkg_info_member)
                        if pkg_info_file:
                            metadata_text = pkg_info_file.read().decode("utf-8", errors="replace")
                            parsed = Parser().parsestr(metadata_text)
                            package_name = parsed.get("Name") or Path(filename).stem
                            version = parsed.get("Version", "")
                            dependencies = parsed.get_all("Requires-Dist", []) or []
                            return ExtractedMetadata(
                                package_name=package_name,
                                version=version,
                                architecture="source",
                                dependencies=dependencies,
                                metadata_json={
                                    "filename": filename,
                                    "parser": "sdist-pkg-info",
                                    "parsed_from_content": True,
                                    "summary": parsed.get("Summary", ""),
                                    "home_page": parsed.get("Home-page", ""),
                                    "license": parsed.get("License", ""),
                                    "metadata_version": parsed.get("Metadata-Version", ""),
                                },
                            )
            except Exception:
                pass

        if filename.endswith(".whl"):
            try:
                name, version, *_rest = parse_wheel_filename(filename)
                return ExtractedMetadata(
                    package_name=str(name),
                    version=str(version),
                    architecture="any",
                    dependencies=[],
                    metadata_json={"filename": filename, "parser": "wheel-filename", "parsed_from_content": False},
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
                metadata_json={"filename": filename, "parser": "sdist-filename", "parsed_from_content": False},
            )
        return ExtractedMetadata(
            package_name=Path(filename).stem,
            version="",
            architecture="any",
            dependencies=[],
            metadata_json={"filename": filename, "parser": "pypi-fallback", "parsed_from_content": False},
        )

    @classmethod
    def _extract_msi(cls, filename: str, file_path: str | None = None) -> ExtractedMetadata:
        content_hints = cls._extract_windows_content_hints(filename, file_path)
        lowered = filename.lower()
        if lowered.endswith(".msi"):
            match = MSI_FILE_RE.match(filename)
            if not match:
                return ExtractedMetadata(
                    package_name=content_hints.get("package_name") or Path(filename).stem,
                    version=content_hints.get("version") or "",
                    architecture=content_hints.get("architecture") or "x64",
                    dependencies=[],
                    metadata_json={
                        "filename": filename,
                        "parser": "msi-fallback",
                        "installer_type": "msi",
                        "parsed_from_content": bool(content_hints),
                        "content_hints": content_hints,
                    },
                )
            return ExtractedMetadata(
                package_name=content_hints.get("package_name") or match.group("name"),
                version=content_hints.get("version") or match.group("version"),
                architecture=content_hints.get("architecture") or match.group("arch"),
                dependencies=[],
                metadata_json={
                    "filename": filename,
                    "parser": "msi-filename",
                    "installer_type": "msi",
                    "parsed_from_content": bool(content_hints),
                    "content_hints": content_hints,
                },
            )

        match = MSU_FILE_RE.match(filename)
        if match:
            return ExtractedMetadata(
                package_name=content_hints.get("package_name") or match.group("name"),
                version=content_hints.get("version") or match.group("version"),
                architecture=content_hints.get("architecture") or match.group("arch"),
                dependencies=[],
                metadata_json={
                    "filename": filename,
                    "parser": "msu-filename",
                    "installer_type": "msu",
                    "parsed_from_content": bool(content_hints),
                    "content_hints": content_hints,
                },
            )

        kb_match = MSU_KB_RE.match(filename)
        if kb_match:
            package_name = (kb_match.group("name") or "windows-update").strip("-_")
            if not package_name:
                package_name = "windows-update"
            arch = kb_match.group("arch") or "x64"
            version = kb_match.group("kb").upper()
            return ExtractedMetadata(
                package_name=content_hints.get("package_name") or package_name,
                version=content_hints.get("version") or version,
                architecture=content_hints.get("architecture") or arch,
                dependencies=[],
                metadata_json={
                    "filename": filename,
                    "parser": "msu-kb",
                    "installer_type": "msu",
                    "parsed_from_content": bool(content_hints),
                    "content_hints": content_hints,
                },
            )

        return ExtractedMetadata(
            package_name=content_hints.get("package_name") or Path(filename).stem,
            version=content_hints.get("version") or "",
            architecture=content_hints.get("architecture") or "x64",
            dependencies=[],
            metadata_json={
                "filename": filename,
                "parser": "msu-fallback",
                "installer_type": "msu",
                "parsed_from_content": bool(content_hints),
                "content_hints": content_hints,
            },
        )

    @classmethod
    def _extract_windows_content_hints(cls, filename: str, file_path: str | None) -> dict:
        if not file_path:
            return {}

        hints: dict[str, str] = {}
        try:
            file_prefix = _read_prefix_bytes(file_path)
        except Exception:
            return {}

        text_fragments = [
            file_prefix.decode("utf-8", errors="ignore"),
            file_prefix.decode("utf-16le", errors="ignore"),
            file_prefix.decode("latin-1", errors="ignore"),
        ]
        combined_text = "\n".join(text_fragments)

        kb_match = re.search(r"KB\d{6,8}", combined_text, re.IGNORECASE)
        if kb_match:
            hints["version"] = kb_match.group(0).upper()

        version_match = re.search(r'ProductVersion[^0-9]{0,40}([0-9][0-9A-Za-z.\-]+)', combined_text, re.IGNORECASE)
        if version_match and "version" not in hints:
            hints["version"] = version_match.group(1)

        package_match = re.search(
            r'(?:ProductName|title|package|name)[^A-Za-z0-9]{0,40}([A-Za-z0-9._ \-]{3,120})',
            combined_text,
            re.IGNORECASE,
        )
        if package_match:
            hints["package_name"] = package_match.group(1).strip().strip(".")

        arch_match = re.search(r"\b(amd64|x86_64|x64|x86|arm64|aarch64)\b", combined_text, re.IGNORECASE)
        if arch_match:
            hints["architecture"] = _normalize_architecture(arch_match.group(1))

        if olefile is not None and filename.lower().endswith(".msi"):
            try:
                if olefile.isOleFile(file_path):
                    with olefile.OleFileIO(file_path) as ole:
                        metadata = ole.get_metadata()
                        if metadata.title and "package_name" not in hints:
                            hints["package_name"] = str(metadata.title)
            except Exception:
                pass

        return hints


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
    ArtifactMetadataExtractor.validate_upload_content(repository.type, uploaded_file.name, uploaded_file)

    storage_backend = storage_backend or LocalFileStorageBackend()
    filename_metadata = ArtifactMetadataExtractor.extract(repository.type, uploaded_file.name)
    checksum = calculate_sha256(uploaded_file)
    if expected_checksum and checksum != expected_checksum:
        raise ValueError("Checksum validation failed")

    artifact_path = _default_repo_relative_path(
        repository,
        filename_metadata.package_name,
        uploaded_file.name,
    )
    storage_path = storage_backend.store(
        uploaded_file,
        repository=repository.name,
        relative_path=artifact_path,
    )
    metadata = ArtifactMetadataExtractor.extract(
        repository.type,
        uploaded_file.name,
        file_path=storage_path,
    )
    resolved_package_name = metadata.package_name or filename_metadata.package_name
    resolved_version = metadata.version or filename_metadata.version
    resolved_architecture = metadata.architecture or filename_metadata.architecture

    artifact = Artifact.objects.create(
        repository=repository,
        name=uploaded_file.name,
        path=artifact_path,
        version=resolved_version,
        architecture=resolved_architecture,
        checksum=checksum,
        size=uploaded_file.size,
        storage_path=storage_path,
        uploaded_by=user if user and user.is_authenticated else None,
    )
    PackageMetadata.objects.create(
        artifact=artifact,
        package_name=resolved_package_name,
        version=resolved_version,
        architecture=resolved_architecture,
        dependencies=metadata.dependencies,
        metadata_json=metadata.metadata_json,
    )

    log_audit_event(
        action="artifact.uploaded",
        actor=user if user and user.is_authenticated else None,
        repository=repository,
        artifact=artifact,
        payload={
            "filename": uploaded_file.name,
            "checksum": checksum,
            "metadata_parser": metadata.metadata_json.get("parser"),
            "parsed_from_content": metadata.metadata_json.get("parsed_from_content", False),
        },
    )

    from package_indexes.tasks import regenerate_repository_indexes
    from artifacts.tasks import extract_metadata_for_artifact

    extract_metadata_for_artifact.delay(artifact.id)
    regenerate_repository_indexes.delay(repository.id)
    return artifact

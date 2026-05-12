from __future__ import annotations

import gzip
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings

from artifacts.models import Artifact, PackageMetadata
from repositories.models import Repository


@dataclass
class GeneratedFile:
    relative_path: str
    absolute_path: Path


class BaseIndexGenerator:
    def _repository_base(self, repository: Repository) -> Path:
        return settings.ARTIFACT_STORAGE_ROOT / "repositories" / repository.name

    def _metadata_base(self, repository: Repository) -> Path:
        return self._repository_base(repository) / "metadata"

    def regenerate(self, repository: Repository) -> list[GeneratedFile]:
        raise NotImplementedError


class NoopIndexGenerator(BaseIndexGenerator):
    def regenerate(self, repository: Repository) -> list[GeneratedFile]:
        return []


class DebianIndexGenerator(BaseIndexGenerator):
    def regenerate(self, repository: Repository) -> list[GeneratedFile]:
        generated: list[GeneratedFile] = []
        artifacts = (
            Artifact.objects.filter(repository=repository)
            .order_by("name")
            .select_related("package_metadata")
        )
        by_arch: dict[str, list[Artifact]] = defaultdict(list)
        for artifact in artifacts:
            arch = artifact.architecture or "amd64"
            by_arch[arch].append(artifact)

        metadata_root = self._metadata_base(repository)
        dist_root = metadata_root / "dists" / "stable" / "main"
        dist_root.mkdir(parents=True, exist_ok=True)

        release_entries: list[tuple[str, str, int]] = []
        for arch, arch_artifacts in by_arch.items():
            binary_dir = dist_root / f"binary-{arch}"
            binary_dir.mkdir(parents=True, exist_ok=True)

            packages_content = []
            for artifact in arch_artifacts:
                try:
                    package_name = artifact.package_metadata.package_name
                except PackageMetadata.DoesNotExist:
                    package_name = Path(artifact.name).stem
                packages_content.append(
                    "\n".join(
                        [
                            f"Package: {package_name}",
                            f"Version: {artifact.version or '0'}",
                            f"Architecture: {arch}",
                            f"Filename: {artifact.path}",
                            f"Size: {artifact.size}",
                            f"SHA256: {artifact.checksum}",
                            "",
                        ]
                    )
                )

            packages_file = binary_dir / "Packages"
            packages_data = "\n".join(packages_content).strip() + "\n" if packages_content else ""
            packages_file.write_text(packages_data, encoding="utf-8")
            generated.append(
                GeneratedFile(
                    relative_path=str(packages_file.relative_to(metadata_root)),
                    absolute_path=packages_file,
                )
            )

            packages_gz = binary_dir / "Packages.gz"
            with gzip.open(packages_gz, "wt", encoding="utf-8") as gz_handle:
                gz_handle.write(packages_data)
            generated.append(
                GeneratedFile(
                    relative_path=str(packages_gz.relative_to(metadata_root)),
                    absolute_path=packages_gz,
                )
            )
            release_entries.extend(
                [
                    (
                        str(packages_file.relative_to(metadata_root / "dists" / "stable")),
                        hashlib.sha256(packages_file.read_bytes()).hexdigest(),
                        packages_file.stat().st_size,
                    ),
                    (
                        str(packages_gz.relative_to(metadata_root / "dists" / "stable")),
                        hashlib.sha256(packages_gz.read_bytes()).hexdigest(),
                        packages_gz.stat().st_size,
                    ),
                ]
            )

        release_file = metadata_root / "dists" / "stable" / "Release"
        lines = [
            "Origin: ArtifactRepo",
            "Label: ArtifactRepo",
            "Suite: stable",
            "Codename: stable",
            f"Date: {datetime.now(UTC).strftime('%a, %d %b %Y %H:%M:%S %z')}",
            "Architectures: " + " ".join(sorted(by_arch.keys()) or ["amd64"]),
            "Components: main",
            "SHA256:",
        ]
        for rel_path, digest, size in release_entries:
            lines.append(f" {digest} {size:16d} {rel_path}")
        release_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        generated.append(
            GeneratedFile(
                relative_path=str(release_file.relative_to(metadata_root)),
                absolute_path=release_file,
            )
        )
        return generated


class RPMIndexGenerator(BaseIndexGenerator):
    def regenerate(self, repository: Repository) -> list[GeneratedFile]:
        metadata_root = self._metadata_base(repository)
        repodata = metadata_root / "repodata"
        repodata.mkdir(parents=True, exist_ok=True)
        artifacts = Artifact.objects.filter(repository=repository).order_by("name")
        timestamp = int(datetime.now(UTC).timestamp())

        primary_xml = repodata / "primary.xml"
        filelists_xml = repodata / "filelists.xml"
        repomd_xml = repodata / "repomd.xml"
        primary_lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<metadata>"]
        filelists_lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<filelists>"]

        for artifact in artifacts:
            try:
                package_name = artifact.package_metadata.package_name
            except PackageMetadata.DoesNotExist:
                package_name = Path(artifact.name).stem
            version = artifact.version or "0"
            arch = artifact.architecture or "noarch"
            primary_lines.extend(
                [
                    '  <package type="rpm">',
                    f"    <name>{escape(package_name)}</name>",
                    f"    <arch>{escape(arch)}</arch>",
                    f'    <version ver="{escape(version)}" rel="1"/>',
                    f'    <checksum type="sha256">{artifact.checksum}</checksum>',
                    f'    <size package="{artifact.size}"/>',
                    f'    <location href="{escape(artifact.path)}"/>',
                    "  </package>",
                ]
            )
            filelists_lines.extend(
                [
                    f'  <package pkgid="{artifact.checksum}" name="{escape(package_name)}" arch="{escape(arch)}">',
                    f"    <version ver=\"{escape(version)}\" rel=\"1\"/>",
                    f"    <file>{escape(artifact.path)}</file>",
                    "  </package>",
                ]
            )

        primary_lines.append("</metadata>")
        filelists_lines.append("</filelists>")
        primary_xml.write_text("\n".join(primary_lines) + "\n", encoding="utf-8")
        filelists_xml.write_text("\n".join(filelists_lines) + "\n", encoding="utf-8")

        primary_gz = repodata / "primary.xml.gz"
        filelists_gz = repodata / "filelists.xml.gz"
        with gzip.open(primary_gz, "wt", encoding="utf-8") as handle:
            handle.write(primary_xml.read_text(encoding="utf-8"))
        with gzip.open(filelists_gz, "wt", encoding="utf-8") as handle:
            handle.write(filelists_xml.read_text(encoding="utf-8"))

        primary_checksum = hashlib.sha256(primary_gz.read_bytes()).hexdigest()
        filelists_checksum = hashlib.sha256(filelists_gz.read_bytes()).hexdigest()
        repomd_xml.write_text(
            "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8"?>',
                    "<repomd>",
                    "  <data type=\"primary\">",
                    f"    <checksum type=\"sha256\">{primary_checksum}</checksum>",
                    f"    <location href=\"repodata/{primary_gz.name}\"/>",
                    f"    <timestamp>{timestamp}</timestamp>",
                    "  </data>",
                    "  <data type=\"filelists\">",
                    f"    <checksum type=\"sha256\">{filelists_checksum}</checksum>",
                    f"    <location href=\"repodata/{filelists_gz.name}\"/>",
                    f"    <timestamp>{timestamp}</timestamp>",
                    "  </data>",
                    "</repomd>",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return [
            GeneratedFile(relative_path=str(primary_gz.relative_to(metadata_root)), absolute_path=primary_gz),
            GeneratedFile(
                relative_path=str(filelists_gz.relative_to(metadata_root)),
                absolute_path=filelists_gz,
            ),
            GeneratedFile(relative_path=str(repomd_xml.relative_to(metadata_root)), absolute_path=repomd_xml),
        ]


class PyPIIndexGenerator(BaseIndexGenerator):
    def regenerate(self, repository: Repository) -> list[GeneratedFile]:
        metadata_root = self._metadata_base(repository)
        simple_root = metadata_root / "simple"
        simple_root.mkdir(parents=True, exist_ok=True)

        artifacts = (
            Artifact.objects.filter(repository=repository)
            .order_by("name")
            .select_related("package_metadata")
        )
        packages: dict[str, list[Artifact]] = defaultdict(list)
        for artifact in artifacts:
            try:
                package_name = artifact.package_metadata.package_name
            except PackageMetadata.DoesNotExist:
                package_name = Path(artifact.name).stem
            normalized = package_name.lower().replace("_", "-")
            packages[normalized].append(artifact)

        generated: list[GeneratedFile] = []
        index_html = simple_root / "index.html"
        links = [f'<a href="{name}/">{name}</a><br/>' for name in sorted(packages)]
        index_html.write_text("<html><body>\n" + "\n".join(links) + "\n</body></html>\n", encoding="utf-8")
        generated.append(
            GeneratedFile(relative_path=str(index_html.relative_to(metadata_root)), absolute_path=index_html)
        )

        for package_name, package_artifacts in packages.items():
            package_dir = simple_root / package_name
            package_dir.mkdir(parents=True, exist_ok=True)
            detail_file = package_dir / "index.html"
            artifact_links = []
            for artifact in package_artifacts:
                href = f"/repo/{repository.name}/{artifact.path}#sha256={artifact.checksum}"
                artifact_links.append(f'<a href="{href}">{artifact.name}</a><br/>')
            detail_file.write_text(
                "<html><body>\n" + "\n".join(artifact_links) + "\n</body></html>\n",
                encoding="utf-8",
            )
            generated.append(
                GeneratedFile(
                    relative_path=str(detail_file.relative_to(metadata_root)),
                    absolute_path=detail_file,
                )
            )
        return generated


def get_generator_for_repository(repository: Repository) -> BaseIndexGenerator:
    if repository.type == Repository.Type.DEB:
        return DebianIndexGenerator()
    if repository.type == Repository.Type.RPM:
        return RPMIndexGenerator()
    if repository.type == Repository.Type.PYPI:
        return PyPIIndexGenerator()
    return NoopIndexGenerator()

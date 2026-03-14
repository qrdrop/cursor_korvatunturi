from django.test import SimpleTestCase

from artifacts.services import ArtifactMetadataExtractor
from repositories.models import Repository


class MetadataExtractorTests(SimpleTestCase):
    def test_detect_types_from_extension(self):
        self.assertEqual(
            ArtifactMetadataExtractor.detect_repository_type("pkg_1.0_amd64.deb"),
            Repository.Type.DEB,
        )
        self.assertEqual(
            ArtifactMetadataExtractor.detect_repository_type("pkg-1.0-1.x86_64.rpm"),
            Repository.Type.RPM,
        )
        self.assertEqual(
            ArtifactMetadataExtractor.detect_repository_type("demo-1.2.3-py3-none-any.whl"),
            Repository.Type.PYPI,
        )
        self.assertEqual(
            ArtifactMetadataExtractor.detect_repository_type("installer-1.2-x64.msi"),
            Repository.Type.MSI,
        )

    def test_extract_deb_filename_metadata(self):
        metadata = ArtifactMetadataExtractor.extract(Repository.Type.DEB, "hello_2.0_amd64.deb")
        self.assertEqual(metadata.package_name, "hello")
        self.assertEqual(metadata.version, "2.0")
        self.assertEqual(metadata.architecture, "amd64")

    def test_extract_rpm_filename_metadata(self):
        metadata = ArtifactMetadataExtractor.extract(
            Repository.Type.RPM,
            "example-2.1.0-7.x86_64.rpm",
        )
        self.assertEqual(metadata.package_name, "example")
        self.assertEqual(metadata.version, "2.1.0-7")
        self.assertEqual(metadata.architecture, "x86_64")

    def test_extract_pypi_wheel_filename_metadata(self):
        metadata = ArtifactMetadataExtractor.extract(
            Repository.Type.PYPI,
            "my_pkg-1.0.0-py3-none-any.whl",
        )
        self.assertEqual(metadata.package_name, "my-pkg")
        self.assertEqual(metadata.version, "1.0.0")

    def test_extract_msi_filename_metadata(self):
        metadata = ArtifactMetadataExtractor.extract(Repository.Type.MSI, "agent-3.4.1-x64.msi")
        self.assertEqual(metadata.package_name, "agent")
        self.assertEqual(metadata.version, "3.4.1")
        self.assertEqual(metadata.architecture, "x64")

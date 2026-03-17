import io
import tarfile
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from artifacts.services import ArtifactMetadataExtractor
from repositories.models import Repository


class UploadContentValidationTests(SimpleTestCase):
    def test_validate_deb_content_accepts_ar_header(self):
        uploaded = SimpleUploadedFile("hello_1.0_amd64.deb", b"!<arch>\ndebian-binary")
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.DEB, uploaded.name, uploaded)

    def test_validate_rpm_content_accepts_magic(self):
        uploaded = SimpleUploadedFile("demo-1.0-1.x86_64.rpm", b"\xed\xab\xee\xdb" + b"payload")
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.RPM, uploaded.name, uploaded)

    def test_validate_whl_content_accepts_zip_with_metadata(self):
        wheel = self._build_wheel_bytes("demo_pkg", "1.0.0")
        uploaded = SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", wheel)
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.PYPI, uploaded.name, uploaded)

    def test_validate_whl_content_rejects_invalid_binary(self):
        uploaded = SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", b"invalid-whl")
        with self.assertRaises(ValueError):
            ArtifactMetadataExtractor.validate_upload_content(Repository.Type.PYPI, uploaded.name, uploaded)

    def test_validate_sdist_content_accepts_pkg_info(self):
        sdist = self._build_sdist_bytes("demo_pkg", "1.0.0")
        uploaded = SimpleUploadedFile("demo_pkg-1.0.0.tar.gz", sdist)
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.PYPI, uploaded.name, uploaded)

    def test_validate_msi_content_accepts_ole_signature(self):
        uploaded = SimpleUploadedFile("agent-1.0.0-x64.msi", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1extra")
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.MSI, uploaded.name, uploaded)

    def test_validate_msu_content_accepts_cab_signature(self):
        uploaded = SimpleUploadedFile("windows-KB5030219-x64.msu", b"MSCF\x00\x00\x00\x00payload")
        ArtifactMetadataExtractor.validate_upload_content(Repository.Type.MSI, uploaded.name, uploaded)

    def test_validate_msu_content_rejects_invalid_payload(self):
        uploaded = SimpleUploadedFile("windows-KB5030219-x64.msu", b"bad-msu")
        with self.assertRaises(ValueError):
            ArtifactMetadataExtractor.validate_upload_content(Repository.Type.MSI, uploaded.name, uploaded)

    @staticmethod
    def _build_wheel_bytes(package_name: str, version: str) -> bytes:
        metadata = f"Metadata-Version: 2.1\nName: {package_name}\nVersion: {version}\nSummary: Demo\n"
        fileobj = io.BytesIO()
        dist_info = f"{package_name}-{version}.dist-info"
        with ZipFile(fileobj, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(f"{dist_info}/METADATA", metadata)
            archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n")
            archive.writestr(f"{dist_info}/RECORD", "")
        return fileobj.getvalue()

    @staticmethod
    def _build_sdist_bytes(package_name: str, version: str) -> bytes:
        fileobj = io.BytesIO()
        with tarfile.open(fileobj=fileobj, mode="w:gz") as archive:
            pkg_info = f"Metadata-Version: 2.1\nName: {package_name}\nVersion: {version}\n"
            data = pkg_info.encode("utf-8")
            info = tarfile.TarInfo(name=f"{package_name}-{version}/PKG-INFO")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return fileobj.getvalue()

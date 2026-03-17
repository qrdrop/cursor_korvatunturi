import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from artifacts.models import Artifact, DownloadLog
from repositories.models import Repository
from users.models import UserRole


@override_settings(
    ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-api-tests",
    CELERY_TASK_ALWAYS_EAGER=True,
    SECURE_SSL_REDIRECT=False,
)
class ApiFlowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="uploader", password="pw")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.repo = Repository.objects.create(
            name="pypi-local",
            type=Repository.Type.PYPI,
            mode=Repository.Mode.LOCAL,
        )
        UserRole.objects.create(user=self.user, repository=self.repo, role=UserRole.Role.MAINTAINER)

    def test_upload_list_and_download_artifact(self):
        wheel_bytes = self._build_wheel(
            package_name="demo_pkg",
            version="1.2.3",
            requires_dist=[],
        )
        upload_response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-1.2.3-py3-none-any.whl", wheel_bytes),
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.content)
        self.assertIn("metadata_json", upload_response.json())
        self.assertIn("dependencies", upload_response.json())
        artifact_id = upload_response.json()["id"]
        artifact = Artifact.objects.get(id=artifact_id)
        self.assertEqual(artifact.repository_id, self.repo.id)

        list_response = self.client.get("/api/artifacts/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        download_response = self.client.get(f"/repo/{self.repo.name}/{artifact.path}")
        self.assertEqual(download_response.status_code, 200)
        payload = b"".join(download_response.streaming_content)
        self.assertEqual(payload, wheel_bytes)
        self.assertEqual(DownloadLog.objects.count(), 1)

    def test_repository_create_requires_admin(self):
        response = self.client.post(
            "/api/repositories/",
            {"name": "new-one", "type": Repository.Type.DEB, "mode": Repository.Mode.LOCAL},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_rejects_wrong_artifact_type(self):
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("wrong_1.0_amd64.deb", b"deb-bytes"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_checksum_mismatch(self):
        wheel_bytes = self._build_wheel(
            package_name="demo_pkg",
            version="2.0.0",
            requires_dist=[],
        )
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-2.0.0-py3-none-any.whl", wheel_bytes),
                "expected_checksum": "0" * 64,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_accepts_msu_in_windows_repo(self):
        windows_repo = Repository.objects.create(
            name="windows-updates",
            type=Repository.Type.MSI,
            mode=Repository.Mode.LOCAL,
        )
        UserRole.objects.create(user=self.user, repository=windows_repo, role=UserRole.Role.MAINTAINER)
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": windows_repo.id,
                "file": self._make_file("windows10.0-KB5030219-x64.msu", b"MSCF\x00\x00\x00\x00payload"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_upload_parses_wheel_metadata_content(self):
        wheel_bytes = self._build_wheel(
            package_name="demo_pkg",
            version="3.4.5",
            requires_dist=["requests>=2.0", "urllib3>=2.0"],
        )
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-3.4.5-py3-none-any.whl", wheel_bytes),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload["package_name"], "demo_pkg")
        self.assertIn("requests>=2.0", payload["dependencies"])
        self.assertEqual(payload["metadata_json"]["parser"], "wheel-metadata")
        self.assertTrue(payload["metadata_json"]["parsed_from_content"])

    def test_upload_rejects_invalid_content_for_extension(self):
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-1.0.0-py3-none-any.whl", b"not-a-wheel"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    @staticmethod
    def _make_file(name: str, content: bytes):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, content)

    @staticmethod
    def _build_wheel(package_name: str, version: str, requires_dist: list[str]) -> bytes:
        metadata_lines = [
            "Metadata-Version: 2.1",
            f"Name: {package_name}",
            f"Version: {version}",
            "Summary: Demo package",
        ]
        metadata_lines.extend([f"Requires-Dist: {item}" for item in requires_dist])
        metadata_body = "\n".join(metadata_lines) + "\n"
        fileobj = BytesIO()
        dist_info = f"{package_name}-{version}.dist-info"
        with ZipFile(fileobj, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(f"{dist_info}/METADATA", metadata_body)
            archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\n")
            archive.writestr(f"{dist_info}/RECORD", "")
        return fileobj.getvalue()

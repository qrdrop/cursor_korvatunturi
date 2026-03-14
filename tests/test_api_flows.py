import tempfile
from pathlib import Path

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
        upload_response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-1.2.3-py3-none-any.whl", b"wheel-bytes"),
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.content)
        artifact_id = upload_response.json()["id"]
        artifact = Artifact.objects.get(id=artifact_id)
        self.assertEqual(artifact.repository_id, self.repo.id)

        list_response = self.client.get("/api/artifacts/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

        download_response = self.client.get(f"/repo/{self.repo.name}/{artifact.path}")
        self.assertEqual(download_response.status_code, 200)
        payload = b"".join(download_response.streaming_content)
        self.assertEqual(payload, b"wheel-bytes")
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
        response = self.client.post(
            "/api/artifacts/upload/",
            {
                "repository": self.repo.id,
                "file": self._make_file("demo_pkg-2.0.0-py3-none-any.whl", b"wheel-bytes"),
                "expected_checksum": "0" * 64,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    @staticmethod
    def _make_file(name: str, content: bytes):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, content)

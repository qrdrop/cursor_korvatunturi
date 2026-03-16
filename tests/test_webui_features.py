import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from artifacts.models import Artifact
from repositories.models import Repository
from users.models import UserRole


@override_settings(
    ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-webui-tests",
    CELERY_TASK_ALWAYS_EAGER=True,
    SECURE_SSL_REDIRECT=False,
)
class WebUiFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="web", password="pw")
        self.repo = Repository.objects.create(name="web-pypi", type=Repository.Type.PYPI, mode=Repository.Mode.LOCAL)
        UserRole.objects.create(user=self.user, repository=self.repo, role=UserRole.Role.MAINTAINER)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_frontend_upload_flow(self):
        self.client.login(username="web", password="pw")
        response = self.client.post(
            "/upload/",
            {
                "repository": self.repo.id,
                "file": SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", b"wheel"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Artifact.objects.count(), 1)

    def test_package_browse_page(self):
        Artifact.objects.create(
            repository=self.repo,
            name="demo_pkg-1.0.0-py3-none-any.whl",
            path="packages/demo/demo_pkg-1.0.0-py3-none-any.whl",
            version="1.0.0",
            architecture="any",
            checksum="a" * 64,
            size=5,
            storage_path="/tmp/demo.whl",
            uploaded_by=self.user,
        )
        self.client.login(username="web", password="pw")
        response = self.client.get("/packages/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "demo_pkg-1.0.0-py3-none-any.whl")

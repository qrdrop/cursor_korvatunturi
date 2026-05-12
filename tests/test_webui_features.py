import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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
        self.admin = get_user_model().objects.create_superuser(
            username="web-admin",
            email="admin@example.com",
            password="pw",
        )
        self.repo = Repository.objects.create(name="web-pypi", type=Repository.Type.PYPI, mode=Repository.Mode.LOCAL)
        UserRole.objects.create(user=self.user, repository=self.repo, role=UserRole.Role.MAINTAINER)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_frontend_upload_flow(self):
        self.client.login(username="web", password="pw")
        wheel_bytes = self._build_wheel("demo_pkg", "1.0.0")
        response = self.client.post(
            "/upload/",
            {
                "repository": self.repo.id,
                "files": SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", wheel_bytes),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Artifact.objects.count(), 1)

    def test_frontend_multi_upload_flow(self):
        self.client.login(username="web", password="pw")
        files = [
            SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", self._build_wheel("demo_pkg", "1.0.0")),
            SimpleUploadedFile("demo_pkg-1.1.0-py3-none-any.whl", self._build_wheel("demo_pkg", "1.1.0")),
        ]
        response = self.client.post(
            "/upload/",
            {
                "repository": self.repo.id,
                "files": files,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Artifact.objects.count(), 2)

    def test_frontend_multi_upload_rejects_single_checksum_mode(self):
        self.client.login(username="web", password="pw")
        files = [
            SimpleUploadedFile("demo_pkg-1.0.0-py3-none-any.whl", self._build_wheel("demo_pkg", "1.0.0")),
            SimpleUploadedFile("demo_pkg-1.1.0-py3-none-any.whl", self._build_wheel("demo_pkg", "1.1.0")),
        ]
        response = self.client.post(
            "/upload/",
            {
                "repository": self.repo.id,
                "files": files,
                "expected_checksum": "0" * 64,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expected checksum can only be used")

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

    def test_legacy_admin_repo_url_redirects(self):
        self.client.login(username="web-admin", password="pw")
        response = self.client.get("/admin/repositories/new/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/manage/repositories/new/", response.url)

    def test_manage_admin_repo_page_works(self):
        self.client.login(username="web-admin", password="pw")
        response = self.client.get("/manage/repositories/new/")
        self.assertEqual(response.status_code, 200)

    @staticmethod
    def _build_wheel(package_name: str, version: str) -> bytes:
        metadata = f"Metadata-Version: 2.1\nName: {package_name}\nVersion: {version}\nSummary: Test\n"
        fileobj = BytesIO()
        dist_info = f"{package_name}-{version}.dist-info"
        with ZipFile(fileobj, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(f"{dist_info}/METADATA", metadata)
            archive.writestr(f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\n")
            archive.writestr(f"{dist_info}/RECORD", "")
        return fileobj.getvalue()

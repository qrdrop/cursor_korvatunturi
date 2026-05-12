import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from artifacts.models import Artifact, PackageMetadata
from package_indexes.tasks import regenerate_repository_indexes
from proxy.tasks import cleanup_proxy_cache
from repositories.models import Repository


@override_settings(
    ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-task-tests",
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TaskTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="task-user", password="pw")

    def test_regenerate_repository_indexes_task(self):
        repo = Repository.objects.create(name="deb-task", type=Repository.Type.DEB, mode=Repository.Mode.LOCAL)
        artifact = Artifact.objects.create(
            repository=repo,
            name="hello_1.0_amd64.deb",
            path="pool/main/hello/hello_1.0_amd64.deb",
            version="1.0",
            architecture="amd64",
            checksum="b" * 64,
            size=100,
            storage_path="/tmp/hello_1.0_amd64.deb",
            uploaded_by=self.user,
        )
        PackageMetadata.objects.create(
            artifact=artifact,
            package_name="hello",
            version="1.0",
            architecture="amd64",
            dependencies=[],
            metadata_json={},
        )
        generated = regenerate_repository_indexes(repo.id)
        self.assertTrue(any(path.endswith("Release") for path in generated))

    def test_cleanup_proxy_cache_task(self):
        repo = Repository.objects.create(name="rpm-task", type=Repository.Type.RPM, mode=Repository.Mode.LOCAL)
        stale = Artifact.objects.create(
            repository=repo,
            name="old.rpm",
            path="packages/old.rpm",
            version="1",
            architecture="x86_64",
            checksum="c" * 64,
            size=1,
            storage_path="/tmp/old.rpm",
            uploaded_by=self.user,
            is_cached=True,
        )
        Artifact.objects.filter(id=stale.id).update(uploaded_at=timezone.now() - timedelta(days=31))
        deleted = cleanup_proxy_cache(days=30)
        self.assertEqual(deleted, 1)

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from artifacts.models import Artifact
from proxy.services import fetch_and_cache_remote_artifact
from repositories.models import Repository


@override_settings(ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-proxy-tests")
class ProxyServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="proxy", password="pw")
        self.repo = Repository.objects.create(
            name="remote-rpm",
            type=Repository.Type.RPM,
            mode=Repository.Mode.REMOTE,
            remote_url="https://packages.example.com",
        )

    @patch("proxy.services.requests.get")
    def test_fetch_and_cache_remote_artifact(self, get_mock):
        response = Mock()
        response.iter_content.return_value = [b"abc", b"123"]
        response.raise_for_status.return_value = None
        get_mock.return_value = response

        artifact = fetch_and_cache_remote_artifact(
            repository=self.repo,
            artifact_path="packages/demo-1.0-1.x86_64.rpm",
            user=self.user,
        )
        self.assertEqual(artifact.repository_id, self.repo.id)
        self.assertTrue(artifact.is_cached)
        self.assertEqual(artifact.size, 6)
        self.assertEqual(Artifact.objects.count(), 1)

import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from artifact_storage.backends import LocalFileStorageBackend


class LocalStorageBackendTests(TestCase):
    @override_settings(ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-storage-tests")
    def test_store_retrieve_delete(self):
        backend = LocalFileStorageBackend()
        payload = SimpleUploadedFile("pkg.deb", b"payload-content")
        storage_path = backend.store(payload, repository="repo1", relative_path="pool/main/pkg.deb")
        self.assertTrue(Path(storage_path).exists())

        resolved = backend.retrieve(storage_path)
        self.assertEqual(resolved, storage_path)

        backend.delete(storage_path)
        self.assertFalse(Path(storage_path).exists())

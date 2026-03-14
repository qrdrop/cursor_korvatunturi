import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from artifacts.models import Artifact, PackageMetadata
from package_indexes.generators import DebianIndexGenerator, PyPIIndexGenerator, RPMIndexGenerator
from repositories.models import Repository


@override_settings(ARTIFACT_STORAGE_ROOT=Path(tempfile.gettempdir()) / "artifact-repo-index-tests")
class IndexGeneratorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="idx", password="pw")

    def _artifact(self, repo, name, path, version, architecture):
        artifact = Artifact.objects.create(
            repository=repo,
            name=name,
            path=path,
            version=version,
            architecture=architecture,
            checksum="a" * 64,
            size=123,
            storage_path=f"/tmp/{name}",
            uploaded_by=self.user,
        )
        PackageMetadata.objects.create(
            artifact=artifact,
            package_name=name.split(".")[0],
            version=version,
            architecture=architecture,
            dependencies=[],
            metadata_json={},
        )
        return artifact

    def test_debian_generator_outputs_packages_and_release(self):
        repo = Repository.objects.create(name="deb-repo", type=Repository.Type.DEB, mode=Repository.Mode.LOCAL)
        self._artifact(repo, "hello_1.0_amd64.deb", "pool/main/hello/hello_1.0_amd64.deb", "1.0", "amd64")
        generated = DebianIndexGenerator().regenerate(repo)
        generated_paths = {entry.relative_path for entry in generated}
        self.assertIn("dists/stable/main/binary-amd64/Packages", generated_paths)
        self.assertIn("dists/stable/main/binary-amd64/Packages.gz", generated_paths)
        self.assertIn("dists/stable/Release", generated_paths)

    def test_rpm_generator_outputs_repodata_files(self):
        repo = Repository.objects.create(name="rpm-repo", type=Repository.Type.RPM, mode=Repository.Mode.LOCAL)
        self._artifact(repo, "demo-1.0-1.x86_64.rpm", "packages/demo-1.0-1.x86_64.rpm", "1.0-1", "x86_64")
        generated = RPMIndexGenerator().regenerate(repo)
        generated_paths = {entry.relative_path for entry in generated}
        self.assertIn("repodata/repomd.xml", generated_paths)
        self.assertIn("repodata/primary.xml.gz", generated_paths)
        self.assertIn("repodata/filelists.xml.gz", generated_paths)

    def test_pypi_generator_outputs_simple_index(self):
        repo = Repository.objects.create(name="pypi-repo", type=Repository.Type.PYPI, mode=Repository.Mode.LOCAL)
        self._artifact(
            repo,
            "demo_pkg-1.0.0-py3-none-any.whl",
            "packages/demo-pkg/demo_pkg-1.0.0-py3-none-any.whl",
            "1.0.0",
            "any",
        )
        generated = PyPIIndexGenerator().regenerate(repo)
        generated_paths = {entry.relative_path for entry in generated}
        self.assertIn("simple/index.html", generated_paths)
        self.assertIn("simple/demo-pkg-1/index.html", generated_paths)

from django.contrib.auth import get_user_model
from django.test import TestCase

from repositories.models import Repository
from users.models import UserRole
from users.permissions import can_read, can_write, user_role_for_repository


class RepositoryPermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dev", password="pw")
        self.repo = Repository.objects.create(name="deb-repo", type=Repository.Type.DEB, mode=Repository.Mode.LOCAL)

    def test_reader_can_only_read(self):
        UserRole.objects.create(user=self.user, repository=self.repo, role=UserRole.Role.READER)
        self.assertEqual(user_role_for_repository(self.user, self.repo), UserRole.Role.READER)
        self.assertTrue(can_read(self.user, self.repo))
        self.assertFalse(can_write(self.user, self.repo))

    def test_maintainer_can_read_and_write(self):
        UserRole.objects.create(user=self.user, repository=self.repo, role=UserRole.Role.MAINTAINER)
        self.assertTrue(can_read(self.user, self.repo))
        self.assertTrue(can_write(self.user, self.repo))

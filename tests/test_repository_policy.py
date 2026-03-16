from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from repositories.models import RepositoryTypePolicy


@override_settings(SECURE_SSL_REDIRECT=False)
class RepositoryPolicyTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin-policy",
            email="admin@example.com",
            password="pw",
        )
        self.token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        policy = RepositoryTypePolicy.load()
        policy.allow_pypi = False
        policy.save()

    def test_disabled_repo_type_rejected_by_api(self):
        response = self.client.post(
            "/api/repositories/",
            {"name": "blocked-pypi", "type": "pypi", "mode": "local"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

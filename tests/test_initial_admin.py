import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from users import bootstrap


class InitialAdminBootstrapTests(TestCase):
    def test_init_admin_command_creates_superuser_from_env(self):
        bootstrap._BOOTSTRAP_DONE = False
        os.environ["DJANGO_INITIAL_ADMIN_USERNAME"] = "first-admin"
        os.environ["DJANGO_INITIAL_ADMIN_PASSWORD"] = "strong-pass-123"
        os.environ["DJANGO_INITIAL_ADMIN_EMAIL"] = "first@example.com"
        try:
            call_command("init_admin")
            user = get_user_model().objects.get(username="first-admin")
            self.assertTrue(user.is_superuser)
            self.assertTrue(user.is_staff)
        finally:
            os.environ.pop("DJANGO_INITIAL_ADMIN_USERNAME", None)
            os.environ.pop("DJANGO_INITIAL_ADMIN_PASSWORD", None)
            os.environ.pop("DJANGO_INITIAL_ADMIN_EMAIL", None)

from __future__ import annotations

from django.core.management.base import BaseCommand

from users.bootstrap import bootstrap_initial_admin_from_env


class Command(BaseCommand):
    help = "Create the initial admin user from DJANGO_INITIAL_ADMIN_* environment variables."

    def handle(self, *args, **options):
        bootstrap_initial_admin_from_env()
        self.stdout.write(self.style.SUCCESS("Initial admin bootstrap check completed."))

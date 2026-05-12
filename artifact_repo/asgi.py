"""ASGI config for artifact_repo project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "artifact_repo.settings")

application = get_asgi_application()

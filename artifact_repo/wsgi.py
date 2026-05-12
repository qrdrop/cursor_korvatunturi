"""WSGI config for artifact_repo project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "artifact_repo.settings")

application = get_wsgi_application()

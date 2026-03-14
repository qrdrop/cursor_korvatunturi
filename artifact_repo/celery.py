"""Celery application for asynchronous processing."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "artifact_repo.settings")

app = Celery("artifact_repo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

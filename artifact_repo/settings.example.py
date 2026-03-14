"""
Example settings profile for production-like deployments.

Copy values into environment variables and use artifact_repo.settings as runtime settings.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DJANGO_SECRET_KEY = "change-me"
DJANGO_DEBUG = False
DJANGO_ALLOWED_HOSTS = ["repo.example.internal"]

POSTGRES_DB = "artifact_repo"
POSTGRES_USER = "artifact_repo"
POSTGRES_PASSWORD = "artifact_repo"
POSTGRES_HOST = "db"
POSTGRES_PORT = 5432

REDIS_URL = "redis://redis:6379/0"
CELERY_BROKER_URL = "redis://redis:6379/1"
CELERY_RESULT_BACKEND = "redis://redis:6379/2"

ARTIFACT_STORAGE_ROOT = BASE_DIR / "storage"
MAX_ARTIFACT_SIZE = 2 * 1024 * 1024 * 1024

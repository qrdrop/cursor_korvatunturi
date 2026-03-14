#!/usr/bin/env bash
set -euo pipefail

echo "Installing dependencies..."
pip3 install --user --break-system-packages -r requirements.txt

export DJANGO_USE_SQLITE="${DJANGO_USE_SQLITE:-true}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-ci-secret-key}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-*}"
export DJANGO_SECURE_SSL_REDIRECT="${DJANGO_SECURE_SSL_REDIRECT:-false}"
export CELERY_TASK_ALWAYS_EAGER=true

echo "Running migrations..."
python3 manage.py migrate --noinput

echo "Running unit tests with coverage..."
python3 -m coverage run --source=. manage.py test
python3 -m coverage report --fail-under=80

echo "Generating OpenAPI schema..."
mkdir -p docs
python3 manage.py generateschema --file docs/openapi.yaml

echo "CI script completed successfully."

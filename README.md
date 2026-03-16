# Django Artifact Repository

A modular Django-based artifact repository server inspired by Artifactory.

Supported first-class repository types:

- Debian APT (`.deb`)
- RPM (`.rpm`)
- PyPI (`.whl`, `.tar.gz`)
- MSI (`.msi`)

## Tech Stack

- Python + Django + Django REST Framework
- PostgreSQL
- Redis
- Celery
- Local filesystem storage (S3-ready extension point)

## Quick Start (Docker)

```bash
docker compose up --build
```

Service endpoints:

- API root: `http://localhost:8000/api/`
- Admin: `http://localhost:8000/admin/`
- PyPI simple API: `http://localhost:8000/simple/`

## Core API Endpoints

- `POST /api/auth/token/`
- `GET|POST /api/repositories/`
- `GET /api/artifacts/`
- `POST /api/artifacts/upload/`
- `GET /repo/<repository>/<path>`

## Project Layout

- `artifact_repo/` Django project and settings
- `repositories/` repository model
- `artifacts/` artifact and metadata models + upload services
- `storage/` storage backend abstraction
- `users/` repository role model and permission logic
- `proxy/` remote proxy fetch + cache cleanup
- `auditing/` audit trail
- `package_indexes/` Debian, RPM, and PyPI index generators
- `api/` DRF endpoints

Detailed architecture: `docs/architecture.md`

## Development (local Python)

```bash
pip3 install --user --break-system-packages -r requirements.txt
export DJANGO_USE_SQLITE=true
export DJANGO_SECURE_SSL_REDIRECT=false
python3 manage.py migrate
python3 manage.py runserver
```

## CI Helper

Run tests (coverage gate 80%) and schema generation:

```bash
./scripts/ci.sh
```

## Cloud Agent Environment

This repository includes `.cursor/environment.json` so cloud agents preinstall
Python dependencies on startup and can run `./scripts/ci.sh` without additional
manual setup.

## OpenAPI/OpenSpec Contract

Generate API schema:

```bash
python3 manage.py generateschema --file docs/openapi.yaml
```

Compatibility notes: `docs/openspec.md`

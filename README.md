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
- Web UI login: `http://localhost:8000/login/`
- Web UI dashboard: `http://localhost:8000/dashboard/`
- PyPI simple API: `http://localhost:8000/simple/`

## Core API Endpoints

- `POST /api/auth/token/`
- `GET|POST /api/repositories/`
- `GET /api/artifacts/`
- `POST /api/artifacts/upload/`
- `GET /repo/<repository>/<path>`

## Web UI Features

- Browse all accessible packages: `/packages/`
- Browse repository contents: `/repositories/<name>/`
- Upload packages from frontend: `/upload/`
- Admin repository creation UI: `/admin/repositories/new/`
- Admin package-type policy UI: `/admin/repository-types/`

## Project Layout

- `artifact_repo/` Django project and settings
- `repositories/` repository model
- `artifacts/` artifact and metadata models + upload services
- `artifact_storage/` storage backend abstraction
- `users/` repository role model and permission logic
- `proxy/` remote proxy fetch + cache cleanup
- `auditing/` audit trail
- `package_indexes/` Debian, RPM, and PyPI index generators
- `api/` DRF endpoints
- `webui/` Django template-based frontend
- `demo/` command-line demo clients

Detailed architecture: `docs/architecture.md`

## Development (local Python)

```bash
pip3 install --user --break-system-packages -r requirements.txt
export DJANGO_USE_SQLITE=true
export DJANGO_DEBUG=true
export DJANGO_SECURE_SSL_REDIRECT=false
export DJANGO_INITIAL_ADMIN_USERNAME=admin
export DJANGO_INITIAL_ADMIN_PASSWORD=admin123
python3 manage.py migrate
python3 manage.py init_admin
python3 manage.py runserver
```

If admin/frontend pages appear unstyled, confirm `DJANGO_DEBUG=true` in local development.

The first-start admin bootstrap is controlled with:

- `DJANGO_INITIAL_ADMIN_USERNAME`
- `DJANGO_INITIAL_ADMIN_PASSWORD`
- `DJANGO_INITIAL_ADMIN_EMAIL` (optional)

Detailed setup and rotation guide: `docs/admin_credentials.md`

## Package Upload Documentation

See `docs/package_uploads.md` for step-by-step API and frontend upload guidance.

## Demo Clients

See `demo/README.md` for command-line demo clients for APT, RPM, PyPI, and MSI usage.

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

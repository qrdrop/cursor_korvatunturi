# Artifact Repository Architecture

## Apps and Responsibilities

- **repositories**: Repository entity and repository-level behavior (`type`, `mode`, remote origin metadata).
- **artifacts**: Uploaded artifacts, package metadata extraction state, and download logging.
- **storage**: Pluggable storage abstraction (`StorageBackend`) with `LocalFileStorageBackend` implementation.
- **users**: Repository-scoped authorization model (`UserRole`) and permission helpers.
- **proxy**: Remote proxy cache and lazy fetch from upstream repositories when local artifact is missing.
- **auditing**: Immutable security and operational audit event trail.
- **package_indexes**: Package index generation for Debian APT, RPM, and PyPI simple API output.
- **api**: Django REST Framework endpoints for repository/artifact management and package delivery.

## Core Flow

1. Client uploads an artifact to `POST /api/artifacts/upload/`.
2. Upload service validates size/checksum, extracts metadata, stores file, creates DB records.
3. Background tasks:
   - metadata extraction/refinement
   - repository index regeneration
4. Artifact download endpoint streams files (`FileResponse`) and logs download/audit events.
5. Remote mode repositories fetch missing artifacts from upstream and cache locally.

## Storage Layout

```text
storage/
  repositories/
    <repository-name>/
      packages/
        ...
      metadata/
        dists/ ...           # Debian
        repodata/ ...        # RPM
        simple/ ...          # PyPI
```

## Security Controls

- Token-based API authentication.
- Repository-scoped authorization (`admin`, `maintainer`, `reader`).
- Upload size limits and optional checksum validation.
- Secure deployment defaults for HTTPS headers/cookies.
- Audit logging for create/upload/download/proxy/index operations.

# OpenSpec Compatibility Notes

This repository exposes an OpenAPI-compatible contract via Django REST Framework's schema generator:

```bash
python3 manage.py generateschema --file docs/openapi.yaml
```

The generated `docs/openapi.yaml` follows the OpenAPI schema format and can be consumed by tools that support OpenAPI/OpenSpec-compatible contracts for:

- Client SDK generation
- API gateways
- Contract testing and validation
- Documentation portals

## Exposed API Surface (v1)

- `POST /api/auth/token/` – obtain token for authenticated API access
- `GET|POST /api/repositories/` – repository list/create
- `GET /api/artifacts/` – list artifacts accessible by role (includes parsed metadata)
- `POST /api/artifacts/upload/` – upload artifact with checksum support and content validation
- `GET /repo/{repository}/{path}` – streaming artifact download
- `GET /simple/` and `GET /simple/{package-name}/` – PyPI simple index endpoints

## Artifact Metadata Contract

Artifact list/upload responses include:

- `package_name` (string)
- `dependencies` (array of strings)
- `metadata_json` (object)

`metadata_json` contains parser-specific details, for example:

- `parser` (e.g. `wheel-metadata`, `deb-control`, `rpm-headers`, `msu-kb`)
- `parsed_from_content` (boolean)
- additional format-specific fields

## Upload Validation and Error Semantics

The upload API validates both:

1. **Extension/type compatibility** with repository type
2. **Binary/content signature** for the package format

Duplicate uploads are rejected by repository-scoped SHA256 checksum detection.

Common client-visible error behaviors:

- `400 Bad Request` for:
  - invalid package content for declared extension
  - repository type mismatch
  - checksum mismatch (`expected_checksum`)
  - duplicate package content (already uploaded SHA256)

## UI (Non-OpenAPI) Note

The web interface (`/upload/`, `/packages/`, `/repositories/{name}/`) uses the same backend service path and therefore enforces the same content validation and duplicate SHA256 behavior as the REST API.

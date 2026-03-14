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

## Exposed API Surface

- `POST /api/auth/token/` – obtain token for authenticated API access
- `GET|POST /api/repositories/` – repository list/create
- `GET /api/artifacts/` – list artifacts accessible by role
- `POST /api/artifacts/upload/` – upload artifact with checksum support
- `GET /repo/{repository}/{path}` – streaming artifact download
- `GET /simple/` and `GET /simple/{package-name}/` – PyPI simple index endpoints

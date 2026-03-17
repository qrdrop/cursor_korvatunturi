# How to Add Packages

You can upload packages from either the web UI or the API.

## Prerequisites

1. Login credentials (token for API, user/password for web UI)
2. A repository where your user has `maintainer` or `admin` role
3. Repository type must match the package type:
   - `.deb` -> `deb`
   - `.rpm` -> `rpm`
   - `.whl` / `.tar.gz` -> `pypi`
   - `.msi` / `.msu` -> `msi`

## Option A: Web UI Upload

1. Open `/login/` and sign in.
2. Go to `/upload/`.
3. Select repository.
4. Drag-and-drop one or multiple package files (or click to browse).
5. Optional: provide SHA256 checksum for single-file uploads.
6. Submit upload.

Upload validation checks package content signatures (not just file names/extensions) so invalid files are rejected.
Duplicate uploads are prevented per repository using SHA256 checksum comparison. If the same package content is uploaded again, the system reports that it was already uploaded.

After upload, indexes are regenerated asynchronously:
- Debian: `Packages`, `Packages.gz`, `Release`
- RPM: `repodata` metadata
- PyPI: simple index HTML

Metadata is parsed from package content whenever possible and exposed in:

- Web UI package/repository browse pages
- `GET /api/artifacts/` response (`package_name`, `dependencies`, `metadata_json`)

## Option B: API Upload

```bash
TOKEN="your-token"
REPO_ID=1
FILE_PATH="/path/to/package.deb"

curl -X POST "http://localhost:8000/api/artifacts/upload/" \
  -H "Authorization: Token ${TOKEN}" \
  -F "repository=${REPO_ID}" \
  -F "file=@${FILE_PATH}"
```

With checksum validation:

```bash
SHA256="$(sha256sum "$FILE_PATH" | awk '{print $1}')"
curl -X POST "http://localhost:8000/api/artifacts/upload/" \
  -H "Authorization: Token ${TOKEN}" \
  -F "repository=${REPO_ID}" \
  -F "file=@${FILE_PATH}" \
  -F "expected_checksum=${SHA256}"
```

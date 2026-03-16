# How to Add Packages

You can upload packages from either the web UI or the API.

## Prerequisites

1. Login credentials (token for API, user/password for web UI)
2. A repository where your user has `maintainer` or `admin` role
3. Repository type must match the package type:
   - `.deb` -> `deb`
   - `.rpm` -> `rpm`
   - `.whl` / `.tar.gz` -> `pypi`
   - `.msi` -> `msi`

## Option A: Web UI Upload

1. Open `/login/` and sign in.
2. Go to `/upload/`.
3. Select repository.
4. Select package file.
5. Optional: provide SHA256 checksum.
6. Submit upload.

After upload, indexes are regenerated asynchronously:
- Debian: `Packages`, `Packages.gz`, `Release`
- RPM: `repodata` metadata
- PyPI: simple index HTML

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

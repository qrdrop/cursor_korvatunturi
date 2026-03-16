# Demo CLI Clients

This folder contains command-line demos for interacting with the artifact repository.

## Setup

```bash
export BASE_URL="http://localhost:8000"
export USERNAME="admin"
export PASSWORD="admin123"
```

Get an auth token:

```bash
TOKEN="$(python3 demo/repo_client.py token --base-url "$BASE_URL" --username "$USERNAME" --password "$PASSWORD")"
export TOKEN
```

## Generic API client

```bash
python3 demo/repo_client.py --help
```

## Repo-specific demos

- `demo/apt_demo.sh`
- `demo/rpm_demo.sh`
- `demo/pypi_demo.sh`
- `demo/msi_demo.sh`

Each script demonstrates repository creation, package upload via API, and package listing.

#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
WHEEL_FILE="${WHEEL_FILE:-/tmp/demo_pkg-1.0.0-py3-none-any.whl}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN first."
  exit 1
fi

echo "Creating PyPI repository..."
REPO_JSON="$(python3 demo/repo_client.py --base-url "$BASE_URL" create-repo --token "$TOKEN" --name "demo-pypi" --type pypi)"
REPO_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$REPO_JSON")"

echo "Uploading wheel..."
python3 demo/repo_client.py --base-url "$BASE_URL" upload --token "$TOKEN" --repository-id "$REPO_ID" --file "$WHEEL_FILE"

echo "PyPI simple index is now available at: ${BASE_URL}/simple/"

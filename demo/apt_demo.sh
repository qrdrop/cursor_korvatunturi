#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
DEB_FILE="${DEB_FILE:-/tmp/example_1.0_amd64.deb}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN first."
  exit 1
fi

echo "Creating Debian repository..."
REPO_JSON="$(python3 demo/repo_client.py --base-url "$BASE_URL" create-repo --token "$TOKEN" --name "demo-deb" --type deb)"
REPO_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$REPO_JSON")"

echo "Uploading .deb artifact..."
python3 demo/repo_client.py --base-url "$BASE_URL" upload --token "$TOKEN" --repository-id "$REPO_ID" --file "$DEB_FILE"

echo "List artifacts..."
python3 demo/repo_client.py --base-url "$BASE_URL" list-artifacts --token "$TOKEN"

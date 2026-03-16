#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
RPM_FILE="${RPM_FILE:-/tmp/example-1.0-1.x86_64.rpm}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN first."
  exit 1
fi

echo "Creating RPM repository..."
REPO_JSON="$(python3 demo/repo_client.py --base-url "$BASE_URL" create-repo --token "$TOKEN" --name "demo-rpm" --type rpm)"
REPO_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$REPO_JSON")"

echo "Uploading .rpm artifact..."
python3 demo/repo_client.py --base-url "$BASE_URL" upload --token "$TOKEN" --repository-id "$REPO_ID" --file "$RPM_FILE"

echo "List artifacts..."
python3 demo/repo_client.py --base-url "$BASE_URL" list-artifacts --token "$TOKEN"

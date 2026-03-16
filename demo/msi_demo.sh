#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
MSI_FILE="${MSI_FILE:-/tmp/agent-1.0.0-x64.msi}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN first."
  exit 1
fi

echo "Creating MSI repository..."
REPO_JSON="$(python3 demo/repo_client.py --base-url "$BASE_URL" create-repo --token "$TOKEN" --name "demo-msi" --type msi)"
REPO_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$REPO_JSON")"

echo "Uploading .msi artifact..."
python3 demo/repo_client.py --base-url "$BASE_URL" upload --token "$TOKEN" --repository-id "$REPO_ID" --file "$MSI_FILE"

echo "List artifacts..."
python3 demo/repo_client.py --base-url "$BASE_URL" list-artifacts --token "$TOKEN"

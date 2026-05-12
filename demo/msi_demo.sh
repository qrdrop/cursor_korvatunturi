#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"
WINDOWS_FILE="${WINDOWS_FILE:-/tmp/windows10.0-KB5030219-x64.msu}"

if [[ -z "$TOKEN" ]]; then
  echo "Set TOKEN first."
  exit 1
fi

echo "Creating Windows (MSI/MSU) repository..."
REPO_JSON="$(python3 demo/repo_client.py --base-url "$BASE_URL" create-repo --token "$TOKEN" --name "demo-msi" --type msi)"
REPO_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$REPO_JSON")"

echo "Uploading Windows package (.msi or .msu)..."
python3 demo/repo_client.py --base-url "$BASE_URL" upload --token "$TOKEN" --repository-id "$REPO_ID" --file "$WINDOWS_FILE"

echo "List artifacts..."
python3 demo/repo_client.py --base-url "$BASE_URL" list-artifacts --token "$TOKEN"

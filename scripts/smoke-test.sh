
#!/usr/bin/env bash

set -euo pipefail

API="${API:-https://klrm3es403.execute-api.us-east-1.amazonaws.com/Prod}"

echo "Checking OPTIONS preflight..."

HEADERS_FILE="$(mktemp)"
trap 'rm -f "$HEADERS_FILE"' EXIT

curl --fail-with-body -sS \
  -D "$HEADERS_FILE" \
  -o /dev/null \
  -X OPTIONS \
  "$API/webhook" \
  -H "Origin: http://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"

grep -qi \
  '^access-control-allow-origin: \*' \
  "$HEADERS_FILE"

echo "CORS preflight passed."

echo "Checking deployment history..."

curl --fail-with-body -sS \
  "$API/deployments?limit=10" \
  | python3 -c '
import json
import sys

data = json.load(sys.stdin)

assert isinstance(
    data["deployments"],
    list,
)

print("Deployment history passed.")
'

if [[ -n "${REPO:-}" ]]; then
  echo "Queueing deployment for $REPO..."

  PAYLOAD="$(
    REPO="$REPO" python3 -c '
import json
import os

print(
    json.dumps({
        "repository": {
            "full_name": os.environ["REPO"]
        }
    })
)
'
  )"

  curl --fail-with-body -sS \
    -X POST \
    "$API/webhook" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD"

  echo
fi

echo "Smoke checks finished."
echo "Verify deployment completion separately."

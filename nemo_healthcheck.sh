#!/bin/bash

# Simple healthcheck for NeMo Data Designer
# Uses the local default URL; override with NEMO_BASE_URL if needed.

URL="${NEMO_BASE_URL:-http://localhost:8000}/health"

echo "Checking NeMo Data Designer health at $URL ..."

response=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

if [ "$response" -eq 200 ]; then
  echo "NeMo Data Designer is healthy."
  exit 0
else
  echo "NeMo Data Designer is NOT healthy. HTTP status: $response"
  exit 1
fi

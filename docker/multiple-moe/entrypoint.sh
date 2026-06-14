#!/bin/bash
set -euo pipefail

/download-models.sh

echo "[entrypoint] starting llama-server router (preset: ${LLAMA_ARG_MODELS_PRESET})"
exec /app/llama-server \
  --host 0.0.0.0 \
  --port 8080 \
  "$@"
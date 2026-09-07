#!/bin/bash
set -euo pipefail

source /detect-preset.sh

PREFER_DEPLOYMENT="${PREFER_DEPLOYMENT:-${LLAMA_DEPLOYMENT:-}}"
PREFER_BUNDLE="${PREFER_BUNDLE:-${LLAMA_BUNDLE:-}}"
PREFER_MODELS="${PREFER_MODELS:-${LLAMA_MODELS:-}}"
PREFER_SERVER_OVERRIDES="${PREFER_SERVER_OVERRIDES:-${LLAMA_SERVER_OVERRIDES:-}}"
PREFER_MODEL_OVERRIDES="${PREFER_MODEL_OVERRIDES:-${LLAMA_MODEL_OVERRIDES:-}}"

if [ -n "${PREFER_DEPLOYMENT:-}${PREFER_BUNDLE:-}${PREFER_MODELS:-}${PREFER_SERVER_OVERRIDES:-}${PREFER_MODEL_OVERRIDES:-}" ]; then
  mkdir -p /run/prefer
  runtime_preset=/run/prefer/llama.ini
  runtime_prestage=/run/prefer/llama.prestage
  runtime_plan=/run/prefer/plan.json
  python3 /prefer-catalog/generate-presets.py \
    --compose \
    --base "${PREFER_DEPLOYMENT:-$LLAMA_ARG_MODELS_PRESET}" \
    --bundles "${PREFER_BUNDLE:-}" \
    --models "${PREFER_MODELS:-}" \
    --server-overrides "${PREFER_SERVER_OVERRIDES:-}" \
    --model-overrides "${PREFER_MODEL_OVERRIDES:-}" \
    --output "$runtime_preset" \
    --prestage-output "$runtime_prestage" \
    --plan-output "$runtime_plan"
  export LLAMA_ARG_MODELS_PRESET="$runtime_preset"
  export PREFER_EFFECTIVE_PLAN="$runtime_plan"
fi

/download-models.sh

echo "[entrypoint] starting llama-server router (preset: ${LLAMA_ARG_MODELS_PRESET})"
exec /app/llama-server \
  --host 0.0.0.0 \
  --port 8080 \
  "$@"

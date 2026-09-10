#!/bin/bash
set -euo pipefail

source /detect-preset.sh
source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh

PREFER_DEPLOYMENT="${PREFER_DEPLOYMENT:-${LLAMA_DEPLOYMENT:-}}"
PREFER_BUNDLE="${PREFER_BUNDLE:-${LLAMA_BUNDLE:-}}"
PREFER_MODELS="${PREFER_MODELS:-${LLAMA_MODELS:-}}"
PREFER_SERVER_OVERRIDES="${PREFER_SERVER_OVERRIDES:-${LLAMA_SERVER_OVERRIDES:-}}"
PREFER_MODEL_OVERRIDES="${PREFER_MODEL_OVERRIDES:-${LLAMA_MODEL_OVERRIDES:-}}"
PREFER_RUNTIME_HANDOFF="${PREFER_RUNTIME_HANDOFF:-${LLAMA_RUNTIME_HANDOFF:-}}"
PREFER_RUNTIME_HANDOFF_BASE64="${PREFER_RUNTIME_HANDOFF_BASE64:-${LLAMA_RUNTIME_HANDOFF_BASE64:-}}"

if [ -n "$PREFER_RUNTIME_HANDOFF" ] && [ -n "$PREFER_RUNTIME_HANDOFF_BASE64" ]; then
  echo "[entrypoint] path and base64 runtime handoff inputs are mutually exclusive" >&2
  exit 2
fi

if [ -n "${PREFER_RUNTIME_HANDOFF}${PREFER_RUNTIME_HANDOFF_BASE64}" ]; then
  if [ -n "${PREFER_BUNDLE:-}${PREFER_MODELS:-}" ]; then
    echo "[entrypoint] a runtime handoff cannot be combined with bundle or model selectors" >&2
    exit 2
  fi
  mkdir -p /run/prefer
  runtime_handoff=/run/prefer/handoff.json
  runtime_artifacts=/run/prefer/handoff-artifacts.tsv
  runtime_preset=/run/prefer/llama.ini
  runtime_prestage=/run/prefer/llama.prestage
  runtime_plan=/run/prefer/plan.json
  if [ -n "$PREFER_RUNTIME_HANDOFF" ]; then
    runtime_handoff_input=(--handoff "$PREFER_RUNTIME_HANDOFF")
  else
    runtime_handoff_input=(--handoff-base64-env PREFER_RUNTIME_HANDOFF_BASE64)
  fi
  prefer runtime materialize \
    "${runtime_handoff_input[@]}" \
    --output "$runtime_handoff" \
    --artifacts-output "$runtime_artifacts"
  unset PREFER_RUNTIME_HANDOFF_BASE64 LLAMA_RUNTIME_HANDOFF_BASE64
  python3 /prefer-catalog/generate-presets.py \
    --compose-handoff \
    --handoff-input "$runtime_handoff" \
    --base "${PREFER_DEPLOYMENT:-}" \
    --default-base "$LLAMA_ARG_MODELS_PRESET" \
    --server-overrides "${PREFER_SERVER_OVERRIDES:-}" \
    --model-overrides "${PREFER_MODEL_OVERRIDES:-}" \
    --output "$runtime_preset" \
    --prestage-output "$runtime_prestage" \
    --plan-output "$runtime_plan"
  prefer_download_runtime_manifest \
    "runtime-handoff" "${MODEL_DOWNLOAD_JOBS:-4}" 8 "$runtime_artifacts" \
    "${S3_BUCKET_NAME:-}" "${S3_MODEL_PREFIX:-}"
  export LLAMA_ARG_MODELS_PRESET="$runtime_preset"
  export PREFER_EFFECTIVE_PLAN="$runtime_plan"
elif [ -n "${PREFER_DEPLOYMENT:-}${PREFER_BUNDLE:-}${PREFER_MODELS:-}${PREFER_SERVER_OVERRIDES:-}${PREFER_MODEL_OVERRIDES:-}" ]; then
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

if [ -z "$runtime_artifacts" ]; then
  /download-models.sh
fi

echo "[entrypoint] starting llama-server router (preset: ${LLAMA_ARG_MODELS_PRESET})"
exec /app/llama-server \
  --host 0.0.0.0 \
  --port 8080 \
  "$@"

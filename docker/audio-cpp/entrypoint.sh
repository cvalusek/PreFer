#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh
source /model-downloads.generated.sh

PREFER_DEPLOYMENT="${PREFER_DEPLOYMENT:-${AUDIO_DEPLOYMENT:-}}"
PREFER_BUNDLE="${PREFER_BUNDLE:-${AUDIO_BUNDLE:-}}"
PREFER_MODELS="${PREFER_MODELS:-${AUDIO_MODELS:-}}"
PREFER_SERVER_OVERRIDES="${PREFER_SERVER_OVERRIDES:-${AUDIO_SERVER_OVERRIDES:-}}"
PREFER_MODEL_OVERRIDES="${PREFER_MODEL_OVERRIDES:-${AUDIO_MODEL_OVERRIDES:-}}"
PREFER_RUNTIME_HANDOFF="${PREFER_RUNTIME_HANDOFF:-${AUDIO_RUNTIME_HANDOFF:-}}"
PREFER_RUNTIME_HANDOFF_BASE64="${PREFER_RUNTIME_HANDOFF_BASE64:-${AUDIO_RUNTIME_HANDOFF_BASE64:-}}"

server_config="${AUDIO_SERVER_CONFIG:-/app/server.json}"
runtime_artifacts=""
if [ -n "$PREFER_RUNTIME_HANDOFF" ] && [ -n "$PREFER_RUNTIME_HANDOFF_BASE64" ]; then
  echo "[audio-entrypoint] path and base64 runtime handoff inputs are mutually exclusive" >&2
  exit 2
fi
if [ -n "${PREFER_RUNTIME_HANDOFF}${PREFER_RUNTIME_HANDOFF_BASE64}" ]; then
  if [ -n "${PREFER_BUNDLE:-}${PREFER_MODELS:-}" ]; then
    echo "[audio-entrypoint] a runtime handoff cannot be combined with bundle or model selectors" >&2
    exit 2
  fi
  mkdir -p /run/prefer
  runtime_handoff=/run/prefer/handoff.json
  runtime_artifacts=/run/prefer/handoff-artifacts.tsv
  runtime_config=/run/prefer/audio.json
  runtime_prestage=/run/prefer/audio.prestage
  runtime_plan=/run/prefer/plan.json
  if [ -n "$PREFER_RUNTIME_HANDOFF" ]; then
    runtime_handoff_input=(--handoff "$PREFER_RUNTIME_HANDOFF")
  else
    runtime_handoff_input=(--handoff-base64-env PREFER_RUNTIME_HANDOFF_BASE64)
  fi
  prefer runtime materialize "${runtime_handoff_input[@]}" --output "$runtime_handoff" --artifacts-output "$runtime_artifacts"
  unset PREFER_RUNTIME_HANDOFF_BASE64 AUDIO_RUNTIME_HANDOFF_BASE64
  python3 /prefer-catalog/generate.py \
    --compose-handoff \
    --handoff-input "$runtime_handoff" \
    --base "${PREFER_DEPLOYMENT:-}" \
    --default-base "$server_config" \
    --server-overrides "${PREFER_SERVER_OVERRIDES:-}" \
    --model-overrides "${PREFER_MODEL_OVERRIDES:-}" \
    --output "$runtime_config" \
    --prestage-output "$runtime_prestage" \
    --plan-output "$runtime_plan"
  server_config="$runtime_config"
  export PREFER_EFFECTIVE_PLAN="$runtime_plan"
elif [ -n "${PREFER_DEPLOYMENT:-}${PREFER_BUNDLE:-}${PREFER_MODELS:-}${PREFER_SERVER_OVERRIDES:-}${PREFER_MODEL_OVERRIDES:-}" ]; then
  mkdir -p /run/prefer
  runtime_config=/run/prefer/audio.json
  runtime_prestage=/run/prefer/audio.prestage
  runtime_plan=/run/prefer/plan.json
  python3 /prefer-catalog/generate.py \
    --compose \
    --base "${PREFER_DEPLOYMENT:-$server_config}" \
    --bundles "${PREFER_BUNDLE:-}" \
    --models "${PREFER_MODELS:-}" \
    --server-overrides "${PREFER_SERVER_OVERRIDES:-}" \
    --model-overrides "${PREFER_MODEL_OVERRIDES:-}" \
    --output "$runtime_config" \
    --prestage-output "$runtime_prestage" \
    --plan-output "$runtime_plan"
  server_config="$runtime_config"
  export PREFER_EFFECTIVE_PLAN="$runtime_plan"
fi
if [ ! -f "$server_config" ]; then
  echo "[audio-entrypoint] server config not found: $server_config" >&2
  exit 2
fi

if [ -n "$runtime_artifacts" ]; then
  prefer_download_runtime_manifest "audio-runtime-handoff" "${AUDIO_DOWNLOAD_JOBS:-${MODEL_DOWNLOAD_JOBS:-4}}" 8 "$runtime_artifacts"
  requested="none"
else
  requested="${AUDIO_PRESTAGE_MODELS:-}"
fi
if [ -z "$requested" ]; then
  prestage_manifest="${server_config%.json}.prestage"
  if [ -f "$prestage_manifest" ]; then
    requested="$(tr -d '\r\n' < "$prestage_manifest")"
  else
    requested="$AUDIO_GENERATED_MODEL_KEYS"
  fi
fi
declare -A seen=()
model_keys=()
IFS=',' read -ra keys <<< "$requested"
for key in "${keys[@]}"; do
  key="${key//[[:space:]]/}"
  if [ -z "$key" ] || [ "$key" = "none" ] || [ -n "${seen[$key]:-}" ]; then
    continue
  fi
  seen["$key"]=1
  model_keys+=("$key")
done
audio_download_model_keys "${model_keys[@]}"

echo "[audio-entrypoint] starting audio.cpp server with $server_config"
exec /app/entrypoint.sh server --config "$server_config" "$@"

#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh
source /model-downloads.generated.sh

PREFER_DEPLOYMENT="${PREFER_DEPLOYMENT:-${VLLM_DEPLOYMENT:-}}"
PREFER_BUNDLE="${PREFER_BUNDLE:-${VLLM_BUNDLE:-}}"
PREFER_MODELS="${PREFER_MODELS:-${VLLM_MODELS:-}}"
PREFER_SERVER_OVERRIDES="${PREFER_SERVER_OVERRIDES:-${VLLM_SERVER_OVERRIDES:-}}"
PREFER_MODEL_OVERRIDES="${PREFER_MODEL_OVERRIDES:-${VLLM_MODEL_OVERRIDES:-}}"
PREFER_RUNTIME_HANDOFF="${PREFER_RUNTIME_HANDOFF:-${VLLM_RUNTIME_HANDOFF:-}}"

resolve_s3_settings() {
  local bucket="${VLLM_S3_BUCKET_NAME:-${S3_BUCKET_NAME:-}}"
  local prefix="${VLLM_S3_MODEL_PREFIX:-${S3_MODEL_PREFIX:-}}"
  local segment=""
  local segments=()

  if [ -n "$bucket" ]; then
    if [[ "$bucket" == s3://* || "$bucket" == */* || "$bucket" == *\\* ]]; then
      echo "[vllm-entrypoint] S3 bucket must be a bucket name, not a URI or path" >&2
      exit 2
    fi
    if [[ "$prefix" == s3://* || "$prefix" == *\\* ]]; then
      echo "[vllm-entrypoint] S3 model prefix must be a relative object prefix" >&2
      exit 2
    fi
    prefix="${prefix#/}"
    prefix="${prefix%/}"
    IFS='/' read -ra segments <<< "$prefix"
    for segment in "${segments[@]}"; do
      if [ "$segment" = ".." ]; then
        echo "[vllm-entrypoint] S3 model prefix must not contain '..' path components" >&2
        exit 2
      fi
    done
    echo "[vllm-entrypoint] S3 read-through enabled: s3://$bucket${prefix:+/$prefix} (HF fallback enabled)"
  else
    prefix=""
    echo "[vllm-entrypoint] Hugging Face staging enabled (S3 read-through disabled)"
  fi
  export VLLM_S3_BUCKET_NAME="$bucket"
  export VLLM_S3_MODEL_PREFIX="$prefix"
}

resolve_s3_settings

server_config="${VLLM_SERVER_CONFIG:-/app/server.json}"
runtime_artifacts=""
if [ -n "$PREFER_RUNTIME_HANDOFF" ]; then
  if [ -n "${PREFER_BUNDLE:-}${PREFER_MODELS:-}" ]; then
    echo "[vllm-entrypoint] PREFER_RUNTIME_HANDOFF cannot be combined with bundle or model selectors" >&2
    exit 2
  fi
  mkdir -p /run/prefer
  runtime_handoff=/run/prefer/handoff.json
  runtime_artifacts=/run/prefer/handoff-artifacts.tsv
  runtime_config=/run/prefer/vllm.json
  runtime_prestage=/run/prefer/vllm.prestage
  runtime_plan=/run/prefer/plan.json
  prefer runtime materialize --handoff "$PREFER_RUNTIME_HANDOFF" --output "$runtime_handoff" --artifacts-output "$runtime_artifacts"
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
  runtime_config=/run/prefer/vllm.json
  runtime_prestage=/run/prefer/vllm.prestage
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
  echo "[vllm-entrypoint] server config not found: $server_config" >&2
  exit 2
fi

requested="${VLLM_PRESTAGE_MODELS:-${PRESTAGE_MODELS:-}}"
if [ -z "$requested" ]; then
  prestage_manifest="${server_config%.json}.prestage"
  if [ -f "$prestage_manifest" ]; then
    requested="$(tr -d '\r\n' < "$prestage_manifest")"
  else
    requested="$VLLM_GENERATED_MODEL_KEYS"
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

download_jobs="${VLLM_DOWNLOAD_JOBS:-${MODEL_DOWNLOAD_JOBS:-4}}"
stage_models() {
  if [ -n "$runtime_artifacts" ]; then
    prefer_download_runtime_manifest "vllm-runtime-handoff" "$download_jobs" 8 "$runtime_artifacts" "$VLLM_S3_BUCKET_NAME" "$VLLM_S3_MODEL_PREFIX"
  elif [ -n "$VLLM_S3_BUCKET_NAME" ]; then
    VLLM_DOWNLOAD_JOBS="$download_jobs" vllm_download_model_keys_s3 "${model_keys[@]}"
  else
    VLLM_DOWNLOAD_JOBS="$download_jobs" vllm_download_model_keys "${model_keys[@]}"
  fi
}

echo "[vllm-entrypoint] staging ${#model_keys[@]} model key(s) in the background"
stage_models &
staging_pid=$!

echo "[vllm-entrypoint] starting vLLM gateway with $server_config"
exec python3 /prefer-vllm-router.py "$server_config" "$staging_pid" "$@"

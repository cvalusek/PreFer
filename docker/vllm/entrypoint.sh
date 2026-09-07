#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /model-downloads.generated.sh

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
  if [ -n "$VLLM_S3_BUCKET_NAME" ]; then
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

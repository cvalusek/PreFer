#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /model-downloads.generated.sh

resolve_s3_settings() {
  local bucket="${SGLANG_S3_BUCKET_NAME:-${S3_BUCKET_NAME:-}}"
  local prefix="${SGLANG_S3_MODEL_PREFIX:-${S3_MODEL_PREFIX:-}}"
  local segment=""
  local segments=()

  if [ -n "$bucket" ]; then
    if [[ "$bucket" == s3://* || "$bucket" == */* || "$bucket" == *\\* ]]; then
      echo "[sglang-entrypoint] S3 bucket must be a bucket name, not a URI or path" >&2
      exit 2
    fi
    if [[ "$prefix" == s3://* || "$prefix" == *\\* ]]; then
      echo "[sglang-entrypoint] S3 model prefix must be a relative object prefix" >&2
      exit 2
    fi
    prefix="${prefix#/}"
    prefix="${prefix%/}"
    IFS='/' read -ra segments <<< "$prefix"
    for segment in "${segments[@]}"; do
      if [ "$segment" = ".." ]; then
        echo "[sglang-entrypoint] S3 model prefix must not contain '..' path components" >&2
        exit 2
      fi
    done
    echo "[sglang-entrypoint] S3 read-through enabled: s3://$bucket${prefix:+/$prefix} (HF fallback enabled)"
  else
    prefix=""
    echo "[sglang-entrypoint] Hugging Face staging enabled (S3 read-through disabled)"
  fi
  export SGLANG_S3_BUCKET_NAME="$bucket"
  export SGLANG_S3_MODEL_PREFIX="$prefix"
}

resolve_s3_settings

server_config="${SGLANG_SERVER_CONFIG:-/app/server.json}"
if [ ! -f "$server_config" ]; then
  echo "[sglang-entrypoint] server config not found: $server_config" >&2
  exit 2
fi

requested="${SGLANG_PRESTAGE_MODELS:-${PRESTAGE_MODELS:-}}"
if [ -z "$requested" ]; then
  prestage_manifest="${server_config%.json}.prestage"
  if [ -f "$prestage_manifest" ]; then
    requested="$(tr -d '\r\n' < "$prestage_manifest")"
  else
    requested="$SGLANG_GENERATED_MODEL_KEYS"
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
download_jobs="${SGLANG_DOWNLOAD_JOBS:-${MODEL_DOWNLOAD_JOBS:-4}}"
if [ -n "$SGLANG_S3_BUCKET_NAME" ]; then
  SGLANG_DOWNLOAD_JOBS="$download_jobs" sglang_download_model_keys_s3 "${model_keys[@]}"
else
  SGLANG_DOWNLOAD_JOBS="$download_jobs" sglang_download_model_keys "${model_keys[@]}"
fi

write_llama_compatibility_marker() {
  local model_key="$1"
  local models_dir="${PREFER_MODELS_DIR:-/models}"
  local marker_dir="$models_dir/.prefer-cache/downloads-v1"
  local marker="$marker_dir/$model_key.complete"
  local temporary=""
  local expected_size=""
  local artifact=""
  local actual_size=""

  mkdir -p "$marker_dir"
  temporary="$(mktemp "$marker_dir/.$model_key.XXXXXX")"
  printf 'v1\t-\t%s\t%s\n' "$(model_key_fingerprint "$model_key")" "$(date +%s)" > "$temporary"
  while IFS=$'\t' read -r expected_size artifact; do
    actual_size="$(stat -c '%s' "$models_dir/$artifact")"
    if [ "$actual_size" != "$expected_size" ]; then
      rm -f "$temporary"
      echo "[sglang-entrypoint] $model_key: compatibility marker size mismatch: $artifact" >&2
      return 1
    fi
    printf '%s\t%s\n' "$actual_size" "$artifact" >> "$temporary"
  done < <(model_key_artifact_records "$model_key")
  mv -f "$temporary" "$marker"
}

for model_key in "${model_keys[@]}"; do
  write_llama_compatibility_marker "$model_key"
done

echo "[sglang-entrypoint] starting SGLang server with $server_config"
exec python3 - "$server_config" "$@" <<'PY'
import json
import os
import sys


config_path = sys.argv[1]
extra_args = sys.argv[2:]
with open(config_path, encoding="utf-8") as handle:
    config = json.load(handle)
command = config.get("command")
if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command):
    raise SystemExit(f"[sglang-entrypoint] invalid command in {config_path}")
os.execvp(command[0], [*command, *extra_args])
PY

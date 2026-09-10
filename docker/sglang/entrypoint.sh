#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh
source /model-downloads.generated.sh

PREFER_DEPLOYMENT="${PREFER_DEPLOYMENT:-${SGLANG_DEPLOYMENT:-}}"
PREFER_BUNDLE="${PREFER_BUNDLE:-${SGLANG_BUNDLE:-}}"
PREFER_MODELS="${PREFER_MODELS:-${SGLANG_MODELS:-}}"
PREFER_SERVER_OVERRIDES="${PREFER_SERVER_OVERRIDES:-${SGLANG_SERVER_OVERRIDES:-}}"
PREFER_MODEL_OVERRIDES="${PREFER_MODEL_OVERRIDES:-${SGLANG_MODEL_OVERRIDES:-}}"
PREFER_RUNTIME_HANDOFF="${PREFER_RUNTIME_HANDOFF:-${SGLANG_RUNTIME_HANDOFF:-}}"
PREFER_RUNTIME_HANDOFF_BASE64="${PREFER_RUNTIME_HANDOFF_BASE64:-${SGLANG_RUNTIME_HANDOFF_BASE64:-}}"

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
runtime_artifacts=""
if [ -n "$PREFER_RUNTIME_HANDOFF" ] && [ -n "$PREFER_RUNTIME_HANDOFF_BASE64" ]; then
  echo "[sglang-entrypoint] path and base64 runtime handoff inputs are mutually exclusive" >&2
  exit 2
fi
if [ -n "${PREFER_RUNTIME_HANDOFF}${PREFER_RUNTIME_HANDOFF_BASE64}" ]; then
  if [ -n "${PREFER_BUNDLE:-}${PREFER_MODELS:-}" ]; then
    echo "[sglang-entrypoint] a runtime handoff cannot be combined with bundle or model selectors" >&2
    exit 2
  fi
  mkdir -p /run/prefer
  runtime_handoff=/run/prefer/handoff.json
  runtime_artifacts=/run/prefer/handoff-artifacts.tsv
  runtime_config=/run/prefer/sglang.json
  runtime_prestage=/run/prefer/sglang.prestage
  runtime_plan=/run/prefer/plan.json
  if [ -n "$PREFER_RUNTIME_HANDOFF" ]; then
    runtime_handoff_input=(--handoff "$PREFER_RUNTIME_HANDOFF")
  else
    runtime_handoff_input=(--handoff-base64-env PREFER_RUNTIME_HANDOFF_BASE64)
  fi
  prefer runtime materialize "${runtime_handoff_input[@]}" --output "$runtime_handoff" --artifacts-output "$runtime_artifacts"
  unset PREFER_RUNTIME_HANDOFF_BASE64 SGLANG_RUNTIME_HANDOFF_BASE64
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
  runtime_config=/run/prefer/sglang.json
  runtime_prestage=/run/prefer/sglang.prestage
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
if [ -n "$runtime_artifacts" ]; then
  prefer_download_runtime_manifest "sglang-runtime-handoff" "$download_jobs" 8 "$runtime_artifacts" "$SGLANG_S3_BUCKET_NAME" "$SGLANG_S3_MODEL_PREFIX"
elif [ -n "$SGLANG_S3_BUCKET_NAME" ]; then
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

if [ -z "$runtime_artifacts" ]; then
  for model_key in "${model_keys[@]}"; do
    write_llama_compatibility_marker "$model_key"
  done
fi

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
if config.get("mode") == "diffusion":
    os.execvp(
        "python3",
        ["python3", "/prefer-sglang-video-gateway.py", config_path, *extra_args],
    )
os.execvp(command[0], [*command, *extra_args])
PY

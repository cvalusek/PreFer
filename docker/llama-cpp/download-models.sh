#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${PREFER_MODELS_DIR:-/models}"
source /model-downloads.generated.sh
source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh

# Runtime composition always writes a sibling prestage manifest. An explicit
# PRESTAGE_MODELS value still wins; use `none` for an intentional no-download
# launch. There is deliberately no implicit model or hardware preset.
if [ -z "${PRESTAGE_MODELS:-}" ]; then
  preset_path="${LLAMA_ARG_MODELS_PRESET:-}"
  prestage_file="${preset_path%.ini}.prestage"
  if [ -z "$preset_path" ] || [ ! -f "$prestage_file" ]; then
    echo "[download-models] no runtime prestage manifest; select models or provide a handoff" >&2
    exit 2
  fi
  IFS= read -r PRESTAGE_MODELS < "$prestage_file" || true
  PRESTAGE_MODELS="${PRESTAGE_MODELS%$'\r'}"
fi

if [ "$PRESTAGE_MODELS" = "none" ]; then
  echo "[download-models] model staging disabled (PRESTAGE_MODELS=none)"
  exit 0
fi
if [ -z "$PRESTAGE_MODELS" ]; then
  echo "[download-models] runtime prestage manifest is empty" >&2
  exit 2
fi

manifest="$(mktemp /tmp/prefer-llama-artifacts.XXXXXX)"
trap 'rm -f "$manifest"' EXIT

declare -A seen_keys=()
declare -A seen_artifacts=()
IFS=',' read -ra requested_keys <<< "$PRESTAGE_MODELS"
for raw_key in "${requested_keys[@]}"; do
  key="${raw_key#"${raw_key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"
  if [ -z "$key" ]; then
    echo "[download-models] PRESTAGE_MODELS contains an empty model key" >&2
    exit 2
  fi
  if [ -n "${seen_keys[$key]:-}" ]; then
    continue
  fi
  seen_keys["$key"]=1
  while IFS= read -r artifact_id; do
    if [ -z "$artifact_id" ] || [ -n "${seen_artifacts[$artifact_id]:-}" ]; then
      continue
    fi
    seen_artifacts["$artifact_id"]=1
    llama_artifact_record "$artifact_id" >> "$manifest"
  done < <(llama_model_artifact_ids "$key")
done

if [ ! -s "$manifest" ]; then
  echo "[download-models] no artifacts resolved from PRESTAGE_MODELS" >&2
  exit 2
fi

if [ -n "${S3_BUCKET_NAME:-}" ]; then
  default_jobs=4
else
  default_jobs=1
fi
prefer_download_runtime_manifest \
  "download-models" "${MODEL_DOWNLOAD_JOBS:-$default_jobs}" 8 "$manifest" \
  "${S3_BUCKET_NAME:-}" "${S3_MODEL_PREFIX:-}"

echo "[download-models] exact artifacts staged with downloads-v2 verification markers"

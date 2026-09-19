#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /prefer-runtime-handoff-download.sh

handoff_path="${PREFER_RUNTIME_HANDOFF:-}"
handoff_base64="${PREFER_RUNTIME_HANDOFF_BASE64:-}"
if [ -n "$handoff_path" ] && [ -n "$handoff_base64" ]; then
  echo "[prefer-downloader] path and base64 runtime handoffs are mutually exclusive" >&2
  exit 2
fi
if [ -z "$handoff_path" ] && [ -z "$handoff_base64" ]; then
  echo "[prefer-downloader] PREFER_RUNTIME_HANDOFF or PREFER_RUNTIME_HANDOFF_BASE64 is required" >&2
  exit 2
fi
if [ -z "${PREFER_ENGINE:-}" ]; then
  echo "[prefer-downloader] PREFER_ENGINE must match the handoff engine" >&2
  exit 2
fi

materialized=/run/prefer/handoff.json
manifest=/run/prefer/artifacts.tsv
if [ -n "$handoff_path" ]; then
  handoff_input=(--handoff "$handoff_path")
else
  handoff_input=(--handoff-base64-env PREFER_RUNTIME_HANDOFF_BASE64)
fi
prefer runtime materialize \
  "${handoff_input[@]}" \
  --output "$materialized" \
  --artifacts-output "$manifest"
unset PREFER_RUNTIME_HANDOFF_BASE64

prefer_download_runtime_manifest \
  "prefer-downloader" "${PREFER_DOWNLOAD_JOBS:-4}" 8 "$manifest" \
  "${S3_BUCKET_NAME:-}" "${S3_MODEL_PREFIX:-}"

echo "[prefer-downloader] all release-bound artifacts are staged in ${PREFER_MODELS_DIR:-/models}"

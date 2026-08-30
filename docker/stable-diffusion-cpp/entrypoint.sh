#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /model-downloads.generated.sh

server_config="${IMAGE_SERVER_CONFIG:-/app/server.json}"
if [ ! -f "$server_config" ]; then
  echo "[image-entrypoint] server config not found: $server_config" >&2
  exit 2
fi

requested="${IMAGE_PRESTAGE_MODELS:-}"
if [ -z "$requested" ]; then
  prestage_manifest="${server_config%.json}.prestage"
  if [ -f "$prestage_manifest" ]; then
    requested="$(tr -d '\r\n' < "$prestage_manifest")"
  else
    requested="$IMAGE_GENERATED_MODEL_KEYS"
  fi
fi

rm -f /tmp/prefer-image-prestage.status /tmp/prefer-image-prestage.status.tmp
(
  set +e
  declare -A seen=()
  model_keys=()
  status=0
  IFS=',' read -ra keys <<< "$requested"
  for key in "${keys[@]}"; do
    key="${key//[[:space:]]/}"
    if [ -z "$key" ] || [ "$key" = "none" ] || [ -n "${seen[$key]:-}" ]; then
      continue
    fi
    seen["$key"]=1
    model_keys+=("$key")
  done
  image_download_model_keys "${model_keys[@]}"
  status=$?
  printf '%s\n' "$status" > /tmp/prefer-image-prestage.status.tmp
  mv /tmp/prefer-image-prestage.status.tmp /tmp/prefer-image-prestage.status
  exit "$status"
) &
export IMAGE_PRESTAGE_PID=$!

echo "[image-entrypoint] discovery starting immediately with $server_config"
exec python3 /app/router.py --config "$server_config" "$@"

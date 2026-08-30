#!/usr/bin/env bash
set -euo pipefail

source /prefer-download-artifacts.sh
source /model-downloads.generated.sh

server_config="${AUDIO_SERVER_CONFIG:-/app/server.json}"
if [ ! -f "$server_config" ]; then
  echo "[audio-entrypoint] server config not found: $server_config" >&2
  exit 2
fi

requested="${AUDIO_PRESTAGE_MODELS:-}"
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

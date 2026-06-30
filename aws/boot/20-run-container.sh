#!/usr/bin/env bash
# Pull and (re)launch the PreFer container with /models on the freshly-mounted
# NVMe. Runs after 10-prep-nvme.sh in the same systemd unit.
set -euo pipefail

NVME_MOUNT="${NVME_MOUNT:-/mnt/nvme}"
MODELS_SUBDIR="${MODELS_SUBDIR:-models}"
PREFER_IMAGE="${PREFER_IMAGE:?PREFER_IMAGE must be set (see /opt/prefer/prefer-boot.env)}"
LLM_PORT="${LLM_PORT:-8080}"
CONTAINER_NAME="${CONTAINER_NAME:-prefer}"

log() { echo "[run-container] $*"; }

# Refresh the image so a new container build flows in on the next start without
# rebuilding the AMI. The baked image is the offline fallback if the pull fails.
log "pulling $PREFER_IMAGE"
docker pull "$PREFER_IMAGE" || log "pull failed; using locally cached image"

# Replace any prior container left over from a previous boot. systemd owns the
# lifecycle (this unit re-runs on every start; ExecStop does `docker stop`), so
# the container itself uses --restart no below.
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# Pass through only env vars that are actually set, so unset ones fall back to
# the container's own defaults (detect-preset, HF-only download, etc.).
ENV_ARGS=()
for v in S3_BUCKET_NAME HF_TOKEN PRESTAGE_MODELS LLAMA_ARG_MODELS_PRESET LLAMA_ARG_MODELS_MAX AWS_REGION; do
  if [ -n "${!v:-}" ]; then
    ENV_ARGS+=(-e "$v=${!v}")
  fi
done

log "starting container $CONTAINER_NAME"
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart no \
  --gpus all \
  -p "${LLM_PORT}:8080" \
  -v "${NVME_MOUNT}/${MODELS_SUBDIR}:/models" \
  "${ENV_ARGS[@]}" \
  "$PREFER_IMAGE"

log "started; watch model staging with: docker logs -f $CONTAINER_NAME"

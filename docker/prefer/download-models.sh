#!/bin/bash
set -euo pipefail

MODELS_DIR="/models"
mkdir -p "$MODELS_DIR"

# Comma-separated list of model keys to pre-stage. presets use local `model =`
# paths (not HF-direct `hf =` loading; that was tried and reverted, see
# AGENTS.md), so anything not pre-staged here simply won't be available to load.
# Available keys: gemma-4-26b-a4b, gemma-4-e2b, gemma-4-e4b, qwen-3.6-35b-a3b,
# qwen-3.6-27b, glm-4.7-flash, deepseek-v4-flash, glm-5.2, glm-5.2-reap, smol
#
# The default is preset-aware. Some presets own their host and want exactly one
# model staged, not the full small-model lineup: the big multi-GPU presets
# (deepseek-v4-flash, glm-5.2, glm-5.2-reap), and the tiny single-model `smol`
# preset (companion-app smoke tests). When one of those is the selected preset,
# the default is to stage ONLY that one model. The preset comes from
# LLAMA_ARG_MODELS_PRESET, which entrypoint.sh resolves (via detect-preset.sh)
# and exports into the environment before running this script; its basename
# matches the download key one-to-one. Any other preset (the `<N>gb.ini` tiers)
# defaults to the full small-model set.
#
# An explicit PRESTAGE_MODELS always wins — set it to stage a subset, or to
# stage a big model when pre-warming directly (e.g.
# `docker compose run --rm prefer /download-models.sh`) without the preset env
# var set.
SMALL_MODELS="gemma-4-26b-a4b,gemma-4-e2b,gemma-4-e4b,qwen-3.6-35b-a3b,qwen-3.6-27b,glm-4.7-flash"
PRESET_NAME="$(basename "${LLAMA_ARG_MODELS_PRESET:-}" .ini)"
case "$PRESET_NAME" in
  deepseek-v4-flash|glm-5.2|glm-5.2-reap|smol) DEFAULT_PRESTAGE="$PRESET_NAME" ;;
  *)                                           DEFAULT_PRESTAGE="$SMALL_MODELS" ;;
esac
PRESTAGE_MODELS="${PRESTAGE_MODELS:-$DEFAULT_PRESTAGE}"

wanted() {
  case ",$PRESTAGE_MODELS," in
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Optional S3 model cache. When S3_BUCKET_NAME is set (e.g. on EC2 with an
# instance role granting access to the bucket), each model is synced down from
# s3://$S3_BUCKET_NAME/<hf-repo>/ before hitting Hugging Face, and any newly
# downloaded files are synced back up afterwards so the bucket warms itself.
# Unset (local / RunPod) means HF-only — exactly the prior behavior.
#
# Sync is per-repo (inside download() below), not a blanket sync of /models,
# because HF_HOME=/models also holds HF cache cruft (xet, .cache, locks) that
# we don't want in the bucket. Per-repo dirs contain only the model files.
S3_BUCKET_NAME="${S3_BUCKET_NAME:-}"
if [ -n "$S3_BUCKET_NAME" ]; then
  echo "[download-models] S3 cache enabled: s3://$S3_BUCKET_NAME"
fi

# download <hf-repo> [extra hf-download args...]
# Always invokes `hf download` rather than checking for existing files first —
# `hf download` already hashes/resumes incomplete or partial downloads itself,
# which a simple "does a .gguf exist" presence check can't do safely. That
# matters for large multi-shard repos (e.g. Kimi K2.7, GLM 5.2): a presence
# check would see the first completed shard and wrongly skip re-running the
# whole download, leaving the rest of the shards missing if a prior run died
# partway through (a real, reported failure mode for downloads this size).
download() {
  local repo="$1"
  shift
  local dest="$MODELS_DIR/$repo"
  mkdir -p "$dest"

  # Cache sync-down: pull this repo's cached files first so `hf download` only
  # fetches what's missing. `|| true` because s5cmd errors when the prefix is
  # empty (first-ever boot, cold cache), which is not a failure here.
  if [ -n "$S3_BUCKET_NAME" ]; then
    echo "[download-models] $repo: sync down from s3://$S3_BUCKET_NAME/$repo"
    s5cmd sync "s3://$S3_BUCKET_NAME/$repo/*" "$dest/" || true
  fi

  echo "[download-models] $repo: syncing to $dest"
  hf download "$repo" --local-dir "$dest" "$@"

  # hf_xet keeps a chunk/shard cache (under $HF_HOME/xet) to speed up
  # re-downloads and dedup across repos. On a space-constrained volume this
  # competes with the models themselves for room, and we don't need fast
  # re-downloads badly enough to keep it around — clear it after each model
  # so disk usage doesn't accumulate across the whole download run.
  if [ -d "$MODELS_DIR/xet" ]; then
    rm -rf "$MODELS_DIR/xet"
  fi

  # Cache sync-up: push newly downloaded files back to the bucket in the
  # background (fire-and-forget) so warming the cache doesn't delay
  # `exec llama-server`. On a cache hit there's nothing new to upload, so this
  # is a fast no-op; on a miss it warms the bucket for the next boot. If it
  # fails, the next boot just re-uploads — self-healing. Excludes hf's per-dir
  # `.cache` bookkeeping so only model files land in S3.
  if [ -n "$S3_BUCKET_NAME" ]; then
    echo "[download-models] $repo: sync up to s3://$S3_BUCKET_NAME/$repo (background)"
    nohup s5cmd sync --exclude ".cache/*" "$dest/" "s3://$S3_BUCKET_NAME/$repo/" \
      >>/var/log/prefer-s3-sync.log 2>&1 &
  fi
}

if wanted gemma-4-26b-a4b; then
  download unsloth/gemma-4-26B-A4B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*" \
    --include "mmproj-F16.gguf"
fi

if wanted gemma-4-e2b; then
  download unsloth/gemma-4-E2B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*" \
    --include "mmproj-F16.gguf"
fi

if wanted gemma-4-e4b; then
  download unsloth/gemma-4-E4B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*" \
    --include "mmproj-F16.gguf"
fi

if wanted qwen-3.6-35b-a3b; then
  download unsloth/Qwen3.6-35B-A3B-MTP-GGUF \
    --include "*UD-Q6_K_XL*"
fi

if wanted qwen-3.6-27b; then
  download unsloth/Qwen3.6-27B-MTP-GGUF \
    --include "*UD-Q6_K_XL*"
fi

if wanted glm-4.7-flash; then
  download unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF \
    --include "*UD-Q6_K_XL*"
fi

if wanted deepseek-v4-flash; then
  download antirez/deepseek-v4-gguf \
    --include "*Q4KExperts-F16HC*imatrix*" \
    --include "*MTP-Q4K-Q8_0-F32*"
fi

if wanted glm-5.2; then
  download unsloth/GLM-5.2-GGUF \
    --include "UD-Q4_K_XL/*"
fi

if wanted glm-5.2-reap; then
  download 0xSero/GLM-5.2-REAP-504B-GGUF \
    --include "*Q4_K_XL*"
fi

if wanted smol; then
  download unsloth/SmolLM2-135M-Instruct-GGUF \
    --include "*Q8_0.gguf"
fi

if [ -n "$S3_BUCKET_NAME" ]; then
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none}; S3 cache: s3://$S3_BUCKET_NAME, uploads finishing in background)"
else
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none})"
fi

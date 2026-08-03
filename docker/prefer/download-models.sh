#!/bin/bash
set -euo pipefail

MODELS_DIR="/models"
mkdir -p "$MODELS_DIR"

source /model-downloads.generated.sh

# Comma-separated list of model keys to pre-stage. presets use local `model =`
# paths (not HF-direct `hf =` loading; that was tried and reverted, see
# AGENTS.md), so anything not pre-staged here simply won't be available to load.
# Available keys are generated from preset-catalog.json into
# model-downloads.generated.sh.
#
# The default is preset-aware. Generated deployment presets have a sibling
# `.prestage` file with the exact catalog keys needed by that preset. Named
# legacy single-model presets still use their basename as the key. Numeric
# legacy tiers retain the historical small-model default.
#
# A non-empty PRESTAGE_MODELS always wins — set it to stage a subset, to
# `none` for an intentional no-download run, or to stage a big model when
# pre-warming directly (e.g.
# `docker compose run --rm prefer /download-models.sh`) without the preset env
# var set.
if [ -z "${PRESTAGE_MODELS:-}" ]; then
  PRESET_PATH="${LLAMA_ARG_MODELS_PRESET:-}"
  PRESTAGE_FILE="${PRESET_PATH%.ini}.prestage"
  PRESET_NAME="$(basename "$PRESET_PATH" .ini)"
  if [ -n "$PRESET_PATH" ] && [ -f "$PRESTAGE_FILE" ]; then
    IFS= read -r PRESTAGE_MODELS < "$PRESTAGE_FILE" || true
    PRESTAGE_MODELS="${PRESTAGE_MODELS%$'\r'}"
  else
    case ",$GENERATED_MODEL_KEYS," in
      *",$PRESET_NAME,"*) PRESTAGE_MODELS="$PRESET_NAME" ;;
      *)                  PRESTAGE_MODELS="$LEGACY_SMALL_MODELS" ;;
    esac
  fi
fi

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

# download <hf-repo> <revision-or-empty> [extra hf-download args...]
# Always invokes `hf download` rather than checking for existing files first —
# `hf download` already hashes/resumes incomplete or partial downloads itself,
# which a simple "does a .gguf exist" presence check can't do safely. That
# matters for large multi-shard repos (e.g. Kimi K2.7, GLM 5.2): a presence
# check would see the first completed shard and wrongly skip re-running the
# whole download, leaving the rest of the shards missing if a prior run died
# partway through (a real, reported failure mode for downloads this size).
download() {
  local repo="$1"
  local revision="$2"
  shift 2
  local dest="$MODELS_DIR/$repo"
  local revision_args=()
  mkdir -p "$dest"

  if [ -n "$revision" ]; then
    revision_args=(--revision "$revision")
  fi

  # Cache sync-down: pull this repo's cached files first so `hf download` only
  # fetches what's missing. `|| true` because s5cmd errors when the prefix is
  # empty (first-ever boot, cold cache), which is not a failure here.
  if [ -n "$S3_BUCKET_NAME" ]; then
    echo "[download-models] $repo: sync down from s3://$S3_BUCKET_NAME/$repo"
    s5cmd sync "s3://$S3_BUCKET_NAME/$repo/*" "$dest/" || true
  fi

  echo "[download-models] $repo: syncing to $dest"
  hf download "$repo" "${revision_args[@]}" --local-dir "$dest" "$@"

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

declare -A SEEN_MODEL_KEYS=()
IFS=',' read -ra REQUESTED_MODEL_KEYS <<< "$PRESTAGE_MODELS"
for model_key in "${REQUESTED_MODEL_KEYS[@]}"; do
  model_key="${model_key//[[:space:]]/}"
  if [ -z "$model_key" ] || [ "$model_key" = "none" ] || [ -n "${SEEN_MODEL_KEYS[$model_key]:-}" ]; then
    continue
  fi
  SEEN_MODEL_KEYS[$model_key]=1
  download_model_key "$model_key"
done

if [ -n "$S3_BUCKET_NAME" ]; then
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none}; S3 cache: s3://$S3_BUCKET_NAME, uploads finishing in background)"
else
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none})"
fi

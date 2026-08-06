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

# Optional S3 model cache. S3-backed staging uses catalog fingerprints as
# completion markers, stages independent model keys concurrently, and excludes
# Hugging Face cache bookkeeping from both directions. Unset (local / RunPod)
# remains HF-only and sequential by default.
S3_BUCKET_NAME="${S3_BUCKET_NAME:-}"
if [ -n "$S3_BUCKET_NAME" ]; then
  echo "[download-models] S3 cache enabled: s3://$S3_BUCKET_NAME"
  DEFAULT_MODEL_DOWNLOAD_JOBS=4
else
  DEFAULT_MODEL_DOWNLOAD_JOBS=1
fi

MODEL_CACHE_RECHECK_DAYS="${MODEL_CACHE_RECHECK_DAYS:-7}"
MODEL_DOWNLOAD_JOBS="${MODEL_DOWNLOAD_JOBS:-$DEFAULT_MODEL_DOWNLOAD_JOBS}"
MODEL_CACHE_MARKER_DIR="$MODELS_DIR/.prefer-cache/downloads-v1"

if [[ ! "$MODEL_CACHE_RECHECK_DAYS" =~ ^[0-9]+$ ]]; then
  echo "[download-models] MODEL_CACHE_RECHECK_DAYS must be a non-negative integer" >&2
  exit 2
fi
if [[ ! "$MODEL_DOWNLOAD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
  echo "[download-models] MODEL_DOWNLOAD_JOBS must be a positive integer" >&2
  exit 2
fi

MODEL_SKIP_HF=0
MODEL_SKIP_S3=0
MODEL_ACTIVE_KEY=""

# download <hf-repo> <revision-or-empty> [extra hf-download args...]
# Unless a fresh completion marker is being validated, always invokes
# `hf download` rather than using a simple presence check. hf already
# hashes/resumes incomplete downloads; the marker path separately validates
# every exact catalog artifact and observed size, including every model shard.
download() {
  local repo="$1"
  local revision="$2"
  shift 2
  local dest="$MODELS_DIR/$repo"
  local download_args=("$@")
  local revision_args=()
  local s3_filters=(--exclude ".cache/*" --exclude "*/.cache/*")
  local artifact=""
  local artifact_count=0
  mkdir -p "$dest"

  if [ -n "$revision" ]; then
    revision_args=(--revision "$revision")
  fi

  # S3 uses the exact generated artifact manifest rather than HF's sometimes
  # broad include globs. This prevents old .cache metadata and other
  # quantizations from matching filenames that happen to contain the target.
  if [ -n "$S3_BUCKET_NAME" ]; then
    while IFS= read -r artifact; do
      if [[ "$artifact" == "$repo/"* ]]; then
        s3_filters+=(--include "${artifact#"$repo/"}")
        artifact_count=$((artifact_count + 1))
      fi
    done < <(model_key_artifacts "$MODEL_ACTIVE_KEY")
    if [ "$artifact_count" -eq 0 ]; then
      echo "[download-models] $MODEL_ACTIVE_KEY: no catalog artifacts found for $repo" >&2
      return 2
    fi
  fi

  # Cache sync-down: pull this repo's cached files first so `hf download` only
  # fetches what's missing. `|| true` because s5cmd errors when the prefix is
  # empty (first-ever boot, cold cache), which is not a failure here.
  if [ -n "$S3_BUCKET_NAME" ] && [ "$MODEL_SKIP_S3" != "1" ]; then
    echo "[download-models] $repo: sync down from s3://$S3_BUCKET_NAME/$repo"
    s5cmd sync "${s3_filters[@]}" "s3://$S3_BUCKET_NAME/$repo/*" "$dest/" || true
  fi

  # Old buckets may contain Hugging Face lock files from the original broad
  # sync. They are never useful on a new machine and can make hf wait forever.
  find "$dest/.cache" -type f -name '*.lock' -delete 2>/dev/null || true

  if [ "$MODEL_SKIP_HF" = "1" ]; then
    echo "[download-models] $repo: fresh cache marker; skipping Hugging Face verification"
    return
  fi

  echo "[download-models] $repo: syncing to $dest"
  hf download "$repo" "${revision_args[@]}" --local-dir "$dest" "${download_args[@]}"
}

MARKER_REASON=""

marker_metadata_is_fresh() {
  local model_key="$1"
  local marker="$2"
  local schema=""
  local bucket=""
  local fingerprint=""
  local checked_epoch=""
  local expected_fingerprint=""
  local now_epoch=""
  local age_seconds=0
  local max_age_seconds=0

  if [ ! -s "$marker" ]; then
    MARKER_REASON="missing"
    return 1
  fi
  IFS=$'\t' read -r schema bucket fingerprint checked_epoch < "$marker" || true
  expected_fingerprint="$(model_key_fingerprint "$model_key")"
  if [ "$schema" != "v1" ]; then
    MARKER_REASON="schema changed"
    return 1
  fi
  if [ "$bucket" != "$S3_BUCKET_NAME" ]; then
    MARKER_REASON="bucket changed"
    return 1
  fi
  if [ "$fingerprint" != "$expected_fingerprint" ]; then
    MARKER_REASON="catalog changed"
    return 1
  fi
  if [[ ! "$checked_epoch" =~ ^[0-9]+$ ]]; then
    MARKER_REASON="invalid timestamp"
    return 1
  fi
  if [ "$MODEL_CACHE_RECHECK_DAYS" = "0" ]; then
    MARKER_REASON="forced recheck"
    return 1
  fi

  now_epoch="$(date +%s)"
  if [ "$now_epoch" -gt "$checked_epoch" ]; then
    age_seconds=$((now_epoch - checked_epoch))
  fi
  max_age_seconds=$((MODEL_CACHE_RECHECK_DAYS * 86400))
  if [ "$age_seconds" -ge "$max_age_seconds" ]; then
    MARKER_REASON="older than ${MODEL_CACHE_RECHECK_DAYS}d"
    return 1
  fi
  MARKER_REASON="fresh"
}

marker_artifacts_match() {
  local model_key="$1"
  local marker="$2"
  local line_number=0
  local recorded_size=""
  local artifact=""
  local actual_size=""
  declare -A recorded_sizes=()

  while IFS=$'\t' read -r recorded_size artifact; do
    line_number=$((line_number + 1))
    if [ "$line_number" -eq 1 ]; then
      continue
    fi
    if [[ ! "$recorded_size" =~ ^[0-9]+$ ]] || [ -z "$artifact" ]; then
      MARKER_REASON="invalid artifact record"
      return 1
    fi
    recorded_sizes["$artifact"]="$recorded_size"
  done < "$marker"

  while IFS= read -r artifact; do
    recorded_size="${recorded_sizes[$artifact]:-}"
    if [ -z "$recorded_size" ] || [ ! -f "$MODELS_DIR/$artifact" ]; then
      MARKER_REASON="missing artifact: $artifact"
      return 1
    fi
    actual_size="$(stat -c '%s' "$MODELS_DIR/$artifact")"
    if [ "$actual_size" != "$recorded_size" ]; then
      MARKER_REASON="size mismatch: $artifact"
      return 1
    fi
  done < <(model_key_artifacts "$model_key")
  MARKER_REASON="fresh and complete"
}

write_model_marker() {
  local model_key="$1"
  local marker="$MODEL_CACHE_MARKER_DIR/$model_key.complete"
  local temp_marker=""
  local artifact=""
  local actual_size=""
  local fingerprint=""

  mkdir -p "$MODEL_CACHE_MARKER_DIR"
  fingerprint="$(model_key_fingerprint "$model_key")"
  temp_marker="$(mktemp "$MODEL_CACHE_MARKER_DIR/.$model_key.XXXXXX")"
  printf 'v1\t%s\t%s\t%s\n' "$S3_BUCKET_NAME" "$fingerprint" "$(date +%s)" > "$temp_marker"
  while IFS= read -r artifact; do
    if [ ! -f "$MODELS_DIR/$artifact" ]; then
      echo "[download-models] $model_key: required artifact missing after download: $artifact" >&2
      rm -f "$temp_marker"
      return 1
    fi
    actual_size="$(stat -c '%s' "$MODELS_DIR/$artifact")"
    printf '%s\t%s\n' "$actual_size" "$artifact" >> "$temp_marker"
  done < <(model_key_artifacts "$model_key")
  mv -f "$temp_marker" "$marker"
}

fetch_s3_marker() {
  local model_key="$1"
  local marker="$MODEL_CACHE_MARKER_DIR/$model_key.complete"
  local candidate=""

  mkdir -p "$MODEL_CACHE_MARKER_DIR"
  candidate="$(mktemp "$MODEL_CACHE_MARKER_DIR/.$model_key.s3.XXXXXX")"
  if s5cmd cp "s3://$S3_BUCKET_NAME/.prefer-cache/downloads-v1/$model_key.complete" "$candidate" >/dev/null 2>&1; then
    mv -f "$candidate" "$marker"
    return 0
  fi
  rm -f "$candidate"
  return 1
}

start_model_upload() {
  local model_key="$1"
  local marker="$MODEL_CACHE_MARKER_DIR/$model_key.complete"
  local artifacts=()
  mapfile -t artifacts < <(model_key_artifacts "$model_key")

  echo "[download-models] $model_key: syncing catalog artifacts and marker to S3 (background)"
  nohup bash -c '
    set -euo pipefail
    marker="$1"
    bucket="$2"
    model_key="$3"
    shift 3
    for artifact in "$@"; do
      s5cmd sync "/models/$artifact" "s3://$bucket/${artifact%/*}/"
    done
    s5cmd cp "$marker" "s3://$bucket/.prefer-cache/downloads-v1/$model_key.complete"
  ' _ "$marker" "$S3_BUCKET_NAME" "$model_key" "${artifacts[@]}" \
    >>/var/log/prefer-s3-sync.log 2>&1 &
}

stage_model_key() {
  local model_key="$1"
  local marker="$MODEL_CACHE_MARKER_DIR/$model_key.complete"
  MODEL_ACTIVE_KEY="$model_key"

  if [ -z "$S3_BUCKET_NAME" ]; then
    download_model_key "$model_key"
    return
  fi

  # Persistent volumes can use the local marker without touching S3 at all.
  if marker_metadata_is_fresh "$model_key" "$marker" && marker_artifacts_match "$model_key" "$marker"; then
    echo "[download-models] $model_key: local cache marker hit; skipping rescan"
    return
  fi

  # Fresh EC2 NVMe has no local marker. Fetch the tiny S3 marker first, then
  # trust only catalog artifact sizes after the filtered S3 copies finish.
  fetch_s3_marker "$model_key" || true
  if marker_metadata_is_fresh "$model_key" "$marker"; then
    MODEL_SKIP_HF=1
    MODEL_SKIP_S3=0
    download_model_key "$model_key"
    if marker_artifacts_match "$model_key" "$marker"; then
      echo "[download-models] $model_key: S3 cache marker hit; skipped Hugging Face rescan"
      return
    fi
    echo "[download-models] $model_key: marker validation failed ($MARKER_REASON); repairing via Hugging Face"
    MODEL_SKIP_HF=0
    MODEL_SKIP_S3=1
  else
    echo "[download-models] $model_key: refreshing cache marker ($MARKER_REASON)"
    MODEL_SKIP_HF=0
    MODEL_SKIP_S3=0
  fi

  download_model_key "$model_key"
  write_model_marker "$model_key"
  start_model_upload "$model_key"
}

declare -A SEEN_MODEL_KEYS=()
MODEL_KEYS=()
IFS=',' read -ra REQUESTED_MODEL_KEYS <<< "$PRESTAGE_MODELS"
for model_key in "${REQUESTED_MODEL_KEYS[@]}"; do
  model_key="${model_key//[[:space:]]/}"
  if [ -z "$model_key" ] || [ "$model_key" = "none" ] || [ -n "${SEEN_MODEL_KEYS[$model_key]:-}" ]; then
    continue
  fi
  SEEN_MODEL_KEYS[$model_key]=1
  MODEL_KEYS+=("$model_key")
done

run_model_batch() {
  local model_key=""
  local index=0
  local failed=0
  local pids=()
  local keys=()

  for model_key in "$@"; do
    echo "[download-models] $model_key: staging started"
    (stage_model_key "$model_key") &
    pids+=("$!")
    keys+=("$model_key")
  done
  while [ "$index" -lt "${#pids[@]}" ]; do
    if ! wait "${pids[$index]}"; then
      echo "[download-models] ${keys[$index]}: staging failed" >&2
      failed=1
    fi
    index=$((index + 1))
  done
  return "$failed"
}

MODEL_BATCH=()
for model_key in "${MODEL_KEYS[@]}"; do
  MODEL_BATCH+=("$model_key")
  if [ "${#MODEL_BATCH[@]}" -ge "$MODEL_DOWNLOAD_JOBS" ]; then
    run_model_batch "${MODEL_BATCH[@]}"
    MODEL_BATCH=()
  fi
done
if [ "${#MODEL_BATCH[@]}" -gt 0 ]; then
  run_model_batch "${MODEL_BATCH[@]}"
fi

# hf_xet's shared chunk cache cannot be removed while parallel downloads are
# active. Clear it once all foreground staging jobs have joined. S3 mode also
# removes per-repo HF metadata; cache markers replace it between AWS boots.
if [ -d "$MODELS_DIR/xet" ]; then
  rm -rf "$MODELS_DIR/xet"
fi
if [ -n "$S3_BUCKET_NAME" ]; then
  find "$MODELS_DIR" -type d -name .cache -prune -exec rm -rf '{}' '+'
fi

if [ -n "$S3_BUCKET_NAME" ]; then
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none}; jobs: $MODEL_DOWNLOAD_JOBS; marker recheck: ${MODEL_CACHE_RECHECK_DAYS}d; S3 uploads finishing in background)"
else
  echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none})"
fi

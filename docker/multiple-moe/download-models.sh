#!/bin/bash
set -euo pipefail

MODELS_DIR="/models"
mkdir -p "$MODELS_DIR"

# Comma-separated list of model keys to pre-stage. Anything not in this list
# downloads lazily on first request instead, via each preset's `hf =` entry
# (slower — plain HTTP via libcurl, no Xet — but no separate step needed).
# Available keys: gemma-4-26b-a4b, gemma-4-e2b, gemma-4-e4b, qwen-3.6-35b-a3b,
# qwen-3.6-27b, glm-4.7-flash
PRESTAGE_MODELS="${PRESTAGE_MODELS:-gemma-4-26b-a4b,gemma-4-e2b,qwen-3.6-35b-a3b,qwen-3.6-27b,glm-4.7-flash}"

wanted() {
  case ",$PRESTAGE_MODELS," in
    *",$1,"*) return 0 ;;
    *) return 1 ;;
  esac
}

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

  echo "[download-models] $repo: syncing to $dest"
  mkdir -p "$dest"
  hf download "$repo" --local-dir "$dest" "$@"
}

if wanted gemma-4-26b-a4b; then
  download unsloth/gemma-4-26B-A4B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*"
fi

if wanted gemma-4-e2b; then
  download unsloth/gemma-4-E2B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*"
fi

if wanted gemma-4-e4b; then
  download unsloth/gemma-4-E4B-it-qat-GGUF \
    --include "*UD-Q4_K_XL*" \
    --include "*mtp-gemma*"
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

echo "[download-models] done (pre-staged: ${PRESTAGE_MODELS:-none})"
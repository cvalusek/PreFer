# Auto-detect a preset based on GPU VRAM if not explicitly set. Explicit
# LLAMA_ARG_MODELS_PRESET (and LLAMA_ARG_MODELS_MAX) always win.
#
# Presets are named <N>gb.ini, where N is the VRAM tier (in GB) they're
# tuned for. The largest tier that fits within detected VRAM is selected;
# if VRAM is below the smallest available tier, that smallest tier is used
# anyway (best effort - llama.cpp's own checks will fail loudly if it truly
# doesn't fit).
#
# LLAMA_ARG_MODELS_MAX is set to 1 (swap-on-demand) unless the chosen preset
# has any `load-on-startup` entries, in which case llama-server's own
# default (4) is left in place.
#
# This file is meant to be sourced (not executed) so the exported env vars
# are visible to the process that execs llama-server, e.g.:
#   source /detect-preset.sh

if [ -z "${LLAMA_ARG_MODELS_PRESET:-}" ]; then
  VRAM_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d ' \r' || true)"

  if [ -z "$VRAM_MIB" ]; then
    echo "[detect-preset] ERROR: nvidia-smi unavailable and LLAMA_ARG_MODELS_PRESET not set." >&2
    echo "[detect-preset] set LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini explicitly." >&2
    exit 1
  fi

  echo "[detect-preset] detected GPU VRAM: ${VRAM_MIB} MiB"

  BEST=""
  BEST_N=0
  SMALLEST=""
  SMALLEST_N=999999

  for f in /presets/*gb.ini; do
    name="$(basename "$f" .ini)"
    n="${name%gb}"
    tier_mib=$((n * 1024))

    if [ "$tier_mib" -le "$VRAM_MIB" ] && [ "$n" -gt "$BEST_N" ]; then
      BEST="$f"
      BEST_N="$n"
    fi

    if [ "$n" -lt "$SMALLEST_N" ]; then
      SMALLEST="$f"
      SMALLEST_N="$n"
    fi
  done

  if [ -z "$BEST" ]; then
    BEST="$SMALLEST"
    echo "[detect-preset] WARNING: detected VRAM (${VRAM_MIB} MiB) is below the smallest preset tier (${SMALLEST_N}gb); using $BEST anyway" >&2
  fi

  export LLAMA_ARG_MODELS_PRESET="$BEST"
  echo "[detect-preset] auto-selected preset: $LLAMA_ARG_MODELS_PRESET"

  if ! grep -q '^load-on-startup' "$LLAMA_ARG_MODELS_PRESET"; then
    export LLAMA_ARG_MODELS_MAX="${LLAMA_ARG_MODELS_MAX:-1}"
  fi
fi
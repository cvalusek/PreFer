# PreFer multiple-moe

A llama.cpp router container hosting Gemma 4, Qwen3.6, and GLM-4.7-Flash.
On first start it downloads the models from Hugging Face, then serves them
via `llama-server`'s router mode (OpenAI-compatible API on port 8080).

Base image: pinned to `ghcr.io/ggml-org/llama.cpp:server-cuda-b9592` (not the
rolling `server-cuda` tag) — builds around the gemma4-assistant MTP merge
(#23398, ~b9549) were unstable. Bump the `FROM` line in the `Dockerfile`
manually after confirming a newer build works.

## Presets

On startup, `detect-preset.sh` reads the GPU's total VRAM (`nvidia-smi`) and
picks the largest `presets/<N>gb.ini` whose tier fits, falling back to the
smallest tier if VRAM is below all of them. Override with
`LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini` (and optionally
`LLAMA_ARG_MODELS_MAX`) to force a specific preset.

| Preset | VRAM tier | Models | `models-max` | Notes |
| ------ | --------- | ------ | ------------- | ----- |
| `96gb.ini` | ~96GB | All 3 models, each at native max context, `load-on-startup = true` | default (4) | `n-cpu-moe = 0` — everything stays on GPU |
| `12gb.ini` | ~12GB | All 3 models, each with a 64k and a full-context variant (6 ids), swap-on-demand | `1` | Per-model `n-cpu-moe` (12-26), `mmap = false`, `sleep-idle-seconds = 1800` |
| `8gb.ini` | ~8GB | Same 6 variants as `12gb.ini` | `1` | Higher `n-cpu-moe` (18-32), same `mmap`/sleep settings |

All presets share `dry-multiplier = 0.8`, `dry-base = 1.75`,
`dry-allowed-length = 24` (DRY sampling) as a mitigation against repetition
loops, particularly relevant to Gemma 4's tool-calling.

## Models

All models download from Hugging Face on first start (see
`download-models.sh`) and land under `/models/<hf-org>/<hf-repo>/...`. Mount
a persistent volume at `/models` to avoid re-downloading on restart — the
layout means multiple presets/services can safely share one volume.

| Source repo | Quant | Notes |
| ------------ | ----- | ----- |
| [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-26B-A4B-it.gguf` (MTP speculative-decoding draft) in the same repo |
| [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) | `UD-Q4_K_XL` | MTP draft is built into the main GGUF, no separate `model-draft` |
| [unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF) | `UD-Q4_K_XL` | No speculative decoding |

## Router model ids

| Model id | Context | `96gb.ini` | `12gb.ini` / `8gb.ini` |
| -------- | ------- | :--------: | :---------------------: |
| `gemma-4-26b-a4b-64k`              | 65536  |   | ✓ |
| `gemma-4-26b-a4b-256k`             | 262144 | ✓ | ✓ |
| `qwen3.6-35b-a3b-64k`               | 65536  |   | ✓ |
| `qwen3.6-35b-a3b-256k`              | 262144 | ✓ | ✓ |
| `glm-4.7-flash-reap-23b-a3b-64k`    | 65536  |   | ✓ |
| `glm-4.7-flash-reap-23b-a3b-198k`   | 202752 | ✓ | ✓ |

Full per-model sampling params and shared defaults live in the corresponding
`presets/<N>gb.ini`.

## Running

From the repo root:

```bash
docker compose --profile llm-capacity up --build multiple-moe
```

Relevant env vars (all read from your shell or a `.env` file in the repo
root — on Windows, prefer a `.env` file for path-shaped values like
`LLAMA_ARG_MODELS_PRESET`, since Git Bash mangles leading-`/` paths passed as
shell env vars):

- `LLM_MODEL_VOLUME` — Docker volume mounted at `/models` (default `llm-hosting-model-cache`)
- `LLM_PORT` — host port mapped to the container's 8080 (default `8080`)
- `HF_TOKEN` — optional, helps with Hugging Face rate limits
- `PRESTAGE_MODELS` — optional comma-separated subset of model keys to download
- `LLAMA_ARG_MODELS_PRESET` / `LLAMA_ARG_MODELS_MAX` — optional, force a
  specific preset instead of auto-detection

On `96gb.ini`, all 3 models have `load-on-startup = true`, so first start
downloads ~tens of GB and loads everything into VRAM before the server is
ready. On `12gb.ini`/`8gb.ini`, nothing loads until first requested.

Once running, `GET /v1/models` lists the available router model ids, and
`POST /v1/chat/completions` with `"model": "<id>"` routes to (and
loads/swaps in, if needed) the matching model.

## Pre-warming model downloads

To populate `/models` without starting the GPU server (e.g. ahead of time on
a slow connection):

```bash
docker compose run --rm multiple-moe /download-models.sh
```

## Extra args

The entrypoint forwards any extra container arguments to `llama-server`
after its fixed flags (`--host`, `--port`), so you can override or add flags
at runtime without rebuilding by setting `command:` on the service in
`docker-compose.yml`, e.g. `command: ["--cache-ram", "0"]`.

## Aliases (for litellm or similar)

Example client-side aliases — not configured in this container, just
documented here for reference when wiring up a routing layer. Pick the
target id based on which preset you're running:

```
gemma-4-256k    -> gemma-4-26b-a4b-256k
qwen-3.6-256k   -> qwen3.6-35b-a3b-256k
glm-4.7-flash   -> glm-4.7-flash-reap-23b-a3b-198k   (96gb) / -64k (12gb, 8gb)

# 12gb / 8gb only:
gemma-4-64k     -> gemma-4-26b-a4b-64k
qwen-3.6-64k    -> qwen3.6-35b-a3b-64k
```

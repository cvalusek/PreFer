# PreFer Container

A llama.cpp router container hosting Gemma 4, Qwen3.6, and GLM-4.7-Flash.
On first start it downloads the models from Hugging Face, then serves them
via `llama-server`'s router mode (OpenAI-compatible API on port 8080).

Base image: pinned to `ghcr.io/ggml-org/llama.cpp:server-cuda-b9592` (not the
rolling `server-cuda` tag) because builds around the gemma4-assistant MTP
merge (#23398, ~b9549) were unstable. Bump the `FROM` line in the
`Dockerfile` manually after confirming a newer build works.

## Presets

On startup, `detect-preset.sh` reads the GPU's total VRAM (`nvidia-smi`) and
picks the largest `presets/<N>gb.ini` whose tier fits, falling back to the
smallest tier if VRAM is below all of them. Override with
`LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini` (and optionally
`LLAMA_ARG_MODELS_MAX`) to force a specific preset.

| Preset | VRAM tier | Models | `models-max` | Notes |
| ------ | --------- | ------ | ------------- | ----- |
| `96gb.ini` | ~96GB | Gemma 4 26B/E2B/E4B, Qwen3.6 35B + 1M, Qwen3.6 27B, GLM-4.7-Flash | default (4) | `n-cpu-moe = 0` - everything stays on GPU |
| `12gb.ini` | ~12GB | Same model ids as `96gb.ini`, swap-on-demand | `1` | Per-model `n-cpu-moe` (12-26), `mmap = false`, `sleep-idle-seconds = 1800` |
| `8gb.ini` | ~8GB | Same model ids as `96gb.ini`, swap-on-demand | `1` | Higher `n-cpu-moe` (18-32), same `mmap`/sleep settings |

All presets share `dry-multiplier = 0.8`, `dry-base = 1.75`,
`dry-allowed-length = 24` (DRY sampling) as a mitigation against repetition
loops, particularly relevant to Gemma 4's tool-calling.

## Models

All models download from Hugging Face on first start (see
`download-models.sh`) and land under `/models/<hf-org>/<hf-repo>/...`. Mount
a persistent volume at `/models` to avoid re-downloading on restart. The
layout means multiple presets/services can safely share one volume.

| Source repo | Quant | Notes |
| ------------ | ----- | ----- |
| [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-26B-A4B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/gemma-4-E2B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-E2B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-E4B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) | `UD-Q6_K_XL` | MTP draft is built into the main GGUF, no separate `model-draft` |
| [unsloth/Qwen3.6-27B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF) | `UD-Q6_K_XL` | MTP draft is built into the main GGUF, no separate `model-draft` |
| [unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF) | `UD-Q6_K_XL` | No speculative decoding |

## Router model ids

| Alias | Context | Presets |
| ----- | ------- | ------- |
| `gemma-4`, `gemma-4-26b-a4b` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `gemma-4-e2b` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `gemma-4-e4b` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `qwen-3.6`, `qwen-3.6-35b-a3b` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `qwen-3.6-35b-a3b-1m` | 1048576 | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `qwen-3.6-27b` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |
| `glm-4.7-flash` | native | `96gb.ini`, `12gb.ini`, `8gb.ini` |

Full per-model sampling params and shared defaults live in the corresponding
`presets/<N>gb.ini`.

## Running

From the repo root:

```bash
docker compose up --build prefer
```

Relevant env vars (all read from your shell or a `.env` file in the repo
root; on Windows, prefer a `.env` file for path-shaped values like
`LLAMA_ARG_MODELS_PRESET`, since Git Bash mangles leading-`/` paths passed as
shell env vars):

- `LLM_MODEL_VOLUME` - Docker volume mounted at `/models` (default `prefer-model-cache`)
- `LLM_PORT` - host port mapped to the container's 8080 (default `8080`)
- `HF_TOKEN` - optional, helps with Hugging Face rate limits
- `PRESTAGE_MODELS` - optional comma-separated subset of model keys to download
- `S3_BUCKET_NAME` - optional. When set, `download-models.sh` syncs each model
  down from `s3://<bucket>/<hf-repo>/` before hitting Hugging Face, and syncs
  newly downloaded files back up (in the background) to warm the cache. Unset =
  Hugging Face only. On EC2, supply the bucket via an instance role rather than
  static keys (the container reads IMDS; the instance needs IMDS hop limit 2).
- `LLAMA_ARG_MODELS_PRESET` / `LLAMA_ARG_MODELS_MAX` - optional, force a
  specific preset instead of auto-detection

On `96gb.ini`, models with `load-on-startup = true` download tens of GB and
load into VRAM before the server is ready. On `12gb.ini`/`8gb.ini`, nothing
loads until first requested.

Once running, `GET /v1/models` lists the available router model ids, and
`POST /v1/chat/completions` with `"model": "<id>"` routes to (and
loads/swaps in, if needed) the matching model.

## Pre-warming model downloads

To populate `/models` without starting the GPU server (e.g. ahead of time on
a slow connection):

```bash
docker compose run --rm prefer /download-models.sh
```

## Extra args

The entrypoint forwards any extra container arguments to `llama-server`
after its fixed flags (`--host`, `--port`), so you can override or add flags
at runtime without rebuilding by setting `command:` on the service in
`docker-compose.yml`, e.g. `command: ["--cache-ram", "0"]`.

## Aliases

The presets already expose short aliases such as `gemma-4`,
`qwen-3.6`, `qwen-3.6-35b-a3b-1m`, and `glm-4.7-flash`; an external routing
layer can usually target those directly.
